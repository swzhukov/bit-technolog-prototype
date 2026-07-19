"""
БИТ.Технолог — Прототип v0.1
AI-помощник технолога для ускорения создания техкарт.

Запуск: python app.py
Открыть: http://localhost:8080
"""

import os
import json
import io
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment
load_dotenv()
LLM_API_URL = os.getenv("LLM_API_URL", "https://api.1bitai.ru/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash-thinking")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

# Стоимость и лимиты
LLM_PRICE_INPUT_RUB_PER_1K = float(os.getenv("LLM_PRICE_INPUT_RUB_PER_1K", "0.40"))
LLM_PRICE_OUTPUT_RUB_PER_1K = float(os.getenv("LLM_PRICE_OUTPUT_RUB_PER_1K", "1.20"))
LLM_DAILY_LIMIT_RUB = float(os.getenv("LLM_DAILY_LIMIT_RUB", "200"))

# Auto-enable demo mode if API key is empty
if not LLM_API_KEY and not DEMO_MODE:
    log_msg = "No LLM_API_KEY set — auto-enabling DEMO_MODE"
    print(f"[WARN] {log_msg}")
    DEMO_MODE = True

# Auth (C1 fix): HTTP Basic с переменной PILOT_USERS=user:pass,admin:pass
PILOT_USERS_RAW = os.getenv("PILOT_USERS", "")
PILOT_USERS = {}
if PILOT_USERS_RAW:
    for pair in PILOT_USERS_RAW.split(","):
        if ":" in pair:
            u, p = pair.split(":", 1)
            PILOT_USERS[u.strip()] = p.strip()
PILOT_AUTH_ENABLED = bool(PILOT_USERS) and not os.getenv("PILOT_AUTH_DISABLED", "").lower() == "true"

# LLM client singleton (C4 fix)
_LLM_CLIENT = None

def get_llm_client():
    """Lazy-init singleton OpenAI client"""
    global _LLM_CLIENT
    if _LLM_CLIENT is None and not DEMO_MODE:
        from openai import OpenAI
        _LLM_CLIENT = OpenAI(
            base_url=LLM_API_URL,
            api_key=LLM_API_KEY,
            timeout=LLM_TIMEOUT
        )
    return _LLM_CLIENT

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("bit-technolog")

# FastAPI app
app = FastAPI(title="БИТ.Технолог — Прототип", version="0.2.1")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ========== C1 fix: HTTP Basic Auth middleware ==========
from fastapi import status as http_status
from fastapi.responses import Response

def check_auth(request: Request) -> bool:
    """Проверяет HTTP Basic Auth. False = пускать без auth (для тестов/DEMO)."""
    if not PILOT_AUTH_ENABLED:
        return True
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Basic "):
        return False
    import base64
    try:
        decoded = base64.b64decode(auth[6:]).decode("utf-8")
        if ":" in decoded:
            u, p = decoded.split(":", 1)
            return PILOT_USERS.get(u) == p
    except Exception:
        return False
    return False


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Middleware: требует auth для всех кроме /static, /health, /login, /docs"""
    path = request.url.path
    # Публичные пути
    public = ("/static", "/health", "/login", "/docs", "/openapi.json", "/favicon.ico")
    if any(path.startswith(p) for p in public):
        return await call_next(request)
    if PILOT_AUTH_ENABLED and not check_auth(request):
        return Response(
            content="<h1>401 Unauthorized</h1><p>Нужен логин/пароль из PILOT_USERS в .env</p>",
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": 'Basic realm="BIT-Technolog"'},
            media_type="text/html; charset=utf-8"
        )
    return await call_next(request)


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Показывает форму логина если браузер не Basic Auth"""
    return HTMLResponse(
        '<h1>BIT-Technolog</h1><p>Откройте в браузере с логином/паролем или введите в URL: '
        '<code>http://user:pass@host:8000/</code></p>',
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="BIT-Technolog"'}
    )


# Jinja globals: daily_cost() вызывается в каждом шаблоне автоматически
def _daily_cost_global():
    return get_daily_cost()

templates.env.globals["daily_cost"] = _daily_cost_global


# Middleware: добавляет daily_cost в request.state (для endpoints, не для шаблонов)
@app.middleware("http")
async def add_daily_cost(request: Request, call_next):
    request.state.daily_cost = get_daily_cost()
    response = await call_next(request)
    return response

# Local imports
from prompts import TECH_CARD_PROMPT
from mock_data import MOCK_DETAILS
from few_shot import FEW_SHOT_4C85941A

with open("equipment.json", "r", encoding="utf-8") as f:
    EQUIPMENT = json.load(f)

with open("structure.json", "r", encoding="utf-8") as f:
    STRUCTURE = json.load(f)

# Database
DB_PATH = "bit_technolog.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    # C5 fix: WAL mode для concurrent writes (3+ пользователей)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row  # доступ по имени колонки
    return conn


