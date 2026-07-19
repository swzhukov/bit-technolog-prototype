"""
metrics_auto.py — автоматический сбор метрик пилота (v0.4.9, F16.1).
Выделено для тестируемости. Раньше метрики собирались вручную через формы.
Теперь:
- session_start: при открытии карточки
- time_to_card: при approve (delta от session_start)
- accepted_op / total_ops / edits_count: при approve (diff llm_output vs final)
"""
import json
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger("bit-technolog")


def compute_acceptance_from_versions(detail_id: str) -> dict:
    """Сравнивает первую AI-генерацию с текущим состоянием черновика.
    Возвращает:
        {
            "total_ops": N,           # операций в финале
            "accepted_ops": M,        # без изменений
            "edited_ops": K,          # изменённые
            "added_ops": A,           # добавленные
            "deleted_ops": D,         # удалённые
            "edits_count": K + A + D  # все правки
        }
    Использует draft_versions: source='llm_generate' (оригинал) vs
    последняя версия (или current llm_output).
    """
    from db import get_conn
    conn = get_conn()
    try:
        # Оригинальные операции из первой llm_generate версии
        orig_row = conn.execute("""SELECT operations_json FROM draft_versions
            WHERE detail_id=? AND source='llm_generate'
            ORDER BY version ASC LIMIT 1""", (detail_id,)).fetchone()
        if not orig_row:
            # Нет AI-генерации — нечего сравнивать
            return {"total_ops": 0, "accepted_ops": 0, "edited_ops": 0,
                    "added_ops": 0, "deleted_ops": 0, "edits_count": 0}
        try:
            orig_ops = json.loads(orig_row[0])
        except Exception:
            orig_ops = []

        # Финальные операции из current draft (llm_output)
        draft_row = conn.execute("""SELECT llm_output FROM drafts WHERE detail_id=?""",
                                  (detail_id,)).fetchone()
        if not draft_row:
            return {"total_ops": 0, "accepted_ops": 0, "edited_ops": 0,
                    "added_ops": 0, "deleted_ops": 0, "edits_count": 0}
        try:
            draft = json.loads(draft_row[0])
        except Exception:
            draft = {}
        final_ops = draft.get("operations", [])

        # Сравнение по нормализованному ключу
        def _op_key(op):
            return (op.get("name", "").strip().lower(),
                    op.get("department", "").strip().lower(),
                    str(op.get("duration_hours", 0)))

        orig_keys = {_op_key(op): op for op in orig_ops}
        final_keys = {_op_key(op): op for op in final_ops}

        accepted = 0
        edited = 0
        for k, op in final_keys.items():
            if k in orig_keys:
                # Ключ совпал — но проверим поля детальнее
                orig_op = orig_keys[k]
                if (op.get("equipment") == orig_op.get("equipment") and
                    op.get("notes") == orig_op.get("notes")):
                    accepted += 1
                else:
                    edited += 1
            else:
                # Новый ключ — отредактированный name/dept/duration ИЛИ новая операция
                # Если name совпадает с одним из orig — отредактирован
                name = op.get("name", "").strip().lower()
                if any(o.get("name", "").strip().lower() == name for o in orig_ops):
                    edited += 1
                else:
                    # Добавлен
                    pass

        # Подсчёт added/deleted через name
        orig_names = {op.get("name", "").strip().lower() for op in orig_ops}
        final_names = {op.get("name", "").strip().lower() for op in final_ops}
        added = len(final_names - orig_names)
        deleted = len(orig_names - final_names)

        total = len(final_ops)
        edits_count = edited + added + deleted
        return {
            "total_ops": total,
            "accepted_ops": accepted,
            "edited_ops": edited,
            "added_ops": added,
            "deleted_ops": deleted,
            "edits_count": edits_count
        }
    finally:
        conn.close()


def record_session_start(detail_id: str, author: str = "technologist"):
    """Записать момент открытия карточки (auto-timer)."""
    from db import get_conn
    conn = get_conn()
    try:
        conn.execute("""INSERT INTO pilot_metrics (detail_id, metric, value, extra)
            VALUES (?, 'session_start', ?, ?)""",
            (detail_id, datetime.now().timestamp(),
             json.dumps({"author": author, "ts": datetime.now().isoformat()}, ensure_ascii=False)))
        conn.commit()
    except Exception as e:
        log.error(f"record_session_start failed: {e}")
    finally:
        conn.close()


def compute_time_to_card(detail_id: str) -> Optional[float]:
    """Посчитать минуты от последнего session_start до сейчас."""
    from db import get_conn
    conn = get_conn()
    try:
        row = conn.execute("""SELECT value FROM pilot_metrics
            WHERE detail_id=? AND metric='session_start'
            ORDER BY created_at DESC LIMIT 1""", (detail_id,)).fetchone()
        if not row:
            return None
        started = datetime.fromtimestamp(row[0])
        elapsed = (datetime.now() - started).total_seconds() / 60
        return round(max(0.1, elapsed), 1)
    except Exception as e:
        log.error(f"compute_time_to_card failed: {e}")
        return None
    finally:
        conn.close()
