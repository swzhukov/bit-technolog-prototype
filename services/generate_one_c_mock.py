"""
generate_one_c_mock.py — генератор реалистичной эмуляции 1С:ERP.

Создаёт XML-файлы в формате, приближённом к стандартному обмену 1С
(но упрощённый для препилота).

Структура:
- data/one_c_exchange/in/
  - nomenclature.xml  # Номенклатура (50+ items)
  - materials.xml     # Материалы (15+)
  - equipment.xml     # Оборудование (30+)
  - professions.xml   # Профессии + тарифы (10+)
  - product_models.xml # Модели изделий (5+)

Использует референсную схему актуального 1С:ERP 2.5 (упрощённо).
"""
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Референсная схема: https://its.1c.ru/db/erp25doc
# Формат обмена: EnterpriseData (не используем, делаем проще)


OUTPUT_DIR = Path(__file__).parent.parent / "data" / "one_c_exchange" / "in"


def _make_xml(root_tag: str, items: list, item_tag: str, attrs_func, text_func) -> str:
    """Создать XML и pretty-print."""
    root = ET.Element(root_tag)
    for item in items:
        el = ET.SubElement(root, item_tag)
        for k, v in attrs_func(item).items():
            el.set(k, str(v))
        for k, v in text_func(item).items():
            sub = ET.SubElement(el, k)
            sub.text = str(v) if v is not None else ""
    rough = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(rough).toprettyxml(indent="  ", encoding="UTF-8")
    return pretty.decode("utf-8")


# ============================================================
# 1. НОМЕНКЛАТУРА (50+ items)
# ============================================================

