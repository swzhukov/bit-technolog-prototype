"""Few-shot примеры: 3 примера для разных типов деталей (F16.3).

Изначально был 1 пример (сварочно-сборочный). Добавлены 2:
- FEW_SHOT_HYDRAULIC: гидравлический узел (типично для пожарной машины)
- FEW_SHOT_ELECTRICAL: электрический жгут
"""

FEW_SHOT_4C85941A = {
    "input": {
        "name": "Упор продольный",
        "designation": "ЛМША.301314.010",
        "material": "Сталь 3",
        "gost_material": "ГОСТ 16523-97",
        "mass_kg": 8.5,
        "dimensions_mm": {"x": 600, "y": 100, "z": 50},
        "surface_treatment": "оцинковка",
        "chassis": "various"
    },
    "output": {
        "summary": {
            "total_operations": 7,
            "total_hours": 4.2,
            "prep_hours": 0.5,
            "complexity": "средняя",
            "closest_analog": "ЛМША.301314.020"
        },
        "route": [
            {"step": 1, "operation": "010 Подготовительная", "duration_hours": 0.2},
            {"step": 2, "operation": "015 Установка ножей", "duration_hours": 0.5},
            {"step": 3, "operation": "020 Приварка ножей к основанию", "duration_hours": 0.6},
            {"step": 4, "operation": "025 Установка рёбер", "duration_hours": 0.7},
            {"step": 5, "operation": "030 Приварка рёбер", "duration_hours": 0.6},
            {"step": 6, "operation": "035 Установка настила, уголков, планок", "duration_hours": 0.8},
            {"step": 7, "operation": "040 Сварка", "duration_hours": 0.8}
        ],
        "operations": [
            {
                "name": "010 Подготовительная",
                "equipment": None,
                "duration_hours": 0.2,
                "duration_source": "экспертная оценка",
                "confidence": 75,
                "materials": ["проволока Св-08Г2С-О 1,0 ГОСТ 2246-70", "смесь газовая М21 ГОСТ Р ИСО 14175-2010"],
                "control_points": [],
                "gosts": [],
                "department": "Сварочно-сборочный КТ",
                "workplace": "01/01/04"
            },
            {
                "name": "015 Установка ножей (сборка под сварку)",
                "equipment": "Кедр-300",
                "duration_hours": 0.5,
                "duration_source": "аналог: ЛМША.301314.020",
                "confidence": 92,
                "materials": [],
                "control_points": ["ОТК визуальный"],
                "gosts": ["ГОСТ 3.1404-86"],
                "department": "Сварочно-сборочный КТ",
                "workplace": "01/01/04"
            },
            {
                "name": "020 Приварка ножей к основанию",
                "equipment": "Кедр-300",
                "duration_hours": 0.6,
                "duration_source": "аналог: ЛМША.301314.020",
                "confidence": 92,
                "materials": [],
                "control_points": ["ОТК визуальный", "ОТК измерительный"],
                "gosts": ["ГОСТ 3.1404-86"],
                "department": "Сварочно-сборочный КТ",
                "workplace": "01/01/04"
            },
            {
                "name": "025 Установка рёбер и приварка пластин",
                "equipment": "Кедр-300",
                "duration_hours": 0.7,
                "duration_source": "аналог: ЛМША.301314.020",
                "confidence": 85,
                "materials": ["пластина ЛМША.301714.006"],
                "control_points": ["ОТК визуальный"],
                "gosts": ["ГОСТ 3.1404-86"],
                "department": "Сварочно-сборочный КТ",
                "workplace": "01/01/04"
            },
            {
                "name": "030 Приварка рёбер к основанию",
                "equipment": "Кедр-300",
                "duration_hours": 0.6,
                "duration_source": "аналог: ЛМША.301314.020",
                "confidence": 85,
                "materials": [],
                "control_points": ["ОТК визуальный"],
                "gosts": ["ГОСТ 3.1404-86"],
                "department": "Сварочно-сборочный КТ",
                "workplace": "01/01/04"
            },
            {
                "name": "035 Установка настила, уголков, планок",
                "equipment": "Кедр-300",
                "duration_hours": 0.8,
                "duration_source": "аналог: ЛМША.301314.020",
                "confidence": 80,
                "materials": ["уголок", "планка", "пруток"],
                "control_points": ["ОТК визуальный", "ОТК измерительный"],
                "gosts": ["ГОСТ 3.1404-86"],
                "department": "Сварочно-сборочный КТ",
                "workplace": "01/01/04"
            },
            {
                "name": "040 Сварка",
                "equipment": "Кедр-300",
                "duration_hours": 0.8,
                "duration_source": "аналог: ЛМША.301314.020",
                "confidence": 85,
                "materials": [],
                "control_points": ["ОТК визуальный", "ОТК измерительный", "испытания"],
                "gosts": ["ГОСТ 3.1404-86", "ГОСТ 3.1703-79"],
                "department": "Сварочно-сборочный КТ",
                "workplace": "01/01/04"
            }
        ],
        "reasoning": {
            "operations_choice": "Операции 015-040 выбраны на основе аналога ЛМША.301314.020 (упор продольный, ближайший аналог). Все сварочные операции выполняются на аппарате Кедр-300 (единственное оборудование для сварки в цехе). Разряд сварщика — 4, код профессии 19905.",
            "duration_estimates": "Время операций рассчитано по аналогу 020. Коэффициент 1.0 (аналог с тем же материалом и габаритами).",
            "equipment_choice": "Кедр-300 — единственный аппарат механизированной сварки в сварочно-сборочном цехе КТ, рабочее место 04.",
            "risks": "Операции 025 и 035 имеют пониженную уверенность (80-85%) из-за различий в форме ножей. Требуется проверка технолога."
        },
        "warnings": [
            {
                "type": "missing_data",
                "quote": "surface_treatment: 'оцинковка'",
                "concern": "Не указана толщина цинкового покрытия (обычно 10-25 мкм)",
                "question": "Какая требуется толщина цинкового покрытия? 10, 15, 20 или 25 мкм?"
            },
            {
                "type": "ambiguous",
                "quote": "material: 'Сталь 3'",
                "concern": "Сталь 3 — устаревшее обозначение. Возможно, Ст3сп, Ст3пс, Ст3кп?",
                "question": "Какая марка стали точно? Ст3сп, Ст3пс или Ст3кп?"
            }
        ],
        "questions": [
            {
                "id": "Q1",
                "topic": "оцинковка",
                "question": "Толщина цинкового покрытия?",
                "options": ["10 мкм", "15 мкм", "20 мкм", "25 мкм", "не знаю"],
                "default": "15 мкм",
                "impact_if_changed": "Не влияет на время операций, но влияет на материальные затраты"
            },
            {
                "id": "Q2",
                "topic": "материал",
                "question": "Марка стали (Ст3сп, Ст3пс или Ст3кп)?",
                "options": ["Ст3сп", "Ст3пс", "Ст3кп", "не знаю"],
                "default": "Ст3сп",
                "impact_if_changed": "Может изменить трудоёмкость обработки на ±5-10%"
            }
        ]
    }
}


