"""
БИТ.Технолог — FastAPI приложение (тонкое).

Архитектура (ADR-0011):
- presentation: этот файл (routes + templates)
- services: rs_factory, notices, learning, tp_parser, auth
- repositories: db (25 таблиц)
- domain: llm_provider, yandexgpt, mock_llm
- gateways: one_c_gateway (FileGateway, HttpGateway)

8 экранов:
1. /dashboard       — Мои задачи
2. /products        — Изделия
3. /detail/{id}     — Карточка ТК (5 табов)
4. /notices         — Извещения
5. /profiles        — Профили РС
6. /knowledge       — База знаний
7. /llm-admin       — Управление LLM
8. /help            — Помощь
"""
import base64
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# === Jinja2 filter: from_json ===

# === Пути ===
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


# === Sprint 6 E1: workshop_context.md (реальные операции Техинкома) ===
def _load_workshop_context() -> str:
    """Загрузить справочник операций Техинкома для подстановки в prompt LLM.

    Файл лежит в seed/workshop_context.md (скопирован из attachments/).
    Используется в REFINE_PROMPT через плейсхолдер $workshops_context.
    """
    path = ROOT / "seed" / "workshop_context.md"
    if not path.exists():
        return "(справочник операций Техинкома не найден — seed/workshop_context.md)"
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return "(ошибка чтения seed/workshop_context.md)"

WORKSHOP_CONTEXT = _load_workshop_context()

# === Модули ===
from repositories import db  # noqa
from domain.llm_provider import (  # noqa
    get_registry, call_llm, parse_llm_json_safe,
)
from services.auth import (  # noqa
    authenticate, ROLES, has_permission, User, seed_users,
    hash_password, verify_password,
)
from services.rs_factory import (  # noqa
    build_rs, to_one_c_spec, DEFAULT_PROFILE, is_deterministic,
)
from services.tp_parser import parse_tp_text, validate_parsed_tp
from services.evidence import (  # noqa
    collect_evidence_for_tech_card, tech_card_evidence_summary,
    update_operation_evidence,
)
from services.notices import (  # noqa
    create_notice, list_notices, get_notice, generate_ai_diff,
    resolve_notice as resolve_notice_svc, find_affected_items,
)
from services.audit import log_history  # B3 (Sprint 6): audit-trail
from gateways.one_c_gateway import get_gateway, OneCResourceSpec  # noqa

# === Инициализация ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# RATE LIMITER (M37-#3)
# ============================================================
# Защита от runaway-clients: один user не может запустить больше
# N операций за окно T. In-memory dict (до пилота; потом Redis).
import time as _time
from collections import defaultdict as _defaultdict
from services import state as _state  # D1 (Sprint 6): shared state (sessions + rate limit)

_rate_limit_buckets: dict = _defaultdict(list)  # DEPRECATED (D1): см. state.rate_limit_check


def _rate_limit_check(key: str, max_calls: int, window_sec: int) -> tuple[bool, int]:
    """D1 (Sprint 6): rate limit через shared state (SQLite). Возвращает (ok, retry_after_sec)."""
    return _state.rate_limit_check(key, max_calls, window_sec)

app = FastAPI(title="БИТ.Технолог", version="1.0.0")

# ============================================================
# GRACEFUL SHUTDOWN (M37-#5) — no signal handler, just check before requests
# ============================================================
# uvicorn handles SIGTERM itself (drains in-flight, then exits).
# We just keep a flag (default False). It can be set externally
# (e.g. from /admin/shutdown endpoint or test). For prod we use
# uvicorn'''s built-in timeout_graceful_shutdown=30.
_shutting_down: bool = False
_shutting_down_reason: str = ""


# ============================================================
# SHUTDOWN MIDDLEWARE (M37-#5)
# ============================================================
# Возвращает 503 + Retry-After если идёт shutdown. Это даёт in-flight
# запросам время завершиться, а новых — не пускает.

@app.middleware("http")
async def shutdown_middleware(request: Request, call_next):
    if _shutting_down:
        from starlette.responses import JSONResponse
        return JSONResponse(
            {"detail": "Server is shutting down, please retry"},
            status_code=503,
            headers={"Retry-After": "30"},
        )
    return await call_next(request)


# ============================================================
# CSRF PROTECTION (M37-#2)
# ============================================================
# Проверяем для всех POST/PUT/DELETE:
# - X-Requested-With: XMLHttpRequest (для fetch/AJAX)
#   (Same-Origin Policy не даёт чужому сайту ставить custom header)
# - ИЛИ Origin/Referer == наш base URL (для form submit)
# Исключение: /login (первичный логин, куки ещё нет)
#
# Без CSRF атакующий сайт может сделать <form action=...> с method=POST
# и заставить браузер жертвы отправить запрос с её cookies.

CSRF_EXEMPT_PATHS = {"/login"}

@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        path = request.url.path
        if path not in CSRF_EXEMPT_PATHS:
            xrw = request.headers.get("x-requested-with", "")
            origin = request.headers.get("origin", "")
            referer = request.headers.get("referer", "")
            base = str(request.base_url).rstrip("/")
            # OK если: AJAX (XHR) ИЛИ same-origin (Origin/Referer)
            if xrw == "XMLHttpRequest":
                pass  # AJAX, browser Same-Origin Policy enforced
            elif origin == base or referer.startswith(base):
                pass  # form submit from our own site
            else:
                # No valid CSRF token
                from starlette.responses import JSONResponse
                return JSONResponse(
                    {"detail": "CSRF check failed: missing X-Requested-With or same-origin Referer"},
                    status_code=403,
                )
    return await call_next(request)
templates = Jinja2Templates(directory=str(ROOT / "templates"))

# Jinja2 filters
def from_json(value):
    import json as _json
    if not value:
        return {}
    try:
        return _json.loads(value)
    except (ValueError, TypeError):
        return {}

def ru_level(level):
    return {"detail": "Деталь", "assembly": "Узел/Сборка", "product": "Продукт",
            "purchased": "Покупное", "semi": "Полуфабрикат"}.get(level, level or "—")

def ru_sourcing(s):
    return {"make": "Изготавливаем", "buy": "Покупное",
            "coop_da": "Кооперация (давальч.)", "coop_full": "Кооперация (полная)"}.get(s, s or "—")

templates.env.filters["from_json"] = from_json
templates.env.filters["ru_level"] = ru_level
templates.env.filters["ru_sourcing"] = ru_sourcing

app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

# Инициализация БД + сидинг
db.init_db()
seed_users(verbose=False)


# ============================================================
# AUTH (Cookie + Basic fallback)
# ============================================================

# D1 (Sprint 6): shared sessions через SQLite (для multi-worker)
# Старая in-memory: _sessions: Dict[str, str] = {}


def _create_session(username: str) -> str:
    return _state.session_create(username)


def get_current_user(request: Request) -> Optional[User]:
    # 1. Cookie (нормальная авторизация через login-форму)
    session_id = request.cookies.get("session_id")
    if session_id:
        username = _state.session_get(session_id)
        if username:
            row = db.query_one("SELECT * FROM pilot_users WHERE username = ? AND is_active = 1", (username,))
            if row:
                return User(
                    id=row["id"],
                    username=row["username"],
                    role=row["role"],
                    display_name=row["display_name"],
                    email=row["email"] or "",
                    is_active=bool(row["is_active"]),
                )
    # 2. Basic Auth (для curl/тестов)
    auth = request.headers.get("authorization", "")
    if auth.startswith("Basic "):
        try:
            creds = base64.b64decode(auth[6:]).decode()
            username, password = creds.split(":", 1)
            return authenticate(username, password)
        except Exception:
            return None
    return None


def get_user_from_request(request: Request) -> Optional[User]:
    return get_current_user(request)


def require_user(request: Request) -> User:
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401, "Authentication required",
                            headers={"WWW-Authenticate": 'Basic realm="bit-technolog"'})
    return user


# ============================================================
# LOGIN / LOGOUT
# ============================================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    ctx = get_template_context(request, None)
    ctx["error"] = error
    return templates.TemplateResponse("login.html", ctx)


@app.post("/login")
async def login_post(request: Request):
    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")
    # B2 (Sprint 6): IP + User-Agent для audit_logins
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "")
    user_agent = request.headers.get("user-agent", "")
    user = authenticate(username, password, ip=client_ip, user_agent=user_agent)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Неверный логин или пароль", "is_mock_mode": True,
             "app_env": "PROD", "app_version": "1.0.0", "daily_cost": 0, "cost_budget": 500},
        )
    sid = _create_session(username)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("session_id", sid, max_age=7*24*3600, httponly=True, samesite="lax", secure=True)  # F3-003
    return response


@app.get("/logout")
async def logout(request: Request):
    sid = request.cookies.get("session_id")
    if sid:
        _state.session_delete(sid)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_id")
    return response


