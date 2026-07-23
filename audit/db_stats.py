"""A3: count tables on prod."""
import sqlite3
c = sqlite3.connect('/opt/beget/bit-technolog/data/bit_technolog_v0_8.db')
for t in ['drafts', 'draft_versions', 'pilot_runs', 'llm_calls', 'pilot_metrics', 'iot', 'kompas_events', 'ext_attributes', 'benchmarks', 'pilot_users', 'work_history', 'edits']:
    try:
        n = c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        print(f'  {t}: {n}')
    except Exception as e:
        print(f'  {t}: ERR {e}')
