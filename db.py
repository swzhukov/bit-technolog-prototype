"""
db.py — модуль работы с БД (v0.4.9, F15).
Выделено из app.py для уменьшения монолита.
Содержит: подключение, инициализация схемы, CRUD-функции.
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "bit_technolog.db")


def get_conn():
    """Подключение к БД с WAL mode (для concurrent writes)"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn


def get_table_columns(table: str) -> list:
    """Helper для PRAGMA (без утечки соединений)"""
    conn = get_conn()
    cols = [d[1] for d in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    conn.close()
    return cols


def init_db():
    """Инициализация SQLite-схемы. Идемпотентна (CREATE IF NOT EXISTS)."""
    conn = get_conn()
    conn.executescript("""
        -- V5-3: indexes для быстрого поиска (создаются ДО таблиц — SQLite OK)
        CREATE INDEX IF NOT EXISTS idx_details_model ON details(model);
        CREATE INDEX IF NOT EXISTS idx_details_chassis ON details(chassis);
        CREATE INDEX IF NOT EXISTS idx_details_status ON details(status);
        CREATE INDEX IF NOT EXISTS idx_details_level ON details(level);
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
            parent_id TEXT,
            level TEXT DEFAULT 'detail',
            drawing_path TEXT,
            drawing_format TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS drafts (
            detail_id TEXT PRIMARY KEY,
            llm_output TEXT,
            status TEXT DEFAULT 'new',
            author TEXT,
            status_ext TEXT,
            approver TEXT,
            submitted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
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
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_type TEXT,
            condition_json TEXT,
            action_json TEXT,
            confidence REAL DEFAULT 0.5,
            uses_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            type TEXT,
            code TEXT,
            max_thickness_mm REAL,
            max_mass_kg REAL,
            source TEXT DEFAULT '1c',
            external_id TEXT,
            notes TEXT,
            last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            type TEXT,
            code TEXT,
            unit TEXT,
            price_per_unit REAL,
            source TEXT DEFAULT '1c',
            external_id TEXT,
            notes TEXT,
            last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            production TEXT,
            name TEXT,
            code TEXT,
            source TEXT DEFAULT '1c',
            external_id TEXT
        );
        CREATE TABLE IF NOT EXISTS iot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT,
            description TEXT,
            applies_to TEXT,
            source TEXT DEFAULT '1c',
            external_id TEXT
        );
        CREATE TABLE IF NOT EXISTS benchmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric TEXT,
            value REAL,
            context TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id TEXT,
            action TEXT,
            details TEXT,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        -- F16.8: A4-11 — soft-delete для операций (с возможностью restore)
        CREATE TABLE IF NOT EXISTS deleted_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id TEXT NOT NULL,
            op_index INTEGER,
            op_name TEXT,
            op_json TEXT,
            deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted_by TEXT,
            reason TEXT,
            restored_at TIMESTAMP,
            restored_by TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_deleted_ops_detail ON deleted_operations(detail_id);
        -- v3: A4-2 — answers для 3-step flow (backup для localStorage)
        CREATE TABLE IF NOT EXISTS step_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id TEXT NOT NULL,
            step TEXT,  -- 'analyze' / 'draft' / 'refine'
            answers_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_step_answers_detail ON step_answers(detail_id);
        CREATE TABLE IF NOT EXISTS pilot_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id TEXT,
            metric TEXT,
            value REAL,
            extra TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
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
        CREATE TABLE IF NOT EXISTS professions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            name TEXT,
            grade INTEGER,
            hourly_rate REAL,
            source TEXT DEFAULT 'etc',
            external_id TEXT
        );
        CREATE TABLE IF NOT EXISTS resource_specs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id TEXT,
            op_index INTEGER,
            kind TEXT,
            ref_id INTEGER,
            name TEXT,
            quantity REAL,
            unit TEXT,
            norm_per_unit REAL,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS drawings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_format TEXT,
            file_size INTEGER,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uploaded_by TEXT
        );
        CREATE TABLE IF NOT EXISTS pilot_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'technologist',
            display_name TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            created_by TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_logins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip TEXT,
            user_agent TEXT,
            success INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value_encrypted BLOB,
            value_masked TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );
    """)
    # Миграции
    try:
        conn.execute("ALTER TABLE details ADD COLUMN version TEXT DEFAULT '1.0'")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE llm_calls ADD COLUMN cost_rub REAL DEFAULT 0")
    except Exception:
        pass
    conn.commit()
    conn.close()


# ========== CRUD: details ==========
def get_detail(detail_id: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM details WHERE id=?", (detail_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def get_all_details(filters: dict = None, page: int = 1, per_page: int = 25) -> tuple:
    """Список деталей с фильтрами и пагинацией.
    Returns: (list of dicts, total count)."""
    conn = get_conn()
    where_clauses = []
    params = []
    if filters:
        if filters.get("q"):
            q = f"%{filters['q']}%"
            where_clauses.append("(designation LIKE ? OR name LIKE ? OR model LIKE ? OR material LIKE ? OR chassis LIKE ?)")
            params.extend([q, q, q, q, q])
        if filters.get("status"):
            where_clauses.append("(SELECT status FROM drafts WHERE detail_id=details.id) = ?")
            params.append(filters["status"])
        if filters.get("model"):
            where_clauses.append("model = ?")
            params.append(filters["model"])
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    count_row = conn.execute(f"SELECT COUNT(*) FROM details {where_sql}", params).fetchone()
    total = count_row[0] if count_row else 0
    per_page = max(1, min(100, per_page))
    page = max(1, page)
    offset = (page - 1) * per_page
    rows = conn.execute(f"""
        SELECT d.id, d.designation, d.name, d.model, d.chassis, d.material, d.mass_kg,
               d.surface_treatment, d.created_at,
               COALESCE((SELECT status FROM drafts WHERE detail_id=d.id), 'new') as status
        FROM details d
        {where_sql}
        ORDER BY d.created_at DESC LIMIT ? OFFSET ?""", params + [per_page, offset]).fetchall()
    conn.close()
    return [dict(r) for r in rows], total


def get_distinct_models() -> list:
    """Список уникальных моделей для фильтра"""
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT model FROM details WHERE model IS NOT NULL AND model != '' ORDER BY model").fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


# ========== CRUD: drafts ==========
def get_draft(detail_id: str) -> Optional[dict]:
    """Получает draft (и output) для детали"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM drafts WHERE detail_id=?", (detail_id,)).fetchone()
    conn.close()
    if not row:
        return None
    result = dict(row)
    if result.get("llm_output"):
        try:
            result["output"] = json.loads(result["llm_output"])
        except Exception:
            result["output"] = None
    return result


def save_draft(detail_id: str, llm_output: dict, status: str = "draft", author: str = "", status_ext: str = None):
    conn = get_conn()
    conn.execute("""INSERT INTO drafts (detail_id, llm_output, status, author, status_ext)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(detail_id) DO UPDATE SET
            llm_output=excluded.llm_output, status=excluded.status,
            author=excluded.author, status_ext=COALESCE(excluded.status_ext, drafts.status_ext),
            updated_at=CURRENT_TIMESTAMP""",
        (detail_id, json.dumps(llm_output, ensure_ascii=False), status, author, status_ext))
    conn.commit()
    conn.close()


def update_draft_status(detail_id: str, status: str, status_ext: str = None, approver: str = ""):
    conn = get_conn()
    if status_ext:
        conn.execute("""UPDATE drafts SET status=?, status_ext=?, approver=COALESCE(NULLIF(?, ''), approver),
            submitted_at=CASE WHEN ?='review' THEN CURRENT_TIMESTAMP ELSE submitted_at END
            WHERE detail_id=?""", (status, status_ext, approver, status_ext, detail_id))
    else:
        conn.execute("""UPDATE drafts SET status=?, approver=COALESCE(NULLIF(?, ''), approver)
            WHERE detail_id=?""", (status, approver, detail_id))
    conn.commit()
    conn.close()


# ========== Versions & Edits ==========
def get_versions(detail_id: str) -> list:
    conn = get_conn()
    rows = conn.execute("""SELECT version, operations_json, author, source, notes, created_at
        FROM draft_versions WHERE detail_id=? ORDER BY version DESC""", (detail_id,)).fetchall()
    conn.close()
    return [{"version": r[0], "operations_json": r[1], "author": r[2],
             "source": r[3], "notes": r[4], "created_at": r[5]} for r in rows]


def get_edits(detail_id: str) -> list:
    conn = get_conn()
    rows = conn.execute("""SELECT field, old_value, new_value, reason, author, created_at
        FROM edits WHERE detail_id=? ORDER BY id DESC LIMIT 50""", (detail_id,)).fetchall()
    conn.close()
    return [{"field": r[0], "old_value": r[1], "new_value": r[2],
             "reason": r[3], "author": r[4], "created_at": r[5]} for r in rows]


# ========== Справочники ==========
def get_all_equipment() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM equipment ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_materials() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM materials ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_iot() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM iot ORDER BY number").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ========== History ==========
def add_history(detail_id: str, action: str, details: dict = None):
    conn = get_conn()
    conn.execute("INSERT INTO history (detail_id, action, details) VALUES (?, ?, ?)",
                 (detail_id, action, json.dumps(details or {}, ensure_ascii=False)))
    conn.commit()
    conn.close()


def get_history(detail_id: str = None, limit: int = 100) -> list:
    """Если detail_id указан — история по детали, иначе общая"""
    conn = get_conn()
    if detail_id:
        rows = conn.execute("""SELECT detail_id, action, details, ts FROM history
            WHERE detail_id=? ORDER BY ts DESC LIMIT ?""", (detail_id, limit)).fetchall()
    else:
        rows = conn.execute("""SELECT detail_id, action, details, ts FROM history
            ORDER BY ts DESC LIMIT ?""", (limit,)).fetchall()
    conn.close()
    return [{"detail_id": r[0], "action": r[1], "details": r[2], "ts": r[3]} for r in rows]


# ========== Pilot metrics ==========
def get_daily_cost(date_str: str = None) -> dict:
    """Расход за день. Устойчив к отсутствию таблицы."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    conn = None
    try:
        conn = get_conn()
        row = conn.execute("""SELECT
            COALESCE(SUM(cost_rub), 0) as total, COUNT(*) as calls,
            COALESCE(SUM(tokens_in), 0) as tokens_in,
            COALESCE(SUM(tokens_out), 0) as tokens_out
            FROM llm_calls WHERE DATE(created_at, 'localtime') = ? AND cost_rub > 0""",
            (date_str,)).fetchone()
    except Exception:
        row = (0, 0, 0, 0)
    finally:
        if conn:
            try: conn.close()
            except Exception: pass
    return {
        "date": date_str,
        "total_rub": round(row[0] or 0, 4),
        "calls": row[1] or 0,
        "tokens_in": row[2] or 0,
        "tokens_out": row[3] or 0,
        "limit_rub": 200.0,
        "remaining_rub": round(200.0 - (row[0] or 0), 4),
        "exceeded": (row[0] or 0) >= 200.0
    }


def get_pilot_metrics() -> dict:
    """Агрегированные метрики пилота"""
    conn = get_conn()
    total_processed = conn.execute("""SELECT COUNT(DISTINCT detail_id) FROM (
        SELECT detail_id FROM drafts WHERE status IN ('draft', 'approved', 'review')
        UNION SELECT detail_id FROM pilot_metrics WHERE metric='time_to_card_min'
    )""").fetchone()[0] or 0
    avg_edits = conn.execute("""SELECT AVG(cnt) FROM (
        SELECT detail_id, COUNT(*) as cnt FROM edits GROUP BY detail_id
    )""").fetchone()[0] or 0
    accepted_row = conn.execute("""SELECT
        COALESCE(SUM(CASE WHEN metric='accepted_op' THEN value ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN metric='total_ops' THEN value ELSE 0 END), 1)
        FROM pilot_metrics""").fetchone()
    accepted_pct = (accepted_row[0] / accepted_row[1] * 100) if accepted_row[1] else 0
    avg_time = conn.execute("""SELECT AVG(value) FROM pilot_metrics
        WHERE metric='time_to_card_min'""").fetchone()[0] or 0
    total_cost = conn.execute("""SELECT COALESCE(SUM(cost_rub), 0) FROM llm_calls
        WHERE cost_rub > 0""").fetchone()[0] or 0
    total_gens = conn.execute("""SELECT COUNT(*) FROM llm_calls
        WHERE error IS NULL AND response_parsed_ok=1""").fetchone()[0] or 0
    conn.close()
    return {
        "total_details_processed": total_processed,
        "edits_per_card": round(avg_edits, 2),
        "accepted_pct": round(accepted_pct, 1),
        "avg_time_to_card_min": round(avg_time, 1),
        "total_llm_cost_rub": round(total_cost, 2),
        "total_successful_gens": total_gens,
        "kpi": {
            "time_target": 60,
            "accepted_target": 30,
            "edits_target": 8
        }
    }