# ============================================================
# SETTINGS (под tech_admin / llm_admin)
# ============================================================

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, message: str = ""):
    user = get_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login?next=/settings", status_code=303)
    if not (has_permission(user.role, "manage_llm_providers") or has_permission(user.role, "manage_llm_model_assignments")):
        raise HTTPException(403, "Requires admin role")
    ctx = get_template_context(request, user)
    cur = db.query_one("SELECT name, display_name FROM llm_providers WHERE is_active = 1 LIMIT 1")
    ctx["current_provider"] = cur["display_name"] if cur else ""
    ctx["assignments"] = db.rows_to_dicts(db.query("""
        SELECT ma.*, p.display_name AS provider_display
        FROM llm_model_assignments ma
        JOIN llm_providers p ON p.id = ma.llm_provider_id
        WHERE ma.is_active = 1
    """))
    ctx["message"] = message
    return templates.TemplateResponse("settings.html", ctx)


@app.post("/settings/llm")
async def settings_save_llm(request: Request):
    user = get_user_from_request(request)
    if not user or not has_permission(user.role, "manage_llm_providers"):
        raise HTTPException(403)
    form = await request.form()
    name = form.get("name", "").strip()
    display_name = form.get("display_name", "").strip()
    endpoint = form.get("endpoint", "").strip()
    api_key = form.get("api_key", "").strip()
    cost_str = form.get("cost", "0.40 / 1.20").strip()
    try:
        cost_in, cost_out = [float(x.strip()) for x in cost_str.split("/")]
    except (ValueError, AttributeError):
        cost_in, cost_out = 0.40, 1.20
    from domain.llm_provider import encrypt_api_key
    api_key_enc = encrypt_api_key(api_key) if api_key else ""
    existing = db.query_one("SELECT id FROM llm_providers WHERE name = ?", (name,))
    if existing:
        db.execute("""
            UPDATE llm_providers SET display_name=?, endpoint=?, api_key_enc=?, cost_per_1k_input=?, cost_per_1k_output=?, is_active=1
            WHERE id=?
        """, (display_name, endpoint, api_key_enc, cost_in, cost_out, existing["id"]))
    else:
        db.insert_and_get_id("llm_providers", {
            "name": name, "display_name": display_name, "endpoint": endpoint,
            "api_key_enc": api_key_enc, "cost_per_1k_input": cost_in, "cost_per_1k_output": cost_out,
            "is_active": 1,
        })
    from domain.llm_provider import get_registry
    get_registry().__init__()
    return RedirectResponse(url=f"/settings?message=Сохранено: {display_name}", status_code=303)


# ============================================================
# CONTEXT для всех шаблонов
# ============================================================

def normalize_user_role(user) -> None:
    """M38-c3-fix: нормализует роль через _ROLE_ALIASES.
    'tech_admin' → 'admin', 'llm_admin' → 'admin'.
    Вызывать ПОСЛЕ get_user_from_request, до RBAC проверок.
    """
    if user is None:
        return
    from services.auth import _ROLE_ALIASES
    user.role = _ROLE_ALIASES.get(user.role, user.role)


def get_template_context(request: Request, user: Optional[User] = None) -> Dict[str, Any]:
    """Общий контекст для всех шаблонов."""
    registry = get_registry()
    # Счётчик открытых извещений (нужен в nav)
    n_open_notices = db.query_one("SELECT COUNT(*) AS n FROM change_notices WHERE status IN ('open','in_progress')")["n"]
    return {
        "request": request,
        "current_user": user,
        "user": user,  # M38-fix: alias for templates using {{ user.role }}
        "is_mock_mode": registry.is_mock_mode(),
        "daily_cost": registry.daily_cost_estimate(),
        "cost_budget": 500.0,
        "app_version": "1.0.0",
        "app_env": "PROD",
        "ROLES": ROLES,
        "counters": {"notices": n_open_notices},  # для nav
    }


# ============================================================
# ROUTES — 8 ЭКРАНОВ
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_user_from_request(request)
    if not user:  # M36-E2E-fix: redirect to login instead of 401
        return RedirectResponse(url="/login?next=/", status_code=303)
    ctx = get_template_context(request, user)

    # Метрики (b — время генерации, c — % зелёных)
    from services.metrics import get_dashboard_metrics, calc_green_pct
    metrics = get_dashboard_metrics()
    green = metrics["green_pct_all"]

    # Счётчики
    counters = {
        "drafts": db.query_one("SELECT COUNT(*) AS n FROM tech_cards WHERE status='draft'")["n"],
        "review": db.query_one("SELECT COUNT(*) AS n FROM tech_cards WHERE status='review'")["n"],
        "notices": db.query_one("SELECT COUNT(*) AS n FROM change_notices WHERE status='open'")["n"],
        "ai_questions": 3,  # Заглушка
        "evidence_green_pct": green["green_pct"],
        "etalons": db.query_one("SELECT COUNT(*) AS n FROM etalons")["n"],
        "green_total": green["total"],
        "green_confirmed": green["green"],
        "green_analog": green["yellow"],
        "green_guess": green["red"],
    }

    # Задачи (последние 5) — Q-007: "Мои задачи" = ТК, которые я генерил
    # Используем LEFT JOIN: tc_id может быть NULL (если не было approve),
    # но если pilot_runs.user = ? — это "моя" ТК.
    # M38-fix: только последняя ТК на item (раньше было 5 версий одного — мусор)
    tasks = db.query("""
        SELECT tc.id AS tech_card_id, i.id AS item_id, i.designation, i.name,
               tc.status, tc.version,
               p.designation AS product_model,
               pr.id AS pilot_run_id, pr.user AS pilot_user
        FROM tech_cards tc
        JOIN items i ON i.id = tc.item_id
        LEFT JOIN product_models p ON p.id = i.product_model_id
        LEFT JOIN pilot_runs pr ON pr.item_id = tc.item_id AND pr.user = ?
        WHERE pr.id IS NOT NULL
          AND tc.id = (
              SELECT MAX(tc2.id) FROM tech_cards tc2
              WHERE tc2.item_id = tc.item_id
          )
        ORDER BY tc.updated_at DESC
        LIMIT 5
    """, (user.username,))
    tasks = [db.row_to_dict(t) for t in tasks]

    # Извещения
    notices = db.query("""
        SELECT * FROM change_notices
        WHERE status IN ('open', 'in_progress')
        ORDER BY date DESC LIMIT 3
    """)
    notices = [db.row_to_dict(n) for n in notices]

    # История b (время генерации)
    b_history = metrics["gen_history"]

    ctx.update({
        "counters": counters,
        "tasks": tasks,
        "notices": notices,
        "metrics": metrics,
        "b_history": b_history,
        "top_draft": tasks[0] if tasks else None,  # Q-005: контекстная подсказка
        "learning": _compute_learning(),  # Q-001: петля обратной связи
    })
    return templates.TemplateResponse("dashboard.html", ctx)  # M35u-fix2: возврат HTML


def _compute_learning() -> dict:
    """Q-001 (M35u): реальные метрики петли обратной связи.
    Заменяет placeholder "17 ТК, 42% → 61%" в /dashboard.
    """
    try:
        approved_28d = db.query_one(
            "SELECT COUNT(*) AS n FROM tech_cards WHERE is_approved = 1 AND approved_at >= datetime('now', '-28 days')"
        )["n"]
        total_etalons = db.query_one("SELECT COUNT(*) AS n FROM etalons")["n"]
        # Текущая доля зелёных
        from services.metrics import calc_green_pct
        green_now_dict = calc_green_pct(scope="all")
        green_now = int(green_now_dict.get("green_pct", 0))
        # Изменение за 28 дней: считаем через pilot_metrics (если есть)
        green_then = 0
        try:
            row = db.query_one(
                "SELECT metric_value FROM pilot_metrics WHERE metric_code = 'green_pct' "
                "AND measured_at <= date('now', '-28 days') ORDER BY id DESC LIMIT 1"
            )
            if row:
                green_then = int(row["metric_value"])
        except Exception:
            pass
        green_change = green_now - green_then
        # Edits: всего + name-правок (Q-001)
        edits_total = db.query_one("SELECT COUNT(*) AS n FROM edits")["n"]
        edits_name = db.query_one("SELECT COUNT(*) AS n FROM edits WHERE field = 'name'")["n"]
        return {
            "approved_last_28d": approved_28d,
            "total_etalons": total_etalons,
            "green_now": green_now,
            "green_change": green_change,
            "edits_total": edits_total,
            "edits_name": edits_name,
        }
    except Exception as e:
        return {
            "approved_last_28d": 0,
            "total_etalons": 0,
            "green_now": 0,
            "green_change": 0,
            "edits_total": 0,
            "edits_name": 0,
        }
    return templates.TemplateResponse("dashboard.html", ctx)


