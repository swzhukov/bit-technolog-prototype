"""
economics.py — модуль расчёта себестоимости (v0.4.9, F15).
Выделено из app.py.
Process-based pricing (CADDi pattern): трудоёмкость по цехам + материал + накладные.
"""
from db import get_draft, get_detail


def calc_cost_estimate(detail_id: str) -> dict:
    """Sprint 1: Process-based pricing (CADDi pattern) — разбивка по этапам маршрута.
    Returns dict с total_hours, labor_cost, material_cost, overhead, total_cost, price, by_department.
    Пустой dict если нет draft или detail."""
    draft = get_draft(detail_id)
    detail = get_detail(detail_id)
    if not draft or not detail:
        return {}
    operations = draft["output"].get("operations", [])
    total_hours = sum(op.get("duration_hours", 0) for op in operations)
    cost_per_hour = detail.get("cost_per_hour") or 0
    material_cost = detail.get("material_cost_rub") or 0
    overhead_pct = detail.get("overhead_pct") or 0

    # Группировка по цехам (process-based breakdown)
    breakdown_by_dept = {}
    for op in operations:
        dept = op.get("department") or "Без цеха"
        if dept not in breakdown_by_dept:
            breakdown_by_dept[dept] = {"hours": 0.0, "operations": 0, "labor_cost": 0.0}
        breakdown_by_dept[dept]["hours"] += op.get("duration_hours", 0)
        breakdown_by_dept[dept]["operations"] += 1
    for d in breakdown_by_dept.values():
        d["hours"] = round(d["hours"], 2)
        d["labor_cost"] = round(d["hours"] * cost_per_hour, 2)

    # Распределение материала по этапам пропорционально часам
    material_by_dept = {}
    for dept, d in breakdown_by_dept.items():
        share = (d["hours"] / total_hours) if total_hours else 0
        material_by_dept[dept] = round(material_cost * share, 2)

    labor_cost = total_hours * cost_per_hour
    direct_cost = labor_cost + material_cost
    overhead = direct_cost * (overhead_pct / 100)
    total_cost = direct_cost + overhead
    price = total_cost * 1.3  # 30% наценка

    return {
        "total_hours": round(total_hours, 2),
        "labor_cost": round(labor_cost, 2),
        "material_cost": round(material_cost, 2),
        "direct_cost": round(direct_cost, 2),
        "overhead_pct": overhead_pct,
        "overhead": round(overhead, 2),
        "total_cost": round(total_cost, 2),
        "price": round(price, 2),
        "by_department": [
            {"department": dept, "hours": d["hours"], "operations": d["operations"],
             "labor_cost": d["labor_cost"], "material_cost": material_by_dept[dept]}
            for dept, d in sorted(breakdown_by_dept.items(), key=lambda x: -x[1]["hours"])
        ]
    }
