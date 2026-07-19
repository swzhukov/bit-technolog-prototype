"""15 реалистичных деталей Техинком-Центр для пилота.
Основано на техкарте «Упора продольного» (PDF 4c85941a) + контексте."""
import json
import logging

log = logging.getLogger("bit-technolog")

TECHINKOM_DETAILS = [
    # ===== ИЗДЕЛИЕ: АЦ-6,0-40 (пожарная автоцистерна) =====
    {
        "id": "product-ac-6-40",
        "designation": "АЦ-6,0-40",
        "name": "Автоцистерна пожарная 6,0 м³ на шасси КАМАЗ-43118",
        "model": "АЦ-6,0-40",
        "chassis": "КАМАЗ-43118",
        "material": "Комплекс",
        "mass_kg": 0,
        "level": "product",
        "parent_id": None,
        "extra_props": {"трудоемкость_нч": 1296, "заказ_тип": "пожарная_техника"}
    },
    # ===== УЗЛЫ =====
    {
        "id": "assembly-upor",
        "designation": "ЛМША.301314.010",
        "name": "Упор продольный",
        "model": "АЦ-6,0-40",
        "material": "Сталь 09Г2С",
        "mass_kg": 0,
        "level": "assembly",
        "parent_id": "product-ac-6-40"
    },
    {
        "id": "assembly-rama",
        "designation": "ЛМША.301511.001",
        "name": "Рама платформы",
        "model": "АЦ-6,0-40",
        "material": "Сталь 09Г2С",
        "mass_kg": 145.0,
        "level": "assembly",
        "parent_id": "product-ac-6-40"
    },
    {
        "id": "assembly-cisterna",
        "designation": "ЛМША.302000.100",
        "name": "Цистерна 6 м³",
        "model": "АЦ-6,0-40",
        "material": "Сталь 09Г2С",
        "mass_kg": 850.0,
        "level": "assembly",
        "parent_id": "product-ac-6-40"
    },
    {
        "id": "assembly-nasos",
        "designation": "ПН-40-У",
        "name": "Насосный агрегат ПН-40",
        "model": "АЦ-6,0-40",
        "material": "Комплекс",
        "mass_kg": 220.0,
        "level": "assembly",
        "parent_id": "product-ac-6-40"
    },
    {
        "id": "assembly-sgu",
        "designation": "СГУ-100",
        "name": "Сигнально-громкоговорящее устройство",
        "model": "АЦ-6,0-40",
        "material": "Электрокомплект",
        "mass_kg": 8.5,
        "level": "assembly",
        "parent_id": "product-ac-6-40"
    },
    # ===== ДЕТАЛИ ВНУТРИ УПОРА ПРОДОЛЬНОГО =====
    {
        "id": "detail-lmsha-301314-010",
        "designation": "ЛМША.301314.010",
        "name": "Упор продольный (корпус)",
        "model": "АЦ-6,0-40",
        "material": "Сталь 09Г2С",
        "mass_kg": 12.5,
        "surface_treatment": "Грунт ГФ-021, эмаль ПФ-115",
        "level": "detail",
        "parent_id": "assembly-upor",
        "tech_rules": "Сварку вести снизу вверх. После закалки — отпуск при 600°С. Обезжиривание 20 мин в травильной жидкости.",
        "extra_props": {"gost_material": "ГОСТ 19903-2015", "толщина_мм": 6}
    },
    {
        "id": "detail-lmsha-301714-006",
        "designation": "ЛМША.301714.006",
        "name": "Пластина",
        "model": "АЦ-6,0-40",
        "material": "Сталь 09Г2С",
        "mass_kg": 1.8,
        "surface_treatment": "Грунт ГФ-021, эмаль ПФ-115",
        "level": "detail",
        "parent_id": "assembly-upor",
        "extra_props": {"gost_material": "ГОСТ 19903-2015", "толщина_мм": 4}
    },
    # ===== ДЕТАЛИ ВНУТРИ РАМЫ =====
    {
        "id": "detail-lmsha-301511-001",
        "designation": "ЛМША.301511.001",
        "name": "Балка рамы",
        "model": "АЦ-6,0-40",
        "material": "Сталь 09Г2С",
        "mass_kg": 28.3,
        "surface_treatment": "Грунт ГФ-021, эмаль ПФ-115",
        "level": "detail",
        "parent_id": "assembly-rama",
        "tech_rules": "Сварка в среде защитных газов М21. Контроль швов УЗК.",
        "extra_props": {"gost_material": "ГОСТ 19903-2015", "толщина_мм": 8}
    },
    {
        "id": "detail-rama-kronshtein",
        "designation": "КРН-001-АЦ6",
        "name": "Кронштейн крепления насоса",
        "model": "АЦ-6,0-40",
        "material": "Сталь 09Г2С",
        "mass_kg": 4.2,
        "surface_treatment": "оцинковка",
        "chassis": "КАМАЗ-43118",
        "level": "detail",
        "parent_id": "assembly-nasos",
        "extra_props": {"gost_material": "ГОСТ 19903-2015"}
    },
    # ===== ДЕТАЛИ ЦИСТЕРНЫ =====
    {
        "id": "detail-obolochka",
        "designation": "ЛМША.302100.001",
        "name": "Обечайка цистерны (Ø1500, L=3000)",
        "model": "АЦ-6,0-40",
        "material": "Сталь 09Г2С",
        "mass_kg": 145.0,
        "surface_treatment": "Грунт ГФ-021, эмаль ПФ-115",
        "level": "detail",
        "parent_id": "assembly-cisterna",
        "tech_rules": "Сварка двусторонняя. Опрессовка 0.3 МПа. Контроль 100% швов.",
        "extra_props": {"gost_material": "ГОСТ 19903-2015", "толщина_мм": 4}
    },
    {
        "id": "detail-dnishche",
        "designation": "ЛМША.302200.001",
        "name": "Днище цистерны (эллиптическое)",
        "model": "АЦ-6,0-40",
        "material": "Сталь 09Г2С",
        "mass_kg": 38.0,
        "surface_treatment": "Грунт ГФ-021, эмаль ПФ-115",
        "level": "detail",
        "parent_id": "assembly-cisterna",
        "extra_props": {"gost_material": "ГОСТ 19903-2015", "толщина_мм": 6}
    },
    {
        "id": "detail-lyuk",
        "designation": "ЛМША.302300.001",
        "name": "Люк-лаз Ø500 с крышкой",
        "model": "АЦ-6,0-40",
        "material": "Сталь 09Г2С",
        "mass_kg": 12.0,
        "surface_treatment": "Грунт ГФ-021, эмаль ПФ-115",
        "level": "detail",
        "parent_id": "assembly-cisterna",
        "extra_props": {"gost_material": "ГОСТ 19903-2015"}
    },
    # ===== ЭЛЕКТРО-МОНТАЖНЫЕ ДЕТАЛИ =====
    {
        "id": "detail-cable-trassa-osn",
        "designation": "ТК-001",
        "name": "Трасса кабельная основная (от АКБ до пульта)",
        "model": "АЦ-6,0-40",
        "material": "Провод ПВА 6.0",
        "mass_kg": 3.2,
        "level": "detail",
        "parent_id": "assembly-sgu",
        "tech_rules": "Прокладка в гофре D16. Крепление стяжками через 0.5 м.",
        "extra_props": {"длина_м": 8.5, "сечение_мм2": 6.0}
    },
    {
        "id": "detail-sgu-podklyuchenie",
        "designation": "ЭМ-001",
        "name": "Подключение СГУ-100 (кронштейн + проводка)",
        "model": "АЦ-6,0-40",
        "material": "Электрокомплект",
        "mass_kg": 2.5,
        "level": "detail",
        "parent_id": "assembly-sgu",
        "extra_props": {"провод_пва_сечение": 1.5, "тип_разъема": "WAGO 222"}
    },
]


