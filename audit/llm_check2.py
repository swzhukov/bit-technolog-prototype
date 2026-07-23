import sqlite3
c = sqlite3.connect('/opt/beget/bit-technolog/data/bit_technolog_v0_8.db')
print('PROVIDERS:')
for r in c.execute('SELECT id, name, is_active, model_default FROM llm_providers').fetchall():
    print(' ', r)
print('ASSIGNMENTS:')
for r in c.execute('SELECT id, task_type, llm_provider_id FROM llm_model_assignments').fetchall():
    print(' ', r)
