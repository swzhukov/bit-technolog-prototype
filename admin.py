"""
admin.py — админ-эндпоинты через APIRouter (v0.4.9, F15.7).
Выделено из app.py для уменьшения app.py с 4769 до ~4000 строк.

Содержит:
- /admin (дашборд)
- /admin/users, /api/admin/users/* (CRUD пользователей)
- /admin/login-log (лог входов)
- /admin/llm-calls (лог LLM-вызовов)
- /api/admin/backup, /api/admin/rag-rebuild
- /admin/settings, /api/admin/settings/* (глобальные настройки)
- /admin/system (системные метрики)

Использует зависимости из app.py:
- get_current_role (auth.py)
- hash_password (auth.py)
- get_conn, add_history, get_all_settings, set_setting, delete_setting, get_setting
- SETTING_REGISTRY, _mask_value, _encrypt
- ROLES, DB_PATH
- templates, log, err
- _get_param, _require_admin_or_json
"""
import os
import sys
import json
import shutil
import platform
import logging
import subprocess
from typing import Optional

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse

# Создаём router
router = APIRouter(tags=["admin"])
log = logging.getLogger("bit-technolog")


def _get_templates_db_path_roles():
    """Lazy import — избегаем циклических зависимостей."""
    import app
    return app.templates, app.DB_PATH, app.ROLES, app.err, app._get_param, app._require_admin_or_json, app.add_history