def get_table_columns(table: str) -> list:
    """C3 fix: helper для PRAGMA, без утечки соединений"""
    conn = get_conn()
    cols = [d[1] for d in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    conn.close()
    return cols


def init_db():
    """Initialize SQLite database with full schema"""
    conn = get_conn()
    conn.executescript("""
        -- 1. Детали от конструкторов (вместо mock_data.py)
        CREATE TABLE IF NOT EXISTS details (
            id TEXT PRIMARY KEY,
            designation TEXT NOT NULL,
            name TEXT,
            model TEXT,
            chassis TEXT,
            material TEXT,
            size_mm TEXT,
            mass_kg REAL,
            surface_treatment TEXT,
            extra_props TEXT,
            tech_rules TEXT,
            cost_per_hour REAL DEFAULT 0,
            overhead_pct REAL DEFAULT 15,
            material_cost_rub REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 2. Черновики техкарт (LLM output)
        CREATE TABLE IF NOT EXISTS drafts (
            detail_id TEXT PRIMARY KEY,
            llm_output TEXT,
            status TEXT DEFAULT 'new',
            author TEXT DEFAULT 'system',
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );

        -- 3. Версии черновика (v1, v2, v3...)
        CREATE TABLE IF NOT EXISTS draft_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id TEXT,
            version INTEGER,
            operations_json TEXT,
            author TEXT,
            source TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 4. Правки технолога (для обучения)
        CREATE TABLE IF NOT EXISTS edits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id TEXT,
            version INTEGER,
            field TEXT,
            old_value TEXT,
            new_value TEXT,
            reason TEXT,
            author TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 5. Извлечённые правила (обучение)
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_type TEXT,
            condition_json TEXT,
            action_json TEXT,
            confidence REAL DEFAULT 0.5,
            uses_count INTEGER DEFAULT 0,
            source_edits TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 6. Оборудование
        CREATE TABLE IF NOT EXISTS equipment (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            code TEXT,
            max_thickness_mm REAL,
            max_mass_kg REAL,
            notes TEXT,
            source TEXT DEFAULT '1c',
            external_id TEXT,
            last_sync_at TIMESTAMP
        );

        -- 7. Материалы
        CREATE TABLE IF NOT EXISTS materials (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            grade TEXT,
            gost TEXT,
            notes TEXT,
            source TEXT DEFAULT '1c',
            external_id TEXT,
            last_sync_at TIMESTAMP
        );

        -- 8. Цеха/участки/РМ (структура)
        CREATE TABLE IF NOT EXISTS departments (
            id TEXT PRIMARY KEY,
            production TEXT,
            name TEXT NOT NULL,
            code TEXT
        );

        -- 9. ИОТ номера
        CREATE TABLE IF NOT EXISTS iot (
            id TEXT PRIMARY KEY,
            number TEXT NOT NULL,
            description TEXT,
            applies_to TEXT,
            source TEXT DEFAULT '1c',
            external_id TEXT,
            last_sync_at TIMESTAMP
        );

        -- 10. Бенчмарки трудоёмкости
        CREATE TABLE IF NOT EXISTS benchmarks (
            id TEXT PRIMARY KEY,
            detail_type TEXT NOT NULL,
            norm_hours REAL,
            source TEXT,
            sample_size INTEGER DEFAULT 1,
            external_id TEXT,
            last_sync_at TIMESTAMP
        );

        -- 11. История действий
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id TEXT,
            action TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT
        );

        -- 13. Пилотные метрики (KPI)
        CREATE TABLE IF NOT EXISTS pilot_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id TEXT,
            metric TEXT,
            value REAL,
            extra TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 12. Лог LLM-вызовов (промпт + ответ + токены)
        CREATE TABLE IF NOT EXISTS llm_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id TEXT,
            model TEXT,
            system_prompt TEXT,
            user_prompt TEXT,
            response_text TEXT,
            response_parsed_ok INTEGER,
            tokens_in INTEGER,
            tokens_out INTEGER,
            duration_ms INTEGER,
            cost_rub REAL DEFAULT 0,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Миграция: добавляем колонку cost_rub если её нет (для старых БД)
    try:
        conn.execute("ALTER TABLE llm_calls ADD COLUMN cost_rub REAL DEFAULT 0")
    except Exception:
        pass
    # Миграции для новых полей в справочниках
    for table, col in [
        ("equipment", "source"), ("equipment", "external_id"), ("equipment", "last_sync_at"),
        ("materials", "source"), ("materials", "external_id"), ("materials", "last_sync_at"),
        ("iot", "source"), ("iot", "external_id"), ("iot", "last_sync_at"),
        ("benchmarks", "external_id"), ("benchmarks", "last_sync_at"),
    ]:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
        except Exception:
            pass
    # Миграции для details
    for col, dtype in [("tech_rules", "TEXT"), ("cost_per_hour", "REAL"), ("overhead_pct", "REAL"), ("material_cost_rub", "REAL")]:
        try:
            conn.execute(f"ALTER TABLE details ADD COLUMN {col} {dtype}")
        except Exception:
            pass
    # Миграции для drafts (ролевая модель)
    for col, dtype in [("status_ext", "TEXT DEFAULT 'draft'"), ("approver", "TEXT"), ("submitted_at", "TIMESTAMP")]:
        try:
            conn.execute(f"ALTER TABLE drafts ADD COLUMN {col} {dtype}")
        except Exception:
            pass
    conn.commit()
    conn.close()
    seed_initial_data()


def seed_initial_data():
    """Заполняет справочники дефолтными данными из mock-файлов (если пусто)"""
    conn = get_conn()

    # 1. Детали из mock_data.py
    if conn.execute("SELECT COUNT(*) FROM details").fetchone()[0] == 0:
        for d in MOCK_DETAILS:
            conn.execute("""INSERT INTO details
                (id, designation, name, model, chassis, material, mass_kg, surface_treatment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (d["id"], d["designation"], d["name"], d.get("model"),
                 d.get("chassis"), d.get("material"), d.get("mass_kg"),
                 d.get("surface_treatment")))

    # 2. Оборудование
    if conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0] == 0:
        for i, e in enumerate(EQUIPMENT, 1):
            eid = f"eq-{i:03d}"
            conn.execute("""INSERT INTO equipment
                (id, name, type, code, max_thickness_mm, max_mass_kg, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (eid, e["name"], e.get("type"), str(e.get("code") or ""),
                 e.get("max_dim_mm"), e.get("max_mass_kg"),
                 f"group={e.get('group','')}; rank={e.get('rank','')}; operations={','.join(e.get('operations', []))}"))

    # 3. Цеха
    if conn.execute("SELECT COUNT(*) FROM departments").fetchone()[0] == 0:
        for prod in STRUCTURE.get("productions", []):
            for ws in prod.get("workshops", []):
                wsid = f"{prod.get('code', '01')}/{ws.get('code')}"
                conn.execute("""INSERT INTO departments (id, production, name, code)
                    VALUES (?, ?, ?, ?)""",
                    (wsid, prod.get("name", ""), ws.get("name", ""), ws.get("code", "")))

    # 4. Материалы (базовые)
    if conn.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 0:
        for m_id, m_name, m_gost in [
            ("steel-3", "Сталь 3", "ГОСТ 380-2005"),
            ("steel-09g2s", "Сталь 09Г2С", "ГОСТ 19281-2014"),
            ("steel-30khgsa", "Сталь 30ХГСА", "ГОСТ 4543-2016"),
            ("steel-st3sp", "Сталь Ст3сп", "ГОСТ 380-2005"),
            ("ocinkovka", "Сталь оцинкованная", "ГОСТ 14918-2020"),
            ("aluminum-5083", "Алюминий 5083", "ГОСТ 21631-76"),
        ]:
            conn.execute("INSERT INTO materials (id, name, gost) VALUES (?, ?, ?)",
                         (m_id, m_name, m_gost))

    # 5. ИОТ (базовые для Техинкома)
    if conn.execute("SELECT COUNT(*) FROM iot").fetchone()[0] == 0:
        for i_id, num, desc, applies in [
            ("iot-3", "3", "Сварочные работы", "Сварка"),
            ("iot-11", "11", "Работа с подъёмниками", "Сборка"),
            ("iot-26", "26", "Грузоподъёмные операции", "Кран"),
            ("iot-49", "49", "Обработка металлов резанием", "Механообработка"),
            ("iot-15", "15", "Покрасочные работы", "Покраска"),
        ]:
            conn.execute("""INSERT INTO iot (id, number, description, applies_to)
                VALUES (?, ?, ?, ?)""", (i_id, num, desc, applies))

    # 6. Бенчмарки
    if conn.execute("SELECT COUNT(*) FROM benchmarks").fetchone()[0] == 0:
        for b_id, dtype, hrs, src in [
            ("bk-plastina", "Пластина", 0.48, "ведомость Техинкома"),
            ("bk-ugolok", "Уголок", 0.48, "ведомость Техинкома"),
            ("bk-planka", "Планка", 0.48, "ведомость Техинкома"),
            ("bk-kronshtein", "Кронштейн замка", 4.5, "ведомость Техинкома"),
            ("bk-shassi-podgot", "Шасси подготовленное", 16.0, "ведомость Техинкома"),
            ("bk-pss131", "ПСС 131.35Э итого", 1296.36, "ведомость Техинкома"),
        ]:
            conn.execute("""INSERT INTO benchmarks (id, detail_type, norm_hours, source)
                VALUES (?, ?, ?, ?)""", (b_id, dtype, hrs, src))

    conn.commit()
    conn.close()


# CRUD-функции
def get_all_details() -> list:
    conn = get_conn()
    rows = conn.execute("""SELECT id, designation, name, model, chassis, material,
        mass_kg, surface_treatment, created_at
        FROM details ORDER BY created_at DESC""").fetchall()
    conn.close()
    cols = ["id", "designation", "name", "model", "chassis", "material",
            "mass_kg", "surface_treatment", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


def get_detail(detail_id: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM details WHERE id = ?", (detail_id,)).fetchone()
    if not row:
        conn.close()
        return None
    cols = [d[1] for d in conn.execute("PRAGMA table_info(details)").fetchall()]
    conn.close()
    return dict(zip(cols, row))


def create_detail(d: dict) -> str:
    import uuid
    detail_id = d.get("id") or f"d-{uuid.uuid4().hex[:8]}"
    conn = get_conn()
    conn.execute("""INSERT INTO details
        (id, designation, name, model, chassis, material, size_mm, mass_kg, surface_treatment, extra_props)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (detail_id, d.get("designation", ""), d.get("name", ""),
         d.get("model", ""), d.get("chassis", ""), d.get("material", ""),
         d.get("size_mm", ""), d.get("mass_kg", 0), d.get("surface_treatment", ""),
         json.dumps(d.get("extra_props", {}), ensure_ascii=False)))
    conn.commit()
    conn.close()
    return detail_id


def get_all_equipment() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM equipment ORDER BY name").fetchall()
    conn.close()
    cols = ["id", "name", "type", "code", "max_thickness_mm", "max_mass_kg", "notes",
            "source", "external_id", "last_sync_at"]
    return [dict(zip(cols, r)) for r in rows]


def create_equipment(e: dict) -> str:
    import uuid
    eid = e.get("id") or f"eq-{uuid.uuid4().hex[:6]}"
    conn = get_conn()
    conn.execute("""INSERT INTO equipment
        (id, name, type, code, max_thickness_mm, max_mass_kg, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (eid, e["name"], e.get("type", ""), e.get("code", ""),
         e.get("max_thickness_mm"), e.get("max_mass_kg"), e.get("notes", "")))
    conn.commit()
    conn.close()
    return eid


def get_all_materials() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM materials ORDER BY name").fetchall()
    conn.close()
    cols = ["id", "name", "grade", "gost", "notes"]
    return [dict(zip(cols, r)) for r in rows]


def create_material(m: dict) -> str:
    import uuid
    mid = m.get("id") or f"m-{uuid.uuid4().hex[:6]}"
    conn = get_conn()
    conn.execute("INSERT INTO materials (id, name, grade, gost, notes) VALUES (?, ?, ?, ?, ?)",
                 (mid, m["name"], m.get("grade", ""), m.get("gost", ""), m.get("notes", "")))
    conn.commit()
    conn.close()
    return mid


def get_all_iot() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM iot ORDER BY number").fetchall()
    conn.close()
    cols = ["id", "number", "description", "applies_to"]
    return [dict(zip(cols, r)) for r in rows]


def create_iot(i: dict) -> str:
    import uuid
    iid = i.get("id") or f"iot-{uuid.uuid4().hex[:6]}"
    conn = get_conn()
    conn.execute("INSERT INTO iot (id, number, description, applies_to) VALUES (?, ?, ?, ?)",
                 (iid, i["number"], i.get("description", ""), i.get("applies_to", "")))
    conn.commit()
    conn.close()
    return iid


def get_all_benchmarks() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM benchmarks ORDER BY detail_type").fetchall()
    conn.close()
    cols = ["id", "detail_type", "norm_hours", "source", "sample_size"]
    return [dict(zip(cols, r)) for r in rows]


def create_benchmark(b: dict) -> str:
    import uuid
    bid = b.get("id") or f"bk-{uuid.uuid4().hex[:6]}"
    conn = get_conn()
    conn.execute("""INSERT INTO benchmarks (id, detail_type, norm_hours, source, sample_size)
        VALUES (?, ?, ?, ?, ?)""",
        (bid, b["detail_type"], b.get("norm_hours", 0), b.get("source", ""), b.get("sample_size", 1)))
    conn.commit()
    conn.close()
    return bid


# Версии черновика
def save_version(detail_id: str, operations: list, author: str, source: str = "edit", notes: str = ""):
    """Сохраняет новую версию черновика"""
    conn = get_conn()
    last_v = conn.execute(
        "SELECT MAX(version) FROM draft_versions WHERE detail_id = ?", (detail_id,)
    ).fetchone()[0] or 0
    new_v = last_v + 1
    conn.execute("""INSERT INTO draft_versions
        (detail_id, version, operations_json, author, source, notes)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (detail_id, new_v, json.dumps(operations, ensure_ascii=False), author, source, notes))
    conn.commit()
    conn.close()
    return new_v


def get_versions(detail_id: str) -> list:
    conn = get_conn()
    rows = conn.execute("""SELECT version, author, source, notes, created_at
        FROM draft_versions WHERE detail_id = ? ORDER BY version DESC""", (detail_id,)).fetchall()
    conn.close()
    return [{"version": r[0], "author": r[1], "source": r[2], "notes": r[3], "created_at": r[4]}
            for r in rows]


def get_version(detail_id: str, version: int) -> Optional[list]:
    conn = get_conn()
    row = conn.execute("""SELECT operations_json FROM draft_versions
        WHERE detail_id = ? AND version = ?""", (detail_id, version)).fetchone()
    conn.close()
    if not row:
        return None
    return json.loads(row[0])


# Правки (для обучения)
def record_edit(detail_id: str, version: int, field: str, old: str, new: str, reason: str = "", author: str = "technologist"):
    conn = get_conn()
    conn.execute("""INSERT INTO edits (detail_id, version, field, old_value, new_value, reason, author)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (detail_id, version, field, str(old)[:500], str(new)[:500], reason, author))
    conn.commit()
    conn.close()


def get_edits(detail_id: str = None) -> list:
    conn = get_conn()
    if detail_id:
        rows = conn.execute("""SELECT id, detail_id, version, field, old_value, new_value, reason, author, created_at
            FROM edits WHERE detail_id = ? ORDER BY id DESC""", (detail_id,)).fetchall()
    else:
        rows = conn.execute("""SELECT id, detail_id, version, field, old_value, new_value, reason, author, created_at
            FROM edits ORDER BY id DESC LIMIT 100""").fetchall()
    conn.close()
    cols = ["id", "detail_id", "version", "field", "old_value", "new_value", "reason", "author", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


# Правила (обучение)
def calc_cost_rub(tokens_in: int, tokens_out: int) -> float:
    """Считает стоимость вызова в рублях"""
    if not tokens_in or not tokens_out:
        return 0.0
    return round(
        (tokens_in / 1000.0) * LLM_PRICE_INPUT_RUB_PER_1K +
        (tokens_out / 1000.0) * LLM_PRICE_OUTPUT_RUB_PER_1K,
        4
    )


def get_daily_cost(date_str: str = None) -> dict:
    """Считает расход за указанный день (по умолчанию — сегодня)"""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    row = conn.execute("""SELECT
        COALESCE(SUM(cost_rub), 0) as total,
        COUNT(*) as calls,
        COALESCE(SUM(tokens_in), 0) as tokens_in,
        COALESCE(SUM(tokens_out), 0) as tokens_out
        FROM llm_calls
        WHERE DATE(created_at, 'localtime') = ? AND cost_rub > 0""",
        (date_str,)).fetchone()
    conn.close()
    return {
        "date": date_str,
        "total_rub": round(row[0] or 0, 4),
        "calls": row[1] or 0,
        "tokens_in": row[2] or 0,
        "tokens_out": row[3] or 0,
        "limit_rub": LLM_DAILY_LIMIT_RUB,
        "remaining_rub": round(LLM_DAILY_LIMIT_RUB - (row[0] or 0), 4),
        "exceeded": (row[0] or 0) >= LLM_DAILY_LIMIT_RUB
    }


# Pilot metrics
def record_metric(detail_id: str, metric: str, value: float, extra: dict = None):
    """Записывает KPI пилота (time_to_card, edits_count, accepted_pct, и т.д.)"""
    conn = get_conn()
    conn.execute("""INSERT INTO pilot_metrics (detail_id, metric, value, extra)
        VALUES (?, ?, ?, ?)""",
        (detail_id, metric, value, json.dumps(extra or {}, ensure_ascii=False)))
    conn.commit()
    conn.close()


def get_pilot_metrics() -> dict:
    """Возвращает KPI для дашборда пилота"""
    conn = get_conn()
    # Всего деталей прошло через пилот
    total = conn.execute("SELECT COUNT(DISTINCT detail_id) FROM pilot_metrics").fetchone()[0] or 0
    # Среднее число правок на черновик
    edits_per_card = conn.execute("""SELECT AVG(cnt) FROM (
        SELECT detail_id, COUNT(*) as cnt FROM pilot_metrics WHERE metric='edit' GROUP BY detail_id
    )""").fetchone()[0] or 0
    # % принятых операций (метрика 'accepted')
    accepted = conn.execute("""SELECT
        COALESCE(SUM(CASE WHEN metric='accepted_op' THEN value ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN metric='total_ops' THEN value ELSE 0 END), 1)
        FROM pilot_metrics""").fetchone()
    accepted_pct = (accepted[0] / accepted[1] * 100) if accepted[1] else 0
    # Среднее время на техкарту
    avg_time = conn.execute("""SELECT AVG(value) FROM pilot_metrics
        WHERE metric='time_to_card_min'""").fetchone()[0] or 0
    # Всего потрачено на LLM
    total_cost = conn.execute("""SELECT COALESCE(SUM(cost_rub), 0) FROM llm_calls
        WHERE cost_rub > 0""").fetchone()[0] or 0
    # Генераций
    total_gens = conn.execute("SELECT COUNT(*) FROM llm_calls WHERE error IS NULL AND response_parsed_ok=1").fetchone()[0] or 0
    conn.close()
    return {
        "total_details_processed": total,
        "edits_per_card": round(edits_per_card, 2),
        "accepted_pct": round(accepted_pct, 1),
        "avg_time_to_card_min": round(avg_time, 1),
        "total_llm_cost_rub": round(total_cost, 2),
        "total_successful_gens": total_gens,
        # Целевые KPI (из совета)
        "kpi": {
            "time_target": 60,  # мин (текущее 240-480)
            "accepted_target": 50,  # % (минимум)
            "edits_target": 8,  # правок (максимум)
        }
    }


def log_llm_call(detail_id: str, model: str, system_prompt: str, user_prompt: str,
                 response_text: str = None, response_parsed_ok: bool = None,
                 tokens_in: int = None, tokens_out: int = None,
                 duration_ms: int = None, error: str = None):
    """Записывает каждый LLM-вызов в БД для отладки"""
    cost = calc_cost_rub(tokens_in or 0, tokens_out or 0)
    conn = get_conn()
    conn.execute("""INSERT INTO llm_calls
        (detail_id, model, system_prompt, user_prompt, response_text,
         response_parsed_ok, tokens_in, tokens_out, duration_ms, cost_rub, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (detail_id, model, system_prompt[:5000], user_prompt[:10000],
         (response_text or "")[:10000],
         1 if response_parsed_ok else (0 if response_parsed_ok is False else None),
         tokens_in, tokens_out, duration_ms, cost, error))
    conn.commit()
    conn.close()
    return cost


def get_llm_calls(detail_id: str = None, limit: int = 50) -> list:
    """Получает последние LLM-вызовы (для UI)"""
    conn = get_conn()
    if detail_id:
        rows = conn.execute("""SELECT id, detail_id, model, response_parsed_ok,
            tokens_in, tokens_out, duration_ms, error, created_at
            FROM llm_calls WHERE detail_id = ? ORDER BY id DESC LIMIT ?""",
            (detail_id, limit)).fetchall()
    else:
        rows = conn.execute("""SELECT id, detail_id, model, response_parsed_ok,
            tokens_in, tokens_out, duration_ms, error, created_at
            FROM llm_calls ORDER BY id DESC LIMIT ?""", (limit,)).fetchall()
    conn.close()
    cols = ["id", "detail_id", "model", "response_parsed_ok", "tokens_in",
            "tokens_out", "duration_ms", "error", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


def get_llm_call_detail(call_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("""SELECT id, detail_id, model, system_prompt, user_prompt,
        response_text, response_parsed_ok, tokens_in, tokens_out, duration_ms, error, created_at
        FROM llm_calls WHERE id = ?""", (call_id,)).fetchone()
    conn.close()
    if not row:
        return None
    cols = ["id", "detail_id", "model", "system_prompt", "user_prompt",
            "response_text", "response_parsed_ok", "tokens_in", "tokens_out",
            "duration_ms", "error", "created_at"]
    return dict(zip(cols, row))
def extract_rule_from_edits():
    """Извлекает правила из частых правок"""
    conn = get_conn()
    rows = conn.execute("""SELECT field, old_value, new_value, COUNT(*) as cnt
        FROM edits GROUP BY field, old_value, new_value HAVING cnt >= 2""").fetchall()
    rules = []
    for r in rows:
        rules.append({
            "field": r[0], "old": r[1], "new": r[2], "uses": r[3]
        })
    conn.close()
    return rules


def get_metrics() -> dict:
    """Метрики точности"""
    conn = get_conn()
    total_drafts = conn.execute("SELECT COUNT(*) FROM drafts").fetchone()[0]
    approved = conn.execute("SELECT COUNT(*) FROM drafts WHERE status='approved'").fetchone()[0]
    total_edits = conn.execute("SELECT COUNT(*) FROM edits").fetchone()[0]
    total_details = conn.execute("SELECT COUNT(*) FROM details").fetchone()[0]
    # Среднее правок на черновик
    avg_edits = 0
    if approved > 0:
        avg_edits = total_edits / approved
    # Процент точности: 0 правок = 100%, 10 правок = 0%
    accuracy = max(0, 100 - int(avg_edits * 10))
    conn.close()
    return {
        "total_details": total_details,
        "total_drafts": total_drafts,
        "approved": approved,
        "total_edits": total_edits,
        "avg_edits_per_draft": round(avg_edits, 2),
        "accuracy_pct": accuracy
    }


def get_draft(detail_id: str) -> Optional[dict]:
    """Get draft from DB"""
    conn = get_conn()
    cursor = conn.execute(
        "SELECT llm_output, status FROM drafts WHERE detail_id = ?",
        (detail_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return {"output": json.loads(row[0]), "status": row[1]}
    return None


def save_draft(detail_id: str, llm_output: dict, status: str = "draft", author: str = "llm"):
    """Save draft to DB + create version"""
    conn = get_conn()
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO drafts (detail_id, llm_output, status, author, created_at, updated_at)
           VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM drafts WHERE detail_id = ?), ?), ?)""",
        (detail_id, json.dumps(llm_output, ensure_ascii=False), status, author, detail_id, now, now)
    )
    conn.commit()
    conn.close()
    # Сохраняем версию операций
    if "operations" in llm_output:
        save_version(detail_id, llm_output["operations"], author=author, source="llm_generate")


def add_history(detail_id: str, action: str, details: dict = None):
    """Add history entry"""
    conn = get_conn()
    conn.execute(
        "INSERT INTO history (detail_id, action, details) VALUES (?, ?, ?)",
        (detail_id, action, json.dumps(details or {}, ensure_ascii=False))
    )
    conn.commit()
    conn.close()


# Pydantic models
class GenerateRequest(BaseModel):
    detail_id: str
    answers: Optional[dict] = None


async def _get_param(request: Request, name: str, log_name: str = "") -> Optional[str]:
    """Получает параметр из body (JSON или form-encoded) или query string.
    В FastAPI нельзя читать body дважды, поэтому читаем один раз и парсим руками."""
    from urllib.parse import parse_qs
    # 1. Query string
    qs_val = request.query_params.get(name)
    if qs_val:
        if log_name: log.info(f"{log_name}: '{name}' from query = {qs_val!r}")
        return qs_val
    # 2. Body (form-encoded или JSON)
    body = await request.body()
    if log_name: log.info(f"{log_name}: body={body!r}, content_type={request.headers.get('content-type')!r}")
    if not body:
        return None
    body_str = body.decode('utf-8', errors='ignore').strip()
    if not body_str:
        return None
    # Сначала пробуем JSON
    try:
        data = json.loads(body_str)
        if isinstance(data, dict) and name in data:
            val = str(data[name])
            if log_name: log.info(f"{log_name}: '{name}' from JSON = {val!r}")
            return val
    except Exception:
        pass
    # Потом form-encoded
    try:
        parsed = parse_qs(body_str)
        if name in parsed and parsed[name]:
            val = parsed[name][0]
            if log_name: log.info(f"{log_name}: '{name}' from form = {val!r}")
            return val
    except Exception:
        pass
    return None


# Routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, q: str = "", page: int = 1, per_page: int = 25, status: str = ""):
    # N+1 fix: один запрос со всеми статусами
    conn = get_conn()
    where_clauses = []
    params = []
    if q:
        where_clauses.append("(designation LIKE ? OR name LIKE ? OR model LIKE ? OR material LIKE ?)")
        like_q = f"%{q}%"
        params.extend([like_q, like_q, like_q, like_q])
    if status:
        where_clauses.append("status = ?")
        params.append(status)
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    # Всего
    count_row = conn.execute(f"SELECT COUNT(*) FROM details {where_sql}", params).fetchone()
    total = count_row[0] if count_row else 0
    # Пагинация
    per_page = max(1, min(100, per_page))
    page = max(1, page)
    total_pages = (total + per_page - 1) // per_page
    offset = (page - 1) * per_page
    # Детали + статус через LEFT JOIN
    rows = conn.execute(f"""
        SELECT d.id, d.designation, d.name, d.model, d.chassis, d.material, d.mass_kg, d.surface_treatment, d.created_at,
               COALESCE(dr.status, 'new') as draft_status
        FROM details d
        LEFT JOIN drafts dr ON d.id = dr.detail_id
        {where_sql}
        ORDER BY d.created_at DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset]).fetchall()
    cols = ["id", "designation", "name", "model", "chassis", "material", "mass_kg", "surface_treatment", "created_at", "status"]
    details = [dict(zip(cols, r)) for r in rows]
    conn.close()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "details": details,
        "demo_mode": DEMO_MODE,
        "llm_model": LLM_MODEL,
        "q": q,
        "status": status,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages
    })


