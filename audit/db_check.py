"""DB check."""
import sqlite3
c = sqlite3.connect('/opt/beget/bit-technolog/data/bit_technolog_v0_8.db')
print(f"Items: {c.execute('SELECT COUNT(*) FROM items').fetchone()[0]}")
print(f"Test items: {c.execute(\"SELECT COUNT(*) FROM items WHERE designation LIKE 'TEST-%' OR designation LIKE 'RBAC-%' OR designation LIKE 'DBG-%'\").fetchone()[0]}")
print(f"Notices: {c.execute('SELECT COUNT(*) FROM change_notices').fetchone()[0]}")
print(f"Test notices: {c.execute(\"SELECT COUNT(*) FROM change_notices WHERE number LIKE 'И-%'\").fetchone()[0]}")
print(f"History: {c.execute('SELECT COUNT(*) FROM history').fetchone()[0]}")
print(f"Pilot_runs: {c.execute('SELECT COUNT(*) FROM pilot_runs').fetchone()[0]}")
print(f"Edits: {c.execute('SELECT COUNT(*) FROM edits').fetchone()[0]}")
print(f"Tech_cards: {c.execute('SELECT COUNT(*) FROM tech_cards').fetchone()[0]}")
