"""B2 verify: audit_logins содержит IP и UA."""
import sqlite3
c = sqlite3.connect('/opt/beget/bit-technolog/data/bit_technolog_v0_8.db')
print('Last 5 audit_logins:')
for r in c.execute('SELECT id, username, ip, user_agent, success, reason, created_at FROM audit_logins ORDER BY id DESC LIMIT 5').fetchall():
    print(f'  {r}')
print()
# Count by IP filled vs empty
filled = c.execute('SELECT COUNT(*) FROM audit_logins WHERE ip != ""').fetchone()[0]
empty = c.execute('SELECT COUNT(*) FROM audit_logins WHERE ip = "" OR ip IS NULL').fetchone()[0]
print(f'With IP: {filled}, Without IP: {empty}')
ua_filled = c.execute('SELECT COUNT(*) FROM audit_logins WHERE user_agent != ""').fetchone()[0]
ua_empty = c.execute('SELECT COUNT(*) FROM audit_logins WHERE user_agent = "" OR user_agent IS NULL').fetchone()[0]
print(f'With UA: {ua_filled}, Without UA: {ua_empty}')