@app.get("/products", response_class=HTMLResponse)
async def products(request: Request, q: str = "", level: str = ""):
    user = get_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login?next=/products", status_code=303)
    ctx = get_template_context(request, user)
    where = []
    params = []
    if q:
        where.append("(i.designation LIKE ? OR i.name LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if level:
        where.append("i.level = ?")
        params.append(level)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    items = db.rows_to_dicts(db.query(f"""
        SELECT i.*, p.designation AS product_model_designation
        FROM items i
        LEFT JOIN product_models p ON p.id = i.product_model_id
        {where_sql}
        ORDER BY i.designation
        LIMIT 200
    """, tuple(params)))
    ctx["items"] = items
    ctx["q"] = q
    ctx["level_filter"] = level
    return templates.TemplateResponse("products.html", ctx)


@app.get("/detail/{item_id}", response_class=HTMLResponse)
async def detail(request: Request, item_id: int, flash_kind: str = "", flash_message: str = ""):
    user = get_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login?next=/detail/{item_id}", status_code=303)
    ctx = get_template_context(request, user)

    item = db.get_item_with_bom(item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    # Текущая ТК
    tc = db.query_one("""
        SELECT * FROM tech_cards
        WHERE item_id = ?
        ORDER BY version DESC LIMIT 1
    """, (item_id,))
    if tc:
        tc_full = db.get_tech_card_full(tc["id"])
        # Sprint 5: собираем доказательства (светофор + аналоги)
        evidences = collect_evidence_for_tech_card(tc["id"])
        evidence_summary = tech_card_evidence_summary(tc["id"])
    else:
        tc_full = {}
        evidences = []
        evidence_summary = {"total": 0, "green": 0, "yellow": 0, "red": 0, "gray": 0, "green_pct": 0}

    # Эталоны (для обоснования)
    etalons = db.get_etalons_for_rag(product_type=item.get("product_type") or "", limit=5)

    # Справочники — для отображения и inline-edit (C1 Sprint 6)
    workshop_names = {w["code"]: w["name"] for w in db.query("SELECT code, name FROM workshops")}
    profession_names = {p["code"]: p["name"] for p in db.query("SELECT code, name FROM professions")}
    ctx_workshops = db.rows_to_dicts(db.query("SELECT id, code, name FROM workshops ORDER BY code"))
    ctx_equipment = db.rows_to_dicts(db.query("SELECT id, inventory_no AS code, name, workshop_id FROM equipment ORDER BY inventory_no"))
    ctx_professions = db.rows_to_dicts(db.query("SELECT id, code, name, category FROM professions ORDER BY code"))

    # РС preview (из resource_specs)
    rs_preview = None
    if tc:
        rs_row = db.query_one("SELECT content_json, status FROM resource_specs WHERE tech_card_id = ? ORDER BY id DESC LIMIT 1", (tc["id"],))
        if rs_row and rs_row["content_json"]:
            import json as _json
            rs_preview = _json.loads(rs_row["content_json"])

    # BOM — дочерние детали
    bom_children = []
    if item.get("level") in ("assembly", "product"):
        bom_children = db.rows_to_dicts(db.query("""
            SELECT c.id, c.designation, c.name, c.level, c.mass_kg, bl.qty
            FROM bom_links bl
            JOIN items c ON c.id = bl.child_item_id
            WHERE bl.parent_item_id = ?
            ORDER BY c.designation
        """, (item_id,)))

    # История изменений (edits)
    history = []
    if tc:
        history = db.rows_to_dicts(db.query("""
            SELECT e.ts AS created_at, e.user, e.reason AS note, e.field, e.old_value, e.new_value
            FROM edits e
            WHERE e.operation_id IN (SELECT id FROM operations WHERE tech_card_id = ?)
            ORDER BY e.ts DESC
            LIMIT 20
        """, (tc["id"],)))
        # Дополнить понятным action
        for h in history:
            h["action"] = f"Изменение {h['field']}: {h['old_value']} → {h['new_value']}"

    # Карта доказательств по operation_id
    evidence_map = {ev.to_dict()["operation_id"]: ev.to_dict() for ev in evidences}

    # Flash
    flash = None
    if flash_message:
        flash = {"kind": flash_kind, "message": flash_message}

    ctx.update({
        "item": item,
        "tech_card": tc_full,
        "evidences": evidences,
        "evidence_summary": evidence_summary,
        "evidence_map": evidence_map,
        "etalons": etalons,
        "workshop_names": workshop_names,
        "profession_names": profession_names,
        "workshops_list": ctx_workshops,  # C1 (Sprint 6): для inline-edit
        "equipment_list": ctx_equipment,
        "professions_list": ctx_professions,
        "rs_preview": rs_preview,
        "bom_children": bom_children,
        "history": history,
        "flash": flash,
    })
    return templates.TemplateResponse("detail.html", ctx)


# ============================================================
# ГЕНЕРАЦИЯ ТК (Sprint 8+)
# ============================================================

@app.get("/details/new", response_class=HTMLResponse)
async def details_new_form(request: Request):
    """M38-c4: форма создания новой детали (полная, не placeholder)."""
    user = get_user_from_request(request)
    if not user:
        return RedirectResponse("/login", 303)
    normalize_user_role(user)
    # RBAC: только admin / main_technologist / technologist могут создавать
    if user.role not in ("admin", "main_technologist", "technologist"):
        raise HTTPException(403, "Создавать детали могут только технологи")
    ctx = get_template_context(request, user)
    # Справочники для select'ов
    ctx["materials"] = db.rows_to_dicts(db.query("SELECT id, code, name FROM materials ORDER BY name"))
    ctx["product_models"] = db.rows_to_dicts(db.query("SELECT id, designation, name FROM product_models ORDER BY name"))
    ctx["levels"] = [
        ("detail", "Деталь"),
        ("assembly", "Сборка"),
        ("product", "Изделие"),
        ("purchased", "Покупное"),
        ("semi", "Составная"),
    ]
    ctx["sourcings"] = [
        ("make", "Производим сами"),
        ("buy", "Покупное"),
        ("coop_da", "Кооперация (доработка)"),
        ("coop_full", "Кооперация (целиком)"),
    ]
    ctx.setdefault("form_data", {})
    return templates.TemplateResponse("detail_new.html", ctx)


@app.post("/details/new")
async def details_new_create(request: Request):
    """M38-c4: создание новой детали с валидацией."""
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401)
    normalize_user_role(user)
    if user.role not in ("admin", "main_technologist", "technologist"):
        raise HTTPException(403, "Создавать детали могут только технологи")
    form = await request.form()
    # Валидация
    designation = form.get("designation", "").strip()
    name = form.get("name", "").strip()
    level = form.get("level", "").strip()
    if not designation:
        ctx2 = get_template_context(request, user)
        ctx2["error"] = "Обозначение обязательно"
        ctx2["form_data"] = dict(form)
        return templates.TemplateResponse("detail_new.html", ctx2, status_code=400)
    if not name:
        ctx2 = get_template_context(request, user)
        ctx2["error"] = "Наименование обязательно"
        ctx2["form_data"] = dict(form)
        return templates.TemplateResponse("detail_new.html", ctx2, status_code=400)
    if level not in ("detail", "assembly", "product", "purchased", "semi"):
        ctx2 = get_template_context(request, user)
        ctx2["error"] = "Уровень должен быть: detail/assembly/product/purchased/semi"
        ctx2["form_data"] = dict(form)
        return templates.TemplateResponse("detail_new.html", ctx2, status_code=400)
    # Уникальность designation
    existing = db.query_one("SELECT id FROM items WHERE designation = ?", (designation,))
    if existing:
        ctx2 = get_template_context(request, user)
        ctx2["error"] = f"Деталь с обозначением «{designation}» уже существует"
        ctx2["form_data"] = dict(form)
        return templates.TemplateResponse("detail_new.html", ctx2, status_code=400)
    # Числовые поля
    mass_kg = form.get("mass_kg", "").strip()
    try:
        mass_kg = float(mass_kg) if mass_kg else None
    except ValueError:
        ctx2 = get_template_context(request, user)
        ctx2["error"] = f"Масса должна быть числом: {mass_kg!r}"
        ctx2["form_data"] = dict(form)
        return templates.TemplateResponse("detail_new.html", ctx2, status_code=400)
    # FK поля
    material_id = form.get("material_id", "").strip()
    material_id = int(material_id) if material_id.isdigit() else None
    product_model_id = form.get("product_model_id", "").strip()
    product_model_id = int(product_model_id) if product_model_id.isdigit() else None
    # Валидация FK
    if material_id and not db.query_one("SELECT id FROM materials WHERE id = ?", (material_id,)):
        ctx2 = get_template_context(request, user)
        ctx2["error"] = f"Материал #{material_id} не найден"
        ctx2["form_data"] = dict(form)
        return templates.TemplateResponse("detail_new.html", ctx2, status_code=400)
    if product_model_id and not db.query_one("SELECT id FROM product_models WHERE id = ?", (product_model_id,)):
        ctx2 = get_template_context(request, user)
        ctx2["error"] = f"Изделие #{product_model_id} не найден"
        ctx2["form_data"] = dict(form)
        return templates.TemplateResponse("detail_new.html", ctx2, status_code=400)
    sourcing = form.get("sourcing", "make").strip()
    if sourcing not in ("make", "buy", "coop_da", "coop_full"):
        sourcing = "make"
    drawing_no = form.get("drawing_no", "").strip() or None
    ref_1c = form.get("ref_1c", "").strip() or None
    # INSERT
    new_id = db.insert_and_get_id("items", {
        "designation": designation,
        "name": name,
        "level": level,
        "type": form.get("type", "").strip() or None,
        "material_id": material_id,
        "product_model_id": product_model_id,
        "mass_kg": mass_kg,
        "drawing_no": drawing_no,
        "sourcing": sourcing,
        "ref_1c": ref_1c,
        "source_type": "manual",
    })
    # Записать в history (audit-trail)
    try:
        db.execute(
            "INSERT INTO history (entity_type, entity_id, action, user, details_json) VALUES (?, ?, ?, ?, ?)",
            ("item", new_id, "create", user.username, json.dumps({
                "designation": designation, "name": name, "level": level,
            }, ensure_ascii=False)),
        )
    except Exception:
        pass
    return RedirectResponse(f"/detail/{new_id}", status_code=303)


@app.get("/items/{item_id}/generate", response_class=HTMLResponse)
async def item_generate_form(request: Request, item_id: int):
    user = get_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login?next=/items/{item_id}/generate", status_code=303)
    item = db.get_item_with_bom(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    # M38: pass etalons_count for progress bar
    etalons_count = db.query_one("SELECT COUNT(*) AS n FROM etalons")["n"]
    ctx = get_template_context(request, user)
    ctx["item"] = item
    ctx["etalons_count"] = etalons_count
    return templates.TemplateResponse("item_generate.html", ctx)


@app.post("/items/{item_id}/generate")
async def item_generate_post(request: Request, item_id: int):
    # M37-#3: rate limit 5 generations per 60 sec per user
    # (LLM вызов занимает 24 сек + 1.32₽ — защита от runaway UI)
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401)
    rl_key = f"gen:{user.username}"
    rl_ok, rl_retry = _rate_limit_check(rl_key, max_calls=5, window_sec=60)
    if not rl_ok:
        from starlette.responses import JSONResponse
        return JSONResponse(
            {"detail": f"Слишком много генераций. Подождите {rl_retry} сек.", "retry_after": rl_retry},
            status_code=429,
            headers={"Retry-After": str(rl_retry)},
        )
    item = db.get_item_with_bom(item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    # M36-fix #6: покупное изделие — нечего описывать техпроцессом
    if item.get("sourcing") == "buy":
        raise HTTPException(400, "Для покупного изделия техкарта не нужна — оно приобретается, а не изготавливается.")

    # Метрика b: старт замера
    from services.metrics import start_tc_generation
    run_id = start_tc_generation(item_id, user.username)

    # Генерация ТК через LLM (mock) — подбор аналогов + фабрика РС
    from services.rs_factory import build_rs, to_one_c_spec
    from services.rag import load_etalons, find_analogs

    load_etalons(force=True)

    # Генерируем операции: берём 1 ближайший эталон по названию
    operations = []
    etalon_id = None
    similar_etalon = db.query_one("""
        SELECT id, designation, name FROM etalons
        WHERE name LIKE ? OR designation LIKE ?
        ORDER BY id LIMIT 1
    """, (f"%{item.get('name', '')[:15]}%", f"%{item.get('designation', '')[:10]}%"))
    if not similar_etalon:
        # Fallback: любой эталон с похожим типом материала
        similar_etalon = db.query_one("""
            SELECT id, designation, name FROM etalons
            WHERE content_json LIKE ?
            ORDER BY id LIMIT 1
        """, (f"%{item.get('material_code', '09Г2С')[:5]}%",))
    if not similar_etalon:
        # Последний fallback: первый эталон вообще
        similar_etalon = db.query_one("SELECT id, designation, name FROM etalons ORDER BY id LIMIT 1")
    if similar_etalon:
        etalon_id = similar_etalon["id"]
        # Операции из content_json эталона (для совместимости с PDF-парсерами)
        et = db.query_one("SELECT content_json FROM etalons WHERE id = ?", (etalon_id,))
        ops = []
        if et and et["content_json"]:
            try:
                data = json.loads(et["content_json"])
                ops = data.get("operations", [])
            except Exception:
                ops = []
        operations = ops
        analogs_for_evidence = [{
            "etalon_designation": similar_etalon["designation"],
            "operation_name": (ops[0]["name"] if ops else "—"),
            "similarity": 0.65 if item.get("name") else 0.40,
            "time_per_unit_min": (ops[0].get("time_per_unit_min", 0) if ops else 0),
            "reason": f"На основе {similar_etalon['designation']}",
        }] if ops else []
    else:
        analogs_for_evidence = []

    # Создаём ТК (если уже есть — увеличиваем версию)
    existing = db.query_one("SELECT MAX(version) AS v FROM tech_cards WHERE item_id = ?", (item_id,))
    new_version = (existing["v"] or 0) + 1
    tc_id = db.insert_and_get_id("tech_cards", {
        "item_id": item_id,
        "version": new_version,
        "status": "draft",
        "is_approved": 0,
        "author": user.username,
        "created_at": None,
    })

    # Q-002: M35r — RAG + LLM refine. Берём черновик от RAG, шлём в LLM
    # для коррекции (время, оборудование, материал) под контекст детали.
    # Если LLM упал — fallback на RAG-only (operations уже заполнены).
    if operations and similar_etalon:
        try:
            from domain.llm_provider import call_llm
            from domain.prompts import REFINE_PROMPT
            # Sprint 6 E1: подставляем workshops_context (реальные операции Техинкома)
            refine_system = REFINE_PROMPT.replace("$workshops_context", WORKSHOP_CONTEXT)
            # Готовим контекст для LLM
            etalon_ctx = {
                "designation": similar_etalon["designation"],
                "name": similar_etalon["name"],
                "operations": operations,
            }
            item_ctx = {
                "designation": item.get("designation", ""),
                "name": item.get("name", ""),
                "material": item.get("material_code", ""),
                "mass_kg": item.get("mass_kg", 0),
                "chassis": item.get("chassis_code", ""),
            }
            prompt = (
                f"Деталь: {item_ctx}\n"
                f"Эталон (RAG-черновик): {etalon_ctx}\n\n"
                "Скорректируй операции под эту деталь. "
                "Верни JSON-массив operations с теми же полями, что и в эталоне, "
                "но скорректированный time_per_unit_min (под материал/mass_kg), "
                "equipment (если у детали другое шасси), profession."
            )
            llm_result = call_llm(
                "tech_card_refinement",
                prompt=prompt,
                system=refine_system,
                temperature=0.2,
                max_tokens=1500,  # M35r-fix: 3000→1500 (1bitai.ru 3000 токенов = 170 сек)
                response_format="json",
                user=user.username,
            )
            llm_ops = llm_result.parse_json() if hasattr(llm_result, 'parse_json') else None
            if isinstance(llm_ops, list) and llm_ops and isinstance(llm_ops[0], dict):
                # LLM вернул нормальный список — заменяем operations
                operations = llm_ops
                logger.info(f"item_generate_post: LLM refined {len(operations)} ops for item {item_id}")
            else:
                logger.warning(f"item_generate_post: LLM returned bad JSON for item {item_id}, using RAG")
        except Exception as e:
            # Fallback на RAG (operations не меняем) — уже работает
            logger.warning(f"item_generate_post: LLM refine failed for item {item_id}: {e}, using RAG")

    # Сохраняем операции (используем реальные FK)
    # workshops / equipment / professions по коду
    for i, op in enumerate(operations):
        ws_code = op.get("workshop_code", "01")
        prof_code = op.get("profession_code", "")
        eq_name = op.get("equipment_name", "")
        # FK lookup
        ws_row = db.query_one("SELECT id FROM workshops WHERE code = ?", (ws_code,))
        prof_row = db.query_one("SELECT id FROM professions WHERE code = ?", (prof_code,)) if prof_code else None
        eq_row = db.query_one("SELECT id FROM equipment WHERE name LIKE ? LIMIT 1", (f"%{eq_name[:20]}%",)) if eq_name else None
        op_id = db.insert_and_get_id("operations", {
            "tech_card_id": tc_id,
            "op_number": op.get("op_number", i + 1),
            "name": op.get("name", f"Операция {i+1}"),
            "workshop_id": ws_row["id"] if ws_row else None,
            "profession_id": prof_row["id"] if prof_row else None,
            "equipment_id": eq_row["id"] if eq_row else None,
            "time_setup_min": op.get("time_setup_min", 0),
            "time_per_unit_min": op.get("time_per_unit_min", 0),
            "source": "ai_guess",
        })
        # Запишем доказательство
        # Запишем доказательство прямо в operations.evidence_json (Sprint 5 формат)
        ev_data = {
            "source": "analog_estimate" if analogs_for_evidence else "ai_guess",
            "source_label": "Аналог" if analogs_for_evidence else "AI",
            "note": (f"На основе {analogs_for_evidence[0]['etalon_designation']} "
                    f"({int(analogs_for_evidence[0]['similarity']*100)}%)" if analogs_for_evidence
                    else "Предположение AI (нет аналогов)"),
            "confidence": analogs_for_evidence[0]["similarity"] if analogs_for_evidence else 0.0,
            "analogs": analogs_for_evidence,
        }
        db.execute(
            "UPDATE operations SET evidence_json = ? WHERE id = ?",
            (json.dumps(ev_data, ensure_ascii=False), op_id),
        )

    # Сразу собираем РС
    tc_full = db.get_tech_card_full(tc_id)
    if tc_full.get("operations"):
        report = build_rs(
            item_designation=item.get("designation", ""),
            operations=tc_full["operations"],
            tech_card_id=tc_id,
        )
        # Сохраняем preview РС (в resource_specs)
        db.insert_and_get_id("resource_specs", {
            "item_id": item_id,
            "tech_card_id": tc_id,
            "tech_card_version": 1,
            "rs_profile_id": None,
            "status": "draft",
            "content_json": json.dumps({
                "rows": [r.to_dict() if hasattr(r, "to_dict") else r for r in report.rows],
                "summary": report.summary,
                "ops_count": len(report.rows),
            }, ensure_ascii=False),
            "change_reason": "Первичная генерация",
        })

    return RedirectResponse(
        url=f"/detail/{item_id}?flash_kind=ok&flash_message=ТК сгенерирована: {len(operations)} операций&run_id={run_id}",
        status_code=303,
    )


# ============================================================
# ЭКСПОРТ В 1С (FileGateway, для препилота)
# ============================================================

@app.post("/api/items/{item_id}/export-to-1c")
async def api_export_to_1c(request: Request, item_id: int):
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401)
    normalize_user_role(user)
    if user.role not in ("admin", "main_technologist", "technologist"):
        raise HTTPException(403, "Недостаточно прав")
    item = db.get_item_with_bom(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    # Берём текущую ТК
    tc = db.query_one("SELECT * FROM tech_cards WHERE item_id = ? ORDER BY version DESC LIMIT 1", (item_id,))
    if not tc:
        raise HTTPException(400, "Нет ТК для экспорта")
    tc_full = db.get_tech_card_full(tc["id"])
    if not tc_full.get("operations"):
        raise HTTPException(400, "ТК пустая, нечего экспортировать")

    # Строим РС через фабрику
    from services.rs_factory import build_rs, to_one_c_spec
    report = build_rs(
        item_designation=item.get("designation", ""),
        operations=tc_full["operations"],
        tech_card_id=tc["id"],
    )
    spec = to_one_c_spec(
        report,
        item_ref_1c=item.get("ref_1c") or "",
        tech_card_ref=tc_full.get("ref_1c") or f"TC-{tc['id']:06d}",
        version=tc["version"] if tc["version"] else 1,
        change_reason="Экспорт через UI",
    )

    # Пишем XML в data/one_c_exchange/out/
    import os
    out_dir = "data/one_c_exchange/out"
    os.makedirs(out_dir, exist_ok=True)
    fname = f"RS_{item.get('designation', 'item')}_{tc['id']:04d}.xml"
    fname = fname.replace("/", "_").replace(" ", "_")
    fpath = os.path.join(out_dir, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(spec.to_xml())

    # Регистрируем извещение об изменении (для аудита)
    # B3 (Sprint 6): audit-trail
    log_history("item", item_id, "export", user.username, {"path": fpath, "ops_count": len(report.rows)})
    return {"status": "ok", "path": fpath, "ops_count": len(report.rows), "total_time_min": sum(r.to_dict().get("time_per_unit_min", 0) for r in report.rows) if report.rows else 0}


@app.get("/notices", response_class=HTMLResponse)
async def notices(request: Request):
    user = get_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login?next=/notices", status_code=303)
    ctx = get_template_context(request, user)
    n = list_notices(limit=50)
    ctx["notices"] = n
    return templates.TemplateResponse("notices.html", ctx)


@app.get("/notices/new", response_class=HTMLResponse)
async def notice_new(request: Request):
    user = get_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login?next=/notices/new", status_code=303)
    normalize_user_role(user)
    if user.role not in ("admin", "main_technologist", "technologist"):
        raise HTTPException(403, "Создавать извещения могут только технологи")
    ctx = get_template_context(request, user)
    return templates.TemplateResponse("notice_form.html", ctx)


@app.post("/notices/new")
async def notice_create(request: Request):
    form = await request.form()
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401)
    normalize_user_role(user)
    if user.role not in ("admin", "main_technologist", "technologist"):
        raise HTTPException(403, "Только технолог может создавать извещения")
    author = user.username if user else form.get("author", "Технолог")
    nid = create_notice(
        number=form.get("number", "").strip(),
        date=form.get("date", ""),
        foundation_doc=form.get("foundation_doc", ""),
        reason=form.get("reason", ""),
        description=form.get("description", ""),
        author=author,
        affected_item_designation=form.get("affected_item_designation", "").strip(),
    )
    # B3 (Sprint 6): audit-trail
    log_history("notice", nid, "create", user.username, {"number": form.get("number", ""), "affected_item": form.get("affected_item_designation", "")})
    return RedirectResponse(url=f"/notices/{nid}", status_code=303)


@app.get("/notices/{notice_id}", response_class=HTMLResponse)
async def notice_detail(request: Request, notice_id: int):
    user = get_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login?next=/notices/{notice_id}", status_code=303)
    ctx = get_template_context(request, user)
    notice = get_notice(notice_id)
    if not notice:
        raise HTTPException(404, "Notice not found")
    # M38-c3: AI diff генерируется LAZY через /notices/{id}/generate-diff
    # (не на каждый GET — иначе 24 сек на LLM вызов)
    # Кол-во созданных РС
    rs_count_row = db.query_one(
        "SELECT COUNT(*) AS n FROM resource_specs WHERE change_reason LIKE ?",
        (f"%{notice['number']}%",)
    )
    rs_count = rs_count_row["n"] if rs_count_row else 0
    ctx.update({
        "notice": notice,
        "ai_diff": None,  # генерится по кнопке "Сгенерировать diff"
        "rs_count": rs_count,
    })
    return templates.TemplateResponse("notice_detail.html", ctx)


@app.post("/notices/{notice_id}/generate-diff")
async def notice_generate_diff(request: Request, notice_id: int):
    """M38-c3: lazy AI diff (не вызывается автоматически на GET)."""
    user = get_user_from_request(request)
    normalize_user_role(user)
    if not user or user.role not in ("admin", "main_technologist", "technologist"):
        raise HTTPException(403, "Недостаточно прав")
    # F2-004: 404 check
    n = get_notice(notice_id)
    if not n:
        raise HTTPException(404, "Извещение не найдено")
    try:
        ai_diff = generate_ai_diff(notice_id)
        return {"status": "ok", "ai_diff": ai_diff}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/notices/{notice_id}/resolve")
async def notice_resolve(request: Request, notice_id: int):
    form = await request.form()
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401)
    normalize_user_role(user)
    if user.role not in ("admin", "main_technologist", "technologist"):
        raise HTTPException(403, "Только технолог может решать извещения")
    # F-008: 404 check
    n = get_notice(notice_id)
    if not n:
        raise HTTPException(404, "Извещение не найдено")
    decision = form.get("decision", "manual_review")
    notes = form.get("notes", "")
    result = resolve_notice_svc(notice_id, user.username, decision, notes)
    # B3 (Sprint 6): audit-trail
    log_history("notice", notice_id, "resolve", user.username, {"decision": decision, "result": result})
    return RedirectResponse(url=f"/notices/{notice_id}", status_code=303)


@app.get("/api/change-notices")
async def api_list_notices(request: Request, status: Optional[str] = None):
    if not get_user_from_request(request):
        raise HTTPException(401, "Authentication required")
    return {"notices": list_notices(status=status)}


@app.get("/api/change-notices/{notice_id}")
async def api_notice(request: Request, notice_id: int):
    if not get_user_from_request(request):
        raise HTTPException(401, "Authentication required")
    """F2-003: lazy AI diff (не вызывается на GET — иначе 24 сек LLM)."""
    n = get_notice(notice_id)
    if not n:
        raise HTTPException(404)
    # AI diff генерится только через /api/change-notices/{id}/diff
    return n


@app.post("/api/change-notices/{notice_id}/diff")
async def api_notice_diff(notice_id: int, request: Request):
    """F2-003: явный запрос AI diff (lazy)."""
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401)
    normalize_user_role(user)
    if user.role not in ("admin", "main_technologist", "technologist"):
        raise HTTPException(403)
    n = get_notice(notice_id)
    if not n:
        raise HTTPException(404, "Извещение не найдено")
    try:
        ai_diff = generate_ai_diff(notice_id)
        return {"status": "ok", "ai_diff": ai_diff}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/profiles", response_class=HTMLResponse)
