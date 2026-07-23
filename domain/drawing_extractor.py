"""
Sprint 7 D3: LLM extraction из OCR text чертежа.

Промт извлекает структурированные данные: designation, name, material,
dimensions, mass, surface_treatment, gost, raw_components.
"""
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# Промт для LLM
EXTRACTION_PROMPT = """Ты — инженер-технолог машиностроительного завода. Проанализируй текст с чертежа детали и извлеки структурированные данные.

Текст с чертежа (OCR):
---
{ocr_text}
---

Извлеки ТОЛЬКО следующие поля (верни валидный JSON, без markdown-обёрток, без пояснений):

{{
  "designation": "обозначение по ГОСТ 2.201 (например, 03-ТВ.30.119.01). Если не найдено — null",
  "name": "наименование детали (например, Кронштейн). Если не найдено — null",
  "level": "тип: detail | assembly | standard_item. По умолчанию detail",
  "material": "материал (например, Труба 60х40х3.0 ГОСТ 8645-68, Сталь 35Х, ...). Если не найдено — null",
  "gost": "ГОСТ на материал (если указан). null если не указан",
  "dimensions": "габаритные размеры в мм (например, 200x100x50). null если не найдено",
  "mass_kg": "масса в кг (число, например, 0.45). null если не указана",
  "surface_treatment": "покрытие/обработка поверхности (если указано). null если нет",
  "raw_components": [
    {{"designation": "...", "name": "...", "quantity": 1, "material": "..."}}
  ],
  "author": "ФИО разработчика (если указано). null если нет",
  "drawing_date": "дата чертежа (YYYY-MM-DD если возможно). null если нет",
  "notes": "любые дополнительные заметки (допуски, шероховатость, и т.п.). null если нет"
}}

Правила:
1. Если поле не найдено в тексте — ставь null
2. Не выдумывай данных, которых нет в тексте
3. Обозначение обычно содержит точки, цифры, иногда буквы (например, "03-ТВ.30.119.01")
4. Наименование — короткое слово или 2-3 слова (Кронштейн, Заглушка, Труба, Вал, и т.п.)
5. Материал обычно указан как "Материал: ..." или в графе "Материал"
6. Размеры могут быть в формате "L=200мм" или "200×100" или "Ø50"
7. raw_components — это составные части сборочного чертежа (если это сборочный)

Верни ТОЛЬКО JSON, ничего больше."""


def extract_with_llm(ocr_text: str, llm_provider: Optional[Any] = None) -> Tuple[bool, Dict[str, Any], str]:
    """Извлечь structured data из OCR text через LLM.
    
    Returns: (success, parsed_dict, error_or_empty)
    """
    if not ocr_text or not ocr_text.strip():
        return False, {}, "empty OCR text"
    
    # Lazy import
    from domain.llm_provider import call_llm
    
    prompt = EXTRACTION_PROMPT.format(ocr_text=ocr_text[:3000])  # limit 3000 chars
    
    try:
        result = call_llm(
            task_type="ocr_pdf",
            prompt=prompt,
            temperature=0.0,  # детерминированный
            max_tokens=1000,
        )
        
        # Парсим JSON из ответа
        text = result.get("text", "").strip() if isinstance(result, dict) else str(result).strip()
        
        # Чистим markdown-обёртки
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
        
        # Парсим JSON
        try:
            data = json.loads(text)
        except json.JSONDecodeError as je:
            logger.warning(f"LLM returned invalid JSON, falling back to regex: {je}, text: {text[:200]}")
            return True, extract_with_regex(ocr_text), f"json_fallback: {je}"
        
        if not isinstance(data, dict):
            return False, {}, f"LLM returned non-dict: {type(data)}"
        
        return True, data, ""
    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}, text: {text[:200]}")
        return False, {}, f"invalid JSON: {e} (raw: {text[:100]})"
    except Exception as e:
        logger.exception("LLM extraction failed")
        return False, {}, f"LLM error: {e}"


def extract_with_regex(ocr_text: str) -> Dict[str, Any]:
    """Fallback: regex-парсинг для простых случаев (когда LLM недоступна)."""
    result = {
        "designation": None,
        "name": None,
        "level": "detail",
        "material": None,
        "gost": None,
        "dimensions": None,
        "mass_kg": None,
        "surface_treatment": None,
        "raw_components": [],
        "author": None,
        "drawing_date": None,
        "notes": None,
    }
    
    if not ocr_text:
        return result
    
    # Designation: pattern like XX-XX.XX.XXX or XX.XXXXX.XXX
    desig_match = re.search(r"\b(\d{2,3}[-.]?[А-Яа-я]{1,3}[-.]\d{2,3}[-.]\d{2,4}[-.]\d{2,3})\b", ocr_text)
    if desig_match:
        result["designation"] = desig_match.group(1).replace(" ", "")
    
    # ГОСТ
    gost_match = re.search(r"ГОСТ\s*(\d+[-.]?\d*[-.]?\d*)", ocr_text, re.IGNORECASE)
    if gost_match:
        result["gost"] = "ГОСТ " + gost_match.group(1)
    
    # Размеры: L=200мм или 200x100x50
    dim_match = re.search(r"[L=L]\s*=?\s*(\d+)\s*(мм|mm)?", ocr_text, re.IGNORECASE)
    if dim_match:
        result["dimensions"] = f"{dim_match.group(1)}мм"
    
    return result