# ========== F16.3: Few-shot 2 — гидравлический узел ==========
FEW_SHOT_HYDRAULIC = {
    "input": {
        "name": "Клапан предохранительный",
        "designation": "ГБШ.634.21.014",
        "material": "Сталь 40Х",
        "gost_material": "ГОСТ 4543-71",
        "mass_kg": 1.8,
        "dimensions_mm": {"x": 90, "y": 70, "z": 120},
        "surface_treatment": "цинковое",
        "chassis": "АЦ-6,0-40"
    },
    "output": {
        "summary": {
            "total_operations": 9,
            "total_hours": 3.5,
            "prep_hours": 0.4,
            "complexity": "средняя",
            "closest_analog": "ГБШ.634.21.013"
        },
        "operations": [
            {"name": "010 Заготовительная", "equipment": "Ленточнопильный станок Bomar", "duration_hours": 0.15, "confidence": 90, "department": "Заготовительный"},
            {"name": "020 Токарная", "equipment": "Токарный 16К20", "duration_hours": 0.6, "confidence": 85, "department": "Механический"},
            {"name": "025 Токарная (чистовая)", "equipment": "Токарный 16К20", "duration_hours": 0.4, "confidence": 80, "department": "Механический"},
            {"name": "030 Фрезерная", "equipment": "Вертикально-фрезерный 6Р82", "duration_hours": 0.5, "confidence": 80, "department": "Механический"},
            {"name": "040 Сверлильная", "equipment": "Вертикально-сверлильный 2Н135", "duration_hours": 0.3, "confidence": 85, "department": "Механический"},
            {"name": "050 Термообработка", "equipment": "Печь СШО 8.16/10", "duration_hours": 0.4, "confidence": 75, "department": "Термический"},
            {"name": "060 Шлифовальная", "equipment": "Круглошлифовальный 3М151", "duration_hours": 0.4, "confidence": 80, "department": "Механический"},
            {"name": "070 Промывка", "equipment": "Установка промывки", "duration_hours": 0.15, "confidence": 95, "department": "Слесарный"},
            {"name": "080 Испытания на стенде", "equipment": "Стенд гидроиспытаний", "duration_hours": 0.6, "confidence": 90, "department": "Испытательный"}
        ],
        "warnings": [
            {"type": "missing_data", "quote": "mass_kg: 1.8", "concern": "Не указаны допуски на резьбовые соединения", "question": "Какой класс точности резьбы?"}
        ],
        "questions": [
            {"id": "Q1", "topic": "термообработка", "question": "Твёрдость после закалки?", "options": ["HRC 45-50", "HRC 50-55", "HRC 55-60"], "default": "HRC 50-55", "impact_if_changed": "Влияет на выбор режима термообработки"}
        ]
    }
}