async def profiles(request: Request):
    user = get_user_from_request(request)
    normalize_user_role(user)
    if not user or user.role not in ("admin", "main_technologist"):
        raise HTTPException(403, "Недостаточно прав")
    ctx = get_template_context(request, user)
    profiles_list = db.rows_to_dicts(db.query("SELECT * FROM rs_output_profiles"))
    ctx["profiles"] = profiles_list
    ctx["default_profile"] = DEFAULT_PROFILE
    return templates.TemplateResponse("profiles.html", ctx)


@app.get("/knowledge", response_class=HTMLResponse)
async def knowledge(request: Request):
    user = get_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login?next=/knowledge", status_code=303)
    ctx = get_template_context(request, user)
    etalons = db.rows_to_dicts(db.query("SELECT * FROM etalons ORDER BY approved_date DESC"))
    ctx["etalons"] = etalons
    return templates.TemplateResponse("knowledge.html", ctx)


@app.get("/llm-admin", response_class=HTMLResponse)
async def llm_admin(request: Request):
    user = get_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login?next=/llm-admin", status_code=303)
    if user and not has_permission(user.role, "manage_llm_providers"):
        raise HTTPException(403, "Requires llm_admin role")
    ctx = get_template_context(request, user)
    providers = db.rows_to_dicts(db.query("SELECT * FROM llm_providers"))
    assignments = db.rows_to_dicts(db.query("""
        SELECT ma.*, p.display_name AS provider_display
        FROM llm_model_assignments ma
        JOIN llm_providers p ON p.id = ma.llm_provider_id
    """))
    recent_calls = db.rows_to_dicts(db.query("""
        SELECT * FROM llm_calls ORDER BY ts DESC LIMIT 20
    """))
    ctx.update({
        "providers": providers,
        "assignments": assignments,
        "recent_calls": recent_calls,
    })
    return templates.TemplateResponse("llm_admin.html", ctx)