NOMENCLATURE = [
    # Шасси (отдельно в chassis.xml — здесь только детали)
    # Изделия (5 моделей)
    {"ref": "uuid-ac-8", "designation": "АЦ-8,0-40", "name": "Автоцистерна пожарная 8 м³ на шасси КАМАЗ-43118", "level": "product", "mass_kg": 18500.0},
    {"ref": "uuid-ac-6", "designation": "АЦ-6,0-40", "name": "Автоцистерна пожарная 6 м³ на шасси КАМАЗ-43118", "level": "product", "mass_kg": 15200.0},
    {"ref": "uuid-umk-3", "designation": "УМК-3,0-40", "name": "Установка комбинированная 3 м³", "level": "product", "mass_kg": 9800.0},
    {"ref": "uuid-pss-5", "designation": "ПСС-5,0-40", "name": "Пожарная насосная станция 5 м³/мин", "level": "product", "mass_kg": 11200.0},
    {"ref": "uuid-umk-7", "designation": "УМК-7,0-40", "name": "Установка комбинированная 7 м³", "level": "product", "mass_kg": 19800.0},
    # Узлы (10 сборок)
    {"ref": "uuid-cist-8", "designation": "53-ТВ.05.000", "name": "Цистерна (узел)", "level": "assembly", "mass_kg": 2400.0, "parent_ref": "uuid-ac-8"},
    {"ref": "uuid-rama-8", "designation": "53-РМ.10.000", "name": "Рама (узел)", "level": "assembly", "mass_kg": 850.0, "parent_ref": "uuid-ac-8"},
    {"ref": "uuid-kabin-8", "designation": "53-КБ.20.000", "name": "Кабина (узел)", "level": "assembly", "mass_kg": 320.0, "parent_ref": "uuid-ac-8"},
    {"ref": "uuid-nasos-8", "designation": "53-НС.30.000", "name": "Насосная установка (узел)", "level": "assembly", "mass_kg": 180.0, "parent_ref": "uuid-ac-8"},
    {"ref": "uuid-upor-1", "designation": "ЛМША.301314.010", "name": "Упор продольный", "level": "assembly", "mass_kg": 12.5, "parent_ref": "uuid-rama-8"},
    {"ref": "uuid-rastyag-1", "designation": "ЛМША.301712.000", "name": "Растяжка пружинная", "level": "assembly", "mass_kg": 8.3, "parent_ref": "uuid-rama-8"},
    {"ref": "uuid-kronsh-1", "designation": "ЛМША.301555.020", "name": "Кронштейн боковой", "level": "assembly", "mass_kg": 4.5, "parent_ref": "uuid-rama-8"},
    {"ref": "uuid-probka-1", "designation": "ЛМША.302410.001", "name": "Пробка заливной горловины", "level": "assembly", "mass_kg": 0.8, "parent_ref": "uuid-cist-8"},
    {"ref": "uuid-zadv-1", "designation": "ЛМША.302510.005", "name": "Задвижка донная", "level": "assembly", "mass_kg": 1.2, "parent_ref": "uuid-cist-8"},
    {"ref": "uuid-bak-1", "designation": "ЛМША.303210.100", "name": "Бак пенообразователя", "level": "assembly", "mass_kg": 95.0, "parent_ref": "uuid-nasos-8"},
    # Детали (15 деталей)
    {"ref": "uuid-d1", "designation": "ЛМША.304142.010", "name": "Втулка", "level": "detail", "mass_kg": 0.8, "material_ref": "uuid-m-09g2s", "parent_ref": "uuid-rastyag-1"},
    {"ref": "uuid-d2", "designation": "ЛМША.304142.010-01", "name": "Втулка (модификация)", "level": "detail", "mass_kg": 0.8, "material_ref": "uuid-m-09g2s", "parent_ref": "uuid-rastyag-1"},
    {"ref": "uuid-d3", "designation": "ЛМША.304339.010", "name": "Проушина", "level": "detail", "mass_kg": 1.2, "material_ref": "uuid-m-09g2s", "parent_ref": "uuid-rastyag-1"},
    {"ref": "uuid-d4", "designation": "ЛМША.301624.003", "name": "Шайба", "level": "detail", "mass_kg": 0.02, "material_ref": "uuid-m-09g2s", "parent_ref": "uuid-rastyag-1"},
    {"ref": "uuid-d5", "designation": "ЛМША.301614.001", "name": "Шпилька", "level": "detail", "mass_kg": 0.05, "material_ref": "uuid-m-09g2s", "parent_ref": "uuid-rastyag-1"},
    {"ref": "uuid-d6", "designation": "ЛМША.304590.001", "name": "Пружина тарельчатая", "level": "detail", "mass_kg": 0.05, "material_ref": "uuid-m-65g", "parent_ref": "uuid-rastyag-1"},
    {"ref": "uuid-d7", "designation": "ЛМША.305001.020", "name": "Днище (оболочка)", "level": "detail", "mass_kg": 95.0, "material_ref": "uuid-m-09g2s", "parent_ref": "uuid-cist-8"},
    {"ref": "uuid-d8", "designation": "ЛМША.305002.010", "name": "Обечайка (оболочка)", "level": "detail", "mass_kg": 45.0, "material_ref": "uuid-m-09g2s", "parent_ref": "uuid-cist-8"},
    {"ref": "uuid-d9", "designation": "ЛМША.305003.000", "name": "Крышка люка", "level": "detail", "mass_kg": 12.0, "material_ref": "uuid-m-09g2s", "parent_ref": "uuid-cist-8"},
    {"ref": "uuid-d10", "designation": "ЛМША.306001.005", "name": "Поперечина рамы", "level": "detail", "mass_kg": 32.0, "material_ref": "uuid-m-09g2s", "parent_ref": "uuid-rama-8"},
    {"ref": "uuid-d11", "designation": "ЛМША.306002.007", "name": "Лонжерон (балка)", "level": "detail", "mass_kg": 28.0, "material_ref": "uuid-m-09g2s", "parent_ref": "uuid-rama-8"},
    {"ref": "uuid-d12", "designation": "ЛМША.307001.001", "name": "Кронштейн насоса", "level": "detail", "mass_kg": 8.5, "material_ref": "uuid-m-st3", "parent_ref": "uuid-nasos-8"},
    {"ref": "uuid-d13", "designation": "ЛМША.307002.002", "name": "Фланец патрубка", "level": "detail", "mass_kg": 3.2, "material_ref": "uuid-m-st3", "parent_ref": "uuid-nasos-8"},
    {"ref": "uuid-d14", "designation": "ЛМША.308001.003", "name": "Панель кабины", "level": "detail", "mass_kg": 18.0, "material_ref": "uuid-m-st3", "parent_ref": "uuid-kabin-8"},
    {"ref": "uuid-d15", "designation": "ЛМША.308002.001", "name": "Каркас двери", "level": "detail", "mass_kg": 6.5, "material_ref": "uuid-m-st3", "parent_ref": "uuid-kabin-8"},
    # Покупные (10)
    {"ref": "uuid-p1", "designation": "Гайка М12-6Н.6.019", "name": "Гайка М12", "level": "purchased", "mass_kg": 0.015, "material_ref": "uuid-m-st3", "parent_ref": "uuid-rama-8"},
    {"ref": "uuid-p2", "designation": "Болт М12-6g×60.58.019", "name": "Болт М12×60", "level": "purchased", "mass_kg": 0.05, "material_ref": "uuid-m-st3", "parent_ref": "uuid-rama-8"},
    {"ref": "uuid-p3", "designation": "Шайба 12.01.019", "name": "Шайба 12", "level": "purchased", "mass_kg": 0.005, "material_ref": "uuid-m-st3", "parent_ref": "uuid-rama-8"},
    {"ref": "uuid-p4", "designation": "Подшипник 6205-2RS", "name": "Подшипник 6205", "level": "purchased", "mass_kg": 0.13, "parent_ref": "uuid-nasos-8"},
    {"ref": "uuid-p5", "designation": "Манжета 1.2-25×42-1", "name": "Манжета армированная", "level": "purchased", "mass_kg": 0.02, "parent_ref": "uuid-nasos-8"},
    {"ref": "uuid-p6", "designation": "Ремень SPB-1250", "name": "Ремень клиновой", "level": "purchased", "mass_kg": 0.18, "parent_ref": "uuid-nasos-8"},
    {"ref": "uuid-p7", "designation": "Фильтр ФВТ-150", "name": "Фильтр воздушный", "level": "purchased", "mass_kg": 0.45, "parent_ref": "uuid-nasos-8"},
    {"ref": "uuid-p8", "designation": "Стекло 510×350×4", "name": "Стекло автомобильное", "level": "purchased", "mass_kg": 1.8, "parent_ref": "uuid-kabin-8"},
    {"ref": "uuid-p9", "designation": "Уплотнитель 2000 мм", "name": "Уплотнитель двери", "level": "purchased", "mass_kg": 0.15, "parent_ref": "uuid-kabin-8"},
    {"ref": "uuid-p10", "designation": "Замок 5.780-01", "name": "Замок двери", "level": "purchased", "mass_kg": 0.25, "parent_ref": "uuid-kabin-8"},
    # Полуфабрикаты (5)
    {"ref": "uuid-s1", "designation": "ЛМША.402010.001", "name": "Заготовка обечайки", "level": "semi", "mass_kg": 48.0, "material_ref": "uuid-m-09g2s"},
    {"ref": "uuid-s2", "designation": "ЛМША.402020.001", "name": "Заготовка днища", "level": "semi", "mass_kg": 105.0, "material_ref": "uuid-m-09g2s"},
    {"ref": "uuid-s3", "designation": "ЛМША.402030.001", "name": "Заготовка лонжерона", "level": "semi", "mass_kg": 35.0, "material_ref": "uuid-m-09g2s"},
    {"ref": "uuid-s4", "designation": "ЛМША.402040.001", "name": "Заготовка панели", "level": "semi", "mass_kg": 22.0, "material_ref": "uuid-m-st3"},
    {"ref": "uuid-s5", "designation": "ЛМША.402050.001", "name": "Заготовка каркаса", "level": "semi", "mass_kg": 8.0, "material_ref": "uuid-m-st3"},
]