# ========== F16.3: Few-shot 3 — электрический жгут ==========
FEW_SHOT_ELECTRICAL = {
    "input": {
        "name": "Жгут электрический приборной панели",
        "designation": "ЭЛ.468.91.005",
        "material": "Провод ПВ3 0,75",
        "mass_kg": 0.6,
        "dimensions_mm": {"x": 1500, "y": 80, "z": 40},
        "surface_treatment": "без покрытия",
        "chassis": "КАМАЗ-43118"
    },
    "output": {
        "summary": {
            "total_operations": 6,
            "total_hours": 2.2,
            "prep_hours": 0.3,
            "complexity": "низкая",
            "closest_analog": "ЭЛ.468.91.003"
        },
        "operations": [
            {"name": "010 Заготовка проводов", "equipment": "Станок зачистки/резки ZDBX-1", "duration_hours": 0.4, "confidence": 90, "department": "Электромонтажный"},
            {"name": "020 Обжимка наконечников", "equipment": "Пресс-клещи ПК-6", "duration_hours": 0.5, "confidence": 85, "department": "Электромонтажный"},
            {"name": "030 Сборка жгута на шаблоне", "equipment": "Шаблон сборочный", "duration_hours": 0.6, "confidence": 80, "department": "Электромонтажный"},
            {"name": "040 Изоляция (термоусадка, стяжки)", "equipment": "Термофен", "duration_hours": 0.3, "confidence": 85, "department": "Электромонтажный"},
            {"name": "050 Проверка целостности цепей", "equipment": "Мультиметр + тестер жгутов", "duration_hours": 0.25, "confidence": 95, "department": "Электромонтажный"},
            {"name": "060 Маркировка", "equipment": "Принтер Brady", "duration_hours": 0.15, "confidence": 90, "department": "Электромонтажный"}
        ],
        "warnings": [
            {"type": "missing_data", "quote": "material: 'Провод ПВ3 0,75'", "concern": "Не указана длина каждого провода", "question": "Есть ли таблица длин по схеме Э3?"}
        ],
        "questions": [
            {"id": "Q1", "topic": "разъем", "question": "Какой тип разъёмов на концах?", "options": ["AMP", "KET", "отечественные (2РМ, СНЦ)", "смешанные"], "default": "смешанные", "impact_if_changed": "Влияет на материалы и трудоёмкость"}
        ]
    }
}


# ========== F16.3: Удобный список всех few-shot примеров ==========
FEW_SHOT_EXAMPLES = [
    ("Сварочно-сборочный (упор)", FEW_SHOT_4C85941A),
    ("Гидравлика (клапан)", FEW_SHOT_HYDRAULIC),
    ("Электрика (жгут)", FEW_SHOT_ELECTRICAL),
]


def get_relevant_few_shot(detail: dict) -> dict:
    """F16.3: выбирает few-shot по типу детали (по названию/материалу).
    Возвращает один из FEW_SHOT_EXAMPLES."""
    name = (detail.get("name") or "").lower()
    material = (detail.get("material") or "").lower()
    if any(w in name for w in ("жгут", "провод", "кабель", "электр")):
        return FEW_SHOT_ELECTRICAL
    if any(w in name for w in ("клапан", "насос", "гидро", "цилиндр", "шток", "поршень")):
        return FEW_SHOT_HYDRAULIC
    if any(w in material for w in ("провод", "пв3", "пв1")):
        return FEW_SHOT_ELECTRICAL
    return FEW_SHOT_4C85941A  # default: сварочно-сборочный