@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    user = get_user_from_request(request)
    ctx = get_template_context(request, user)
    return templates.TemplateResponse("help.html", ctx)


# ============================================================
# МЕТРИКИ ПИЛОТА
# ============================================================

@app.get("/metrics", response_class=HTMLResponse)
async def metrics_page(request: Request):
    user = get_user_from_request(request)
    normalize_user_role(user)
    if not user or user.role not in ("admin", "main_technologist"):
        raise HTTPException(403, "Недостаточно прав")
    ctx = get_template_context(request, user)
    from services.metrics import get_dashboard_metrics, calc_green_pct
    ctx["metrics"] = get_dashboard_metrics()
    ctx["green_all"] = calc_green_pct("all")
    ctx["green_7d"] = calc_green_pct("last_7_days")
    ctx["green_30d"] = calc_green_pct("last_30_days")
    return templates.TemplateResponse("metrics.html", ctx)


@app.post("/metrics/record-green")
async def metrics_record_green(request: Request):
    """Записать текущий % зелёных (кнопка 'Зафиксировать замер')."""
    user = get_user_from_request(request)
    if not user or not (has_permission(user.role, "view_llm_calls") if user else False):
        raise HTTPException(403)
    from services.metrics import record_green_pct
    record_green_pct("all")
    return RedirectResponse(url="/metrics?recorded=1", status_code=303)