@app.get("/detail/{detail_id}", response_class=HTMLResponse)
async def detail(request: Request, detail_id: str):
    detail_obj = get_detail(detail_id)
    if not detail_obj:
        raise HTTPException(404, "Detail not found")

    draft_data = get_draft(detail_id)
    versions = get_versions(detail_id)
    edits = get_edits(detail_id)
    status_ext = "draft"
    if draft_data:
        conn = get_conn()
        row = conn.execute("SELECT status_ext FROM drafts WHERE detail_id=?", (detail_id,)).fetchone()
        conn.close()
        if row and row[0]:
            status_ext = row[0]

    return templates.TemplateResponse("detail.html", {
        "request": request,
        "detail": detail_obj,
        "draft": draft_data["output"] if draft_data else None,
        "status": draft_data["status"] if draft_data else "new",
        "status_ext": status_ext,
        "versions": versions,
        "edits": edits,
        "demo_mode": DEMO_MODE,
        "llm_model": LLM_MODEL
    })


@app.post("/api/analyze")
async def api_analyze(request: Request):
    """Sprint 1: AI задаёт 3-5 уточняющих вопросов перед генерацией (blueprint.io pattern)"""
    detail_id = await _get_param(request, "detail_id", log_name="/api/analyze")
    if not detail_id:
        return JSONResponse({"error": "detail_id required"}, status_code=422)
    detail_obj = next((d for d in MOCK_DETAILS if d["id"] == detail_id), None)
    if not detail_obj:
        return JSONResponse({"error": "not found"}, status_code=404)

    daily = get_daily_cost()
    if daily["exceeded"]:
        return JSONResponse({"error": "daily_limit_exceeded", "limit": daily["limit_rub"]}, status_code=429)

    if DEMO_MODE:
        return JSONResponse({
            "questions": [
                {"id": "Q1", "topic": "материал", "question": "Какой материал заготовки?", "options": ["лист 09Г2С", "труба Ст20", "поковка 40Х", "другое"], "default": "лист 09Г2С", "impact_if_changed": "изменит режим сварки и нормы"},
                {"id": "Q2", "topic": "толщина", "question": "Толщина металла в мм?", "options": ["3", "5", "8", "10+"], "default": "5", "impact_if_changed": "изменит параметры сварки"},
                {"id": "Q3", "topic": "термообработка", "question": "Требуется ли термообработка после сварки?", "options": ["да, отпуск", "да, закалка+отпуск", "нет"], "default": "да, отпуск", "impact_if_changed": "добавит 1.5ч в маршрут"},
                {"id": "Q4", "topic": "покрытие", "question": "Какое покрытие?", "options": ["порошковая покраска", "жидкая краска", "горячее цинкование", "без покрытия"], "default": "порошковая покраска", "impact_if_changed": "изменит финишные операции"},
                {"id": "Q5", "topic": "приёмка", "question": "Нужна ли военная приёмка?", "options": ["да", "нет"], "default": "нет", "impact_if_changed": "добавит операции ОТК"}
            ],
            "mode": "demo"
        })

    try:
        from openai import OpenAI
        from string import Template
        from prompts import CLARIFICATION_PROMPT
        client = get_llm_client()
        prompt = Template(CLARIFICATION_PROMPT).substitute(
            properties_json=json.dumps(detail_obj, indent=2, ensure_ascii=False),
            material=detail_obj.get("material", ""),
            mass_kg=detail_obj.get("mass_kg", 0),
            surface_treatment=detail_obj.get("surface_treatment", ""),
            chassis=detail_obj.get("chassis", ""),
            model=detail_obj.get("model", "")
        )
        import time
        t0 = time.time()
        system_msg = "Ты — опытный технолог. Задай 3-5 КРАТКИХ уточняющих вопросов перед генерацией техкарты. Возвращай только JSON без markdown."
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500
        )
        duration = int((time.time() - t0) * 1000)
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else text
            if text.startswith("json"):
                text = text[4:].lstrip()
        result = json.loads(text)
        log_llm_call(detail_id, LLM_MODEL, system_msg, prompt, text, True,
                     response.usage.prompt_tokens if response.usage else None,
                     response.usage.completion_tokens if response.usage else None,
                     duration)
        result["mode"] = "live"
        return JSONResponse(result)
    except Exception as e:
        log.error(f"/api/analyze error: {e}")
        return JSONResponse({"error": str(e)[:200]}, status_code=500)


@app.post("/api/draft-fast")
async def api_draft_fast(request: Request):
    """Sprint 1: быстрый дешёвый draft (короткий промт, 3 операции, ~30 сек, ~1₽)"""
    detail_id = await _get_param(request, "detail_id", log_name="/api/draft-fast")
    if not detail_id:
        return JSONResponse({"error": "detail_id required"}, status_code=422)
    detail_obj = next((d for d in MOCK_DETAILS if d["id"] == detail_id), None)
    if not detail_obj:
        return JSONResponse({"error": "not found"}, status_code=404)
    daily = get_daily_cost()
    if daily["exceeded"]:
        return JSONResponse({"error": "daily_limit_exceeded"}, status_code=429)
    if DEMO_MODE:
        return JSONResponse({"draft": {"summary": {"total_operations": 3, "total_hours": 1.5, "complexity": "средняя", "closest_analog": "4c85941a (упор продольный)"},
                              "route": [{"step": 1, "operation": "010 Подготовительная", "duration_hours": 0.2},
                                       {"step": 2, "operation": "015 Сварка", "duration_hours": 0.7},
                                       {"step": 3, "operation": "020 Контроль", "duration_hours": 0.6}],
                              "operations": [], "warnings": [], "questions": []},
                         "mode": "demo", "cost_estimate": "1.00₽"})
    try:
        from openai import OpenAI
        from string import Template
        from prompts import DRAFT_FAST_PROMPT
        client = get_llm_client()
        answers = await _get_param(request, "answers") or "{}"
        try:
            answers_dict = json.loads(answers) if answers else {}
        except Exception:
            answers_dict = {}
        prompt = Template(DRAFT_FAST_PROMPT).substitute(
            properties_json=json.dumps(detail_obj, indent=2, ensure_ascii=False),
            answers_json=json.dumps(answers_dict, indent=2, ensure_ascii=False)
        )
        import time
        t0 = time.time()
        system_msg = "Сгенерируй КРАТКИЙ draft маршрута (3 операции) для этой детали. Только JSON без markdown."
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500
        )
        duration = int((time.time() - t0) * 1000)
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else text
            if text.startswith("json"):
                text = text[4:].lstrip()
        result = json.loads(text)
        log_llm_call(detail_id, LLM_MODEL, system_msg, prompt, text, True,
                     response.usage.prompt_tokens if response.usage else None,
                     response.usage.completion_tokens if response.usage else None,
                     duration)
        result["mode"] = "live"
        tokens_in = response.usage.prompt_tokens if response.usage else 0
        tokens_out = response.usage.completion_tokens if response.usage else 0
        cost = (tokens_in/1000)*LLM_PRICE_INPUT_RUB_PER_1K + (tokens_out/1000)*LLM_PRICE_OUTPUT_RUB_PER_1K
        result["cost_estimate"] = f"{cost:.2f}₽"
        return JSONResponse({"draft": result, "mode": "live", "cost_estimate": f"{cost:.2f}₽"})
    except Exception as e:
        log.error(f"/api/draft-fast error: {e}")
        return JSONResponse({"error": str(e)[:200]}, status_code=500)