def gen_nomenclature():
    xml = _make_xml(
        "Nomenclature",
        NOMENCLATURE,
        "Item",
        attrs_func=lambda x: {
            "ref": x["ref"],
            "level": x["level"],
            "sourcing": "buy" if x["level"] == "purchased" else "make",
        },
        text_func=lambda x: {
            "Designation": x["designation"],
            "Name": x["name"],
            "Mass": x.get("mass_kg"),
            "MaterialRef": x.get("material_ref", ""),
            "ParentRef": x.get("parent_ref", ""),
        },
    )
    out = OUTPUT_DIR / "nomenclature.xml"
    out.write_text(xml, encoding="utf-8")
    return out


# ============================================================
# 2. МАТЕРИАЛЫ (15+)
# ============================================================

MATERIALS = [
    {"ref": "uuid-m-09g2s", "code": "09Г2С", "name": "Сталь 09Г2С листовая", "category": "лист", "unit": "кг", "price": 95.0},
    {"ref": "uuid-m-10xsnd", "code": "10ХСНД", "name": "Сталь 10ХСНД (морозостойкая)", "category": "лист", "unit": "кг", "price": 125.0},
    {"ref": "uuid-m-st3", "code": "Ст3", "name": "Сталь Ст3 листовая", "category": "лист", "unit": "кг", "price": 75.0},
    {"ref": "uuid-m-65g", "code": "65Г", "name": "Сталь 65Г (пружинная)", "category": "лист", "unit": "кг", "price": 145.0},
    {"ref": "uuid-m-sv08g2s", "code": "Св-08Г2С-О", "name": "Проволока сварочная Св-08Г2С-О 0,8 мм", "category": "проволока", "unit": "кг", "price": 145.0},
    {"ref": "uuid-m-sv08g2s12", "code": "Св-08Г2С-О-1,2", "name": "Проволока сварочная Св-08Г2С-О 1,2 мм", "category": "проволока", "unit": "кг", "price": 142.0},
    {"ref": "uuid-m-sprey", "code": "Спрей Auscon Wpre", "name": "Спрей антипригарный Auscon Wpre!", "category": "вспомогательные", "unit": "л", "price": 850.0},
    {"ref": "uuid-m-kraska", "code": "Эмаль ПФ-115", "name": "Эмаль ПФ-115 (серая)", "category": "лакокрасочные", "unit": "кг", "price": 220.0},
    {"ref": "uuid-m-grunt", "code": "ГФ-021", "name": "Грунт ГФ-021 (коричневый)", "category": "лакокрасочные", "unit": "кг", "price": 185.0},
    {"ref": "uuid-m-rastvor", "code": "Растворитель 646", "name": "Растворитель 646", "category": "лакокрасочные", "unit": "л", "price": 95.0},
    {"ref": "uuid-m-benzin", "code": "Бензин Калоша", "name": "Бензин Калоша (Нефрас)", "category": "вспомогательные", "unit": "л", "price": 75.0},
    {"ref": "uuid-m-tkan", "code": "Стеклоткань Э-200", "name": "Стеклоткань Э-200", "category": "композиты", "unit": "кг", "price": 380.0},
    {"ref": "uuid-m-smola", "code": "ЭД-20", "name": "Эпоксидная смола ЭД-20", "category": "композиты", "unit": "кг", "price": 540.0},
    {"ref": "uuid-m-otverd", "code": "ПЭПА", "name": "Отвердитель ПЭПА", "category": "композиты", "unit": "кг", "price": 720.0},
    {"ref": "uuid-m-maslo", "code": "Масло И-20А", "name": "Масло индустриальное И-20А", "category": "смазочные", "unit": "л", "price": 95.0},
    {"ref": "uuid-m-tormoz", "code": "Жидкость DOT-4", "name": "Тормозная жидкость DOT-4", "category": "технические", "unit": "л", "price": 280.0},
    {"ref": "uuid-m-antifriz", "code": "Антифриз G11", "name": "Антифриз G11 (зелёный)", "category": "технические", "unit": "л", "price": 165.0},
]


