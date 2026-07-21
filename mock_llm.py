"""
mock_llm.py — обёртка для LLM, возвращающая предсказуемые мок-ответы.

Используется когда:
- LLM_API_KEY не задан или невалиден (auth_error)
- DEMO_MODE=true (включается в /admin/settings или .env)
- В тестах (pytest)

Возвращает JSON в том же формате, что и реальный LLM, чтобы flow
генерации ТК, уточняющих вопросов и обоснования работал без API.
"""
import json
import time
import random
from typing import Optional


# ============ Мок-операции для Упор продольный ЛМША.301314.010 ============
MOCK_OPS_UPOR_PRODOLNYI = [
    {
        "op_number": "005",
        "name": "Комплектование",
        "equipment": "Уч. упоров · РМ 04",
        "profession": "Комплектовщик, 2 разр.",
        "time_setup_min": 2.0,
        "time_per_unit_min": 16.0,
        "material": "",
        "notes": "Подбор деталей по спецификации",
    },
    {
        "op_number": "015",
        "name": "Сборка и прихватка ножей",
        "equipment": "Кедр-300",
        "profession": "Сварщик 19905, 4 разр.",
        "time_setup_min": 8.0,
        "time_per_unit_min": 58.0,
        "material": "Св-08Г2С-О ⌀1,0 — 0,12 кг; Смесь М21 — 0,09 м³; Спрей антипригарный — 0,02 л",
        "notes": "Установить ножи (2 шт) на основание по эскизу, прихватить",
    },
    {
        "op_number": "020",
        "name": "Приварка ножей к основанию",
        "equipment": "Кедр-300",
        "profession": "Сварщик 19905, 4 разр.",
        "time_setup_min": 10.0,
        "time_per_unit_min": 77.0,
        "material": "Св-08Г2С-О — 0,31 кг; М21 — 0,22 м³",
        "notes": "Сварка механизированная в среде М21",
    },
    {
        "op_number": "025",
        "name": "Установка рёбер, приварка пластин ЛМША.301714.006",
        "equipment": "Кедр-300",
        "profession": "Сварщик, 4 разр.",
        "time_setup_min": 12.0,
        "time_per_unit_min": 96.0,
        "material": "Св-08Г2С-О — 0,28 кг",
        "notes": "Установить 4 ребра и 2 пластины",
    },
    {
        "op_number": "030",
        "name": "Зачистка сварных швов",
        "equipment": "УШМ · верстак",
        "profession": "Слесарь, 3 разр.",
        "time_setup_min": 5.0,
        "time_per_unit_min": 34.0,
        "material": "",
        "notes": "Зачистка по контуру швов (12 мин/пог.м)",
    },
    {
        "op_number": "035",
        "name": "Контроль ОТК + клеймение для ВП",
        "equipment": "Стол ОТК",
        "profession": "Контролёр",
        "time_setup_min": 4.0,
        "time_per_unit_min": 20.0,
        "material": "",
        "notes": "ВИК 100% швов, клеймение",
    },
]

# ============ Уточняющие вопросы AI ============
MOCK_CLARIFICATION_QUESTIONS = [
    {
        "question": "Тип сварки: механизированная в среде М21 (Кедр-300) или ручная дуговая?",
        "options": ["Механизированная MIG/MAG, М21", "Ручная дуговая, электроды УОНИ-13/55", "Полуавтоматическая, проволока"],
        "hint": "В эталонной ТК 4c85941a (упор .020) — механизированная"
    },
    {
        "question": "Контроль швов: ВИК 100% или выборочный?",
        "options": ["ВИК 100% (для ВП)", "Выборочный 30%", "ВИК + УЗК (для ответственных)"],
        "hint": "Для ВП обычно 100% по ГОСТ"
    },
    {
        "question": "Заготовка: листовой прокат (раскрой лазером) или готовая деталь?",
        "options": ["Лист 09Г2С 6мм, раскрой лазером", "Лист 09Г2С 8мм", "Готовая деталь (отливка)"],
        "hint": "Определяет операции 005-010 (раскрой/правка)"
    },
]