# ============================================================
# AUDIT UI (Sprint 6 / B4)
# ============================================================
# 3 таба: logins / history / llm_calls
# Фильтры: tab + user + date_from + date_to
# Permissions: admin (view_audit_logins + view_llm_calls) + main_technologist (те же)

@app.get("/audit", response_class=HTMLResponse)
async def audit_page(
    request: Request,
    tab: str = "logins",
    user: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = 100,
):
    user_obj = get_user_from_request(request)
    if not user_obj:
        raise HTTPException(401)
    normalize_user_role(user_obj)
    if user_obj.role not in ("admin", "main_technologist"):
        raise HTTPException(403, "Недостаточно прав (нужен admin или main_technologist)")

    # Sanitize inputs
    if tab not in ("logins", "history", "llm"):
        tab = "logins"
    if not isinstance(limit, int) or limit < 10 or limit > 500:
        limit = 100
    user_filter = user.strip()
    date_from = date_from.strip()
    date_to = date_to.strip()

    # Соберём данные в зависимости от tab
    logins = []
    history = []
    llm_calls = []

    if tab == "logins":
        where = []
        params = []
        if user_filter:
            where.append("username = ?")
            params.append(user_filter)
        if date_from:
            where.append("ts >= ?")
            params.append(date_from)
        if date_to:
            where.append("ts <= ?")
            params.append(date_to + " 23:59:59")
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        rows = db.query(
            f"SELECT id, username, ip, user_agent, success, reason, ts "
            f"FROM audit_logins {where_sql} ORDER BY id DESC LIMIT ?",
            tuple(params) + (limit,),
        )
        logins = db.rows_to_dicts(rows)
    elif tab == "history":
        where = []
        params = []
        if user_filter:
            where.append("user = ?")
            params.append(user_filter)
        if date_from:
            where.append("ts >= ?")
            params.append(date_from)
        if date_to:
            where.append("ts <= ?")
            params.append(date_to + " 23:59:59")
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        rows = db.query(
            f"SELECT id, entity_type, entity_id, action, user, details_json, ts "
            f"FROM history {where_sql} ORDER BY id DESC LIMIT ?",
            tuple(params) + (limit,),
        )
        history = db.rows_to_dicts(rows)
    elif tab == "llm":
        where = []
        params = []
        if user_filter:
            where.append("user = ?")
            params.append(user_filter)
        if date_from:
            where.append("ts >= ?")
            params.append(date_from)
        if date_to:
            where.append("ts <= ?")
            params.append(date_to + " 23:59:59")
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        rows = db.query(
            f"SELECT id, task_type, model_name, user, status, error_message, "
            f"duration_ms, prompt_tokens, completion_tokens, ts "
            f"FROM llm_calls {where_sql} ORDER BY id DESC LIMIT ?",
            tuple(params) + (limit,),
        )
        llm_calls = db.rows_to_dicts(rows)

    # Counts для табов
    login_count = db.query_one("SELECT COUNT(*) as c FROM audit_logins")["c"]
    history_count = db.query_one("SELECT COUNT(*) as c FROM history")["c"]
    llm_count = db.query_one("SELECT COUNT(*) as c FROM llm_calls")["c"]

    # Список уникальных users (для фильтра)
    user_rows = db.query("SELECT DISTINCT username FROM audit_logins ORDER BY username")
    login_users = [r["username"] for r in user_rows]
    user_rows2 = db.query("SELECT DISTINCT user FROM history WHERE user IS NOT NULL ORDER BY user")
    history_users = [r["user"] for r in user_rows2]
    user_rows3 = db.query("SELECT DISTINCT user FROM llm_calls WHERE user IS NOT NULL ORDER BY user")
    llm_users = [r["user"] for r in user_rows3]
    all_users = sorted(set(login_users + history_users + llm_users))

    ctx = get_template_context(request, user_obj)
    ctx.update({
        "tab": tab,
        "user_filter": user_filter,
        "date_from": date_from,
        "date_to": date_to,
        "limit": limit,
        "logins": logins,
        "history": history,
        "llm_calls": llm_calls,
        "login_count": login_count,
        "history_count": history_count,
        "llm_count": llm_count,
        "all_users": all_users,
    })
    return templates.TemplateResponse("audit.html", ctx)


# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/rs", response_class=HTMLResponse)
async def rs_export_page(request: Request):
    """M38-c4: страница выгрузки РС."""
    user = get_user_from_request(request)
    if not user:
        return RedirectResponse("/login", 303)
    ctx = get_template_context(request, user)
    return templates.TemplateResponse("rs_export.html", ctx)