def gen_materials():
    xml = _make_xml(
        "Materials",
        MATERIALS,
        "Material",
        attrs_func=lambda x: {
            "ref": x["ref"],
            "unit": x["unit"],
        },
        text_func=lambda x: {
            "Code": x["code"],
            "Name": x["name"],
            "Category": x["category"],
            "Price": x["price"],
        },
    )
    out = OUTPUT_DIR / "materials.xml"
    out.write_text(xml, encoding="utf-8")
    return out


# ============================================================
# 3. ОБОРУДОВАНИЕ (30+)
# ============================================================

EQUIPMENT = [
    # Заготовительный цех (01)
    {"ref": "uuid-e-01-1", "inventory_no": "01-001", "name": "Гильотинные ножницы НГ-6,3×2500", "workshop": "01", "power_kw": 7.5},
    {"ref": "uuid-e-01-2", "inventory_no": "01-002", "name": "Гильотинные ножницы НГ-4×1500", "workshop": "01", "power_kw": 5.5},
    {"ref": "uuid-e-01-3", "inventory_no": "01-003", "name": "Пресс гидравлический П6330", "workshop": "01", "power_kw": 22.0},
    {"ref": "uuid-e-01-4", "inventory_no": "01-004", "name": "Пресс листогибочный ИБ2232", "workshop": "01", "power_kw": 11.0},
    {"ref": "uuid-e-01-5", "inventory_no": "01-005", "name": "Вальцы трехвалковые ИБ2232", "workshop": "01", "power_kw": 5.5},
    {"ref": "uuid-e-01-6", "inventory_no": "01-006", "name": "Ленточнопильный станок Bomar", "workshop": "01", "power_kw": 3.0},
    {"ref": "uuid-e-01-7", "inventory_no": "01-007", "name": "Плазменный резак HyperTherm", "workshop": "01", "power_kw": 25.0},
    # Сварочный цех (02)
    {"ref": "uuid-e-02-1", "inventory_no": "02-001", "name": "Полуавтомат сварочный ПДГ-508", "workshop": "02", "power_kw": 18.0},
    {"ref": "uuid-e-02-2", "inventory_no": "02-002", "name": "Полуавтомат сварочный Fronius TPS 400i", "workshop": "02", "power_kw": 22.0},
    {"ref": "uuid-e-02-3", "inventory_no": "02-003", "name": "Сварочный инвертор Lincoln 355", "workshop": "02", "power_kw": 14.0},
    {"ref": "uuid-e-02-4", "inventory_no": "02-004", "name": "Аргонодуговой аппарат TIG 200", "workshop": "02", "power_kw": 8.0},
    {"ref": "uuid-e-02-5", "inventory_no": "02-005", "name": "Сварочный стол 2000×1000", "workshop": "02", "power_kw": 0.0},
    {"ref": "uuid-e-02-6", "inventory_no": "02-006", "name": "Сборочно-сварочный стенд ССК-2", "workshop": "02", "power_kw": 0.0},
    # Сборочный цех (03)
    {"ref": "uuid-e-03-1", "inventory_no": "03-001", "name": "Стенд сборочный универсальный", "workshop": "03", "power_kw": 0.0},
    {"ref": "uuid-e-03-2", "inventory_no": "03-002", "name": "Кантователь гидравлический 5т", "workshop": "03", "power_kw": 3.0},
    {"ref": "uuid-e-03-3", "inventory_no": "03-003", "name": "Пресс гидравлический 100т", "workshop": "03", "power_kw": 30.0},
    {"ref": "uuid-e-03-4", "inventory_no": "03-004", "name": "Стенд испытательный на герметичность", "workshop": "03", "power_kw": 5.5},
    {"ref": "uuid-e-03-5", "inventory_no": "03-005", "name": "УШМ (болгарка) 125 мм", "workshop": "03", "power_kw": 1.2},
    {"ref": "uuid-e-03-6", "inventory_no": "03-006", "name": "Дрель ручная электрическая", "workshop": "03", "power_kw": 0.6},
    # Окрасочный цех (04)
    {"ref": "uuid-e-04-1", "inventory_no": "04-001", "name": "Камера окрасочная 6×4×3", "workshop": "04", "power_kw": 15.0},
    {"ref": "uuid-e-04-2", "inventory_no": "04-002", "name": "Краскораспылитель SATA 4000", "workshop": "04", "power_kw": 0.0},
    {"ref": "uuid-e-04-3", "inventory_no": "04-003", "name": "Сушильная камера 80°C", "workshop": "04", "power_kw": 30.0},
    {"ref": "uuid-e-04-4", "inventory_no": "04-005", "name": "Пескоструйная камера", "workshop": "04", "power_kw": 7.5},
    # Контроль (05)
    {"ref": "uuid-e-05-1", "inventory_no": "05-001", "name": "Стол ОТК", "workshop": "05", "power_kw": 0.0},
    {"ref": "uuid-e-05-2", "inventory_no": "05-002", "name": "Твердомер ТЭМП-4", "workshop": "05", "power_kw": 0.5},
    {"ref": "uuid-e-05-3", "inventory_no": "05-003", "name": "Ультразвуковой дефектоскоп А1212", "workshop": "05", "power_kw": 0.3},
    {"ref": "uuid-e-05-4", "inventory_no": "05-004", "name": "Толщиномер ультразвуковой А1209", "workshop": "05", "power_kw": 0.2},
    {"ref": "uuid-e-05-5", "inventory_no": "05-005", "name": "Манометр образцовый МО-11202", "workshop": "05", "power_kw": 0.0},
    {"ref": "uuid-e-05-6", "inventory_no": "05-006", "name": "Шаблоны сварочные УШС-2", "workshop": "05", "power_kw": 0.0},
    {"ref": "uuid-e-05-7", "inventory_no": "05-007", "name": "Лупа измерительная 10×", "workshop": "05", "power_kw": 0.0},
]


