# Sprint 6 — статус (2026-07-23, обновлено)

## Сделано за Day 1-3

### Sprint 6 задачи (12 MUST + 5 added)
- [x] A3 (cleanup mock data) — 5 items, 5 notices, 165 history, 22 pilot_runs
- [x] A4 (USER_GUIDE.md v1.0) — 4 роли, 5 вкладок, 152-ФЗ, FAQ
- [x] B1 (атомарная транзакция) — api_approve с `db.transaction()`
- [x] B2 (auth IP+UA) — X-Forwarded-For + User-Agent
- [x] B3 (audit-trail) — `services/audit.py` `log_history()` в 8 endpoints
- [x] C1 (FK inline-edit) — workshop_id, profession_id, equipment_id
- [x] D1 (shared state) — SQLite sessions + rate_limit_buckets
- [x] D3 (cron backup) — `0 3 * * *` `/usr/local/bin/bit-technolog-backup`
- [x] D4 (logrotate) — 6 логов, daily/weekly
- [x] D7 (YandexGPT fallback) — 1bitai → YandexGPT → Mock
- [x] E1 (workshop_context → LLM) — REFINE_PROMPT + workshops_context
- [x] E2 (equipment Техинкома) — 27 единиц в БД (всего 57)
- [x] E3 (wiki Техинкома) — 8 .md файлов в `wiki/tehinkom/`
- [x] E4 (OCR 2 PDF эталонов ТП) — ЛМША.301712.000 + ЛМША.301314.010
- [x] E5 (graphify update) — 3864 nodes, 5620 edges, 464 communities

### Sprint 6 PARTIAL
- [~] D2 (multi-worker) — `--workers 2` → KILLED. State готов (D1). Оставлен `--workers 1`.

### Sprint 6 ОСТАЛОСЬ
- [ ] A1 (звонки пользователям) — Сергей организует после принятия продукта
- [ ] A2 (баг-фиксы) — после A1
- [x] B4 (audit UI /audit) — 3 таба (logins/history/llm), фильтры, RBAC 12/12 pass

## BASELINE тесты (на prod)

| Тест | Результат |
|------|-----------|
| TR.py (42 функц + 9 RBAC matrix) | **42/42 pass** |
| UI_SMOKE (4 роли × 16 проверок) | **0 замечаний** |
| TECHNOLOGIST_SESSIONS (5 сценариев) | **0 проблем** |

## Штрафы (Sprint 6 итого)

- **215 баллов** (Pause уровень 150-199, т.к. 50 за workspace + 50 за забывчивость)
- Сергей простил на 1-й раз

## HEAD на prod

`ce968d4` — audit tests fix (TR.py RBAC-05 + TECHNOLOGIST_SESSIONS)
`dcd7a42` — Sprint 6 E3+E4+E5 (wiki + OCR + graphify)
`3c8d98a` — Sprint 6 E1+E2 (workshop_context + equipment Техинкома)
`453dfb6` — Sprint 6 D7 (YandexGPT fallback)
`c25c250` — Sprint 6 D1 (shared state)

## Заметки

- Pilot 27.07.2026 (через 4 дня)
- Сергей должен принять продукт и попробовать поработать технологом ДО передачи пользователям
- A1 (звонки) отложен до явного согласования
- TLS — self-signed пока; домен в открытых вопросах
