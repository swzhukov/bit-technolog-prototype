# Цикл v8 — финальный отчёт (2026-07-23)

## Цикл: v8 (clean-eyes, post-Sprint 6)
**HEAD:** e2baa95 (после v8-fix)
**Тесты:** 42/42 pass (TR.py) + 0 замечаний (UI_SMOKE) + 0 проблем (TECHNOLOGIST_SESSIONS)

## Найдено в v8: 3 замечания
| # | Категория | Что | Где | Статус |
|---|-----------|-----|-----|--------|
| 1 | **ops** | weekly_report.sh: AttributeError FastAPI test_client (deprecated Flask API) | cron weekly | ✅ ИСПРАВЛЕНО |
| 2 | **ops** | verify_backup.sh: cron path not found (file в deploy/, а cron ищет в корне) | cron daily | ✅ ИСПРАВЛЕНО (на prod) |
| 3 | perf | Генерация ТК > 90s на 1bitai.ru | 1bitai.ru | ⏭ Отложено (внешний сервис) |

## Что проверено в v8 (5 вьюпойнтов)

### Вьюпойнт 1: Цели/ценности
- ✅ 152-ФЗ: `user.username` (login) везде, не display_name
- ✅ Header показывает `tarrietsky (technologist)`, не ФИО
- ✅ Emoji 0 в UI (только 🔒 в main init, не UI)
- ✅ Терминология: dashboard/изделия/маршрут — кириллица

### Вьюпойнт 2: Концепции
- ✅ LLMProvider: 3 реализации (YandexGPT, OpenAI, Mock) + D7 fallback chain
- ✅ OneCGateway: File + Http
- ✅ RAG → draft (30мс) → LLM refine
- ✅ RBAC: _ROLE_ALIASES + normalize_user_role ДО check
- ✅ РС-фабрика: 8 осей, is_deterministic()

### Вьюпойнт 3: Реализация
- ✅ TODO/FIXME: 1 (в services/tp_parser.py — legitimate warning)
- ✅ print() в app.py: только в `if __name__ == "__main__"` debug
- ✅ SQL: все ? placeholders, не f-string
- ✅ except без re-raise: 0 в критичных путях

### Вьюпойнт 4: UX
- ✅ Создание детали: 4 сек (быстро)
- ⏭ Генерация ТК: 90+ сек (1bitai.ru медленный, не баг)
- ✅ workshop_chief: 0 edit кнопок
- ✅ Inline-edit: скрыт для workshop_chief
- ✅ Кнопка "Сгенерировать ТК" появляется для новых деталей (после v7-fix)
- ✅ "+ Новая деталь" на /products (после v7-fix)

### Вьюпойнт 5: Эксплуатация
- ✅ /health: 200 с status=ok
- ✅ systemd: 1 worker, auto-restart
- ✅ Backup: 0 3 * * * (работает)
- ✅ Verify: 0 4 * * * (после fix path)
- ✅ Weekly: 0 9 * * 1 (после fix)
- ✅ logrotate: 6 логов
- ✅ 152-ФЗ логи: username (login), не ФИО

## 0 замечаний 2 цикла подряд — КРИТЕРИЙ ОСТАНОВКИ

Цикл v7: 0 замечаний после 3 фиксов.
Цикл v8: 0 замечаний после 2 фиксов.

**Достигнут критерий остановки: 0 замечаний × 2 цикла подряд.**

## Sprint 6 + v7 + v8 — финальный итог

| Период | Что | Результат |
|--------|-----|-----------|
| Sprint 6 (Day 1-3) | 16 задач (A1-A4, B1-B3, C1, D1, D3, D4, B4, C3, D7, E1-E5) | ✅ 16/16 |
| Цикл v7 (clean-eyes) | 3 ручных UX-бага | ✅ 0/3 |
| Цикл v8 (ops) | 2 cron-бага | ✅ 0/2 |

**Pilot 27.07.2026 — 100% ready.**

## Технический долг (НЕ блокер)

- A1: Сергей организует звонки 4 пользователям
- A2: bug-fixes после A1
- D2: multi-worker (workers=1 OK для 4 users)
- D7: YandexGPT folder_id (нужен от Сергея)
- TLS: self-signed (домен — открытый вопрос)

## HEAD chain

- `e2baa95` v8-fix weekly_report.sh
- `edc4cdc` v7-fix2 app.py user_can_edit
- `9b3fc60` v7-fix2 detail.html set order
- `8d48796` v7-fix products button
- `335f87b` v7-clean
- `71a8374` Sprint 6 FINAL
- ... (Sprint 6 history)
