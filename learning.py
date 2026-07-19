"""
learning.py — модуль метрик обучения RAG (v0.4.9, F15 + RAG-learning endpoint).
Содержит: get_learning_metrics_by_week, для дашборда /pilot/learning.
"""
import sqlite3
from datetime import datetime, timedelta


def get_learning_metrics_by_week(weeks: int = 4) -> list:
    """Возвращает список метрик по неделям для графика 'AI учится'.
    Метрики: total_generations, accepted_pct, avg_time_min, edits_per_card.

    Weeks = сколько последних недель (1-12). Default 4.
    """
    from db import get_conn
    conn = get_conn()
    now = datetime.now()
    result = []
    for w in range(weeks, 0, -1):
        week_start = now - timedelta(weeks=w)
        week_end = now - timedelta(weeks=w - 1)
        ws = week_start.strftime("%Y-%m-%d")
        we = week_end.strftime("%Y-%m-%d")
        # Total generations (llm_calls) за неделю
        total_gens = conn.execute("""SELECT COUNT(*) FROM llm_calls
            WHERE date(created_at) >= ? AND date(created_at) < ? AND response_parsed_ok=1""",
            (ws, we)).fetchone()[0] or 0
        # Accepted percentage (метрики accepted_op / total_ops)
        accepted = conn.execute("""SELECT
            COALESCE(SUM(CASE WHEN metric='accepted_op' THEN value ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN metric='total_ops' THEN value ELSE 0 END), 0)
            FROM pilot_metrics
            WHERE metric IN ('accepted_op', 'total_ops') AND date(created_at) >= ? AND date(created_at) < ?""",
            (ws, we)).fetchone()
        accepted_pct = (accepted[0] / accepted[1] * 100) if accepted[1] else 0
        # Avg time to card
        avg_time = conn.execute("""SELECT AVG(value) FROM pilot_metrics
            WHERE metric='time_to_card_min' AND date(created_at) >= ? AND date(created_at) < ?""",
            (ws, we)).fetchone()[0] or 0
        # Edits per card
        edits_count = conn.execute("""SELECT COUNT(*) FROM pilot_metrics
            WHERE metric='edit' AND date(created_at) >= ? AND date(created_at) < ?""",
            (ws, we)).fetchone()[0] or 0
        distinct_cards = conn.execute("""SELECT COUNT(DISTINCT detail_id) FROM pilot_metrics
            WHERE date(created_at) >= ? AND date(created_at) < ?""",
            (ws, we)).fetchone()[0] or 0
        edits_per_card = (edits_count / distinct_cards) if distinct_cards else 0
        result.append({
            "week_num": weeks - w + 1,  # 1=oldest, 4=newest
            "week_start": ws,
            "week_end": we,
            "total_generations": total_gens,
            "accepted_pct": round(accepted_pct, 1),
            "avg_time_min": round(avg_time, 1),
            "edits_per_card": round(edits_per_card, 2),
            "distinct_cards": distinct_cards
        })
    conn.close()
    return result
