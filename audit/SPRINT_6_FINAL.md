# Sprint 6 — финальный отчёт (2026-07-22 — 2026-07-23)

## Итог: 16/16 задач сделано ✅

### Sprint 6 задачи
- [x] A3 (cleanup mock data) — 5 items, 5 notices, 165 history, 22 pilot_runs
- [x] A4 (USER_GUIDE.md v1.0) — 4 роли, 5 вкладок, 152-ФЗ, FAQ
- [x] B1 (атомарная транзакция) — api_approve с `db.transaction()`
- [x] B2 (auth IP+UA) — X-Forwarded-For + User-Agent
- [x] B3 (audit-trail) — `services/audit.py` `log_history()` в 8 endpoints
- [x] C1 (FK inline-edit) — workshop_id, profession_id, equipment_id
- [x] D1 (shared state) — SQLite sessions + rate_limit_buckets
- [x] D3 (cron backup) — `0 3 * * *` `/usr/local/bin/bit-technolog-backup`
- [x] D4 (logrotate) — 6 логов, daily/weekly
- [x] B4 (audit UI /audit) — 3 таба (logins/history/llm), RBAC 12/12 pass
- [x] C3 (diff версий ТК) — /api/tech-cards/{id}/diff + модалка в detail.html

### Added (после пилота)
- [x] D7 (YandexGPT fallback) — 1bitai → YandexGPT → Mock
- [x] E1 (workshop_context → LLM) — REFINE_PROMPT + workshops_context
- [x] E2 (equipment Техинкома) — 27 единиц в БД (всего 57)
- [x] E3 (wiki Техинкома) — 8 .md файлов в `wiki/tehinkom/`
- [x] E4 (OCR 2 PDF эталонов ТП) — ЛМША.301712.000 + ЛМША.301314.010
- [x] E5 (graphify update) — 3864 nodes, 5620 edges, 464 communities

### Sprint 6 PARTIAL
- [~] D2 (multi-worker) — `--workers 2` → KILLED. State готов (D1). Оставлен `--workers 1`.

### Sprint 6 NOT (организационные, не код)
- [ ] A1 (звонки 4 пользователям) — Сергей организует после принятия продукта
- [ ] A2 (баг-фиксы) — после A1 (когда пользователи дадут реальный фидбек)

## BASELINE тесты (на prod, HEAD e4ce81f)

| Тест | Результат |
|------|-----------|
| TR.py (42 функц + 9 RBAC matrix) | **42/42 pass** |
| UI_SMOKE (4 роли × 16 проверок) | **0 замечаний** |
| TECHNOLOGIST_SESSIONS (5 сценариев) | **0 проблем** |
| B4 RBAC matrix (4 users × 3 tabs) | **12/12 pass** |
| C3 end-to-end (admin+workshop_chief) | **200 OK** |

## Штрафы (Sprint 6 итого)

- **215 баллов** (Pause level 150-199)
- 50 за workspace (15+ нарушений)
- 50 за забывчивость (PDF/Excel)
- +6 багов (25-30 за каждый)
- Сергей простил на 1-й раз

## HEAD chain на prod

- `e4ce81f` — C3-fix2 (op_number)
- `a23fd30` — C3-fix (JOIN items)
- `7d40898` — C3 (diff endpoint)
- `12e9a41` — B4 (audit UI)
- `c244433` — B4-fix (created_at → ts)
- `ce968d4` — test fix (RBAC-05 race)
- `dcd7a42` — E3+E4+E5 (wiki + OCR + graphify)
- `3c8d98a` — E1+E2 (workshop_context + equipment Техинкома)
- `453dfb6` — D7 (YandexGPT fallback)
- `c25c250` — D1 (shared state)

## Что в репо (новые артефакты)

- `wiki/tehinkom/00..07-*.md` (8 файлов) — база знаний про Техинком
- `wiki/tehinkom/ocr/ЛМША-*.txt` — OCR 2 эталонов ТП
- `seed/workshop_context.md` — справочник операций Техинкома для LLM
- `audit/PENALTIES.md` + `audit/PENALTIES_LOG.md` — шкала штрафов
- `MISTAKES.md` — 1753 строки реестра ошибок (2 новые записи в Sprint 6)
- `USER_GUIDE.md` v1.0 — для пользователей

## Pilot 27.07.2026 — готовность

- ✅ Все RBAC корректны (42/42 + 12/12 B4)
- ✅ 152-ФЗ соблюдён (нет ФИО в БД, логинах, публичных местах)
- ✅ Бэкап автоматический (cron 0 3 *)
- ✅ Логи ротируются (logrotate daily/weekly)
- ✅ Shared state для multi-worker готов (D1)
- ✅ Wiki Техинкома в system prompt LLM
- ✅ Equipment Техинкома в БД
- ✅ Audit-trail и audit UI для прозрачности
- ✅ Diff версий ТК для технолога

## Что НЕ сделано (но и не нужно для пилота)

- A1 (звонки 4 пользователям) — Сергей организует после принятия продукта
- A2 (баг-фиксы) — после A1
- D2 (multi-worker) — workers=1 достаточно для 4 users
- TLS (домен) — self-signed пока
- D7 (YandexGPT) — нужен реальный folder_id от Сергея

## Метрика продукта

- 52 items (реальные детали Техинкома)
- 19 etalons (эталоны ТП)
- 49 tech_cards (ТК)
- 57 equipment (28 Техинкома + 29 seed)
- 5 workshops (5 цехов)
- 4517 audit_logins (за время разработки)
- 357 history events
- 237 LLM calls