def gen_equipment():
    xml = _make_xml(
        "Equipment",
        EQUIPMENT,
        "Equipment",
        attrs_func=lambda x: {
            "ref": x["ref"],
            "inventory_no": x["inventory_no"],
            "workshop_ref": f"workshop-{x['workshop']}",
        },
        text_func=lambda x: {
            "Name": x["name"],
            "PowerKW": x["power_kw"],
        },
    )
    out = OUTPUT_DIR / "equipment.xml"
    out.write_text(xml, encoding="utf-8")
    return out


# ============================================================
# 4. ПРОФЕССИИ (10+)
# ============================================================

PROFESSIONS = [
    {"ref": "uuid-p-r3", "code": "Р-3", "name": "Резчик", "grade": 3, "rate": 250.0},
    {"ref": "uuid-p-r4", "code": "Р-4", "name": "Резчик", "grade": 4, "rate": 290.0},
    {"ref": "uuid-p-s4", "code": "С-4", "name": "Слесарь-сборщик", "grade": 4, "rate": 300.0},
    {"ref": "uuid-p-s5", "code": "С-5", "name": "Слесарь-сборщик", "grade": 5, "rate": 340.0},
    {"ref": "uuid-p-e5", "code": "Э-5", "name": "Электросварщик ручной дуговой", "grade": 5, "rate": 380.0},
    {"ref": "uuid-p-e6", "code": "Э-6", "name": "Электросварщик ручной дуговой", "grade": 6, "rate": 430.0},
    {"ref": "uuid-p-g4", "code": "Г-4", "name": "Гибщик", "grade": 4, "rate": 290.0},
    {"ref": "uuid-p-k3", "code": "К-3", "name": "Контролёр ОТК", "grade": 3, "rate": 270.0},
    {"ref": "uuid-p-k4", "code": "К-4", "name": "Контролёр ОТК", "grade": 4, "rate": 310.0},
    {"ref": "uuid-p-m5", "code": "М-5", "name": "Маляр", "grade": 5, "rate": 320.0},
    {"ref": "uuid-p-t4", "code": "Т-4", "name": "Токарь", "grade": 4, "rate": 310.0},
    {"ref": "uuid-p-f4", "code": "Ф-4", "name": "Фрезеровщик", "grade": 4, "rate": 310.0},
]