@app.get("/api/rs/list")
async def api_rs_list(request: Request):
    """M38-c4: список выгруженных РС (XML файлов)."""
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401)
    import os
    out_dir = "data/one_c_exchange/out"
    if not os.path.exists(out_dir):
        return {"files": []}
    files = []
    for f in sorted(os.listdir(out_dir), reverse=True):
        if f.endswith(".xml"):
            full = os.path.join(out_dir, f)
            files.append({
                "filename": f,
                "size": os.path.getsize(full),
                "modified": os.path.getmtime(full),
            })
    return {"files": files}


@app.get("/api/rs/download/{filename}")
async def api_rs_download(filename: str, request: Request):
    """M38-c4: скачать XML РС (для 1С:ERP)."""
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401)
    import os
    # Защита от path traversal
    if "/" in filename or ".." in filename or chr(92) in filename:
        raise HTTPException(400, "invalid filename")
    out_dir = "data/one_c_exchange/out"
    fpath = os.path.join(out_dir, filename)
    if not os.path.exists(fpath):
        raise HTTPException(404, "file not found")
    from fastapi.responses import FileResponse
    return FileResponse(fpath, media_type="application/xml", filename=filename)


@app.get("/health")
async def health():
    """F3-002: health check с защитой от зависания при lock БД."""
    import signal as _signal
    db_status = "ok"
    n_items = 0
    n_etalons = 0
    try:
        # Hard timeout 1 sec (если БД залочена)
        def _timeout_handler(signum, frame):
            raise TimeoutError("db query timeout")
        old_handler = _signal.signal(_signal.SIGALRM, _timeout_handler)
        _signal.alarm(1)
        try:
            result = db.query_one("SELECT COUNT(*) AS n FROM items")
            n_items = result["n"] if result else 0
            result = db.query_one("SELECT COUNT(*) AS n FROM etalons")
            n_etalons = result["n"] if result else 0
        finally:
            _signal.alarm(0)
            _signal.signal(_signal.SIGALRM, old_handler)
    except Exception as e:
        db_status = f"error: {type(e).__name__}"
    overall = "ok" if db_status == "ok" else "degraded"
    return {
        "status": overall,
        "version": "1.0.0",
        "db": db_status,
        "items": n_items,
        "etalons": n_etalons,
        "is_mock_mode": get_registry().is_mock_mode(),
    }


@app.get("/api/items")
async def api_items(
    request: Request,
    level: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
):
    if not get_user_from_request(request):
        raise HTTPException(401, "Authentication required")
    items = db.list_items(level=level, search=search, limit=limit)
    return {"items": items, "total": len(items)}


@app.get("/api/tech-cards/{tech_card_id}/rs-preview")
async def api_rs_preview(request: Request, tech_card_id: int, profile_code: str = "default"):
    if not get_user_from_request(request):
        raise HTTPException(401, "Authentication required")
    """Предпросмотр РС по ТК + профилю (детерминированный расчёт)."""
    tc = db.get_tech_card_full(tech_card_id)
    if not tc:
        raise HTTPException(404, "Tech card not found")

    # Профиль
    if profile_code == "default":
        profile = DEFAULT_PROFILE
    else:
        row = db.query_one("SELECT * FROM rs_output_profiles WHERE code = ?", (profile_code,))
        profile = json.loads(row["axes_json"]) if row else DEFAULT_PROFILE

    report = build_rs(
        item_designation=tc.get("item_designation", "?"),
        operations=tc.get("operations", []),
        profile=profile,
        tech_card_id=tech_card_id,
    )
    return report.to_dict()


@app.get("/api/tech-cards/{tech_card_id}/evidence")
async def api_evidence(request: Request, tech_card_id: int):
    if not get_user_from_request(request):
        raise HTTPException(401, "Authentication required")
    """Sprint 5: «Норма с доказательством» — светофор + топ-3 аналога для каждой операции."""
    evidences = collect_evidence_for_tech_card(tech_card_id)
    return {
        "tech_card_id": tech_card_id,
        "summary": tech_card_evidence_summary(tech_card_id),
        "operations": [e.to_dict() for e in evidences],
    }


@app.post("/api/operations/{operation_id}/confirm")
async def api_confirm_operation(operation_id: int, request: Request, new_time: float = None):
    """Технолог подтверждает или корректирует норму операции."""
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401)
    normalize_user_role(user)
    if user.role not in ("admin", "main_technologist", "technologist"):
        raise HTTPException(403, "Недостаточно прав")
    # F2-005: 404 check
    op = db.query_one("SELECT id FROM operations WHERE id = ?", (operation_id,))
    if not op:
        raise HTTPException(404, "Операция не найдена")
    if new_time is None:
        try:
            body = await request.json()
            new_time = float(body.get("new_time", 0))
        except Exception:
            raise HTTPException(400, "invalid JSON body or missing new_time")
    ok = update_operation_evidence(operation_id, new_time, user.username, "Подтверждение в UI")
    # Метрика c: после подтверждения записать % зелёных
    try:
        from services.metrics import record_green_pct
        record_green_pct("all")
    except Exception:
        pass
    # B3 (Sprint 6): audit-trail
    log_history("operation", operation_id, "confirm", user.username, {"new_time": new_time, "ok": ok})
    return {"status": "ok" if ok else "error", "operation_id": operation_id, "new_time": new_time}


