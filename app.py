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
    return sqlite3.connect(DB_PATH)


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
            notes TEXT
        );

        -- 7. Материалы
        CREATE TABLE IF NOT EXISTS materials (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            grade TEXT,
            gost TEXT,
            notes TEXT
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
            applies_to TEXT
        );

        -- 10. Бенчмарки трудоёмкости
        CREATE TABLE IF NOT EXISTS benchmarks (
            id TEXT PRIMARY KEY,
            detail_type TEXT NOT NULL,
            norm_hours REAL,
            source TEXT,
            sample_size INTEGER DEFAULT 1
        );

        -- 11. История действий
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id TEXT,
            action TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT
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
    conn.close()
    if not row:
        return None
    cols = [d[1] for d in sqlite3.connect(DB_PATH).execute("PRAGMA table_info(details)").fetchall()]
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
    cols = ["id", "name", "type", "code", "max_thickness_mm", "max_mass_kg", "notes"]
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
async def index(request: Request):
    details = get_all_details()
    # Добавим статус черновика
    conn = get_conn()
    for d in details:
        d["status"] = conn.execute(
            "SELECT status FROM drafts WHERE detail_id=?", (d["id"],)
        ).fetchone()
        d["status"] = d["status"][0] if d["status"] else "new"
    conn.close()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "details": details,
        "demo_mode": DEMO_MODE,
        "llm_model": LLM_MODEL
    })


@app.get("/detail/{detail_id}", response_class=HTMLResponse)
async def detail(request: Request, detail_id: str):
    detail_obj = get_detail(detail_id)
    if not detail_obj:
        raise HTTPException(404, "Detail not found")

    draft_data = get_draft(detail_id)
    versions = get_versions(detail_id)
    edits = get_edits(detail_id)

    return templates.TemplateResponse("detail.html", {
        "request": request,
        "detail": detail_obj,
        "draft": draft_data["output"] if draft_data else None,
        "status": draft_data["status"] if draft_data else "new",
        "versions": versions,
        "edits": edits,
        "demo_mode": DEMO_MODE,
        "llm_model": LLM_MODEL
    })


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
    else:
        # Real LLM call via OpenAI-compatible API
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url=LLM_API_URL,
                api_key=LLM_API_KEY,
                timeout=LLM_TIMEOUT
            )

            from string import Template
            prompt = Template(TECH_CARD_PROMPT).substitute(
                properties_json=json.dumps(detail_obj, indent=2, ensure_ascii=False),
                equipment_json=json.dumps(EQUIPMENT, indent=2, ensure_ascii=False),
                structure_json=json.dumps(STRUCTURE, indent=2, ensure_ascii=False),
                few_shot_json=json.dumps(FEW_SHOT_4C85941A, indent=2, ensure_ascii=False)
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
                # Обновляем запись: parsed_ok=True
                conn = get_conn()
                conn.execute("UPDATE llm_calls SET response_parsed_ok=1 WHERE id=(SELECT MAX(id))")
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
async def approve(req: GenerateRequest):
    """Approve draft"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE drafts SET status = 'approved', updated_at = ? WHERE detail_id = ?",
        (datetime.now().isoformat(), req.detail_id)
    )
    conn.commit()
    conn.close()
    add_history(req.detail_id, "approved")
    return {"status": "approved"}


@app.post("/api/send-to-1c")
async def send_to_1c(req: GenerateRequest):
    """MOCK: write RS to 1C:ERP"""
    add_history(req.detail_id, "sent_to_1c_mock", {
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


if __name__ == "__main__":
    init_db()
    log.info(f"Starting БИТ.Технолог (demo_mode={DEMO_MODE})")
    if DEMO_MODE:
        log.info("⚠️  DEMO MODE: no real LLM calls. Mock responses based on heuristics.")
    else:
        log.info(f"✓ LLM: {LLM_MODEL} via {LLM_API_URL}")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
