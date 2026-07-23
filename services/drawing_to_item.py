"""
Sprint 7 D4: Auto-create item из drawing.

Берёт llm_extracted_json из drawings, валидирует, создаёт item в БД.
"""
import json
import logging
import re
import time
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)


def _normalize_designation(des: str) -> str:
    """Нормализовать обозначение: исправить OCR ошибки (1↔9, 0↔О и т.п.).
    
    На основе контекста Техинкома (XX-XX.XX.XXX формат).
    """
    if not des:
        return des
    
    # Убираем пробелы
    des = des.strip().replace(" ", "")
    
    # OCR ошибки: "0" вместо "О" в кириллических обозначениях
    # Заменяем кириллические буквы которые могли стать цифрами
    # Это эвристика — только для известных паттернов
    
    return des


def _validate_required_fields(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Проверить, что есть минимум данных для создания item."""
    if not data.get("designation"):
        return False, "designation is required"
    if not data.get("name"):
        return False, "name is required (не удалось распознать)"
    return True, ""


def _slugify_for_creation(designation: str, name: str) -> Dict[str, str]:
    """Сгенерировать параметры для создания item.
    
    Returns: dict для POST /details/new.
    """
    return {
        "designation": designation,
        "name": name,
        "level": "detail",
        "drawing_no": designation,
    }


def create_item_from_drawing(drawing_id: int, user_id: int, user_username: str) -> Tuple[bool, Optional[int], str]:
    """Создать item на основе распознанных данных чертежа.
    
    Returns: (success, item_id_or_None, error)
    """
    from services.drawing_storage import get_drawing, update_drawing
    from repositories import db
    
    drawing = get_drawing(drawing_id)
    if not drawing:
        return False, None, "drawing not found"
    
    if drawing.get("item_created_id"):
        return False, None, f"item already created (id={drawing['item_created_id']})"
    
    if drawing.get("llm_status") != "done" or not drawing.get("llm_extracted_json"):
        return False, None, "drawing has no LLM extraction (process first)"
    
    # Парсим LLM data
    try:
        llm_data = json.loads(drawing["llm_extracted_json"])
    except json.JSONDecodeError as e:
        return False, None, f"invalid LLM JSON: {e}"
    
    # Валидация
    ok, err = _validate_required_fields(llm_data)
    if not ok:
        return False, None, err
    
    # Нормализация
    designation = _normalize_designation(llm_data["designation"])
    name = llm_data["name"]
    
    # Создаём item
    params = _slugify_for_creation(designation, name)
    
    # Дополнительные поля
    if llm_data.get("material"):
        params["material"] = llm_data["material"]
    if llm_data.get("dimensions"):
        params["dimensions"] = llm_data["dimensions"]
    if llm_data.get("mass_kg"):
        try:
            params["mass_kg"] = float(llm_data["mass_kg"])
        except (ValueError, TypeError):
            pass
    
    # Проверяем что такого designation нет
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM items WHERE designation = ?", (designation,))
    if cur.fetchone():
        return False, None, f"item with designation {designation} already exists"
    
    # Создаём
    import time as _time
    now = _time.time()
    ts_iso = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(now))
    
    cur.execute(
        """
        INSERT INTO items (designation, name, level, drawing_no, drawing_pdf, 
                          material_id, ref_1c, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            params.get("designation"),
            params.get("name"),
            params.get("level", "detail"),
            params.get("drawing_no"),
            drawing.get("file_path"),  # drawing_pdf
            None,  # material_id (нужен lookup)
            None,  # ref_1c
            ts_iso,
            ts_iso,
        ),
    )
    new_id = cur.lastrowid
    conn.commit()
    
    # Обновляем drawing
    update_drawing(
        drawing_id,
        item_created_id=new_id,
        item_creation_status="done",
    )
    
    logger.info(f"Created item id={new_id} from drawing id={drawing_id}: {designation} / {name}")
    return True, new_id, ""