@app.post("/api/refine")
async def api_refine(request: Request):
    """Sprint 1: уточнение draft'а до полного маршрута (с учётом ответов на уточнения)"""
    detail_id = await _get_param(request, "detail_id", log_name="/api/refine")
    if not detail_id:
        return JSONResponse({"error": "detail_id required"}, status_code=422)
    detail_obj = next((d for d in MOCK_DETAILS if d["id"] == detail_id), None)
    if not detail_obj:
        return JSONResponse({"error": "not found"}, status_code=404)
    daily = get_daily_cost()
    if daily["exceeded"]:
        return JSONResponse({"error": "daily_limit_exceeded"}, status_code=429)
    draft_json = await _get_param(request, "draft")
    answers = await _get_param(request, "answers")
    if draft_json:
        try:
            draft_dict = json.loads(draft_json)
        except Exception:
            draft_dict = {}
    else:
        draft_dict = {}
    try:
        answers_dict = json.loads(answers) if answers else {}
    except Exception:
        answers_dict = {}
    if DEMO_MODE:
        llm_output = generate_mock_draft(detail_obj)
        add_history(detail_id, "refined_mock", {"from": "draft"})
    else:
        try:
            from openai import OpenAI
            from string import Template
            from prompts import REFINE_PROMPT
            client = get_llm_client()
            tech_rules_text = detail_obj.get("tech_rules") or ""
            rules_block = f"\nВАЖНО: Технолог указал следующие правила и нюансы — ОБЯЗАТЕЛЬНО учти их:\n{tech_rules_text}\n" if tech_rules_text.strip() else ""
            # Sprint 2: добавляем top-K похожих техкарт из RAG
            similar_block = "(похожих техкарт пока нет)"
            try:
                from rag import rag_search
                similar = rag_search(detail_obj, top_k=3)
                if similar:
                    lines = []
                    for s in similar:
                        meta = s.get("metadata", {})
                        lines.append(f"- {meta.get('designation', '?')} '{meta.get('name', '?')}' "
                                     f"({meta.get('material', '?')}, score={s['score']})")
                    similar_block = "\n".join(lines)
            except Exception as e:
                log.warning(f"RAG search failed in /api/refine: {e}")
            prompt = Template(REFINE_PROMPT).substitute(
                properties_json=json.dumps(detail_obj, indent=2, ensure_ascii=False),
                equipment_json=json.dumps(EQUIPMENT, indent=2, ensure_ascii=False),
                structure_json=json.dumps(STRUCTURE, indent=2, ensure_ascii=False),
                few_shot_json=json.dumps(FEW_SHOT_4C85941A, indent=2, ensure_ascii=False),
                tech_rules="(правила не указаны)",
                rules_block=rules_block,
                draft_json=json.dumps(draft_dict, indent=2, ensure_ascii=False),
                answers_json=json.dumps(answers_dict, indent=2, ensure_ascii=False),
                similar_block=similar_block
            )
            import time
            t_start = time.time()
            system_msg = "Ты — опытный технолог-сварщик. Доработай draft маршрута до полной техкарты. Всегда возвращай валидный JSON без markdown-обёртки."
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=8000
            )
            duration_ms = int((time.time() - t_start) * 1000)
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else text
                if text.startswith("json"):
                    text = text[4:].lstrip()
            log_llm_call(detail_id, LLM_MODEL, system_msg, prompt, text, False,
                         response.usage.prompt_tokens if response.usage else None,
                         response.usage.completion_tokens if response.usage else None,
                         duration_ms)
            try:
                llm_output = json.loads(text)
                conn = get_conn()
                last_id = conn.execute("SELECT MAX(id) FROM llm_calls").fetchone()[0]
                if last_id:
                    conn.execute("UPDATE llm_calls SET response_parsed_ok=1 WHERE id=?", (last_id,))
                    conn.commit()
                conn.close()
            except json.JSONDecodeError as je:
                log_llm_call(detail_id, LLM_MODEL, system_msg, prompt, text, False, duration_ms=duration_ms, error=f"JSON parse: {je}")
                return JSONResponse({"error": "JSON parse"}, status_code=500)
            add_history(detail_id, "refined", {"model": LLM_MODEL,
                                              "tokens_in": response.usage.prompt_tokens if response.usage else None,
                                              "tokens_out": response.usage.completion_tokens if response.usage else None})
        except Exception as e:
            log.error(f"/api/refine LLM error: {e}")
            return JSONResponse({"error": str(e)[:200]}, status_code=500)
    save_draft(detail_id, llm_output, "draft")
    total_ops = len(llm_output.get("operations", []))
    record_metric(detail_id, "total_ops", total_ops, {"source": "refine"})
    tokens_in = response.usage.prompt_tokens if 'response' in dir() and response.usage else 0
    tokens_out = response.usage.completion_tokens if 'response' in dir() and response.usage else 0
    cost = (tokens_in/1000)*LLM_PRICE_INPUT_RUB_PER_1K + (tokens_out/1000)*LLM_PRICE_OUTPUT_RUB_PER_1K
    return JSONResponse({"ok": True, "total_ops": total_ops, "cost": f"{cost:.2f}₽"})


@app.post("/api/feedback")
async def api_feedback(request: Request):
    """Sprint 3 placeholder: кнопка 'Пожаловаться' на AI-результат"""
    detail_id = await _get_param(request, "detail_id", log_name="/api/feedback")
    reason = await _get_param(request, "reason") or ""
    if not detail_id or not reason:
        return JSONResponse({"error": "detail_id and reason required"}, status_code=422)
    add_history(detail_id, "ai_feedback", {"reason": reason[:500]})
    return {"ok": True}


@app.post("/api/generate")
async def generate(request: Request):
    """Generate draft via LLM (or mock in demo mode). Accepts form-data, JSON, or URL param."""
    detail_id = await _get_param(request, "detail_id", log_name="/api/generate")
    if not detail_id:
        return HTMLResponse(
            '<span style="color:red">❌ Не указан detail_id</span>',
            status_code=422
        )
    detail_obj = next((d for d in MOCK_DETAILS if d["id"] == detail_id), None)
    if not detail_obj:
        return HTMLResponse(
            f'<span style="color:red">❌ Деталь {detail_id} не найдена</span>',
            status_code=404
        )

    # Проверка дневного лимита
    daily = get_daily_cost()
    if daily["exceeded"]:
        return HTMLResponse(
            f'<span style="color:red">⛔ Превышен дневной лимит {daily["limit_rub"]:.0f}₽ (потрачено {daily["total_rub"]:.2f}₽). Измени LLM_DAILY_LIMIT_RUB в .env.</span>',
            status_code=429
        )

    # DEMO MODE: return mock response based on detail
    if DEMO_MODE:
        log.info(f"Demo mode: generating mock draft for {detail_id}")
        llm_output = generate_mock_draft(detail_obj)
        add_history(detail_id, "generated_mock", {"mode": "demo"})
        # M5 fix: log mock generation in llm_calls for dashboard
        log_llm_call(detail_id, "demo-mock", "", "", json.dumps(llm_output, ensure_ascii=False), True, 0, 0, 50)
    else:
        # Real LLM call via OpenAI-compatible API
        try:
            client = get_llm_client()

            from string import Template
            tech_rules_text = detail_obj.get("tech_rules") or ""
            rules_block = f"\nВАЖНО: Технолог указал следующие правила и нюансы — ОБЯЗАТЕЛЬНО учти их:\n{tech_rules_text}\n" if tech_rules_text.strip() else ""
            prompt = Template(TECH_CARD_PROMPT).substitute(
                properties_json=json.dumps(detail_obj, indent=2, ensure_ascii=False),
                equipment_json=json.dumps(EQUIPMENT, indent=2, ensure_ascii=False),
                structure_json=json.dumps(STRUCTURE, indent=2, ensure_ascii=False),
                few_shot_json=json.dumps(FEW_SHOT_4C85941A, indent=2, ensure_ascii=False),
                tech_rules="(правила не указаны)",
                rules_block=rules_block
            )

            log.info(f"Calling {LLM_MODEL} via {LLM_API_URL}...")
            import time
            t_start = time.time()
            system_msg = "Ты — опытный технолог-сварщик. Генерируешь техкарты по свойствам деталей. Всегда возвращаешь валидный JSON без markdown-обёртки."
            try:
                response = client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=8000
                )
            except Exception as llm_exc:
                duration = int((time.time() - t_start) * 1000)
                log_llm_call(detail_id, LLM_MODEL, system_msg, prompt,
                             response_text=None, response_parsed_ok=False,
                             duration_ms=duration, error=str(llm_exc))
                raise
            duration_ms = int((time.time() - t_start) * 1000)
            llm_output_text = response.choices[0].message.content
            log_llm_call(detail_id, LLM_MODEL, system_msg, prompt,
                         response_text=llm_output_text, response_parsed_ok=False,
                         tokens_in=response.usage.prompt_tokens if response.usage else None,
                         tokens_out=response.usage.completion_tokens if response.usage else None,
                         duration_ms=duration_ms)
            # Strip markdown code fences if any
            llm_output_text = llm_output_text.strip()
            if llm_output_text.startswith("```"):
                lines = llm_output_text.split("\n")
                llm_output_text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else llm_output_text
                if llm_output_text.startswith("json"):
                    llm_output_text = llm_output_text[4:].lstrip()
            try:
                llm_output = json.loads(llm_output_text)
                # Обновляем запись: parsed_ok=True (используем lastrowid из лога)
                conn = get_conn()
                last_id = conn.execute("SELECT MAX(id) FROM llm_calls").fetchone()[0]
                if last_id:
                    conn.execute("UPDATE llm_calls SET response_parsed_ok=1 WHERE id=?", (last_id,))
                    conn.commit()
                conn.close()
            except json.JSONDecodeError as je:
                log_llm_call(detail_id, LLM_MODEL, system_msg, prompt,
                             response_text=llm_output_text, response_parsed_ok=False,
                             duration_ms=duration_ms, error=f"JSON parse: {je}")
                return HTMLResponse(
                    f'<span style="color:red">❌ LLM вернул невалидный JSON. <a href="/llm-debug" target="_blank">Открыть отладку</a></span>',
                    status_code=500
                )
            add_history(detail_id, "generated", {
                "model": LLM_MODEL,
                "tokens_in": response.usage.prompt_tokens if response.usage else None,
                "tokens_out": response.usage.completion_tokens if response.usage else None
            })
        except Exception as e:
            log.error(f"LLM error: {e}")
            error_msg = str(e).replace("<", "&lt;").replace(">", "&gt;")[:200]
            return HTMLResponse(
                f'<span style="color:red">❌ Ошибка LLM: {error_msg} <a href="/llm-debug" target="_blank">лог</a></span>',
                status_code=500
            )

    save_draft(detail_id, llm_output, "draft")
    # Пилотная метрика: всего операций в черновике
    total_ops = len(llm_output.get("operations", []))
    record_metric(detail_id, "total_ops", total_ops, {"source": "llm"})
    return HTMLResponse('<span style="color:green">✅ Готово! Перезагружаю...</span>')


