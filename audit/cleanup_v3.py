"""A3 cleanup v3: fix bom_links columns."""
import sqlite3, shutil, time

ts = int(time.time())
backup_name = f"data/bit_technolog_v0_8_pre-cleanup-a3-{ts}.db"
shutil.copy('data/bit_technolog_v0_8.db', backup_name)
print(f"Backup: {backup_name}")

c = sqlite3.connect('data/bit_technolog_v0_8.db')
c.execute("PRAGMA foreign_keys=ON")

# 1. Test items
test_items = c.execute("SELECT id, designation FROM items WHERE designation LIKE 'TEST-%' OR designation LIKE 'RBAC-%' OR designation LIKE 'DBG-%' OR designation LIKE 'TEST-UI-%'").fetchall()
print(f"1. Test items: {len(test_items)}")

# Find TCs
tc_to_delete = [r[0] for r in c.execute("SELECT id FROM tech_cards WHERE item_id IN (SELECT id FROM items WHERE designation LIKE 'TEST-%' OR designation LIKE 'RBAC-%' OR designation LIKE 'DBG-%' OR designation LIKE 'TEST-UI-%')").fetchall()]
print(f"   TCs: {len(tc_to_delete)}")

# Delete TCs
for tc_id in tc_to_delete:
    c.execute("DELETE FROM operations WHERE tech_card_id = ?", (tc_id,))
    c.execute("DELETE FROM edits WHERE tech_card_id = ?", (tc_id,))
    c.execute("DELETE FROM tech_cards WHERE id = ?", (tc_id,))
    c.execute("DELETE FROM pilot_runs WHERE tech_card_id = ?", (tc_id,))

# Delete items + their bom_links (parent_item_id or child_item_id)
for item_id, _ in test_items:
    c.execute("DELETE FROM items WHERE id = ?", (item_id,))
    c.execute("DELETE FROM bom_links WHERE parent_item_id = ? OR child_item_id = ?", (item_id, item_id))
    c.execute("DELETE FROM edits WHERE item_id = ?", (item_id,))

# 2. Test notices (exclude real pilot data)
test_notices = c.execute("SELECT id, number FROM change_notices WHERE (number LIKE 'И-TEST-%' OR number LIKE 'И-RBAC-%' OR number LIKE 'И-DBG-%' OR number LIKE 'И-UI-%' OR number LIKE 'И-A12-%' OR number LIKE 'И-V-%' OR number LIKE 'И-CYCLE%') AND number NOT LIKE 'И-2026-%'").fetchall()
print(f"2. Test notices: {len(test_notices)}")

for n_id, _ in test_notices:
    c.execute("DELETE FROM change_notices WHERE id = ?", (n_id,))
    c.execute("DELETE FROM history WHERE entity_type = 'notice' AND entity_id = ?", (n_id,))

# 3. Orphan history (items/tech_cards/operations that don't exist)
c.execute("DELETE FROM history WHERE (entity_type = 'item' AND entity_id NOT IN (SELECT id FROM items)) OR (entity_type = 'tech_card' AND entity_id NOT IN (SELECT id FROM tech_cards)) OR (entity_type = 'operation' AND entity_id NOT IN (SELECT id FROM operations))")
print(f"3. Cleaned orphan history")

# 4. Orphan pilot_runs
c.execute("DELETE FROM pilot_runs WHERE tech_card_id NOT IN (SELECT id FROM tech_cards) OR tech_card_id IS NULL")
print(f"4. Cleaned orphan pilot_runs")

c.commit()

# Verify
print("\n=== AFTER ===")
print(f"Items: {c.execute('SELECT COUNT(*) FROM items').fetchone()[0]}")
print(f"Notices: {c.execute('SELECT COUNT(*) FROM change_notices').fetchone()[0]}")
print(f"Tech_cards: {c.execute('SELECT COUNT(*) FROM tech_cards').fetchone()[0]}")
print(f"Operations: {c.execute('SELECT COUNT(*) FROM operations').fetchone()[0]}")
print(f"History: {c.execute('SELECT COUNT(*) FROM history').fetchone()[0]}")
print(f"Pilot_runs: {c.execute('SELECT COUNT(*) FROM pilot_runs').fetchone()[0]}")
print(f"Edits: {c.execute('SELECT COUNT(*) FROM edits').fetchone()[0]}")
print(f"Etalons: {c.execute('SELECT COUNT(*) FROM etalons').fetchone()[0]}")
