"""Show LLM providers on prod."""
import sqlite3
c = sqlite3.connect('/opt/beget/bit-technolog/data/bit_technolog_v0_8.db')
print('llm_providers:')
for r in c.execute("SELECT id, name, display_name, is_active, model_default, length(api_key_enc) as enc_len FROM llm_providers").fetchall():
    print(' ', r)
print('llm_model_assignments:')
for r in c.execute("SELECT id, task_type, llm_provider_id, model_name FROM llm_model_assignments").fetchall():
    print(' ', r)