def generate_mock_draft(detail_obj: dict) -> dict:
    """Generate a mock draft based on the detail properties"""
    material = detail_obj.get("material", "")
    model = detail_obj.get("model", "")
    mass = detail_obj.get("mass_kg", 0)
    surface = detail_obj.get("surface_treatment", "")

    # Heuristic: welding operations for steel details
    is_steel = material and "Сталь" in material
    is_shtamp = "оцинковка" in surface

    operations = []
    route = []
    step = 0

    if is_steel and not is_shtamp:
        # Steel with painting - has welding operations
        step += 1
        operations.append({
            "name": "010 Подготовительная",
            "equipment": None,
            "duration_hours": 0.2,
            "duration_source": "экспертная оценка",
            "confidence": 70,
            "materials": ["проволока Св-08Г2С-О 1,0 ГОСТ 2246-70"],
            "control_points": [],
            "gosts": [],
            "department": "Сварочно-сборочный КТ",
            "workplace": "01/01/04"
        })
        route.append({"step": step, "operation": "010 Подготовительная", "duration_hours": 0.2})

        # Welding operations
        welding_ops = [
            ("015 Сборка под сварку", 0.5, 90, "аналог: ЛМША.301314.020"),
            ("020 Сварка", 0.6, 92, "аналог: ЛМША.301314.020"),
            ("025 Сборка", 0.7, 85, "аналог: ЛМША.301314.020"),
            ("030 Сварка", 0.6, 85, "аналог: ЛМША.301314.020"),
        ]

        for name, dur, conf, src in welding_ops:
            step += 1
            operations.append({
                "name": name,
                "equipment": "Кедр-300",
                "duration_hours": dur,
                "duration_source": src,
                "confidence": conf,
                "materials": [],
                "control_points": ["ОТК визуальный"],
                "gosts": ["ГОСТ 3.1404-86"],
                "department": "Сварочно-сборочный КТ",
                "workplace": "01/01/04"
            })
            route.append({"step": step, "operation": name, "duration_hours": dur})

        # Painting
        step += 1
        operations.append({
            "name": "035 Покраска",
            "equipment": "Камера покрасочная",
            "duration_hours": 0.8,
            "duration_source": "экспертная оценка",
            "confidence": 75,
            "materials": ["грунт ГФ-021", "эмаль ПФ-115"],
            "control_points": ["ОТК визуальный", "контроль толщины покрытия"],
            "gosts": ["ГОСТ 9.402", "ГОСТ 9.410"],
            "department": "Покраска",
            "workplace": "01/07/01"
        })
        route.append({"step": step, "operation": "035 Покраска", "duration_hours": 0.8})

    elif is_shtamp:
        # Galvanized - no welding, simpler
        operations.append({
            "name": "010 Раскрой",
            "equipment": "Плазменный рез HyperTherm",
            "duration_hours": 0.1,
            "duration_source": "экспертная оценка",
            "confidence": 80,
            "materials": [],
            "control_points": ["ОТК визуальный"],
            "gosts": ["ГОСТ 9.402"],
            "department": "Лазерная резка",
            "workplace": "01/01/01"
        })
        route.append({"step": 1, "operation": "010 Раскрой", "duration_hours": 0.1})

        operations.append({
            "name": "015 Гибка",
            "equipment": "Гибочный станок",
            "duration_hours": 0.15,
            "duration_source": "экспертная оценка",
            "confidence": 75,
            "materials": [],
            "control_points": ["ОТК визуальный"],
            "gosts": [],
            "department": "Гибка",
            "workplace": "01/01/03"
        })
        route.append({"step": 2, "operation": "015 Гибка", "duration_hours": 0.15})

    # Summary
    total_hours = sum(op["duration_hours"] for op in operations)

    # Reasoning
    reasoning = {
        "operations_choice": f"Операции выбраны на основе типа материала ({material}) и характера детали ({detail_obj.get('name', '')}). Аналог: ЛМША.301314.020 (упор продольный).",
        "duration_estimates": f"Расчёт по аналогам из ведомости трудоёмкости Техинкома. Масса детали {mass} кг.",
        "equipment_choice": f"Кедр-300 — основной сварочный аппарат (если применимо). Плазменный HyperTherm — для раскроя листа.",
        "risks": "Точность операций 015-035 — 80-92% (по аналогу). Требуется проверка технолога."
    }

    # Warnings
    warnings = []
    if surface == "покраска":
        warnings.append({
            "type": "ambiguous",
            "quote": "surface_treatment: 'покраска'",
            "concern": "Не указан тип краски (порошковая/жидкая) и грунтовка",
            "question": "Какой тип краски? Требуется ли грунтовка перед покраской?"
        })
    if "Сталь 3" in material:
        warnings.append({
            "type": "ambiguous",
            "quote": f"material: '{material}'",
            "concern": "Сталь 3 — устаревшее обозначение. Возможно, Ст3сп, Ст3пс, Ст3кп?",
            "question": "Какая марка стали точно?"
        })

    # Questions
    questions = []
    if surface == "покраска":
        questions.append({
            "id": "Q1",
            "topic": "покраска",
            "question": "Тип покраски?",
            "options": ["порошковая", "жидкая (эмаль ПФ-115)", "жидкая (грунт + эмаль)", "не знаю"],
            "default": "жидкая (грунт + эмаль)",
            "impact_if_changed": "Порошковая быстрее, но дороже оборудование"
        })
    questions.append({
        "id": "Q2",
        "topic": "термообработка",
        "question": f"Требуется ли термообработка для {material}?",
        "options": ["да, закалка+отпуск", "да, только отпуск", "нет, не требуется", "не знаю"],
        "default": "нет, не требуется",
        "impact_if_changed": "Термообработка добавит 1.5-3 ч"
    })

    return {
        "summary": {
            "total_operations": len(operations),
            "total_hours": round(total_hours, 2),
            "prep_hours": 0.2,
            "complexity": "средняя" if mass > 5 else "низкая",
            "closest_analog": "ЛМША.301314.020" if is_steel else None
        },
        "route": route,
        "operations": operations,
        "reasoning": reasoning,
        "warnings": warnings,
        "questions": questions
    }


@app.post("/api/approve")
async def approve(request: Request):
    """Approve draft + Sprint 2: auto-index in RAG"""
    detail_id = await _get_param(request, "detail_id")
    if not detail_id:
        return JSONResponse({"error": "detail_id required"}, status_code=422)
    conn = get_conn()
    conn.execute(
        "UPDATE drafts SET status = 'approved', updated_at = ? WHERE detail_id = ?",
        (datetime.now().isoformat(), detail_id)
    )
    conn.commit()
    conn.close()
    add_history(detail_id, "approved")
    edits = get_edits(detail_id)
    record_metric(detail_id, "approved", 1, {"edits_count": len(edits)})
    record_metric(detail_id, "edits_count", len(edits))
    # Sprint 2: автоиндексация в RAG
    try:
        from rag import rag_index_detail
        rag_index_detail(detail_id)
    except Exception as e:
        log.warning(f"RAG auto-index failed: {e}")
    return {"status": "approved"}


@app.post("/api/rag/rebuild")
async def api_rag_rebuild():
    """Sprint 2: перестроить RAG-индекс из БД (admin action)"""
    try:
        from rag import get_rag
        rag = get_rag()
        n = rag.rebuild_from_db()
        warning = None
        if n == 0:
            warning = "Нет утверждённых техкарт. Сначала утвердите несколько черновиков."
        elif n < 5:
            warning = f"Только {n} техкарт — similarity может быть ненадёжной. Нужно минимум 5-10."
        return JSONResponse({"ok": True, "indexed": n, "warning": warning})
    except Exception as e:
        return JSONResponse({"error": str(e)[:200]}, status_code=500)


@app.get("/api/rag/similar/{detail_id}")
async def api_rag_similar(detail_id: str, top_k: int = 3):
    """Sprint 2: top-K похожих техкарт по RAG"""
    detail_obj = next((d for d in MOCK_DETAILS if d["id"] == detail_id), None)
    if not detail_obj:
        return JSONResponse({"error": "not_found"}, status_code=404)
    try:
        from rag import rag_search
        results = rag_search(detail_obj, top_k=min(top_k, 10))
        return JSONResponse({"detail_id": detail_id, "similar": results})
    except Exception as e:
        return JSONResponse({"error": str(e)[:200]}, status_code=500)


@app.get("/api/rag/status")
async def api_rag_status():
    try:
        from rag import get_rag
        rag = get_rag()
        return JSONResponse({
            "loaded": rag.loaded,
            "documents": len(rag.ids) if rag.loaded else 0,
            "vocabulary_size": len(rag.vectorizer.vocabulary_) if rag.loaded and rag.vectorizer else 0
        })
    except Exception as e:
        return JSONResponse({"error": str(e)[:200]}, status_code=500)


# ========== Sprint 3: Альтернативные маршруты + Apply similar + Batch ==========
@app.post("/api/alternatives")
async def api_alternatives(request: Request):
    detail_id = await _get_param(request, "detail_id", log_name="/api/alternatives")
    if not detail_id:
        return JSONResponse({"error": "detail_id required"}, status_code=422)
    detail_obj = next((d for d in MOCK_DETAILS if d["id"] == detail_id), None)
    if not detail_obj:
        return JSONResponse({"error": "not found"}, status_code=404)
    daily = get_daily_cost()
    if daily["exceeded"]:
        return JSONResponse({"error": "daily_limit_exceeded"}, status_code=429)
    if DEMO_MODE:
        alts = [
            {"variant": "A", "approach": "Сварка Кедр-300 + отпуск", "total_hours": 2.5, "n_ops": 5,
             "route": [{"step": 1, "operation": "010 Подготовительная", "duration_hours": 0.2},
                       {"step": 2, "operation": "015 Сварка", "duration_hours": 1.0},
                       {"step": 3, "operation": "020 Контроль ОТК", "duration_hours": 0.3},
                       {"step": 4, "operation": "025 Отпуск", "duration_hours": 0.5},
                       {"step": 5, "operation": "030 Финальный контроль", "duration_hours": 0.5}]},
            {"variant": "B", "approach": "TIG-сварка (аргон)", "total_hours": 3.5, "n_ops": 4,
             "route": [{"step": 1, "operation": "010 Зачистка", "duration_hours": 0.3},
                       {"step": 2, "operation": "015 TIG-сварка", "duration_hours": 1.5},
                       {"step": 3, "operation": "020 Контроль", "duration_hours": 0.7},
                       {"step": 4, "operation": "025 ТО", "duration_hours": 1.0}]},
            {"variant": "C", "approach": "Минимум операций (без ТО)", "total_hours": 1.8, "n_ops": 3,
             "route": [{"step": 1, "operation": "010 Сборка", "duration_hours": 0.5},
                       {"step": 2, "operation": "015 Сварка", "duration_hours": 0.8},
                       {"step": 3, "operation": "020 Контроль", "duration_hours": 0.5}]}
        ]
        return JSONResponse({"alternatives": alts, "mode": "demo", "cost": "1.50₽"})
    return JSONResponse({"alternatives": [], "mode": "live-stub", "message": "real LLM for alternatives — в v0.5"})


@app.post("/api/apply-similar")
async def api_apply_similar(request: Request):
    detail_id = await _get_param(request, "detail_id", log_name="/api/apply-similar")
    source_id = await _get_param(request, "source_id")
    if not detail_id or not source_id:
        return JSONResponse({"error": "detail_id and source_id required"}, status_code=422)
    if detail_id == source_id:
        return JSONResponse({"error": "cannot apply to self"}, status_code=400)
    conn = get_conn()
    source_draft = conn.execute("SELECT * FROM drafts WHERE detail_id=?", (source_id,)).fetchone()
    if not source_draft:
        conn.close()
        return JSONResponse({"error": "source has no draft"}, status_code=404)
    try:
        source_output = json.loads(source_draft[1])
    except Exception:
        conn.close()
        return JSONResponse({"error": "source draft corrupt"}, status_code=500)
    target_draft = conn.execute("SELECT * FROM drafts WHERE detail_id=?", (detail_id,)).fetchone()
    if target_draft:
        try:
            target_output = json.loads(target_draft[1])
            target_output["operations"] = source_output.get("operations", [])
            target_output["route"] = source_output.get("route", [])
            target_output["reasoning"] = {
                "operations_choice": f"Скопировано из {source_id} (1-click apply similar)",
                "duration_estimates": "Скопировано",
                "equipment_choice": "Скопировано",
                "risks": "Требует верификации технологом"
            }
            target_output["applied_from"] = source_id
            conn.execute("UPDATE drafts SET llm_output=?, updated_at=? WHERE detail_id=?",
                         (json.dumps(target_output, ensure_ascii=False), datetime.now().isoformat(), detail_id))
        except Exception as e:
            conn.close()
            return JSONResponse({"error": f"failed to update: {e}"}, status_code=500)
    else:
        new_output = source_output.copy()
        new_output["applied_from"] = source_id
        conn.execute("INSERT INTO drafts (detail_id, llm_output, status, author) VALUES (?, ?, 'draft', 'rag-apply')",
                     (detail_id, json.dumps(new_output, ensure_ascii=False)))
    conn.commit()
    conn.close()
    add_history(detail_id, "applied_similar", {"source_id": source_id})
    return JSONResponse({"ok": True, "applied_from": source_id})