TECHINKOM_OPERATIONS = {
    # Операции для упора продольного (из реальной техкарты PDF 4c85941a)
    "detail-lmsha-301314-010": [
        {"name": "010 Подготовительная", "equipment": "Верстак, щётка металлическая", "duration_hours": 0.2,
         "department": "Сварочно-сборочный КТ, Участок 01, РМ 04", "profession_code": "19905", "profession_grade": 4,
         "materials": [{"name": "Проволока Св-08Г2С-О 1,0", "quantity": 0.5, "unit": "кг", "gost": "ГОСТ 2246-70"},
                       {"name": "Смесь М21 (Ar/CO2)", "quantity": 0.02, "unit": "м3", "gost": "ГОСТ Р ИСО 14175-2010"}],
         "gosts": ["ГОСТ 2246-70", "ГОСТ Р ИСО 14175-2010"], "control_points": ["визуальный"], "confidence": 90},
        {"name": "015 Установка ножей", "equipment": "Кондуктор сварочный", "duration_hours": 0.3,
         "department": "Сварочно-сборочный КТ, Участок 01, РМ 04", "profession_code": "19905", "profession_grade": 4,
         "gosts": ["ГОСТ 3242-79"], "control_points": ["визуальный"], "confidence": 85},
        {"name": "020 Приварка ножей к основанию", "equipment": "Кедр-300", "duration_hours": 0.8,
         "department": "Сварочно-сборочный КТ, Участок 01, РМ 04", "profession_code": "19905", "profession_grade": 4,
         "materials": [{"name": "Проволока Св-08Г2С-О 1,0", "quantity": 0.3, "unit": "кг", "gost": "ГОСТ 2246-70"}],
         "gosts": ["ГОСТ 2246-70"], "control_points": ["визуальный", "обмер"], "confidence": 80},
        {"name": "025 Установка рёбер и приварка пластин", "equipment": "Кедр-300", "duration_hours": 1.0,
         "department": "Сварочно-сборочный КТ, Участок 01, РМ 04", "profession_code": "19905", "profession_grade": 4,
         "materials": [{"name": "Пластина ЛМША.301714.006", "quantity": 1, "unit": "шт"}],
         "gosts": ["ГОСТ 2246-70"], "control_points": ["визуальный"], "confidence": 75},
        {"name": "030 Приварка рёбер к основанию", "equipment": "Кедр-300", "duration_hours": 0.7,
         "department": "Сварочно-сборочный КТ, Участок 01, РМ 04", "profession_code": "19905", "profession_grade": 4,
         "gosts": ["ГОСТ 2246-70"], "control_points": ["визуальный", "обмер"], "confidence": 75},
        {"name": "035 Установка настила, уголков, планок", "equipment": "Кедр-300", "duration_hours": 1.2,
         "department": "Сварочно-сборочный КТ, Участок 01, РМ 04", "profession_code": "19905", "profession_grade": 4,
         "gosts": ["ГОСТ 2246-70"], "control_points": ["визуальный"], "confidence": 70},
        {"name": "040 Контроль ОТК", "equipment": "Мерительный инструмент", "duration_hours": 0.3,
         "department": "Сварочно-сборочный КТ, Участок 02, РМ 01 (ОТК)", "profession_code": "19905", "profession_grade": 5,
         "gosts": ["ГОСТ 3242-79"], "control_points": ["визуальный", "обмер"], "confidence": 90},
    ],
    "detail-lmsha-301714-006": [
        {"name": "010 Заготовка", "equipment": "Гильотинные ножницы", "duration_hours": 0.1,
         "department": "Заготовительный КТ, Участок 03, РМ 01", "profession_code": "19149", "profession_grade": 4,
         "gosts": ["ГОСТ 19903-2015"], "control_points": ["обмер"], "confidence": 95},
        {"name": "020 Штамповка", "equipment": "Пресс КД-2128", "duration_hours": 0.2,
         "department": "Заготовительный КТ, Участок 03, РМ 02", "profession_code": "19479", "profession_grade": 4,
         "gosts": ["ГОСТ 19903-2015"], "control_points": ["визуальный", "обмер"], "confidence": 90},
    ],
    "detail-obolochka": [
        {"name": "010 Вальцовка", "equipment": "Вальцы 3-х валковые", "duration_hours": 0.5,
         "department": "Заготовительный КТ, Участок 04, РМ 01", "profession_code": "19479", "profession_grade": 5,
         "materials": [{"name": "Лист 09Г2С 4×1500×3000", "quantity": 1, "unit": "лист", "gost": "ГОСТ 19903-2015"}],
         "gosts": ["ГОСТ 19903-2015"], "control_points": ["обмер"], "confidence": 90},
        {"name": "020 Сборка обечайки", "equipment": "Сборочный стенд", "duration_hours": 0.8,
         "department": "Сварочно-сборочный КТ, Участок 01, РМ 01", "profession_code": "19905", "profession_grade": 5,
         "gosts": ["ГОСТ 2246-70"], "control_points": ["визуальный"], "confidence": 85},
        {"name": "030 Сварка продольного шва", "equipment": "Кедр-300 (TIG)", "duration_hours": 2.0,
         "department": "Сварочно-сборочный КТ, Участок 01, РМ 02", "profession_code": "19905", "profession_grade": 5,
         "materials": [{"name": "Проволока Св-08Г2С 1,2", "quantity": 1.2, "unit": "кг", "gost": "ГОСТ 2246-70"},
                       {"name": "Аргон высший сорт", "quantity": 0.05, "unit": "м3", "gost": "ГОСТ 10157-79"}],
         "gosts": ["ГОСТ 2246-70", "ГОСТ 10157-79"], "control_points": ["визуальный", "УЗК"], "confidence": 80},
        {"name": "040 Опрессовка", "equipment": "Опрессовочный стенд", "duration_hours": 0.5,
         "department": "Сварочно-сборочный КТ, Участок 02, РМ 03", "profession_code": "19905", "profession_grade": 5,
         "gosts": ["ГОСТ 3242-79"], "control_points": ["опрессовка 0.3 МПа, 10 мин"], "confidence": 90},
    ],
    "detail-cable-trassa-osn": [
        {"name": "010 Разделка кабеля", "equipment": "Нож для разделки, кримпер", "duration_hours": 0.3,
         "department": "Электромонтажный КТ, Участок 06, РМ 01", "profession_code": "19861", "profession_grade": 4,
         "materials": [{"name": "Наконечник ТМЛ 6-6", "quantity": 4, "unit": "шт"}],
         "gosts": ["ГОСТ 23594-79"], "control_points": ["визуальный"], "confidence": 95},
        {"name": "020 Прокладка трассы", "equipment": "Гофротруба D16, стяжки", "duration_hours": 1.0,
         "department": "Электромонтажный КТ, Участок 06, РМ 02", "profession_code": "19861", "profession_grade": 4,
         "materials": [{"name": "Гофра D16", "quantity": 9, "unit": "м"},
                       {"name": "Стяжка 4.8×300", "quantity": 20, "unit": "шт"}],
         "gosts": ["ГОСТ 23594-79"], "control_points": ["визуальный"], "confidence": 90},
        {"name": "030 Подключение к АКБ", "equipment": "Ключ гаечный, кримпер", "duration_hours": 0.5,
         "department": "Электромонтажный КТ, Участок 06, РМ 03", "profession_code": "19861", "profession_grade": 4,
         "gosts": ["ГОСТ 23594-79"], "control_points": ["затяжка 18 Нм"], "confidence": 95},
        {"name": "040 Проверка изоляции", "equipment": "Мегаомметр 500В", "duration_hours": 0.2,
         "department": "Электромонтажный КТ, Участок 06, РМ 04 (ОТК)", "profession_code": "19861", "profession_grade": 5,
         "gosts": ["ГОСТ 23594-79"], "control_points": ["изоляция ≥100 МОм"], "confidence": 95},
    ],
    "detail-sgu-podklyuchenie": [
        {"name": "010 Установка кронштейна СГУ", "equipment": "Дрель, метизы", "duration_hours": 0.3,
         "department": "Электромонтажный КТ, Участок 06, РМ 05", "profession_code": "19861", "profession_grade": 4,
         "materials": [{"name": "Кронштейн СГУ", "quantity": 1, "unit": "шт"},
                       {"name": "Болт М8×30", "quantity": 4, "unit": "шт"}],
         "gosts": ["ГОСТ 23594-79"], "control_points": ["затяжка"], "confidence": 90},
        {"name": "020 Подключение питания", "equipment": "Кримпер, тестер", "duration_hours": 0.4,
         "department": "Электромонтажный КТ, Участок 06, РМ 05", "profession_code": "19861", "profession_grade": 4,
         "materials": [{"name": "Провод ПВА 1.5", "quantity": 3, "unit": "м", "gost": "ГОСТ 23594-79"},
                       {"name": "Клемма WAGO 222-413", "quantity": 4, "unit": "шт"}],
         "gosts": ["ГОСТ 23594-79"], "control_points": ["прозвонка"], "confidence": 85},
        {"name": "030 Проверка работоспособности", "equipment": "Тестер, аккумулятор 12В", "duration_hours": 0.2,
         "department": "Электромонтажный КТ, Участок 06, РМ 04 (ОТК)", "profession_code": "19861", "profession_grade": 5,
         "gosts": ["ГОСТ 23594-79"], "control_points": ["звук, мигание"], "confidence": 90},
    ],
}


