import sqlite3
c = sqlite3.connect('/workspace/bit-technolog-prototype/data/bit_technolog_v0_8.db')
print('TABLES:')
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
for t in tables:
    print(f'  {t}')
print(f'TOTAL: {len(tables)}')
print()
print('FK на items:')
for r in c.execute('PRAGMA foreign_key_list(items)').fetchall():
    print(f'  {r[3]} -> {r[2]}({r[4]})')
print()
print('ITEMS:', c.execute('SELECT COUNT(*) FROM items').fetchone()[0])
print('ETALONS:', c.execute('SELECT COUNT(*) FROM etalons').fetchone()[0])
print('TECH_CARDS:', c.execute('SELECT COUNT(*) FROM tech_cards').fetchone()[0])
print('OPERATIONS:', c.execute('SELECT COUNT(*) FROM operations').fetchone()[0])
print('NOTICES:', c.execute('SELECT COUNT(*) FROM change_notices').fetchone()[0])
print('USERS:', c.execute('SELECT COUNT(*) FROM users').fetchone()[0])
print('MATERIALS:', c.execute('SELECT COUNT(*) FROM materials').fetchone()[0])
print('WORKSHOPS:', c.execute('SELECT COUNT(*) FROM workshops').fetchone()[0])
print('OPERATIONS_HISTORY:', c.execute('SELECT COUNT(*) FROM history').fetchone()[0])