def gen_professions():
    xml = _make_xml(
        "Professions",
        PROFESSIONS,
        "Profession",
        attrs_func=lambda x: {
            "ref": x["ref"],
            "grade": x["grade"],
        },
        text_func=lambda x: {
            "Code": x["code"],
            "Name": x["name"],
            "HourlyRate": x["rate"],
        },
    )
    out = OUTPUT_DIR / "professions.xml"
    out.write_text(xml, encoding="utf-8")
    return out


# ============================================================
# 5. ШАССИ (chassis.xml — отдельно)
# ============================================================

CHASSIS = [
    {"ref": "uuid-c-kamaz-43118", "designation": "КАМАЗ-43118", "name": "КАМАЗ-43118 6×6", "manufacturer": "ПАО КАМАЗ", "wheel_formula": "6×6", "curb_weight_kg": 10400, "payload_kg": 7000},
    {"ref": "uuid-c-kamaz-6520", "designation": "КАМАЗ-6520", "name": "КАМАЗ-6520 6×4", "manufacturer": "ПАО КАМАЗ", "wheel_formula": "6×4", "curb_weight_kg": 12800, "payload_kg": 14000},
    {"ref": "uuid-c-ural-4320", "designation": "УРАЛ-4320", "name": "УРАЛ-4320 6×6", "manufacturer": "АЗ УРАЛ", "wheel_formula": "6×6", "curb_weight_kg": 8400, "payload_kg": 12000},
    {"ref": "uuid-c-ural-5557", "designation": "УРАЛ-5557", "name": "УРАЛ-5557 4×4", "manufacturer": "АЗ УРАЛ", "wheel_formula": "4×4", "curb_weight_kg": 6900, "payload_kg": 5000},
]