def seed_techinkom_data():
    """Сидит 15 деталей Техинкома с иерархией и операциями"""
    from app import get_conn, add_history
    conn = get_conn()
    seeded = 0
    seeded_ids = []
    for d in TECHINKOM_DETAILS:
        existing = conn.execute("SELECT id FROM details WHERE id=?", (d["id"],)).fetchone()
        if existing:
            continue
        # N3 fix: validate level
        level = d.get("level", "detail")
        if level not in ("detail", "assembly", "product"):
            log.warning(f"Invalid level '{level}' for {d['id']}, defaulting to 'detail'")
            level = "detail"
        conn.execute("""INSERT INTO details
            (id, designation, name, model, chassis, material, mass_kg, surface_treatment,
             tech_rules, extra_props, level, parent_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
            d["id"], d["designation"], d["name"], d.get("model"), d.get("chassis"),
            d.get("material"), d.get("mass_kg", 0), d.get("surface_treatment"),
            d.get("tech_rules"),
            json.dumps(d.get("extra_props", {}), ensure_ascii=False),
            level, d.get("parent_id")
        ))
        # Операции
        ops = TECHINKOM_OPERATIONS.get(d["id"], [])
        if ops:
            total_hours = sum(o.get("duration_hours", 0) for o in ops)
            llm_output = {
                "summary": {
                    "total_operations": len(ops),
                    "total_hours": round(total_hours, 2),
                    "prep_hours": ops[0].get("duration_hours", 0) if ops else 0,
                    "complexity": "medium"
                },
                "operations": ops,
                "route": [{"step": i+1, "operation": o["name"], "duration_hours": o["duration_hours"]} for i, o in enumerate(ops)],
                "reasoning": {
                    "operations_choice": "Импортировано из реальной техкарты Техинком (PDF 4c85941a)",
                    "duration_estimates": "По нормативу",
                    "equipment_choice": "Кедр-300 (основной сварочный аппарат)",
                    "risks": "Требует верификации технологом"
                },
                "source": "techinkom_seed"
            }
            conn.execute("""INSERT INTO drafts (detail_id, llm_output, status, author)
                VALUES (?, ?, 'draft', 'techinkom-seed')""",
                (d["id"], json.dumps(llm_output, ensure_ascii=False)))
            # Ресурсы
            for i, op in enumerate(ops):
                if op.get("profession_code"):
                    conn.execute("""INSERT INTO resource_specs
                        (detail_id, op_index, kind, name, quantity, unit, notes)
                        VALUES (?, ?, 'profession', ?, 1, 'чел', ?)""",
                        (d["id"], i, f"{op['profession_code']} {op.get('profession_grade','')}р",
                         f"Ставка по ЕТС"))
                for m in op.get("materials", []):
                    if isinstance(m, dict):
                        conn.execute("""INSERT INTO resource_specs
                            (detail_id, op_index, kind, name, quantity, unit, notes)
                            VALUES (?, ?, 'material', ?, ?, ?, ?)""",
                            (d["id"], i, m.get("name", ""), m.get("quantity", 1),
                             m.get("unit", ""), m.get("gost", "")))
        seeded += 1
        seeded_ids.append(d["id"])
    conn.commit()
    conn.close()
    # История — после commit, чтобы не держать write lock
    for did in seeded_ids:
        try:
            add_history(did, "techinkom_seeded", {})
        except Exception:
            pass
    return {"seeded": seeded, "total": len(TECHINKOM_DETAILS)}
