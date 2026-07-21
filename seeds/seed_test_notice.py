"""
seed_test_notice.py — создать тестовое извещение для демо.

И-2026-014 (упоминается в dashboard как «требует решения»).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.notices import create_notice, resolve_notice, list_notices
from repositories import db


def seed_test_notice(verbose: bool = True) -> int:
    """Создать И-2026-014 (упоминается в дизайн-демо)."""
    # Проверим, есть ли уже
    existing = db.query_one("SELECT id FROM change_notices WHERE number = 'И-2026-014'")
    if existing:
        if verbose:
            print(f"⏭  И-2026-014 уже есть (id={existing['id']})")
        return existing["id"]

    nid = create_notice(
        number="И-2026-014",
        date="2026-07-21",
        foundation_doc="Решение главного конструктора №42 от 15.07.2026",
        reason="Замена материала днища с 09Г2С на 10ХСНД",
        description="Улучшение коррозионной стойкости в условиях морского климата. Применяется к изделиям АЦ-8,0-40.",
        author="Баранов А.Н.",
        affected_item_designation="ЛМША.301314.010",
    )
    if verbose:
        print(f"✅ Создано извещение И-2026-014 (id={nid})")
    return nid


if __name__ == "__main__":
    seed_test_notice()
    # Список
    ns = list_notices(limit=5)
    print(f"\nИзвещений в БД: {len(ns)}")
    for n in ns:
        print(f"  {n['number']} ({n['date']}): {n['reason'][:60]} — {n['status']}")
