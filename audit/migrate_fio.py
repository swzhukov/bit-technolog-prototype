"""M38-v6 migration: заменить ФИО → username в существующих строках."""
import sqlite3

c = sqlite3.connect('/opt/beget/bit-technolog/data/bit_technolog_v0_8.db')
FIO_TO_LOGIN = {
    "Баранов А.Н.": "baranov",
    "Воробьев И.Ф.": "vorobyev",
    "Голубев П.В.": "golubev",
    "Тарлецкий А.С.": "tarrietsky",
    "Тех. администратор": "techadmin",
    "LLM администратор": "llmadmin",
}

def map_fio(v):
    if not v:
        return v
    for fio, login in FIO_TO_LOGIN.items():
        if v == fio or v.strip() == fio:
            return login
    return v

total = 0
for table, col in [("change_notices", "author"), ("etalons", "approved_by"), ("tech_cards", "author")]:
    print(f"=== {table}.{col} ===")
    for r in c.execute(f"SELECT id, {col} FROM {table}").fetchall():
        new_val = map_fio(r[1])
        if new_val != r[1]:
            print(f"  {r[0]}: {r[1]!r} -> {new_val!r}")
            c.execute(f"UPDATE {table} SET {col}=? WHERE id=?", (new_val, r[0]))
            total += 1

c.commit()
print(f"\nUpdated: {total}")

# Verify
fio_left = 0
for table, col in [("change_notices", "author"), ("etalons", "approved_by"), ("tech_cards", "author")]:
    for fio in FIO_TO_LOGIN.keys():
        cnt = c.execute(f"SELECT COUNT(*) FROM {table} WHERE {col}=?", (fio,)).fetchone()[0]
        if cnt > 0:
            print(f"WARN: {table}.{col}: {cnt} rows with FIO {fio!r}")
            fio_left += cnt
print(f"FIO left: {fio_left}")