def gen_chassis():
    xml = _make_xml(
        "Chassis",
        CHASSIS,
        "Chassis",
        attrs_func=lambda x: {"ref": x["ref"]},
        text_func=lambda x: {
            "Designation": x["designation"],
            "Name": x["name"],
            "Manufacturer": x["manufacturer"],
            "WheelFormula": x["wheel_formula"],
            "CurbWeightKG": x["curb_weight_kg"],
            "PayloadKG": x["payload_kg"],
        },
    )
    out = OUTPUT_DIR / "chassis.xml"
    out.write_text(xml, encoding="utf-8")
    return out


# ============================================================
# 6. МОДЕЛИ ИЗДЕЛИЙ
# ============================================================

PRODUCT_MODELS = [
    {"ref": "uuid-pm-1", "designation": "АЦ-8,0-40", "name": "Автоцистерна пожарная 8 м³ на шасси КАМАЗ-43118", "product_type": "АЦ", "chassis_ref": "uuid-c-kamaz-43118", "tu": "ТУ 4854-001-14937555-2018"},
    {"ref": "uuid-pm-2", "designation": "АЦ-6,0-40", "name": "Автоцистерна пожарная 6 м³ на шасси КАМАЗ-43118", "product_type": "АЦ", "chassis_ref": "uuid-c-kamaz-43118", "tu": "ТУ 4854-002-14937555-2018"},
    {"ref": "uuid-pm-3", "designation": "УМК-3,0-40", "name": "Установка комбинированная 3 м³ на шасси КАМАЗ-43118", "product_type": "УМК", "chassis_ref": "uuid-c-kamaz-43118", "tu": "ТУ 4854-003-14937555-2018"},
    {"ref": "uuid-pm-4", "designation": "ПСС-5,0-40", "name": "Пожарная насосная станция 5 м³/мин на шасси КАМАЗ-43118", "product_type": "ПСС", "chassis_ref": "uuid-c-kamaz-43118", "tu": "ТУ 4854-004-14937555-2018"},
    {"ref": "uuid-pm-5", "designation": "УМК-7,0-40", "name": "Установка комбинированная 7 м³ на шасси УРАЛ-4320", "product_type": "УМК", "chassis_ref": "uuid-c-ural-4320", "tu": "ТУ 4854-005-14937555-2018"},
]


def gen_product_models():
    xml = _make_xml(
        "ProductModels",
        PRODUCT_MODELS,
        "ProductModel",
        attrs_func=lambda x: {"ref": x["ref"]},
        text_func=lambda x: {
            "Designation": x["designation"],
            "Name": x["name"],
            "ProductType": x["product_type"],
            "ChassisRef": x["chassis_ref"],
            "TU": x["tu"],
        },
    )
    out = OUTPUT_DIR / "product_models.xml"
    out.write_text(xml, encoding="utf-8")
    return out


# ============================================================
# MAIN
# ============================================================

def generate_all(verbose: bool = True) -> int:
    """Сгенерировать все XML. Возвращает кол-во файлов."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = [
        gen_nomenclature(),
        gen_materials(),
        gen_equipment(),
        gen_professions(),
        gen_chassis(),
        gen_product_models(),
    ]
    if verbose:
        for f in files:
            size = f.stat().st_size
            n = sum(1 for _ in open(f, encoding="utf-8") if _.startswith("  <") and not _.startswith("  </"))
            print(f"  {f.name:25s} {size:6d} байт, {n} записей")
    return len(files)


if __name__ == "__main__":
    n = generate_all()
    print(f"\nСгенерировано файлов: {n}")
