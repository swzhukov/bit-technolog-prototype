"""
notices.py — Извещения (change_notices) end-to-end.

Sprint 6.

Workflow (по разбору v2):
1. Регистрация извещения (number, date, foundation_doc, reason)
2. Автопоиск затронутых items через bom_links (вниз по дереву)
3. AI diff «было → стало» (тип задачи notice_diff)
4. Подтверждение технологом
5. Пересчёт РС для всех затронутых ТК
6. Трассировка причины в resource_specs.change_reason = № извещения

ГОСТ 2.503 (примерная структура):
- number: И-YYYY-NNN
- date: дата
- foundation_doc: основание (приказ/решение)
- reason: причина изменения
- description: описание
- status: open / in_progress / resolved / cancelled

Без emoji в UI, простой русский язык (для 50+ технолога).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from repositories import db
from domain.llm_provider import call_llm, parse_llm_json_safe
from services.rs_factory import build_rs, DEFAULT_PROFILE

logger = logging.getLogger(__name__)


# ============================================================
# СТАТУСЫ ИЗВЕЩЕНИЯ (русский для UI)
# ============================================================

NOTICE_STATUSES = {
    "open": "Требует решения",
    "in_progress": "В работе",
    "resolved": "Решено",
    "cancelled": "Отменено",
}


# ============================================================
# СОЗДАНИЕ
# ============================================================

def create_notice(
    number: str,
    date: str,
    foundation_doc: str,
    reason: str,
    description: str = "",
    author: str = "Технолог",
    affected_item_designation: str = "",
) -> int:
    """Создать новое извещение. Возвращает ID."""
    notice_id = db.insert_and_get_id("change_notices", {
        "number": number,
        "date": date,
        "author": author,
        "status": "open",
        "foundation_doc": foundation_doc,
        "reason": reason,
        "description": description,
        "affected_items_json": json.dumps([], ensure_ascii=False),
    })

    # Если указана деталь — поиск затронутых
    if affected_item_designation:
        affected = find_affected_items(affected_item_designation)
        save_affected_items(notice_id, affected)

    return notice_id


# ============================================================
# ПОИСК ЗАТРОНУТЫХ (bom_links)
# ============================================================

def find_affected_items(root_designation: str) -> List[Dict[str, Any]]:
    """Найти все items, которые входят в root_designation (вниз по дереву через bom_links).

    Возвращает список: {item_id, designation, name, level, impact_type, qty}
    impact_type: 'direct' (сама деталь) | 'parent' (сборка, в которую входит) | 'sibling' (одного уровня)
    """
    # Найти корневой item
    root = db.query_one("SELECT * FROM items WHERE designation = ?", (root_designation,))
    if not root:
        return []

    affected = [{
        "item_id": root["id"],
        "designation": root["designation"],
        "name": root["name"],
        "level": root["level"],
        "impact_type": "direct",
        "qty": 1,
    }]

    # Все родители (сборки, в которые входит эта деталь)
    parents = db.query("""
        SELECT i.*, b.qty FROM bom_links b
        JOIN items i ON i.id = b.parent_item_id
        WHERE b.child_item_id = ?
    """, (root["id"],))
    for p in parents:
        affected.append({
            "item_id": p["id"],
            "designation": p["designation"],
            "name": p["name"],
            "level": p["level"],
            "impact_type": "parent",
            "qty": p["qty"] or 1,
        })

    # Все дети (что входит в эту деталь)
    children = db.query("""
        SELECT i.*, b.qty FROM bom_links b
        JOIN items i ON i.id = b.child_item_id
        WHERE b.parent_item_id = ?
    """, (root["id"],))
    for c in children:
        affected.append({
            "item_id": c["id"],
            "designation": c["designation"],
            "name": c["name"],
            "level": c["level"],
            "impact_type": "child",
            "qty": c["qty"] or 1,
        })

    return affected


def save_affected_items(notice_id: int, affected: List[Dict[str, Any]]) -> None:
    """Сохранить список затронутых items в извещение."""
    db.execute(
        "UPDATE change_notices SET affected_items_json = ? WHERE id = ?",
        (json.dumps(affected, ensure_ascii=False), notice_id)
    )


# ============================================================
# AI DIFF (через LLM)
# ============================================================

def generate_ai_diff(notice_id: int) -> Dict[str, Any]:
    """Сгенерировать diff через LLM (тип задачи notice_diff)."""
    notice = db.query_one("SELECT * FROM change_notices WHERE id = ?", (notice_id,))
    if not notice:
        return {"error": "notice not found"}

    affected = []
    try:
        affected = json.loads(notice["affected_items_json"] or "[]")
    except json.JSONDecodeError:
        pass

    prompt = f"""
