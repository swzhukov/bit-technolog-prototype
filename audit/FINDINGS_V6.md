# M38-v6: чистый взгляд (5 вьюпойнтов)

**Дата:** 2026-07-23
**HEAD:** 5d40c45
**Тесты:** 40/42 pass (2 тест-бага, 9 skip)

## ВЬЮПОЙНТ 1: Цели/ценности — 152-ФЗ

### F6-152-001 [CRITICAL] ФИО в public полях UI
**Файл:** templates/detail.html:186, detail.html:483, notice_detail.html:43, notices.html:33
**Симптом:** UI отображает `e.approved_by`, `tech_card.author`, `notice.author` — ФИО из БД
**Риск:** workshop_chief, technologist — все видят ФИО коллег в публичных полях
**Данные:** pilot_users: `('Баранов А.Н.', 'baranov@tehinkom.ru')` — ФИО + email

### F6-152-002 [CRITICAL] user.display_name пишется в БД (approved_by, author, source_doc)
**Файл:** app.py:845, 1044, 1115, 1401, 1527, 1550, 1573, 1603
**Симптом:** При создании/утверждении/решении извещений — пишется ФИО, не username
**Риск:** Логи, бэкапы, отчёты содержат ФИО → утечка ПДн
**Fix:** Заменить `user.display_name` → `user.username` (login) во всех 8 местах

## ВЬЮПОЙНТ 2: Концепции — OK
- LLMProvider: 2+ реализации (1bitai, mock) ✅
- OneCGateway: 2 реализации (File, Http stub) ✅
- RAG + LLM refine ✅
- RBAC: _ROLE_ALIASES + normalize_user_role ДО check ✅
- РС-фабрика: 8 осей + is_deterministic ✅

## ВЬЮПОЙНТ 3: Реализация

### F6-IMP-001 [HIGH] Тест-раннер показывает false fail (RBAC-01, RBAC-05)
**Файл:** /workspace/audit/TR.py
**Симптом:** cookies не пересоздаются между пользователями → RBAC matrix ломается
**Риск:** нельзя автоматически проверить RBAC, ручной retest обязателен
**Fix:** Делать fresh login перед каждой RBAC-проверкой

### F6-IMP-002 [MEDIUM] print() в services/tp_parser.py
**Файл:** services/tp_parser.py:310
**Симптом:** `print(f"Согласовано: {tp.approved_by}")` — debug print в проде
**Риск:** засоряет journalctl, может логировать ФИО
**Fix:** Убрать или заменить на logger

## ВЬЮПОЙНТ 4: UX

### F6-UX-001 [MEDIUM] 9 skip = 9 потенциальных багов
**Файл:** TR.py (skip set)
**Симптом:** A03 (генерация 24с), A04 (progress overlay), A07 (кнопка аналоги), A09 (перегенерация), A14 (AI diff), B02/B06/B07 (RAG, rate, mock), B13 (inline-edit approved)
**Риск:** UI не проверен
**Fix:** Playwright автотесты

## ВЬЮПОЙНТ 5: Эксплуатация
- ✅ systemd работает
- ✅ /health с timeout
- ✅ rate-limit
- ✅ .gitignore для .env, .master_key, certs, data/*.db
- ❌ Нет /metrics для admin (но есть /metrics страница)

## Приоритеты

**CRITICAL (фиксить немедленно):**
- F6-152-001: ФИО в UI (4 места)
- F6-152-002: user.display_name в БД (8 мест)

**HIGH:**
- F6-IMP-001: тест-раннер fresh login

**MEDIUM:**
- F6-UX-001: Playwright для UI skip'ов
- F6-IMP-002: print() в проде

**Отложено в Sprint 6:**
- HttpGateway реальный
- Парсер OCR
