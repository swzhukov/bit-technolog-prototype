"""
seed_more_etalons.py — больше эталонов для Sprint 7 (RAG v2 demo).

5 новых ТК (не из PDF — синтетические, но реалистичные):
- ЛМША.302410.001 (Пробка заливной горловины) — токарка + сборка
- ЛМША.302510.005 (Задвижка донная) — сборка + контроль
- ЛМША.305001.020 (Днище оболочки) — гибка + сварка
- ЛМША.305002.010 (Обечайка) — вальцовка + сварка
- ЛМША.306001.005 (Поперечина рамы) — резка + сварка
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from repositories import db


MORE_ETALONS = [
    {
        "item_designation": "ЛМША.302410.001",
        "item_name": "Пробка заливной горловины",
        "product_type": "АЦ",
        "approved_by": "ВП 3237",
        "approved_date": "2023-03-15",
        "operations": [
            {"op_number": 5, "name": "Токарная обработка", "workshop_code": "01", "profession_code": "Т-4", "equipment_name": "Токарный станок 16К20", "time_setup_min": 8, "time_per_unit_min": 18, "materials": [{"code": "Ст3", "qty": 1.2, "unit": "кг"}]},
            {"op_number": 10, "name": "Сверление отверстий", "workshop_code": "01", "profession_code": "Т-4", "equipment_name": "Сверлильный станок", "time_setup_min": 4, "time_per_unit_min": 6, "materials": []},
            {"op_number": 15, "name": "Нарезка резьбы", "workshop_code": "01", "profession_code": "Т-4", "equipment_name": "Токарный станок 16К20", "time_setup_min": 5, "time_per_unit_min": 8, "materials": []},
            {"op_number": 20, "name": "Контроль ОТК", "workshop_code": "04", "profession_code": "К-3", "equipment_name": "Стол ОТК", "time_setup_min": 3, "time_per_unit_min": 5, "materials": []},
        ],
    },
    {
        "item_designation": "ЛМША.302510.005",
        "item_name": "Задвижка донная",
        "product_type": "АЦ",
        "approved_by": "ВП 3237",
        "approved_date": "2023-04-22",
        "operations": [
            {"op_number": 5, "name": "Сборка корпуса", "workshop_code": "03", "profession_code": "С-5", "equipment_name": "Стенд сборочный", "time_setup_min": 10, "time_per_unit_min": 25, "materials": [{"code": "09Г2С", "qty": 2.5, "unit": "кг"}]},
            {"op_number": 10, "name": "Сварка корпуса", "workshop_code": "02", "profession_code": "Э-5", "equipment_name": "Полуавтомат ПДГ-508", "time_setup_min": 12, "time_per_unit_min": 30, "materials": [{"code": "Св-08Г2С-О", "qty": 0.4, "unit": "кг"}]},
            {"op_number": 15, "name": "Зачистка швов", "workshop_code": "02", "profession_code": "С-4", "equipment_name": "УШМ", "time_setup_min": 4, "time_per_unit_min": 12, "materials": []},
            {"op_number": 20, "name": "Испытание на герметичность", "workshop_code": "03", "profession_code": "К-4", "equipment_name": "Стенд испытательный", "time_setup_min": 8, "time_per_unit_min": 15, "materials": []},
            {"op_number": 25, "name": "Контроль ОТК", "workshop_code": "04", "profession_code": "К-3", "equipment_name": "Стол ОТК", "time_setup_min": 3, "time_per_unit_min": 6, "materials": []},
        ],
    },
    {
        "item_designation": "ЛМША.305001.020",
        "item_name": "Днище оболочки (обечайка)",
        "product_type": "АЦ",
        "approved_by": "ВП 3237",
        "approved_date": "2023-05-10",
        "operations": [
            {"op_number": 5, "name": "Раскрой листа", "workshop_code": "01", "profession_code": "Р-3", "equipment_name": "Плазменный резак HyperTherm", "time_setup_min": 6, "time_per_unit_min": 15, "materials": [{"code": "09Г2С", "qty": 12.0, "unit": "кг"}]},
            {"op_number": 10, "name": "Гибка", "workshop_code": "01", "profession_code": "Г-4", "equipment_name": "Пресс гидравлический П6330", "time_setup_min": 10, "time_per_unit_min": 22, "materials": []},
            {"op_number": 15, "name": "Сварка", "workshop_code": "02", "profession_code": "Э-5", "equipment_name": "Полуавтомат Fronius", "time_setup_min": 15, "time_per_unit_min": 40, "materials": [{"code": "Св-08Г2С-О", "qty": 1.5, "unit": "кг"}]},
            {"op_number": 20, "name": "Зачистка", "workshop_code": "02", "profession_code": "С-4", "equipment_name": "УШМ", "time_setup_min": 5, "time_per_unit_min": 18, "materials": []},
            {"op_number": 25, "name": "Контроль ОТК", "workshop_code": "04", "profession_code": "К-3", "equipment_name": "Стол ОТК", "time_setup_min": 4, "time_per_unit_min": 8, "materials": []},
        ],
    },
    {
        "item_designation": "ЛМША.305002.010",
        "item_name": "Обечайка",
        "product_type": "АЦ",
        "approved_by": "ВП 3237",
        "approved_date": "2023-06-18",
        "operations": [
            {"op_number": 5, "name": "Раскрой листа", "workshop_code": "01", "profession_code": "Р-3", "equipment_name": "Гильотинные ножницы НГ-6,3", "time_setup_min": 5, "time_per_unit_min": 10, "materials": [{"code": "09Г2С", "qty": 6.0, "unit": "кг"}]},
            {"op_number": 10, "name": "Вальцовка", "workshop_code": "01", "profession_code": "Г-4", "equipment_name": "Вальцы ИБ2232", "time_setup_min": 8, "time_per_unit_min": 18, "materials": []},
            {"op_number": 15, "name": "Сварка продольного шва", "workshop_code": "02", "profession_code": "Э-5", "equipment_name": "Полуавтомат ПДГ-508", "time_setup_min": 12, "time_per_unit_min": 28, "materials": [{"code": "Св-08Г2С-О", "qty": 0.8, "unit": "кг"}]},
            {"op_number": 20, "name": "Контроль сварного шва", "workshop_code": "04", "profession_code": "К-4", "equipment_name": "Ультразвуковой дефектоскоп", "time_setup_min": 6, "time_per_unit_min": 10, "materials": []},
        ],
    },
    {
        "item_designation": "ЛМША.306001.005",
        "item_name": "Поперечина рамы",
        "product_type": "АЦ",
        "approved_by": "ВП 3237",
        "approved_date": "2023-07-05",
        "operations": [
            {"op_number": 5, "name": "Раскрой", "workshop_code": "01", "profession_code": "Р-3", "equipment_name": "Ленточнопильный Bomar", "time_setup_min": 5, "time_per_unit_min": 8, "materials": [{"code": "09Г2С", "qty": 35.0, "unit": "кг"}]},
            {"op_number": 10, "name": "Сварка", "workshop_code": "02", "profession_code": "Э-5", "equipment_name": "Полуавтомат Fronius", "time_setup_min": 12, "time_per_unit_min": 35, "materials": [{"code": "Св-08Г2С-О", "qty": 0.6, "unit": "кг"}]},
            {"op_number": 15, "name": "Сверление", "workshop_code": "01", "profession_code": "Т-4", "equipment_name": "Сверлильный станок", "time_setup_min": 6, "time_per_unit_min": 12, "materials": []},
            {"op_number": 20, "name": "Окраска", "workshop_code": "04", "profession_code": "М-5", "equipment_name": "Камера окрасочная", "time_setup_min": 10, "time_per_unit_min": 20, "materials": [{"code": "ГФ-021", "qty": 0.8, "unit": "кг"}]},
            {"op_number": 25, "name": "Контроль ОТК", "workshop_code": "04", "profession_code": "К-3", "equipment_name": "Стол ОТК", "time_setup_min": 3, "time_per_unit_min": 5, "materials": []},
        ],
    },
]


def seed_more_etalons(verbose: bool = True) -> int:
    """Загрузить ещё эталонов (синтетические, реалистичные)."""
    db.init_db()
    loaded = 0
    for spec in MORE_ETALONS:
        # Удалим старый эталон (если есть)
        db.execute("DELETE FROM etalons WHERE designation = ?", (spec["item_designation"],))
        # Создать новый
        etalon_id = db.insert_and_get_id("etalons", {
            "designation": spec["item_designation"],
            "name": spec["item_name"],
            "product_type": spec["product_type"],
            "source_doc": f"Эталон (синтетический) — {spec['approved_date']}",
            "source_pages": 1,
            "approved_by": spec["approved_by"],
            "approved_date": spec["approved_date"],
            "is_approved": 1,
            "is_published": 1,
            "content_json": json.dumps({"operations": spec["operations"]}, ensure_ascii=False),
            "rag_indexed_at": None,
        })
        if verbose:
            n_ops = len(spec["operations"])
            print(f"  {spec['item_designation']} «{spec['item_name']}» — {n_ops} операций")
        loaded += 1
    return loaded


if __name__ == "__main__":
    n = seed_more_etalons()
    print(f"\nЗагружено эталонов: {n}")
    # Сводка
    from services.rag import load_etalons
    ets = load_etalons(force=True)
    print(f"Всего в индексе RAG: {len(ets)} эталонов")
    for et in ets:
        print(f"  - {et.designation} «{et.name}» ({len(et.operations)} оп., {len(et.material_codes)} материалов)")