Извещение об изменении: №{notice['number']}
Дата: {notice['date']}
Основание: {notice['foundation_doc']}
Причина изменения: {notice['reason']}
Описание: {notice['description']}
Затронуто изделий: {len(affected)}

Сгенерируй diff в формате JSON:
{{
  "changes": [
    {{"field": "название поля", "was": "старое", "now": "новое", "impact": "влияние"}}
  ],
  "affected_operations": [15, 20],
  "recommendation": "рекомендация технологу"
}}
"""
    result = call_llm("notice_diff", prompt=prompt, user=notice["author"] or "system")
    diff = result.parse_json()
    if not diff:
        diff = {"changes": [], "affected_operations": [], "recommendation": "AI не смог обработать"}

    return diff


# ============================================================
# ОБРАБОТКА (принятие решения)
# ============================================================

def resolve_notice(
    notice_id: int,
    user: str,
    user_decision: str,  # "accept_ai" | "manual_review" | "reject"
    notes: str = "",
) -> Dict[str, Any]:
    """Обработать извещение: принять решение технолога.

    Returns: {status, affected_count, regenerated_rs_count}
    """
    notice = db.query_one("SELECT * FROM change_notices WHERE id = ?", (notice_id,))
    if not notice:
        return {"error": "notice not found"}

    affected = []
    try:
        affected = json.loads(notice["affected_items_json"] or "[]")
    except json.JSONDecodeError:
        pass

    # Если принято AI — пересчитать РС для всех затронутых
    rs_regenerated = 0
    if user_decision == "accept_ai":
        for item in affected:
            item_id = item.get("item_id")
            if not item_id:
                continue
            # Найти последнюю ТК для этого item
            tc = db.query_one("""
                SELECT id FROM tech_cards WHERE item_id = ? ORDER BY version DESC LIMIT 1
            """, (item_id,))
            if not tc:
                continue
            # Пересчитать РС (через rs_factory)
            tc_full = db.get_tech_card_full(tc["id"])
            operations = tc_full.get("operations", [])
            if not operations:
                continue
            report = build_rs(
                item_designation=item.get("designation", ""),
                operations=operations,
                profile=DEFAULT_PROFILE,
                tech_card_id=tc["id"],
            )
            # Сохранить РС с change_reason
            db.insert_and_get_id("resource_specs", {
                "item_id": item_id,
                "tech_card_id": tc["id"],
                "tech_card_version": tc_full.get("version", 1),
                "rs_profile_id": None,
                "status": "draft",
                "ref_1c": None,
                "version_1c": None,
                "change_reason": f"{notice['number']}: {notice['reason']}",
                "content_json": json.dumps(report.to_dict(), ensure_ascii=False),
            })
            rs_regenerated += 1

    # Обновить статус извещения
    new_status = "resolved" if user_decision in ("accept_ai", "reject") else "in_progress"
    db.execute("""
        UPDATE change_notices
        SET status = ?, user_decision = ?, decided_at = ?, decided_by = ?
        WHERE id = ?
    """, (new_status, user_decision, datetime.now().isoformat(), user, notice_id))

    return {
        "status": "ok",
        "notice_id": notice_id,
        "user_decision": user_decision,
        "affected_count": len(affected),
        "rs_regenerated": rs_regenerated,
    }


# ============================================================
# СПИСОК
# ============================================================

def list_notices(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Список извещений."""
    sql = "SELECT * FROM change_notices WHERE 1=1"
    params: list = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY date DESC LIMIT ?"
    params.append(limit)
    return db.rows_to_dicts(db.query(sql, tuple(params)))


def get_notice(notice_id: int) -> Optional[Dict[str, Any]]:
    """Получить извещение по ID с affected_items."""
    notice = db.query_one("SELECT * FROM change_notices WHERE id = ?", (notice_id,))
    if not notice:
        return None
    d = dict(notice)
    try:
        d["affected_items"] = json.loads(d.get("affected_items_json") or "[]")
    except json.JSONDecodeError:
        d["affected_items"] = []
    return d


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    print("=== Notices service ===")
    # Создать тестовое извещение
    n = list_notices(limit=5)
    print(f"Извещений в БД: {len(n)}")
    for x in n:
        print(f"  {x['number']} ({x['date']}): {x['reason'][:50]}... — {x['status']}")