# ========== /admin dashboard ==========
@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Дашборд администратора"""
    from app import get_conn
    from auth import get_current_role
    templates, DB_PATH, ROLES, err, _, _, _ = _get_templates_db_path_roles()
    if get_current_role(request) != "admin":
        return HTMLResponse("<h1>403 — Доступ только администратору</h1>", status_code=403)
    conn = get_conn()
    counts = {
        "users_total": conn.execute("SELECT COUNT(*) FROM pilot_users").fetchone()[0] or 0,
        "users_active": conn.execute("SELECT COUNT(*) FROM pilot_users WHERE is_active=1").fetchone()[0] or 0,
        "logins_today": conn.execute("SELECT COUNT(*) FROM audit_logins WHERE date(ts)=date('now')").fetchone()[0] or 0,
        "logins_failed_today": conn.execute("SELECT COUNT(*) FROM audit_logins WHERE date(ts)=date('now') AND success=0").fetchone()[0] or 0,
        "llm_calls_today": conn.execute("SELECT COUNT(*) FROM llm_calls WHERE date(created_at)=date('now')").fetchone()[0] or 0,
        "llm_cost_today": conn.execute("SELECT COALESCE(SUM(cost_rub), 0) FROM llm_calls WHERE date(created_at)=date('now')").fetchone()[0] or 0,
        "details_total": conn.execute("SELECT COUNT(*) FROM details").fetchone()[0] or 0,
        "drafts_total": conn.execute("SELECT COUNT(*) FROM drafts").fetchone()[0] or 0,
        "rag_chunks": conn.execute("SELECT COUNT(*) FROM draft_versions").fetchone()[0] or 0,
    }
    recent_logins = conn.execute("""SELECT username, ts, ip, success FROM audit_logins
        ORDER BY ts DESC LIMIT 5""").fetchall()
    recent_logins = [{"username": r[0], "ts": r[1], "ip": r[2], "success": r[3]} for r in recent_logins]
    recent_errors = conn.execute("""SELECT detail_id, error, created_at FROM llm_calls
        WHERE error IS NOT NULL AND error != ''
        ORDER BY created_at DESC LIMIT 5""").fetchall()
    recent_errors = [{"detail_id": r[0], "error": r[1][:200], "ts": r[2]} for r in recent_errors]
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    conn.close()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "counts": counts,
        "recent_logins": recent_logins,
        "recent_errors": recent_errors,
        "db_size_mb": round(db_size / 1024 / 1024, 2)
    })


# ========== /admin/users ==========
@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    from app import get_conn
    from auth import get_current_role
    templates, DB_PATH, ROLES, err, _, _, _ = _get_templates_db_path_roles()
    if get_current_role(request) != "admin":
        return HTMLResponse("<h1>403</h1>", status_code=403)
    conn = get_conn()
    users = conn.execute("""SELECT id, username, role, display_name, is_active, created_at, last_login
        FROM pilot_users ORDER BY id""").fetchall()
    users = [{
        "id": r[0], "username": r[1], "role": r[2], "display_name": r[3],
        "is_active": bool(r[4]), "created_at": r[5], "last_login": r[6]
    } for r in users]
    conn.close()
    return templates.TemplateResponse("admin_users.html", {
        "request": request, "users": users, "roles": ROLES
    })


@router.post("/api/admin/users/create")
async def api_admin_create_user(request: Request):
    from app import get_conn
    from auth import get_current_role, hash_password
    _, _, ROLES, err, _get_param, _require_admin_or_json, _ = _get_templates_db_path_roles()
    err_resp = _require_admin_or_json(request)
    if err_resp: return err_resp
    username = await _get_param(request, "username")
    password = await _get_param(request, "password")
    role = (await _get_param(request, "role")) or "technologist"
    display_name = (await _get_param(request, "display_name")) or ""
    if not username or not password:
        return err("username and password required", 422)
    if role not in ROLES:
        return err(f"role must be one of {list(ROLES.keys())}", 400)
    if len(password) < 6:
        return err("password too short (min 6)", 400)
    conn = get_conn()
    try:
        conn.execute("""INSERT INTO pilot_users (username, password_hash, role, display_name, created_by)
            VALUES (?, ?, ?, ?, ?)""",
            (username, hash_password(password), role, display_name, "admin"))
        conn.commit()
    except Exception as e:
        if "UNIQUE" in str(e):
            return err(f"user '{username}' already exists", 409)
        return err(f"create failed: {e}", 500)
    finally:
        conn.close()
    return JSONResponse({"ok": True, "username": username, "role": role})


@router.post("/api/admin/users/{user_id}/password")
async def api_admin_change_password(request: Request, user_id: int):
    from app import get_conn
    from auth import hash_password
    _, _, _, err, _get_param, _require_admin_or_json, _ = _get_templates_db_path_roles()
    err_resp = _require_admin_or_json(request)
    if err_resp: return err_resp
    password = await _get_param(request, "password")
    if not password or len(password) < 6:
        return err("password required (min 6)", 400)
    conn = get_conn()
    cur = conn.execute("UPDATE pilot_users SET password_hash=? WHERE id=?",
                       (hash_password(password), user_id))
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        return err("user not found", 404)
    conn.close()
    return JSONResponse({"ok": True, "user_id": user_id})


@router.post("/api/admin/users/{user_id}/toggle")
async def api_admin_toggle_user(request: Request, user_id: int):
    from app import get_conn
    _, _, _, err, _, _require_admin_or_json, _ = _get_templates_db_path_roles()
    err_resp = _require_admin_or_json(request)
    if err_resp: return err_resp
    conn = get_conn()
    conn.execute("UPDATE pilot_users SET is_active = 1 - is_active WHERE id=?", (user_id,))
    conn.commit()
    new_state = conn.execute("SELECT is_active FROM pilot_users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if not new_state:
        return err("user not found", 404)
    return JSONResponse({"ok": True, "user_id": user_id, "is_active": bool(new_state[0])})


@router.post("/api/admin/users/{user_id}/delete")
async def api_admin_delete_user(request: Request, user_id: int):
    from app import get_conn
    _, _, _, err, _, _require_admin_or_json, _ = _get_templates_db_path_roles()
    err_resp = _require_admin_or_json(request)
    if err_resp: return err_resp
    conn = get_conn()
    conn.execute("DELETE FROM pilot_users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return JSONResponse({"ok": True, "user_id": user_id})


# ========== /admin/login-log ==========
@router.get("/admin/login-log", response_class=HTMLResponse)
async def admin_login_log(request: Request, limit: int = 100):
    from app import get_conn
    from auth import get_current_role
    templates, _, _, _, _, _, _ = _get_templates_db_path_roles()
    if get_current_role(request) != "admin":
        return HTMLResponse("<h1>403</h1>", status_code=403)
    conn = get_conn()
    rows = conn.execute("""SELECT username, ts, ip, user_agent, success
        FROM audit_logins ORDER BY ts DESC LIMIT ?""", (limit,)).fetchall()
    logins = [{
        "username": r[0], "ts": r[1], "ip": r[2],
        "user_agent": r[3] or "", "success": bool(r[4])
    } for r in rows]
    conn.close()
    return templates.TemplateResponse("admin_login_log.html", {
        "request": request, "logins": logins, "limit": limit
    })


# ========== /admin/llm-calls ==========
@router.get("/admin/llm-calls", response_class=HTMLResponse)
async def admin_llm_calls(request: Request, model: str = "", errors_only: int = 0,
                          days: int = 7, limit: int = 200):
    from app import get_conn
    from auth import get_current_role
    templates, _, _, _, _, _, _ = _get_templates_db_path_roles()
    if get_current_role(request) != "admin":
        return HTMLResponse("<h1>403</h1>", status_code=403)
    conn = get_conn()
    where = [f"created_at > datetime('now', '-{int(days)} day')"]
    params = []
    if model:
        where.append("model = ?")
        params.append(model)
    if errors_only:
        where.append("(error IS NOT NULL AND error != '' OR response_parsed_ok = 0)")
    sql = f"SELECT detail_id, model, tokens_in, tokens_out, cost_rub, duration_ms, response_parsed_ok, error, created_at FROM llm_calls WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    calls = [{
        "detail_id": r[0], "model": r[1], "tokens_in": r[2], "tokens_out": r[3],
        "cost_rub": round(r[4] or 0, 4), "duration_ms": r[5],
        "parsed": bool(r[6]), "error": (r[7] or "")[:200], "ts": r[8]
    } for r in rows]
    cost_sql = f"SELECT COALESCE(SUM(cost_rub), 0), COUNT(*) FROM llm_calls WHERE {' AND '.join(where)}"
    cost_row = conn.execute(cost_sql, params[:-1]).fetchone()
    total_cost = round(cost_row[0] or 0, 2)
    total_count = cost_row[1] or 0
    models = [r[0] for r in conn.execute("SELECT DISTINCT model FROM llm_calls WHERE model IS NOT NULL").fetchall() if r[0]]
    conn.close()
    return templates.TemplateResponse("admin_llm_calls.html", {
        "request": request, "calls": calls, "models": models,
        "filters": {"model": model, "errors_only": errors_only, "days": days, "limit": limit},
        "total_cost": total_cost, "total_count": total_count
    })


# ========== /api/admin/backup и rag-rebuild ==========
@router.post("/api/admin/backup")
async def api_admin_backup(request: Request):
    from app import err
    _, _, _, err, _, _require_admin_or_json, _ = _get_templates_db_path_roles()
    err_resp = _require_admin_or_json(request)
    if err_resp: return err_resp
    backup_script = "/opt/beget/bit-technolog/backup.sh"
    if not os.path.exists(backup_script):
        return err(f"backup script not found: {backup_script}", 404)
    try:
        out = subprocess.run(["bash", backup_script], capture_output=True, text=True, timeout=300)
        return JSONResponse({
            "ok": out.returncode == 0,
            "returncode": out.returncode,
            "stdout": out.stdout[-1000:],
            "stderr": out.stderr[-500:]
        })
    except Exception as e:
        return err(f"backup failed: {e}", 500)


@router.post("/api/admin/rag-rebuild")
async def api_admin_rag_rebuild(request: Request):
    from app import err
    _, _, _, err, _, _require_admin_or_json, _ = _get_templates_db_path_roles()
    err_resp = _require_admin_or_json(request)
    if err_resp: return err_resp
    try:
        from rag import get_rag
        result = get_rag().rebuild_from_db()
        return JSONResponse({"ok": True, "result": result})
    except Exception as e:
        log.exception(f"rag rebuild failed: {e}")
        return err(f"rag rebuild failed: {e}", 500)


# ========== /admin/settings ==========
@router.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings_page(request: Request):
    from app import get_all_settings
    from auth import get_current_role
    templates, _, _, _, _, _, _ = _get_templates_db_path_roles()
    if get_current_role(request) != "admin":
        return HTMLResponse("<h1>403</h1>", status_code=403)
    settings = get_all_settings()
    groups = {
        "LLM (YandexGPT)": [s for s in settings if s["key"].startswith("LLM_") or s["key"] == "DEMO_MODE"],
        "Telegram": [s for s in settings if s["key"].startswith("TELEGRAM_")],
        "SMTP / Email": [s for s in settings if s["key"].startswith("SMTP_") or s["key"] == "NOTIFY_EMAIL_FROM"],
        "Лимиты": [s for s in settings if s["key"].startswith("MAX_") or s["key"] == "PILOT_USERS"],
    }
    return templates.TemplateResponse("admin_settings.html", {
        "request": request, "groups": groups, "settings_count": len(settings)
    })


@router.post("/api/admin/settings/set")
async def api_admin_set_setting(request: Request):
    """M19: после сохранения — redirect на /admin/settings с flash-сообщением.
    Для LLM_API_KEY — валидация через HEAD/GET к YandexGPT API перед сохранением."""
    from fastapi.responses import RedirectResponse
    from app import set_setting
    from settings import SETTING_REGISTRY, _mask_value
    import os
    import httpx

    _, _, _, err, _get_param, _require_admin_or_json, _ = _get_templates_db_path_roles()
    err_resp = _require_admin_or_json(request)
    if err_resp: return err_resp

    key = await _get_param(request, "key")
    value = await _get_param(request, "value")
    if not key:
        return err("key required", 422)
    valid_keys = {s[0] for s in SETTING_REGISTRY}
    if key not in valid_keys:
        return err(f"unknown setting: {key}", 400)

    # M19: валидация LLM ключа перед сохранением
    if key == "LLM_API_KEY" and value:
        api_url = os.getenv("LLM_API_URL", "https://llm.api.cloud.yandex.net/v1").rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # /v1/models — эндпоинт для проверки доступа (не тратит токены)
                r = await client.get(
                    f"{api_url}/models",
                    headers={
                        "Authorization": f"Api-Key {value}",
                        "x-folder-id": os.getenv("LLM_FOLDER_ID", ""),
                    },
                )
                if r.status_code == 401:
                    return err("LLM_API_KEY невалидный (401 Unauthorized). Проверьте ключ в Yandex Cloud.", 400)
                if r.status_code == 403:
                    return err("LLM_API_KEY невалидный (403 Forbidden). Проверьте folder_id.", 400)
                if r.status_code >= 500:
                    return err(f"YandexGPT API недоступен ({r.status_code}). Попробуйте позже.", 503)
                if r.status_code not in (200, 404):  # 404 = неправильный URL, но ключ валидный
                    return err(f"LLM_API_KEY неожиданный ответ: {r.status_code}", 400)
        except httpx.TimeoutException:
            return err("Timeout при проверке LLM_API_KEY (10 сек). YandexGPT недоступен?", 504)
        except Exception as e:
            return err(f"Ошибка проверки LLM_API_KEY: {str(e)[:200]}", 500)

    reg = next(s for s in SETTING_REGISTRY if s[0] == key)
    if reg[1] == "int" and value:
        try:
            int(value)
        except ValueError:
            return err(f"{key} must be integer", 400)
    if reg[1] == "bool" and value not in ("true", "false", "1", "0", ""):
        return err(f"{key} must be true/false", 400)
    ok = set_setting(key, value or "", updated_by=getattr(request.state, "current_role", "admin"))
    if not ok:
        return err("set_setting failed (db error)", 500)

    # M19: после успешного сохранения — redirect на /admin/settings с flash-сообщением
    # Если запрос пришёл из формы (Accept: text/html) — редирект
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        masked = _mask_value(value) if (reg[4] and value) else (value[:50] if value else "")
        # Используем cookie для flash-сообщения
        response = RedirectResponse(url="/admin/settings?ok=1&key=" + key, status_code=303)
        return response

    # API-вызовы получают JSON
    return JSONResponse({
        "ok": ok, "key": key,
        "value_masked": _mask_value(value) if (reg[4] and value) else (value[:100] if value else "")
    })


@router.post("/api/admin/settings/reset")
async def api_admin_reset_setting(request: Request):
    from app import delete_setting
    _, _, _, err, _get_param, _require_admin_or_json, _ = _get_templates_db_path_roles()
    err_resp = _require_admin_or_json(request)
    if err_resp: return err_resp
    key = await _get_param(request, "key")
    if not key:
        return err("key required", 422)
    delete_setting(key)
    return JSONResponse({"ok": True, "key": key, "msg": "reset to .env or default"})


@router.get("/api/admin/settings/raw/{key}")
async def api_admin_get_raw_setting(request: Request, key: str):
    from app import get_setting
    from settings import SETTING_REGISTRY
    _, _, _, err, _, _require_admin_or_json, _ = _get_templates_db_path_roles()
    err_resp = _require_admin_or_json(request)
    if err_resp: return err_resp
    reg = next((s for s in SETTING_REGISTRY if s[0] == key), None)
    if not reg:
        return err(f"unknown setting: {key}", 404)
    value = get_setting(key, reg[2])
    return JSONResponse({"ok": True, "key": key, "value": value, "type": reg[1]})


# ========== /admin/system ==========
@router.get("/admin/system", response_class=HTMLResponse)
async def admin_system(request: Request):
    from app import DB_PATH
    from auth import get_current_role
    templates, _, _, _, _, _, _ = _get_templates_db_path_roles()
    if get_current_role(request) != "admin":
        return HTMLResponse("<h1>403</h1>", status_code=403)
    disk_path = DB_PATH if os.path.exists(os.path.dirname(DB_PATH) or ".") else "."
    try:
        disk = shutil.disk_usage(disk_path if os.path.isdir(disk_path) else ".")
    except Exception:
        disk = shutil.disk_usage(".")
    mem_info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    mem_info[k.strip()] = int(v.strip().split()[0])
        mem_total_mb = mem_info.get("MemTotal", 0) / 1024
        mem_avail_mb = mem_info.get("MemAvailable", 0) / 1024
        mem_used_mb = mem_total_mb - mem_avail_mb
        mem_pct = round(mem_used_mb / mem_total_mb * 100, 1) if mem_total_mb else 0
    except Exception:
        mem_total_mb = mem_avail_mb = mem_used_mb = mem_pct = 0
    try:
        with open("/proc/uptime") as f:
            uptime_sec = float(f.read().split()[0])
    except Exception:
        uptime_sec = 0
    svc_status = "unknown"
    try:
        r = subprocess.run(["systemctl", "is-active", "bit-technolog"],
                           capture_output=True, text=True, timeout=5)
        svc_status = r.stdout.strip()
    except Exception:
        pass
    def du(path):
        if not os.path.exists(path):
            return 0
        if os.path.isfile(path):
            return round(os.path.getsize(path) / 1024 / 1024, 2)
        try:
            total = 0
            for root, dirs, files in os.walk(path):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
            return round(total / 1024 / 1024, 2)
        except Exception:
            return 0
    sizes = {
        "db_mb": du(DB_PATH),
        "drawings_mb": du("drawings"),
        "rag_mb": du(".rag"),
        "venv_mb": du("venv"),
    }
    return templates.TemplateResponse("admin_system.html", {
        "request": request,
        "disk": {"total_gb": round(disk.total / 1024**3, 1) if disk.total else 0,
                 "used_gb": round(disk.used / 1024**3, 1) if disk.used else 0,
                 "free_gb": round(disk.free / 1024**3, 1) if disk.free else 0,
                 "pct": disk.percent if hasattr(disk, 'percent') else 0},
        "mem": {"total_mb": round(mem_total_mb, 0), "used_mb": round(mem_used_mb, 0),
                "avail_mb": round(mem_avail_mb, 0), "pct": mem_pct},
        "uptime_sec": uptime_sec,
        "uptime_human": f"{int(uptime_sec//3600)}ч {int((uptime_sec%3600)//60)}м",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "svc_status": svc_status,
        "sizes": sizes
    })
