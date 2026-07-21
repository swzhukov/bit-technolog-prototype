"""
one_c_loader.py — загрузчик НСИ из XML 1С в локальную БД.

Sprint 7: «Эмуляция 1С:ERP актуального релиза».

Использует FileGateway для чтения XML и переносит в наши таблицы:
- chassis → chassis
- product_models → product_models
- nomenclature → items (с parent_ref → parent_item_id, material_ref → material_id)
- materials → materials
- equipment → equipment
- professions → professions
- bom_links — НЕ из XML (нет в эмуляции, но архитектурно поддерживается)

Идемпотентность: при повторной загрузке обновляет, а не дублирует.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from repositories import db
from gateways.one_c_gateway import FileGateway

logger = logging.getLogger(__name__)


def load_nomenclature(gw: FileGateway) -> int:
    """Загрузить номенклатуру (items) из XML."""
    items = gw.get_nomenclature()
    loaded = 0
    for it in items:
        # Идемпотентность: обновляем или создаём (по ref_1c или designation)
        existing = db.query_one("SELECT id FROM items WHERE ref_1c = ? OR designation = ?", (it.ref_1c, it.designation))
        # Найти material_id по ref
        material_id = None
        if it.material_ref:
            m = db.query_one("SELECT id FROM materials WHERE ref_1c = ?", (it.material_ref,))
            if m:
                material_id = m["id"]
        # Найти parent_item_id
        parent_id = None
        if it.parent_ref:
            p = db.query_one("SELECT id FROM items WHERE ref_1c = ?", (it.parent_ref,))
            if p:
                parent_id = p["id"]
        if existing:
            db.execute("""
                UPDATE items SET designation=?, name=?, level=?, mass_kg=?, material_id=?, parent_item_id=?
                WHERE id=?
            """, (it.designation, it.name, it.level, it.mass_kg, material_id, parent_id, existing["id"]))
        else:
            db.insert_and_get_id("items", {
                "designation": it.designation,
                "name": it.name,
                "level": it.level,
                "type": "деталь" if it.level == "detail" else it.level,
                "mass_kg": it.mass_kg,
                "material_id": material_id,
                "parent_item_id": parent_id,
                "sourcing": it.sourcing,
                "ref_1c": it.ref_1c,
            })
        loaded += 1
    return loaded


def load_materials(gw: FileGateway) -> int:
    """Загрузить материалы из XML."""
    materials = gw.get_materials()
    loaded = 0
    for m in materials:
        existing = db.query_one("SELECT id FROM materials WHERE ref_1c = ? OR code = ?", (m.ref_1c, m.code))
        if existing:
            db.execute("""
                UPDATE materials SET code=?, name=?, category=?, unit=?, price_per_unit=?
                WHERE id=?
            """, (m.code, m.name, "прочее", m.unit, m.price_per_unit, existing["id"]))
        else:
            db.insert_and_get_id("materials", {
                "code": m.code,
                "name": m.name,
                "category": "прочее",
                "unit": m.unit,
                "price_per_unit": m.price_per_unit,
                "ref_1c": m.ref_1c,
            })
        loaded += 1
    return loaded


def load_equipment(gw: FileGateway) -> int:
    """Загрузить оборудование из XML."""
    equipment = gw.get_equipment()
    loaded = 0
    for e in equipment:
        # workshop_ref в формате "workshop-01" → code "01"
        workshop_code = e.workshop_ref.replace("workshop-", "")
        w = db.query_one("SELECT id FROM workshops WHERE code = ?", (workshop_code,))
        workshop_id = w["id"] if w else None
        existing = db.query_one("SELECT id FROM equipment WHERE ref_1c = ? OR inventory_no = ?", (e.ref_1c, e.inventory_no))
        if existing:
            db.execute("""
                UPDATE equipment SET inventory_no=?, name=?, workshop_id=?, power_kw=?
                WHERE id=?
            """, (e.inventory_no, e.name, workshop_id, 0.0, existing["id"]))
        else:
            db.insert_and_get_id("equipment", {
                "inventory_no": e.inventory_no,
                "name": e.name,
                "workshop_id": workshop_id,
                "power_kw": 0.0,
                "ref_1c": e.ref_1c,
            })
        loaded += 1
    return loaded


def load_professions(gw: FileGateway) -> int:
    """Загрузить профессии из XML."""
    profs = gw.get_professions_tariffs()
    loaded = 0
    for p in profs:
        existing = db.query_one("SELECT id FROM professions WHERE ref_1c = ? OR code = ?", (p.ref_1c, p.code))
        if existing:
            db.execute("""
                UPDATE professions SET code=?, name=?, category=?, grade=?, hourly_rate=?
                WHERE id=?
            """, (p.code, p.name, "рабочий", p.grade, p.hourly_rate, existing["id"]))
        else:
            db.insert_and_get_id("professions", {
                "code": p.code,
                "name": p.name,
                "category": "рабочий",
                "grade": p.grade,
                "hourly_rate": p.hourly_rate,
                "ref_1c": p.ref_1c,
            })
        loaded += 1
    return loaded


def load_chassis(gw: FileGateway) -> int:
    """Загрузить шасси напрямую из XML (минуя FileGateway — там нет метода)."""
    import xml.etree.ElementTree as ET
    f = gw.exchange_dir / "in" / "chassis.xml"
    if not f.exists():
        return 0
    try:
        tree = ET.parse(f)
    except Exception:
        return 0
    loaded = 0
    for c in tree.findall(".//Chassis"):
        ref = c.get("ref", "")
        designation = c.findtext("Designation", "")
        name = c.findtext("Name", "")
        manufacturer = c.findtext("Manufacturer", "")
        wheel_formula = c.findtext("WheelFormula", "")
        curb = float(c.findtext("CurbWeightKG", 0) or 0)
        payload = float(c.findtext("PayloadKG", 0) or 0)
        existing = db.query_one("SELECT id FROM chassis WHERE ref_1c = ? OR designation = ?", (ref, designation))
        if existing:
            db.execute("""
                UPDATE chassis SET designation=?, name=?, manufacturer=?, wheel_formula=?, curb_weight_kg=?, payload_kg=?
                WHERE id=?
            """, (designation, name, manufacturer, wheel_formula, curb, payload, existing["id"]))
        else:
            db.insert_and_get_id("chassis", {
                "designation": designation,
                "name": name,
                "manufacturer": manufacturer,
                "wheel_formula": wheel_formula,
                "curb_weight_kg": curb,
                "payload_kg": payload,
                "ref_1c": ref,
            })
        loaded += 1
    return loaded


def load_product_models(gw: FileGateway) -> int:
    """Загрузить модели изделий из XML."""
    import xml.etree.ElementTree as ET
    f = gw.exchange_dir / "in" / "product_models.xml"
    if not f.exists():
        return 0
    try:
        tree = ET.parse(f)
    except Exception:
        return 0
    loaded = 0
    for pm in tree.findall(".//ProductModel"):
        ref = pm.get("ref", "")
        designation = pm.findtext("Designation", "")
        name = pm.findtext("Name", "")
        ptype = pm.findtext("ProductType", "")
        chassis_ref = pm.findtext("ChassisRef", "")
        tu = pm.findtext("TU", "")
        chassis_id = None
        if chassis_ref:
            c = db.query_one("SELECT id FROM chassis WHERE ref_1c = ?", (chassis_ref,))
            if c:
                chassis_id = c["id"]
        existing = db.query_one("SELECT id FROM product_models WHERE ref_1c = ? OR designation = ?", (ref, designation))
        if existing:
            db.execute("""
                UPDATE product_models SET designation=?, name=?, product_type=?, chassis_id=?, tu_doc=?
                WHERE id=?
            """, (designation, name, ptype, chassis_id, tu, existing["id"]))
        else:
            db.insert_and_get_id("product_models", {
                "designation": designation,
                "name": name,
                "product_type": ptype,
                "chassis_id": chassis_id,
                "tu_doc": tu,
                "ref_1c": ref,
            })
        loaded += 1
    return loaded


def load_all_from_1c(verbose: bool = True) -> Dict[str, int]:
    """Загрузить всю НСИ из XML в БД. Идемпотентно."""
    gw = FileGateway()
    gw.connect()

    results = {}
    results["chassis"] = load_chassis(gw)
    results["product_models"] = load_product_models(gw)
    results["materials"] = load_materials(gw)
    results["professions"] = load_professions(gw)
    results["equipment"] = load_equipment(gw)
    # nomenclature — после materials (зависит)
    results["items"] = load_nomenclature(gw)

    if verbose:
        for k, v in results.items():
            print(f"  {k:20s}: {v}")
    return results


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    db.init_db()
    results = load_all_from_1c()
    total = sum(results.values())
    print(f"\nЗагружено записей: {total}")
