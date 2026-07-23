"""B3 verify: проверить что history пишется для разных actions."""
import sqlite3
c = sqlite3.connect('/opt/beget/bit-technolog/data/bit_technolog_v0_8.db')
print('Latest 10 history:')
for r in c.execute('SELECT id, entity_type, action, user, substr(details_json, 1, 100) FROM history ORDER BY id DESC LIMIT 10').fetchall():
    print(f'  id={r[0]} type={r[1]} action={r[2]} user={r[3]} details={r[4]}')
print()
# Stats by action
print('Counts by action:')
for r in c.execute('SELECT action, COUNT(*) FROM history GROUP BY action ORDER BY COUNT(*) DESC').fetchall():
    print(f'  {r[0]}: {r[1]}')
