"""A3: cleanup check + script for prod."""
import sqlite3
c = sqlite3.connect('/opt/beget/bit-technolog/data/bit_technolog_v0_8.db')

print('=== A3 PROD STATE ===')
print(f"Items total: {c.execute('SELECT COUNT(*) FROM items').fetchone()[0]}")
test_items = c.execute("SELECT COUNT(*) FROM items WHERE designation LIKE 'TEST-%' OR designation LIKE 'RBAC-%' OR designation LIKE 'DBG-%' OR designation LIKE 'TEST-UI-%'").fetchone()[0]
print(f"Test items: {test_items}")
test_notices = c.execute("SELECT COUNT(*) FROM change_notices WHERE number LIKE 'И-%'").fetchone()[0]
print(f"Test notices: {test_notices}")
print(f"TC approved=0: {c.execute('SELECT COUNT(*) FROM tech_cards WHERE is_approved=0').fetchone()[0]}")
print(f"TC approved=1: {c.execute('SELECT COUNT(*) FROM tech_cards WHERE is_approved=1').fetchone()[0]}")

# Sample test items
if test_items > 0:
    print("\nSample test items:")
    for r in c.execute("SELECT id, designation FROM items WHERE designation LIKE 'TEST-%' OR designation LIKE 'RBAC-%' LIMIT 5").fetchall():
        print(f"  {r}")
