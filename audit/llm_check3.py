import sqlite3
c = sqlite3.connect('/opt/beget/bit-technolog/data/bit_technolog_v0_8.db')
print('llm_providers schema:')
for r in c.execute('PRAGMA table_info(llm_providers)').fetchall():
    print(' ', r)
print('llm_providers data:')
for r in c.execute('SELECT * FROM llm_providers').fetchall():
    print(' ', r)
print('llm_model_assignments schema:')
for r in c.execute('PRAGMA table_info(llm_model_assignments)').fetchall():
    print(' ', r)
print('llm_model_assignments data:')
for r in c.execute('SELECT * FROM llm_model_assignments').fetchall():
    print(' ', r)