# ============ Аналоги из ведомости ============
MOCK_ANALOGS_UPOR = [
    {"designation": "ЛМША.301314.020", "name": "Упор продольный .020", "similarity": 0.97, "source": "Эталонная ТК 2022", "total_hours": 5.55},
    {"designation": "53Б-ТВ.01.21.00", "name": "Кронштейн замка", "similarity": 0.71, "source": "Ведомость 575 ДСЕ", "total_hours": 4.50},
    {"designation": "ЛМША.302400.001", "name": "Основа растяжки", "similarity": 0.64, "source": "Наряды 2025-26", "total_hours": 6.20},
]

# ============ Обоснование нормы для операции ============
MOCK_EVIDENCE_BY_OP = {
    "005": {
        "source": "factory_data",
        "level": "green",
        "description": "Факт завода. Ведомость трудоёмкости (575 ДСЕ): комплектование сварных узлов до 40 кг — 0,30 н/ч. Наряды за 12 мес: 0,28-0,33 н/ч (n=214). Взято среднее по ведомости.",
    },
    "015": {
        "source": "factory_data",
        "level": "green",
        "description": "Факт завода. Эталонная ТК 4c85941a (Упор ЛМША.301314.020, утв. Баранов, 2022): операция 015 = 1,10 н/ч. Деталь-аналог на 97% совпадает по составу.",
    },
    "020": {
        "source": "factory_data",
        "level": "green",
        "description": "Факт завода. Эталон 4c85941a: 1,45 н/ч. Наряды (уч. упоров, 2025-26): среднее 1,41, разброс 1,3-1,6 (n=380).",
    },
    "025": {
        "source": "analog_estimate",
        "level": "yellow",
        "description": "Оценка по аналогам. Точного эталона нет (в .010 рёбер больше, чем в .020). Аналоги: упор .020 — 1,55 · кронштейн замка — 1,7 · основа растяжки — 2,1. AI интерполировал по массе наплавленного металла. Проверьте.",
    },
    "030": {
        "source": "factory_data+rule",
        "level": "green",
        "description": "Факт завода + правило. Ранее AI ставил 0,50 (-25% к факту). После правила технолога «зачистка после мех. сварки = 12 мин/пог.м шва» — совпадает с нарядами (0,62-0,70).",
    },
    "035": {
        "source": "ai_guess",
        "level": "red",
        "description": "Гипотеза AI — подтвердите. В ведомости и нарядах контроль не выделен отдельной строкой. AI взял типовые 15% от сварочного времени. Укажите факт или примите — и следующая ТК получит уже «зелёное» значение (петля обучения).",
    },
}

# ============ Извещение: AI предложение правки ============
MOCK_NOTICE_DIFF = {
    "notice_id": "И-2026-014",
    "detail": "53-ТВ.05.02.001",
    "operation_changes": [
        {
            "op_number": "040",
            "name": "Сварка днища",
            "was": "Св-08Г2С-О · 1,9 кг · 3,2 н/ч",
            "now": "Св-08ХГСМА · 2,0 кг · 3,8 н/ч",
            "reason": "10ХСНД требует другой проволоки и подогрева кромок; +18% времени по аналогам сварки низколегированных",
        },
        {
            "op_number": "042",
            "name": "Подогрев кромок",
            "was": "— (не было)",
            "now": "+ новая операция · 0,4 н/ч",
            "reason": "Требование для 10ХСНД при δ>8 мм · подтвердить у сварочного технолога",
        },
        {
            "op_number": "070",
            "name": "Контроль швов",
            "was": "ВИК 100%",
            "now": "ВИК 100% (без изменений)",
            "reason": "—",
        },
    ],
    "affected_assy": ["Цистерна 53-ТВ.05.00.00", "Обечайка с днищами 53-ТВ.05.01.000"],
    "affected_config": "АЦ-8,0-40 · зав. №147",
}


