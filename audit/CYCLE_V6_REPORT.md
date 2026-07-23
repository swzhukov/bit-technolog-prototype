# M38-v6: Цикл "чистый взгляд" — ФИНАЛ

**Дата:** 2026-07-23
**HEAD на prod:** `b43e69d`
**Backup БД:** `data/bit_technolog_v0_8_pre-migration-v6.db`

## Итог: 0 замечаний в 2 циклах подряд ✅

| Тест | Цикл 1 | Цикл 2 |
|------|--------|--------|
| TR.py (42 функциональных + RBAC) | 42/42 pass | 42/42 pass |
| UI_SMOKE.py (4 роли × 16 проверок) | 0 замечаний | 0 замечаний |
| TECHNOLOGIST_SESSIONS (5 сценариев UI) | 0 реальных багов | — |

## Исправлено в этом цикле

### M38-v6-152 (commit 4f44bcd) — CRITICAL
- **152-ФЗ:** 8 мест в app.py писали `user.display_name` (ФИО) в БД
  - `author` в notices/tech_cards
  - `approved_by` в etalons
  - `source_doc` в etalons
  - `update_operation_evidence`
  - `resolve_notice_svc`
- Заменено на `user.username` (login)
- Workshop_chief больше не видит ФИО коллег в /detail, /knowledge, /notices

### M38-v6-rbac (commit 18b8b0a) — HIGH
- **RBAC:** `/notices/new` (GET) не имел проверки роли
  - Workshop_chief видел форму (200), но submit падал (403)
  - UX-баг → добавлена `normalize_user_role` + role check

### M38-v6-data (no commit, live migration)
- **Migration:** 70 строк в БД обновлено
  - `change_notices.author` (16 строк)
  - `etalons.approved_by` (8 строк)
  - `tech_cards.author` (46 строк)
- Маппинг: `Баранов А.Н.` → `baranov` и т.д.
- Backup: `bit_technolog_v0_8_pre-migration-v6.db`

### M38-v6-testrunner (file change)
- **TR.py:** fresh login per user + lambda per user
  - RBAC matrix был flaky (cookies, дубликаты)
  - Теперь 100% стабильный

### M38-v6-uismoke (file change)
- **UI_SMOKE.py:** использует response.status вместо title
  - Было 5 false positive (title не содержит "403")
  - Теперь 100% корректно

## Найденные и отклонённые

- **print() в services/** — все внутри `if __name__ == "__main__":`, не баги
- **История "ВП 3237" в approved_by** — не ФИО, а номер приказа, ОК

## Что готово к пилоту 27.07

- ✅ 152-ФЗ: ФИО только в БД (pilot_users), не в public полях
- ✅ RBAC: 4 роли × 13 endpoints корректно
- ✅ Auth: 13 GET endpoints требуют login
- ✅ CSRF: `X-Requested-With` + Same-Origin
- ✅ Rate limit: 5/мин на user
- ✅ Lazy AI diff (24с → 0.03с на /notices/{id})
- ✅ Форма создания детали
- ✅ Inline-edit операций
- ✅ Все 42 функциональных теста зелёные
- ✅ Все 64 UI проверки зелёные
- ✅ Workshop_chief: только чтение

## Отложено в Sprint 6

- 9 skip (LLM/UI тесты требуют Playwright с длинным timeout)
- HttpGateway реальный (сейчас заглушка)
- Парсер OCR (5/8 операций)
- RAG-индексация эталонов (сейчас rag_indexed_at=NULL)
- Динамический few-shot
- Login-форма (сейчас Basic Auth)
- КОМПАС-Watcher