@app.post("/api/batch-generate")
async def api_batch_generate(request: Request):
    detail_ids_raw = await _get_param(request, "detail_ids", log_name="/api/batch-generate")
    if not detail_ids_raw:
        return JSONResponse({"error": "detail_ids required (JSON array)"}, status_code=422)
    try:
        detail_ids = json.loads(detail_ids_raw)
    except Exception:
        return JSONResponse({"error": "detail_ids must be JSON array"}, status_code=422)
    if not isinstance(detail_ids, list) or len(detail_ids) == 0:
        return JSONResponse({"error": "detail_ids must be non-empty array"}, status_code=422)
    if len(detail_ids) > 20:
        return JSONResponse({"error": "max 20 details per batch"}, status_code=400)
    results = []
    for did in detail_ids:
        did = str(did).strip()
        if not did:
            continue
        detail_obj = next((d for d in MOCK_DETAILS if d["id"] == did), None)
        if not detail_obj:
            results.append({"detail_id": did, "status": "not_found"})
            continue
        daily = get_daily_cost()
        if daily["exceeded"]:
            results.append({"detail_id": did, "status": "daily_limit_exceeded"})
            continue
        if DEMO_MODE:
            llm_output = generate_mock_draft(detail_obj)
        else:
            try:
                from openai import OpenAI
                from string import Template
                client = get_llm_client()
                prompt = Template(TECH_CARD_PROMPT).substitute(
                    properties_json=json.dumps(detail_obj, indent=2, ensure_ascii=False),
                    equipment_json=json.dumps(EQUIPMENT, indent=2, ensure_ascii=False),
                    structure_json=json.dumps(STRUCTURE, indent=2, ensure_ascii=False),
                    few_shot_json=json.dumps(FEW_SHOT_4C85941A, indent=2, ensure_ascii=False),
                    tech_rules="(правила не указаны)",
                    rules_block=""
                )
                response = client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[{"role": "system", "content": "Ты — технолог. Генерируй JSON."}, {"role": "user", "content": prompt}],
                    temperature=0.2, max_tokens=8000
                )
                text = response.choices[0].message.content.strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else text
                    if text.startswith("json"):
                        text = text[4:].lstrip()
                llm_output = json.loads(text)
            except Exception as e:
                results.append({"detail_id": did, "status": "llm_error", "error": str(e)[:100]})
                continue
        save_draft(did, llm_output, "draft", author="batch")
        # M5 fix: log batch generation
        log_llm_call(did, "demo-batch" if DEMO_MODE else LLM_MODEL, "", "",
                     json.dumps(llm_output, ensure_ascii=False), True, 0, 0, 80)
        results.append({"detail_id": did, "status": "generated", "ops": len(llm_output.get("operations", []))})
    return JSONResponse({"ok": True, "processed": len(results), "results": results})


# ========== Sprint 5: Audit log + Export ==========
@app.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request, limit: int = 100):
    conn = get_conn()
    cols = [d[1] for d in conn.execute("PRAGMA table_info(history)").fetchall()]
    rows = conn.execute("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    entries = [dict(zip(cols, r)) for r in rows]
    return templates.TemplateResponse("audit.html", {
        "request": request, "entries": entries, "limit": limit
    })


@app.get("/api/audit/export")
async def api_audit_export():
    conn = get_conn()
    cols = [d[1] for d in conn.execute("PRAGMA table_info(history)").fetchall()]
    rows = conn.execute("SELECT * FROM history ORDER BY id").fetchall()
    conn.close()
    entries = [dict(zip(cols, r)) for r in rows]
    return JSONResponse({
        "exported_at": datetime.now().isoformat(),
        "total_entries": len(entries),
        "entries": entries
    })


@app.get("/api/export/all")
async def api_export_all():
    conn = get_conn()
    tables = ["details", "drafts", "draft_versions", "edits", "rules", "equipment",
              "materials", "iot", "benchmarks", "history", "llm_calls", "pilot_metrics"]
    dump = {"exported_at": datetime.now().isoformat(), "version": "v0.4", "tables": {}}
    for t in tables:
        try:
            cols = [d[1] for d in conn.execute(f"PRAGMA table_info({t})").fetchall()]
            rows = conn.execute(f"SELECT * FROM {t}").fetchall()
            dump["tables"][t] = {"columns": cols, "rows": [dict(zip(cols, r)) for r in rows]}
        except Exception as e:
            dump["tables"][t] = {"error": str(e)}
    conn.close()
    return JSONResponse(dump)


# ========== Печатная форма ТК (P0: для подписи в бумажный журнал) ==========
@app.get("/detail/{detail_id}/print", response_class=HTMLResponse)
async def detail_print(request: Request, detail_id: str):
    """Печатная форма ТК — без кнопок, только данные + место для подписи"""
    detail_obj = get_detail(detail_id)
    if not detail_obj:
        raise HTTPException(404, "Detail not found")
    draft_data = get_draft(detail_id)
    return templates.TemplateResponse("print.html", {
        "request": request,
        "detail": detail_obj,
        "draft": draft_data["output"] if draft_data else None,
        "status": draft_data["status"] if draft_data else "new"
    })


# ========== U6 fix: click-to-edit (inline edit) ==========
@app.post("/api/edit/inline")
async def api_edit_inline(request: Request):
    """Inline-edit одной операции: один POST меняет одно поле одной операции"""
    detail_id = await _get_param(request, "detail_id", log_name="/api/edit/inline")
    op_index = await _get_param(request, "op_index")
    field = await _get_param(request, "field")
    value = await _get_param(request, "value")
    if not all([detail_id, op_index, field]):
        return JSONResponse({"error": "detail_id, op_index, field required"}, status_code=422)
    # Whitelist полей для inline-edit
    if field not in ("name", "equipment", "duration_hours", "department", "workplace"):
        return JSONResponse({"error": f"field '{field}' not editable inline"}, status_code=400)
    try:
        op_idx = int(op_index)
    except ValueError:
        return JSONResponse({"error": "op_index must be int"}, status_code=422)
    conn = get_conn()
    row = conn.execute("SELECT llm_output FROM drafts WHERE detail_id=?", (detail_id,)).fetchone()
    if not row:
        conn.close()
        return JSONResponse({"error": "no draft"}, status_code=404)
    try:
        output = json.loads(row[0])
    except Exception:
        conn.close()
        return JSONResponse({"error": "draft corrupt"}, status_code=500)
    if op_idx < 0 or op_idx >= len(output.get("operations", [])):
        conn.close()
        return JSONResponse({"error": "op_index out of range"}, status_code=400)
    op = output["operations"][op_idx]
    # cast
    if field == "duration_hours":
        try:
            value = float(value)
        except (TypeError, ValueError):
            conn.close()
            return JSONResponse({"error": "duration_hours must be float"}, status_code=422)
    old_value = op.get(field)
    op[field] = value
    # Пересчёт summary
    if field == "duration_hours" and "operations" in output:
        total = sum(float(o.get("duration_hours", 0)) for o in output["operations"])
        output["summary"]["total_hours"] = round(total, 2)
    # Update
    conn.execute("UPDATE drafts SET llm_output=?, updated_at=? WHERE detail_id=?",
                 (json.dumps(output, ensure_ascii=False), datetime.now().isoformat(), detail_id))
    conn.commit()  # C5 fix: release write lock before record_edit opens new conn
    # version берём из draft_versions
    v_row = conn.execute("SELECT MAX(version) FROM draft_versions WHERE detail_id=?", (detail_id,)).fetchone()
    version = v_row[0] if v_row and v_row[0] else 1
    conn.close()
    record_edit(detail_id, version, field, str(old_value), str(value), author="inline")
    add_history(detail_id, "inline_edit", {"op_index": op_idx, "field": field, "old": str(old_value), "new": str(value)})
    return JSONResponse({"ok": True, "field": field, "value": value, "total_hours": output.get("summary", {}).get("total_hours")})


# ========== U7 fix: warning с action — указывает куда кликать ==========
@app.post("/api/ai/feedback-positive")
async def api_feedback_positive(request: Request):
    """Положительный feedback (большой палец вверх) — для ML будущего"""
    detail_id = await _get_param(request, "detail_id", log_name="/api/ai/feedback-positive")
    if not detail_id:
        return JSONResponse({"error": "detail_id required"}, status_code=422)
    add_history(detail_id, "ai_feedback_positive", {})
    return JSONResponse({"ok": True, "saved": "positive"})


# ========== B2: Ручная выгрузка техкарт в 1С-формате (Sprint 5) ==========
@app.get("/api/export/onec-csv")
async def api_export_onec_csv(detail_id: str):
    """Экспорт в CSV формате, понятном 1С:ERP (для ручного импорта на пилоте)"""
    detail_obj = get_detail(detail_id)
    if not detail_obj:
        return JSONResponse({"error": "not found"}, status_code=404)
    draft_data = get_draft(detail_id)
    if not draft_data:
        return JSONResponse({"error": "no draft"}, status_code=404)
    output = draft_data["output"]
    ops = output.get("operations", [])
    # CSV с BOM для Excel/1С кириллицы
    lines = ["\ufeffНомер;Операция;Оборудование;Время_ч;Цех;Участок;РМ;Уверенность;Материалы;ГОСТы"]
    for i, op in enumerate(ops, 1):
        lines.append(";".join([
            f"{i:03d}",
            (op.get("name") or "").replace(";", ","),
            (op.get("equipment") or "").replace(";", ","),
            str(op.get("duration_hours", 0)),
            (op.get("department") or "").replace(";", ","),
            (op.get("workplace") or "").replace(";", ","),
            str(op.get("workstation") or ""),
            str(op.get("confidence", 0)),
            "; ".join(op.get("materials", [])).replace(";", ","),
            "; ".join(op.get("gosts", [])).replace(";", ",")
        ]))
    csv_text = "\n".join(lines)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="techcard_{detail_id}.csv"'}
    )


@app.post("/api/send-to-1c")
async def send_to_1c(request: Request):
    """MOCK: write RS to 1C:ERP"""
    detail_id = await _get_param(request, "detail_id")
    if not detail_id:
        return JSONResponse({"error": "detail_id required"}, status_code=422)
    add_history(detail_id, "sent_to_1c_mock", {
        "message": "РС записана в 1С:ERP (mock)",
        "timestamp": datetime.now().isoformat()
    })
    return {"status": "sent", "message": "РС записана в 1С:ERP (mock)"}


