"""D1 verify."""
import sqlite3
c = sqlite3.connect('/opt/beget/bit-technolog/data/bit_technolog_v0_8.db')
print('Tables with session/rate:')
for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'session%' OR name LIKE 'rate%')").fetchall():
    print(' ', r[0])
print('sessions count:', c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0])
print('rate_limit count:', c.execute('SELECT COUNT(*) FROM rate_limit_buckets').fetchone()[0])