def mock_llm_call(task: str, detail_id: str = "", context: dict = None) -> dict:
    """
    Имитация вызова LLM. Возвращает dict с полями:
    - text: str (raw LLM response)
    - parsed: dict (распарсенный JSON)
    - tokens_in, tokens_out: int
    - cost_rub: float
    - model: str (название мок-модели)
    - duration_ms: int
    """
    t0 = time.time()
    time.sleep(random.uniform(0.3, 0.8))  # имитация latency

    if task == "generate_tech_card":
        # Генерация черновика ТК
        design = context.get("designation", detail_id or "деталь")
        ops = MOCK_OPS_UPOR_PRODOLNYI  # мок — все детали получают упор как шаблон
        result = {
            "operations": ops,
            "analogs": MOCK_ANALOGS_UPOR,
            "confidence": 0.78,
            "model": "MockLLM-Technologist-v1",
        }
        text = json.dumps(result, ensure_ascii=False)
        tokens_in = 2500
        tokens_out = 1800
        model = "MockLLM-Technologist-v1"
    elif task == "clarification_questions":
        result = {"questions": MOCK_CLARIFICATION_QUESTIONS}
        text = json.dumps(result, ensure_ascii=False)
        tokens_in = 1800
        tokens_out = 600
        model = "MockLLM-Lite"
    elif task == "refine_tech_card":
        # Доработка ТК с учётом ответов
        ops = list(MOCK_OPS_UPOR_PRODOLNYI)
        # Поправим операции по типу сварки
        for op in ops:
            if "Сварка" in op.get("name", "") or "сварка" in op.get("name", ""):
                if "Смесь М21" in op.get("material", ""):
                    op["material"] = op["material"].replace("Спрей антипригарный — 0,02 л", "Спрей антипригарный — 0,02 л · подтверждено М21")
        result = {
            "operations": ops,
            "model": "MockLLM-Technologist-v1",
        }
        text = json.dumps(result, ensure_ascii=False)
        tokens_in = 3200
        tokens_out = 1500
        model = "MockLLM-Technologist-v1"
    elif task == "ocr_recognize":
        # OCR распознавание чертежа
        result = {
            "designation": context.get("expected_designation", "ЛМША.301314.010"),
            "material": "09Г2С",
            "dimensions": "560×180×120",
            "thickness_mm": 6.0,
            "mass_kg": 38.2,
            "blank_type": "Лист",
            "confidence": 0.72,
            "warnings": [],
        }
        text = json.dumps(result, ensure_ascii=False)
        tokens_in = 800
        tokens_out = 200
        model = "MockLLM-OCR-v1"
    elif task == "evidence_for_op":
        op_num = context.get("op_number", "005")
        result = MOCK_EVIDENCE_BY_OP.get(op_num, MOCK_EVIDENCE_BY_OP["005"])
        text = json.dumps(result, ensure_ascii=False)
        tokens_in = 1500
        tokens_out = 250
        model = "MockLLM-Lite"
    elif task == "notice_diff":
        result = MOCK_NOTICE_DIFF
        text = json.dumps(result, ensure_ascii=False)
        tokens_in = 2800
        tokens_out = 800
        model = "MockLLM-Technologist-v1"
    else:
        result = {"error": f"unknown task: {task}"}
        text = json.dumps(result, ensure_ascii=False)
        tokens_in = 500
        tokens_out = 100
        model = "MockLLM-Generic"

    duration_ms = int((time.time() - t0) * 1000)
    # Мок-стоимость (YandexGPT тариф)
    cost_rub = round((tokens_in / 1000 * 0.06) + (tokens_out / 1000 * 0.12), 4)

    return {
        "text": text,
        "parsed": result,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_rub": cost_rub,
        "model": model,
        "duration_ms": duration_ms,
    }


def is_mock_mode() -> bool:
    """Возвращает True если нужно использовать мок вместо реального LLM.
    Условия: 1) DEMO_MODE=true в settings/env, 2) LLM_API_KEY не задан или '__FILL__'."""
    from settings import get_setting
    demo = get_setting("DEMO_MODE", "false").lower() == "true"
    if demo:
        return True
    key = get_setting("LLM_API_KEY", "")
    if not key or key.startswith("__FILL"):
        return True
    return False


def safe_llm_call(task: str, detail_id: str = "", context: dict = None,
                  real_call_fn=None) -> dict:
    """
    Безопасный вызов LLM: если мок-режим → mock_llm_call,
    иначе real_call_fn(task, ...). Возвращает dict в едином формате.
    """
    if is_mock_mode() or real_call_fn is None:
        return mock_llm_call(task, detail_id, context)
    return real_call_fn(task, detail_id, context)