@app.post("/api/export/excel")
async def export_excel(detail_id: str = Form(...)):
    """Export to Excel"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    detail_obj = next((d for d in MOCK_DETAILS if d["id"] == detail_id), None)
    draft_data = get_draft(detail_id)
    if not detail_obj or not draft_data:
        raise HTTPException(400, "No draft to export")

    draft = draft_data["output"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Техкарта"

    # Header
    ws["A1"] = f"Техкарта: {detail_obj['designation']} — {detail_obj['name']}"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:F1")
    ws["A1"].alignment = Alignment(horizontal="center")

    # Properties
    ws["A3"] = "Материал"
    ws["B3"] = detail_obj.get("material", "")
    ws["A4"] = "Масса, кг"
    ws["B4"] = detail_obj.get("mass_kg", "")
    ws["A5"] = "Шасси"
    ws["B5"] = detail_obj.get("chassis", "")
    ws["A6"] = "Модель"
    ws["B6"] = detail_obj.get("model", "")
    for r in range(3, 7):
        ws[f"A{r}"].font = Font(bold=True)

    # Operations table
    ws["A8"] = "№"
    ws["B8"] = "Операция"
    ws["C8"] = "Оборудование"
    ws["D8"] = "Время, ч"
    ws["E8"] = "Источник"
    ws["F8"] = "Уверенность"
    for col in "ABCDEF":
        cell = ws[f"{col}8"]
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")

    for i, op in enumerate(draft.get("operations", []), 1):
        row = 8 + i
        ws.cell(row=row, column=1, value=i)
        ws.cell(row=row, column=2, value=op.get("name", ""))
        ws.cell(row=row, column=3, value=op.get("equipment", "") or "—")
        ws.cell(row=row, column=4, value=op.get("duration_hours", 0))
        ws.cell(row=row, column=5, value=op.get("duration_source", ""))
        ws.cell(row=row, column=6, value=f"{op.get('confidence', 0)}%")

    # Adjust column widths
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 25
    ws.column_dimensions["D"].width = 12
    ws.column_dimensions["E"].width = 25
    ws.column_dimensions["F"].width = 15

    # Save to buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    # Transliterate filename for ASCII-safe Content-Disposition
    import re
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    raw_name = f"{detail_obj['designation']}"
    ascii_name = ''.join(translit_map.get(c.lower(), c) for c in raw_name)
    ascii_name = re.sub(r'[^a-zA-Z0-9._-]', '_', ascii_name)

    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{ascii_name}.xlsx"'}
    )


@app.post("/api/export/pdf")
async def export_pdf(request: Request):
    """Export reasoning to PDF (for management)"""
    detail_id = await _get_param(request, "detail_id")
    if not detail_id:
        return HTMLResponse('{"error":"detail_id required"}', status_code=422, media_type="application/json")
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    detail_obj = next((d for d in MOCK_DETAILS if d["id"] == detail_id), None)
    draft_data = get_draft(detail_id)
    if not detail_obj or not draft_data:
        raise HTTPException(400, "No draft to export")

    draft = draft_data["output"]
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Try to register a unicode font
    try:
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont("Helvetica"))
        font = "Helvetica"
    except Exception:
        font = "Helvetica"

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, height - 2*cm, f"Обоснование ТК")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2*cm, height - 3*cm, f"{detail_obj['designation']} — {detail_obj['name']}")

    # Properties
    c.setFont("Helvetica-Bold", 11)
    y = height - 4.5*cm
    c.drawString(2*cm, y, "Характеристики детали:")
    c.setFont("Helvetica", 10)
    y -= 0.6*cm
    c.drawString(2*cm, y, f"Материал: {detail_obj.get('material', '')}")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Масса: {detail_obj.get('mass_kg', '')} кг")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Шасси: {detail_obj.get('chassis', '')}")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Модель: {detail_obj.get('model', '')}")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Покрытие: {detail_obj.get('surface_treatment', '')}")

    # Summary
    y -= 1*cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, y, "Сводка")
    c.setFont("Helvetica", 10)
    y -= 0.6*cm
    summary = draft.get("summary", {})
    c.drawString(2*cm, y, f"Операций: {summary.get('total_operations', 0)}")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Общее время: {summary.get('total_hours', 0)} ч")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Подг. время: {summary.get('prep_hours', 0)} ч")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Сложность: {summary.get('complexity', '')}")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Ближайший аналог: {summary.get('closest_analog', '') or 'нет'}")

    # Reasoning
    y -= 1*cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, y, "Обоснование решений")
    c.setFont("Helvetica", 9)
    y -= 0.6*cm
    reasoning = draft.get("reasoning", {})
    for key, value in reasoning.items():
        c.setFont("Helvetica-Bold", 10)
        c.drawString(2*cm, y, f"{key}:")
        y -= 0.5*cm
        c.setFont("Helvetica", 9)
        # Wrap text
        words = str(value).split()
        line = ""
        for word in words:
            if len(line) + len(word) + 1 < 95:
                line += " " + word if line else word
            else:
                c.drawString(2*cm, y, line)
                y -= 0.45*cm
                line = word
        if line:
            c.drawString(2*cm, y, line)
            y -= 0.5*cm
        y -= 0.2*cm

    c.save()
    buffer.seek(0)

    # Transliterate filename for ASCII-safe Content-Disposition
    import re
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    raw_name = f"{detail_obj['designation']}_reasoning"
    ascii_name = ''.join(translit_map.get(c.lower(), c) for c in raw_name)
    ascii_name = re.sub(r'[^a-zA-Z0-9._-]', '_', ascii_name)

    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{ascii_name}.pdf"'}
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "demo_mode": DEMO_MODE,
        "model": LLM_MODEL,
        "api_url": LLM_API_URL if not DEMO_MODE else None,
        "details_count": len(MOCK_DETAILS)
    }


@app.get("/history/{detail_id}")
async def history(detail_id: str):
    """Get history for a detail (for debug)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT id, action, timestamp, details FROM history WHERE detail_id = ? ORDER BY id DESC LIMIT 50",
        (detail_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return {"history": [
        {"id": r[0], "action": r[1], "timestamp": r[2], "details": json.loads(r[3] or "{}")}
        for r in rows
    ]}


# ============================================
# CRUD: детали
# ============================================
@app.get("/details/new", response_class=HTMLResponse)
async def new_detail_form(request: Request):
    materials = get_all_materials()
    return templates.TemplateResponse("detail_form.html", {
        "request": request,
        "detail": None,
        "materials": materials
    })


@app.post("/api/details")
async def api_create_detail(designation: str = Form(...),
                              name: str = Form(""),
                              model: str = Form(""),
                              chassis: str = Form(""),
                              material: str = Form(""),
                              size_mm: str = Form(""),
                              mass_kg: float = Form(0),
                              surface_treatment: str = Form("")):
    d = {"designation": designation, "name": name, "model": model, "chassis": chassis,
         "material": material, "size_mm": size_mm, "mass_kg": mass_kg, "surface_treatment": surface_treatment}
    detail_id = create_detail(d)
    add_history(detail_id, "detail_created", d)
    return RedirectResponse(f"/detail/{detail_id}", status_code=303)


# ============================================
# CRUD: оборудование
# ============================================
@app.get("/equipment", response_class=HTMLResponse)
async def equipment_page(request: Request):
    items = get_all_equipment()
    return templates.TemplateResponse("equipment_list.html", {
        "request": request,
        "items": items
    })


@app.post("/api/equipment")
async def api_create_equipment(name: str = Form(...),
                                type: str = Form(""),
                                code: str = Form(""),
                                max_thickness_mm: float = Form(0),
                                max_mass_kg: float = Form(0),
                                notes: str = Form("")):
    eid = create_equipment({"name": name, "type": type, "code": code,
                            "max_thickness_mm": max_thickness_mm,
                            "max_mass_kg": max_mass_kg, "notes": notes})
    add_history(eid, "equipment_added", {"name": name})
    return RedirectResponse("/equipment", status_code=303)


# ============================================
# CRUD: материалы
# ============================================
@app.get("/materials", response_class=HTMLResponse)
async def materials_page(request: Request):
    items = get_all_materials()
    return templates.TemplateResponse("materials_list.html", {
        "request": request,
        "items": items
    })


@app.post("/api/materials")
async def api_create_material(name: str = Form(...),
                               grade: str = Form(""),
                               gost: str = Form(""),
                               notes: str = Form("")):
    mid = create_material({"name": name, "grade": grade, "gost": gost, "notes": notes})
    return RedirectResponse("/materials", status_code=303)


# ============================================
# CRUD: ИОТ
# ============================================
@app.get("/iot", response_class=HTMLResponse)
async def iot_page(request: Request):
    items = get_all_iot()
    return templates.TemplateResponse("iot_list.html", {
        "request": request,
        "items": items
    })


@app.post("/api/iot")
async def api_create_iot(number: str = Form(...),
                          description: str = Form(""),
                          applies_to: str = Form("")):
    iid = create_iot({"number": number, "description": description, "applies_to": applies_to})
    return RedirectResponse("/iot", status_code=303)


# ============================================
# CRUD: бенчмарки
# ============================================
@app.get("/benchmarks", response_class=HTMLResponse)
async def benchmarks_page(request: Request):
    items = get_all_benchmarks()
    return templates.TemplateResponse("benchmarks_list.html", {
        "request": request,
        "items": items
    })


@app.post("/api/benchmarks")
async def api_create_benchmark(detail_type: str = Form(...),
                                 norm_hours: float = Form(0),
                                 source: str = Form(""),
                                 sample_size: int = Form(1)):
    bid = create_benchmark({"detail_type": detail_type, "norm_hours": norm_hours,
                            "source": source, "sample_size": sample_size})
    return RedirectResponse("/benchmarks", status_code=303)


@app.post("/api/import/equipment")
async def api_import_equipment(department: str = Form(""), type: str = Form(""), limit: int = Form(50)):
    """Mock-импорт оборудования из 1С с фильтром (для прототипа — не реальный обмен)"""
    # Mock: просто обновляем last_sync_at у существующих
    import random
    added = 0
    for eq_id, name, etype in [
        (f"1c-{random.randint(1000,9999)}", f"Импортированное #{i}", type or "Сварочный аппарат")
        for i in range(min(limit, 10))
    ]:
        eid = f"eq-imp-{added}"
        conn = get_conn()
        try:
            conn.execute("""INSERT INTO equipment
                (id, name, type, code, notes, source, last_sync_at)
                VALUES (?, ?, ?, ?, ?, '1c', ?)""",
                (eid, name, etype, str(random.randint(10000, 99999)),
                 f"импорт {datetime.now().isoformat()}", datetime.now().isoformat()))
            conn.commit()
            added += 1
        except Exception:
            pass
        conn.close()
    add_history("import", "equipment_imported", {"added": added, "filter": {"department": department, "type": type}})
    return RedirectResponse("/equipment", status_code=303)


@app.post("/api/import/materials")
async def api_import_materials(grade: str = Form(""), limit: int = Form(50)):
    """Mock-импорт материалов из 1С"""
    import random
    for i in range(min(limit, 5)):
        mid = f"m-imp-{i}"
        conn = get_conn()
        try:
            conn.execute("""INSERT INTO materials (id, name, grade, gost, source, last_sync_at)
                VALUES (?, ?, ?, ?, '1c', ?)""",
                (mid, f"Импортированный материал #{i}", grade or "Ст3",
                 f"ГОСТ {random.randint(100,99999)}-{random.randint(80,2025)}",
                 datetime.now().isoformat()))
            conn.commit()
        except Exception:
            pass
        conn.close()
    return RedirectResponse("/materials", status_code=303)


@app.post("/api/import/iot")
async def api_import_iot(limit: int = Form(50)):
    """Mock-импорт ИОТ"""
    import random
    for i in range(min(limit, 5)):
        iid = f"iot-imp-{i}"
        conn = get_conn()
        try:
            conn.execute("""INSERT INTO iot (id, number, description, source, last_sync_at)
                VALUES (?, ?, ?, '1c', ?)""",
                (iid, str(random.randint(1, 200)), f"Импортированный ИОТ #{i}",
                 datetime.now().isoformat()))
            conn.commit()
        except Exception:
            pass
        conn.close()
    return RedirectResponse("/iot", status_code=303)


@app.post("/api/import/benchmarks")
async def api_import_benchmarks(limit: int = Form(100)):
    """Mock-импорт бенчмарков (ведомость трудоёмкости)"""
    import random
    for i in range(min(limit, 5)):
        bid = f"bk-imp-{i}"
        conn = get_conn()
        try:
            conn.execute("""INSERT INTO benchmarks (id, detail_type, norm_hours, source, sample_size, last_sync_at)
                VALUES (?, ?, ?, '1c', ?, ?)""",
                (bid, f"Импортированный тип #{i}", round(random.uniform(0.1, 5.0), 2),
                 "ведомость Техинкома", random.randint(1, 50),
                 datetime.now().isoformat()))
            conn.commit()
        except Exception:
            pass
        conn.close()
    return RedirectResponse("/benchmarks", status_code=303)


@app.post("/api/equipment/local-params")
async def api_equipment_local_params(id: str = Form(...), local_notes: str = Form("")):
    """Добавить локальные параметры к оборудованию (поверх 1С-данных)"""
    conn = get_conn()
    # Просто пишем в notes, добавляя маркер
    row = conn.execute("SELECT notes FROM equipment WHERE id=?", (id,)).fetchone()
    if not row:
        conn.close()
        return HTMLResponse('❌ Не найдено', status_code=404)
    old_notes = row[0] or ""
    new_notes = old_notes + f"\n[локально {datetime.now().strftime('%d.%m')}] {local_notes}"
    conn.execute("UPDATE equipment SET notes=? WHERE id=?", (new_notes, id))
    conn.commit()
    conn.close()
    return RedirectResponse("/equipment", status_code=303)


# ============================================
# РЕДАКТОР ОПЕРАЦИЙ (правка черновика технологом)
# ============================================
@app.post("/api/edit/operation")
async def api_edit_operation(request: Request):
    """Правка одной операции в черновике (записывается как edit + version)"""
    detail_id = await _get_param(request, "detail_id")
    op_index_str = await _get_param(request, "op_index")
    field = await _get_param(request, "field")
    value = await _get_param(request, "value")
    reason = await _get_param(request, "reason") or ""
    author = await _get_param(request, "author") or "technologist"
    if not all([detail_id, op_index_str, field, value is not None]):
        return HTMLResponse('<span style="color:red">❌ Не хватает параметров</span>', status_code=422)
    op_index = int(op_index_str)

    draft_data = get_draft(detail_id)
    if not draft_data:
        return HTMLResponse('<span style="color:red">❌ Нет черновика</span>', status_code=400)

    operations = draft_data["output"].get("operations", [])
    if op_index < 0 or op_index >= len(operations):
        return HTMLResponse('<span style="color:red">❌ Нет такой операции</span>', status_code=400)

    old_value = operations[op_index].get(field, "")
    operations[op_index][field] = value
    draft_data["output"]["operations"] = operations

    save_draft(detail_id, draft_data["output"], status="draft", author=author)
    new_v = save_version(detail_id, operations, author=author, source="human_edit",
                         notes=f"{field}: {old_value} → {value}")
    record_edit(detail_id, new_v, f"op{op_index}.{field}", old_value, value, reason, author)
    add_history(detail_id, "operation_edited", {"op": op_index, "field": field, "old": old_value, "new": value})

    return HTMLResponse(f'<span style="color:green">✅ Операция {op_index+1} обновлена (v{new_v})</span>')


@app.post("/api/edit/add-operation")
async def api_add_operation(request: Request):
    """Добавляет новую операцию в черновик"""
    detail_id = await _get_param(request, "detail_id")
    name = await _get_param(request, "name")
    equipment = await _get_param(request, "equipment") or ""
    duration_str = await _get_param(request, "duration_hours") or "0"
    author = await _get_param(request, "author") or "technologist"
    if not detail_id or not name:
        return HTMLResponse('<span style="color:red">❌ Не хватает параметров</span>', status_code=422)
    duration_hours = float(duration_str)

    draft_data = get_draft(detail_id)
    if not draft_data:
        return HTMLResponse('<span style="color:red">❌ Нет черновика</span>', status_code=400)

    operations = draft_data["output"].get("operations", [])
    new_op = {
        "name": name, "equipment": equipment, "duration_hours": duration_hours,
        "duration_source": "ручной ввод", "confidence": 100
    }
    operations.append(new_op)
    draft_data["output"]["operations"] = operations
    save_draft(detail_id, draft_data["output"], status="draft", author=author)
    new_v = save_version(detail_id, operations, author=author, source="human_add", notes=f"Added: {name}")
    record_edit(detail_id, new_v, "new_op", "", name, "added by user", author)

    return HTMLResponse(f'<span style="color:green">✅ Операция добавлена (v{new_v})</span>')


@app.post("/api/edit/delete-operation")
async def api_delete_operation(request: Request):
    """Удаляет операцию"""
    detail_id = await _get_param(request, "detail_id")
    op_index_str = await _get_param(request, "op_index")
    reason = await _get_param(request, "reason") or ""
    author = await _get_param(request, "author") or "technologist"
    if not detail_id or op_index_str is None:
        return HTMLResponse('<span style="color:red">❌ Не хватает параметров</span>', status_code=422)
    op_index = int(op_index_str)

    draft_data = get_draft(detail_id)
    if not draft_data:
        return HTMLResponse('<span style="color:red">❌ Нет черновика</span>', status_code=400)

    operations = draft_data["output"].get("operations", [])
    if op_index < 0 or op_index >= len(operations):
        return HTMLResponse('<span style="color:red">❌ Нет такой операции</span>', status_code=400)

    removed = operations.pop(op_index)
    draft_data["output"]["operations"] = operations
    save_draft(detail_id, draft_data["output"], status="draft", author=author)
    new_v = save_version(detail_id, operations, author=author, source="human_delete",
                         notes=f"Deleted: {removed.get('name', '')}")
    record_edit(detail_id, new_v, f"op{op_index}", removed.get("name", ""), "", reason, author)

    return HTMLResponse(f'<span style="color:green">✅ Операция удалена (v{new_v})</span>')


# ============================================
# ОБУЧЕНИЕ: правила + метрики
# ============================================
@app.get("/learning", response_class=HTMLResponse)
async def learning_page(request: Request):
    metrics = get_metrics()
    rules = extract_rule_from_edits()
    all_edits = get_edits()
    llm_calls = get_llm_calls(limit=20)
    return templates.TemplateResponse("learning.html", {
        "request": request,
        "metrics": metrics,
        "rules": rules,
        "edits": all_edits,
        "llm_calls": llm_calls
    })


@app.get("/llm-debug", response_class=HTMLResponse)
async def llm_debug_page(request: Request, detail_id: str = None, call_id: int = None):
    calls = get_llm_calls(detail_id=detail_id, limit=100)
    selected = None
    if call_id:
        selected = get_llm_call_detail(call_id)
    elif calls:
        selected = get_llm_call_detail(calls[0]["id"])
    return templates.TemplateResponse("llm_debug.html", {
        "request": request,
        "calls": calls,
        "selected": selected
    })


# ============================================
# ПИЛОТ: дашборд KPI + ввод метрик
# ============================================
@app.get("/pilot", response_class=HTMLResponse)
async def pilot_dashboard(request: Request):
    metrics = get_pilot_metrics()
    conn = get_conn()
    recent = conn.execute("""SELECT detail_id,
        SUM(CASE WHEN metric='edits_count' THEN value ELSE 0 END) as edits,
        SUM(CASE WHEN metric='time_to_card_min' THEN value ELSE 0 END) as time_min,
        MAX(created_at) as last
        FROM pilot_metrics GROUP BY detail_id ORDER BY last DESC LIMIT 20""").fetchall()
    conn.close()
    approved_list = [{"detail_id": r[0], "edits": r[1] or 0,
                      "time_min": r[2] or 0, "last": r[3]} for r in recent]
    return templates.TemplateResponse("pilot.html", {
        "request": request,
        "metrics": metrics,
        "approved_list": approved_list
    })


@app.post("/api/pilot/time")
async def api_pilot_time(detail_id: str = Form(...), minutes: float = Form(...),
                          author: str = Form("technologist")):
    record_metric(detail_id, "time_to_card_min", minutes, {"author": author})
    return RedirectResponse("/pilot", status_code=303)


@app.post("/api/pilot/accepted")
async def api_pilot_accepted(detail_id: str = Form(...), total_ops: int = Form(...),
                              accepted_ops: int = Form(...)):
    record_metric(detail_id, "total_ops", total_ops)
    record_metric(detail_id, "accepted_op", accepted_ops)
    return RedirectResponse("/pilot", status_code=303)


# ============================================
# ПРАВИЛА ТЕХНОЛОГА (структурированный ввод)
# ============================================
@app.post("/api/details/{detail_id}/rules")
async def api_save_rules(detail_id: str, rules: str = Form(...)):
    """Сохраняет правила технолога для конкретной детали (в свободной форме)"""
    conn = get_conn()
    conn.execute("UPDATE details SET tech_rules=?, updated_at=? WHERE id=?",
                 (rules, datetime.now().isoformat(), detail_id))
    conn.commit()
    conn.close()
    add_history(detail_id, "rules_updated", {"length": len(rules)})
    return {"status": "ok"}


# ============================================
# ЭКОНОМИКА: ставка, накладные, себестоимость
# ============================================
@app.post("/api/details/{detail_id}/economics")
async def api_save_economics(detail_id: str,
                              cost_per_hour: float = Form(...),
                              overhead_pct: float = Form(...),
                              material_cost_rub: float = Form(...)):
    conn = get_conn()
    conn.execute("""UPDATE details SET cost_per_hour=?, overhead_pct=?, material_cost_rub=?, updated_at=?
                    WHERE id=?""",
                 (cost_per_hour, overhead_pct, material_cost_rub,
                  datetime.now().isoformat(), detail_id))
    conn.commit()
    conn.close()
    return {"status": "ok"}


def calc_cost_estimate(detail_id: str) -> dict:
    """Sprint 1: Process-based pricing (CADDi pattern) — разбивка по этапам маршрута"""
    draft = get_draft(detail_id)
    detail = get_detail(detail_id)
    if not draft or not detail:
        return {}
    operations = draft["output"].get("operations", [])
    total_hours = sum(op.get("duration_hours", 0) for op in operations)
    cost_per_hour = detail.get("cost_per_hour") or 0
    material_cost = detail.get("material_cost_rub") or 0
    overhead_pct = detail.get("overhead_pct") or 0

    # Process-based breakdown: группируем по department
    breakdown_by_dept = {}
    for op in operations:
        dept = op.get("department") or "Без цеха"
        if dept not in breakdown_by_dept:
            breakdown_by_dept[dept] = {"hours": 0.0, "operations": 0, "labor_cost": 0.0}
        breakdown_by_dept[dept]["hours"] += op.get("duration_hours", 0)
        breakdown_by_dept[dept]["operations"] += 1
    for d in breakdown_by_dept.values():
        d["hours"] = round(d["hours"], 2)
        d["labor_cost"] = round(d["hours"] * cost_per_hour, 2)

    # Распределяем материал по этапам пропорционально часам
    material_by_dept = {}
    for dept, d in breakdown_by_dept.items():
        share = (d["hours"] / total_hours) if total_hours else 0
        material_by_dept[dept] = round(material_cost * share, 2)

    labor_cost = total_hours * cost_per_hour
    direct_cost = labor_cost + material_cost
    overhead = direct_cost * (overhead_pct / 100)
    total_cost = direct_cost + overhead
    price = total_cost * 1.3  # 30% наценка (mock)

    return {
        "total_hours": round(total_hours, 2),
        "labor_cost": round(labor_cost, 2),
        "material_cost": round(material_cost, 2),
        "direct_cost": round(direct_cost, 2),
        "overhead_pct": overhead_pct,
        "overhead": round(overhead, 2),
        "total_cost": round(total_cost, 2),
        "price": round(price, 2),
        "by_department": [
            {"department": dept, "hours": d["hours"], "operations": d["operations"],
             "labor_cost": d["labor_cost"], "material_cost": material_by_dept[dept]}
            for dept, d in sorted(breakdown_by_dept.items(), key=lambda x: -x[1]["hours"])
        ]
    }


# ============================================
# РОЛЕВАЯ МОДЕЛЬ: workflow утверждения
# ============================================
@app.post("/api/submit-for-review")
async def api_submit_for_review(request: Request):
    detail_id = await _get_param(request, "detail_id")
    if not detail_id:
        return JSONResponse({"error": "detail_id required"}, status_code=422)
    conn = get_conn()
    conn.execute("""UPDATE drafts SET status_ext='review', submitted_at=?
                    WHERE detail_id=?""", (datetime.now().isoformat(), detail_id))
    conn.commit()
    conn.close()
    add_history(detail_id, "submitted_for_review")
    return {"status": "submitted"}


@app.post("/api/approve-chief")
async def api_approve_chief(request: Request):
    """Утверждение начальником (другая роль, не технолог)"""
    detail_id = await _get_param(request, "detail_id")
    chief = await _get_param(request, "chief") or "chief"
    if not detail_id:
        return JSONResponse({"error": "detail_id required"}, status_code=422)
    conn = get_conn()
    conn.execute("""UPDATE drafts SET status_ext='approved_chief', approver=?
                    WHERE detail_id=?""", (chief, detail_id))
    conn.commit()
    conn.close()
    add_history(detail_id, "approved_by_chief", {"chief": chief})
    return {"status": "approved_chief"}


@app.get("/api/economics/{detail_id}")
async def api_economics(detail_id: str):
    """Sprint 1: HTML с метриками + process-based breakdown по цехам (CADDi pattern)"""
    econ = calc_cost_estimate(detail_id)
    if not econ:
        return HTMLResponse('<p>Нет черновика для расчёта.</p>')
    by_dept_rows = ""
    for d in econ.get("by_department", []):
        by_dept_rows += f"""<tr>
            <td>{d['department']}</td>
            <td>{d['operations']}</td>
            <td>{d['hours']}</td>
            <td>{d['labor_cost']}₽</td>
            <td>{d['material_cost']}₽</td>
            <td>{d['labor_cost'] + d['material_cost']}₽</td>
        </tr>"""
    html = f"""
    <div class="metrics">
        <div class="metric"><div class="metric-value">{econ['total_hours']}</div><div class="metric-label">часов всего</div></div>
        <div class="metric"><div class="metric-value">{econ['labor_cost']}₽</div><div class="metric-label">труд</div></div>
        <div class="metric"><div class="metric-value">{econ['material_cost']}₽</div><div class="metric-label">материал</div></div>
        <div class="metric"><div class="metric-value">{econ['overhead']}₽</div><div class="metric-label">накладные ({econ['overhead_pct']}%)</div></div>
        <div class="metric"><div class="metric-value" style="color:#dc2626">{econ['total_cost']}₽</div><div class="metric-label">себестоимость</div></div>
        <div class="metric"><div class="metric-value" style="color:#16a34a">{econ['price']}₽</div><div class="metric-label">цена (наценка 30%)</div></div>
    </div>
    <p class="lead">Расчёт: {econ['total_hours']} ч × ставка + {econ['material_cost']}₽ материал + {econ['overhead_pct']}% накладные = {econ['total_cost']}₽</p>

    <h3 style="margin-top: 24px;">📊 Разбивка по цехам (process-based pricing)</h3>
    <p class="lead"><small>Сколько часов и денег уходит в каждом цехе — CADDi-паттерн для прозрачности себестоимости.</small></p>
    <table class="data-table">
        <thead><tr><th>Цех</th><th>Операций</th><th>Часы</th><th>Труд</th><th>Материал</th><th>Итого</th></tr></thead>
        <tbody>
        {by_dept_rows}
        </tbody>
    </table>
    """
    return HTMLResponse(html)


if __name__ == "__main__":
    init_db()
    log.info(f"Starting БИТ.Технолог (demo_mode={DEMO_MODE})")
    if DEMO_MODE:
        log.info("⚠️  DEMO MODE: no real LLM calls. Mock responses based on heuristics.")
    else:
        log.info(f"✓ LLM: {LLM_MODEL} via {LLM_API_URL}")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
