"""Sprint 6 E2: load real Tehinkom equipment into equipment table."""
import sqlite3
import sys
import os

DB = '/workspace/bit-technolog-prototype/data/bit_technolog_v0_8.db'
if not os.path.exists(DB):
    print(f"DB not found: {DB}")
    sys.exit(1)

# Department → workshop_id
DEPT_TO_WS = {
    'УОМ': 1, 'УОМ(резерв)': 1,
    'ПКТ': 2,
    'ПВТ': 3, 'ПВТ(резерв)': 3,
    # 4 (Окрасочный), 5 (Контроль) — пока без equipment
}

# Type → "металлорежущее" / "сварочное" / "раскройное" / "прочее"
def classify(t):
    if not t:
        return 'прочее'
    t = t.strip()
    if t in ('Токарный', 'Сверлильный', 'Фрезерный'):
        return 'металлорежущее'
    if t in ('Раскрой', 'Лазер', 'Гибка'):
        return 'заготовительное'
    if t in ('Сборка', 'Маркировка'):
        return 'сборочное'
    return 'прочее'

# Read equipment file
equipment = []
with open('/workspace/bit-technolog-prototype/attachments/equipment_tehinkom.txt') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 5:
            continue
        name, year, dept, inv_no, kind = parts[0], parts[1], parts[2], parts[3], parts[4]
        workshop_id = DEPT_TO_WS.get(dept)
        if not workshop_id:
            print(f"SKIP (unknown dept '{dept}'): {line}")
            continue
        type_kind = classify(kind)
        # ref_1c = uuid
        ref_1c = f'uuid-teh-{inv_no.lower().replace("-", "")}'
        equipment.append((inv_no, name, type_kind, workshop_id, 0.0, ref_1c, kind))

# Apply to DB
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

# Get existing inventory_nos
existing = {r['inventory_no'] for r in c.execute('SELECT inventory_no FROM equipment')}
print(f"Existing equipment: {len(existing)} rows")

added = 0
skipped = 0
for inv_no, name, type_kind, ws_id, power, ref_1c, kind_orig in equipment:
    if inv_no in existing:
        skipped += 1
        continue
    c.execute(
        '''INSERT INTO equipment (inventory_no, name, type, workshop_id, power_kw, ref_1c)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (inv_no, name, type_kind, ws_id, power, ref_1c)
    )
    added += 1
    print(f"  + {inv_no:8} | ws={ws_id} | {type_kind:18} | {name[:50]}")

c.commit()
print(f"\nAdded: {added}, Skipped (already exists): {skipped}")
print(f"Total now: {c.execute('SELECT COUNT(*) FROM equipment').fetchone()[0]}")

# Show type distribution
print("\nType distribution:")
for t, n in c.execute("SELECT type, COUNT(*) FROM equipment GROUP BY type ORDER BY 2 DESC"):
    print(f"  {t or '(NULL)'}: {n}")

print("\nWorkshop distribution:")
for w, n in c.execute('''SELECT w.code || ' ' || w.name, COUNT(e.id)
                          FROM workshops w LEFT JOIN equipment e ON e.workshop_id = w.id
                          GROUP BY w.id ORDER BY w.id'''):
    print(f"  {w}: {n}")

c.close()