@app.post("/api/operations/{operation_id}/update")
async def api_update_operation(operation_id: int, request: Request):
    """Q-004 (M35t): inline-edit для любого поля операции.
    Поддерживает: name, time_per_unit_min, time_setup_min, workshop_id, equipment_id, profession_id.
    FK-поля (workshop_id, equipment_id, profession_id) принимают int ID (а не код).
    Текстовые поля (name) — str. Числовые (time_*) — float.
    """
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401)
    normalize_user_role(user)
    # M38-fix A21: RBAC — только редакторы (не workshop_chief)
    if user.role not in ("admin", "main_technologist", "technologist"):
        raise HTTPException(403, "Недостаточно прав для редактирования")
    # M38-c4: defensive — некорректный JSON → 400 а не 500
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "invalid JSON body")
    field = body.get("field")
    value = body.get("value")
    if not field or value is None:
        raise HTTPException(400, "field and value required")

    # Whitelist допустимых полей
    allowed_text = ["name"]
    allowed_num = ["time_per_unit_min", "time_setup_min"]
    allowed_fk = ["workshop_id", "equipment_id", "profession_id"]
    if field in allowed_text:
        sql_value = str(value)[:200]
    elif field in allowed_num:
        try:
            sql_value = float(value)
        except (TypeError, ValueError):
            raise HTTPException(400, f"invalid numeric value: {value!r}")
    elif field in allowed_fk:
        try:
            sql_value = int(value) if value != "" else None
        except (TypeError, ValueError):
            raise HTTPException(400, f"invalid FK value: {value!r}")
    else:
        raise HTTPException(400, f"field {field!r} not editable")

    # Защита: операция должна существовать
    op = db.query_one("SELECT id, tech_card_id, name FROM operations WHERE id = ?", (operation_id,))
    if not op:
        raise HTTPException(404, "operation not found")

    # Защита: нельзя править утверждённую ТК
    tc = db.query_one("SELECT is_approved FROM tech_cards WHERE id = ?", (op["tech_card_id"],))
    if tc and tc["is_approved"]:
        raise HTTPException(403, "ТК утверждена — правки запрещены (откройте новую версию)")

    # Запись в БД + логирование в edits (для петли обратной связи Q-001)
    try:
        # C3 (Sprint 6): логируем ВСЕ поля inline-edit в edits (для diff версий)
        # Раньше логировался только name — теперь любое поле
        old_value_raw = op.get(field) if field in op.keys() else None
        old_value_str = str(old_value_raw) if old_value_raw is not None else None
        new_value_str = str(sql_value) if sql_value is not None else None
        db.execute(f"UPDATE operations SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                   (sql_value, operation_id))
        # C3: логируем ВСЕ поля (не только name) — для diff версий
        if old_value_str != new_value_str:  # Не пишем если значение не изменилось
            db.execute("""INSERT INTO edits (tech_card_id, operation_id, field, old_value, new_value, user, ts)
                          VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                       (op["tech_card_id"], operation_id, field, old_value_str, new_value_str, user.username))
        # B3 (Sprint 6): audit-trail
        log_history("operation", operation_id, "update", user.username, {"field": field, "value": sql_value, "old_value": old_value_str})
        return {"status": "ok", "operation_id": operation_id, "field": field, "value": sql_value}
    except Exception as e:
        raise HTTPException(500, f"db error: {e}")


@app.post("/api/tech-cards/{tech_card_id}/regenerate")
async def api_regenerate(tech_card_id: int, request: Request):
    """Перегенерировать ТК через LLM (mock)."""
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401)
    normalize_user_role(user)
    if user.role not in ("admin", "main_technologist", "technologist"):
        raise HTTPException(403, "Недостаточно прав")
    tc = db.get_tech_card_full(tech_card_id)
    if not tc:
        raise HTTPException(404)
    # Mock
    # Sprint 6 E1: используем REFINE_PROMPT + workshops_context, а не "Ты — главный технолог"
    from domain.prompts import REFINE_PROMPT as _REFINE
    refine_system = _REFINE.replace("$workshops_context", WORKSHOP_CONTEXT)
    result = call_llm("tech_card_generation",
                      prompt=f"Сгенерируй ТК для {tc.get('item_designation')}",
                      system=refine_system)
    return {"status": "ok", "llm_response": result.parse_json(), "model": result.model}


@app.get("/api/tech-cards/{tech_card_id}/diff")
async def api_tech_card_diff(request: Request, tech_card_id: int):
    """C3 (Sprint 6): список изменений (edits) для ТК — визуальный diff версий.

    Возвращает все правки inline-edit (поле, было, стало, кто, когда).
    Используется технологом перед утверждением — увидеть что отличается от эталона.
    """
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401)
    normalize_user_role(user)
    # RBAC: все аутентифицированные пользователи могут смотреть diff (read-only)
    if user.role not in ("admin", "main_technologist", "technologist", "workshop_chief"):
        raise HTTPException(403, "Недостаточно прав")

    # Проверим что ТК существует
    tc = db.query_one("SELECT id, item_designation, is_approved FROM tech_cards WHERE id = ?", (tech_card_id,))
    if not tc:
        raise HTTPException(404, "ТК не найдена")

    # Все edits для этой ТК, сгруппированные по операции
    rows = db.query(
        """SELECT e.id, e.operation_id, e.field, e.old_value, e.new_value, e.user, e.ts, e.reason,
                  o.operation_no, o.name as op_name
           FROM edits e
           LEFT JOIN operations o ON o.id = e.operation_id
           WHERE e.tech_card_id = ?
           ORDER BY e.operation_id, e.ts""",
        (tech_card_id,),
    )
    edits = db.rows_to_dicts(rows)

    # Группировка по операциям
    by_op = {}
    for e in edits:
        op_id = e["operation_id"]
        if op_id not in by_op:
            by_op[op_id] = {
                "operation_id": op_id,
                "operation_no": e.get("operation_no"),
                "operation_name": e.get("op_name"),
                "edits": [],
            }
        by_op[op_id]["edits"].append({
            "id": e["id"],
            "field": e["field"],
            "old_value": e["old_value"],
            "new_value": e["new_value"],
            "user": e["user"],
            "ts": e["ts"],
            "reason": e.get("reason"),
        })

    return {
        "tech_card_id": tech_card_id,
        "item_designation": tc["item_designation"],
        "is_approved": bool(tc["is_approved"]),
        "total_edits": len(edits),
        "by_operation": list(by_op.values()),
    }


@app.post("/api/tech-cards/{tech_card_id}/approve")
async def api_approve(tech_card_id: int, request: Request):
    """Утвердить ТК → добавить в эталоны (петля обратной связи)."""
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401)
    normalize_user_role(user)
    if user.role not in ("admin", "main_technologist"):
        raise HTTPException(403, "Только главный технолог или администратор может утвердить ТК")
    tc = db.get_tech_card_full(tech_card_id)
    if not tc:
        raise HTTPException(404)

    # Получить операции как dict
    operations = tc.get("operations", [])

    # B1 (Sprint 6): атомарная транзакция — INSERT/UPDATE etalons + UPDATE tech_cards
    # Если что-то упадёт между — откат, etalon и tech_card синхронны.
    designation = tc.get("designation") or f"TC-{tech_card_id}"
    with db.transaction() as conn:
        existing = conn.execute("SELECT id FROM etalons WHERE designation = ?", (designation,)).fetchone()
        if existing:
            # Обновляем существующий эталон
            etalon_id = existing["id"]
            conn.execute("""
                UPDATE etalons SET name=?, source_doc=?, approved_by=?, is_approved=1, is_published=1,
                content_json=?, approved_date=CURRENT_DATE
                WHERE id=?
            """, (
                tc.get("name", ""),
                f"Утверждена {user.username} из ТК v{tc.get('version', 1)}",
                user.username,  # M38-v6-152: 152-ФЗ — пишем login, не ФИО
                json.dumps({
                    "operations": [
                        {
                            "op_number": op.get("op_number"),
                            "name": op.get("name"),
                            "time_setup_min": op.get("time_setup_min", 0),
                            "time_per_unit_min": op.get("time_per_unit_min", 0),
                            "profession_code": op.get("profession_code", ""),
                            "equipment_name": op.get("equipment_name", ""),
                        }
                        for op in operations
                    ],
                }, ensure_ascii=False),
                etalon_id,
            ))
        else:
            cur = conn.execute("""
                INSERT INTO etalons (designation, name, product_type, source_doc, source_pages,
                                     approved_by, approved_date, is_approved, is_published, content_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                designation,
                tc.get("name", ""),
                "",
                f"Утверждена {user.username} из ТК v{tc.get('version', 1)}",
                0,
                user.username,  # M38-v6-152
                None,
                1,
                1,
                json.dumps({
                    "operations": [
                        {
                            "op_number": op.get("op_number"),
                            "name": op.get("name"),
                            "time_setup_min": op.get("time_setup_min", 0),
                            "time_per_unit_min": op.get("time_per_unit_min", 0),
                            "profession_code": op.get("profession_code", ""),
                            "equipment_name": op.get("equipment_name", ""),
                        }
                        for op in operations
                    ],
                }, ensure_ascii=False),
            ))
            etalon_id = cur.lastrowid
        # Обновим ТК (is_approved, status, approver)
        conn.execute("""
            UPDATE tech_cards SET is_approved = 1, status = 'approved',
            approver_chief = ?, approved_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (user.username, tech_card_id))  # M38-v6-152

    # Метрика b: финиш замера (если был start в pilot_runs)
    from services.metrics import finish_tc_generation, record_green_pct
    last_run = db.query_one(
        "SELECT id FROM pilot_runs WHERE item_id = (SELECT item_id FROM tech_cards WHERE id = ?) AND finished_at IS NULL ORDER BY id DESC LIMIT 1",
        (tech_card_id,),
    )
    if last_run:
        finish_tc_generation(last_run["id"], tech_card_id, notes=f"approved by {user.username}")
    # Метрика c: записать % зелёных
    record_green_pct("all")

        # B3 (Sprint 6): audit-trail
    log_history("tech_card", tech_card_id, "approve", user.username, {"etalon_id": etalon_id, "version": tc.get("version", 1)})
    return {"status": "ok", "etalon_id": etalon_id, "message": "ТК утверждена и добавлена в эталоны", "duration_sec": None}


@app.post("/api/change-notices/{notice_id}/process")
async def api_process_notice(notice_id: int, request: Request):
    """Обработать извещение: AI diff + пересчёт РС."""
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401)
    normalize_user_role(user)
    if user.role not in ("admin", "main_technologist", "technologist"):
        raise HTTPException(403, "Недостаточно прав")
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    except Exception:
        raise HTTPException(400, "invalid JSON body")
    decision = body.get("decision", "manual_review")
    # B3 (Sprint 6): audit-trail
    result = resolve_notice_svc(notice_id, user.username, decision, "")
    log_history("notice", notice_id, "process", user.username, {"decision": decision, "result": result})
    return result


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():
    """При старте — логируем состояние."""
    n_etalons = db.query_one("SELECT COUNT(*) AS n FROM etalons")["n"]
    n_items = db.query_one("SELECT COUNT(*) AS n FROM items")["n"]
    n_users = db.query_one("SELECT COUNT(*) AS n FROM pilot_users")["n"]
    logger.info(f"startup: etalons={n_etalons}, items={n_items}, users={n_users}")


if __name__ == "__main__":
    import uvicorn
    import os as _os
    _ssl_kwargs = {}
    if _os.path.exists("certs/cert.pem") and _os.path.exists("certs/key.pem"):
        _ssl_kwargs = {"ssl_keyfile": "certs/key.pem", "ssl_certfile": "certs/cert.pem"}
        print("🔒 TLS enabled (certs/cert.pem)")
    # F3-001: единый порт с systemd (8081) — иначе конфликт
    uvicorn.run(
        app, host="0.0.0.0", port=8081, log_level="info",
        timeout_graceful_shutdown=30,  # M37-#5: 30s drain
        **_ssl_kwargs,
    )
