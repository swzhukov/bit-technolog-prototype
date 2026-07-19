# Аудит v5 — БИТ.Технолог (чистый взгляд, цикл 5)

**Дата:** 2026-07-19
**Предыдущий:** AUDIT_v4.md
**Цикл:** v5
**Тесты:** 219/219 passing

---

## Новые замечания v5 (что не увидел в v1-v4)

### Критичные
| # | Уровень | Что |
|---|---|---|
| V5-1 | 🔴 | Backup test restore НЕ делал — backup есть, но восстановление не проверено |
| V5-2 | 🟡 | Нет FK constraints — orphan records (drafts при удалённой detail) |
| V5-3 | 🟡 | Нет indexes на details (model, chassis, status) — медленный поиск при росте |
| V5-4 | 🟡 | /health не проверяет LLM API / Telegram / SMTP (только БД и RAG) |
| V5-5 | 🟡 | Нет soft-delete для details (удаление = безвозвратно) |
| V5-6 | 🟢 | Нет admin guide (для Сергея как админа Техинкома) |
| V5-7 | 🟢 | README без раздела "Для кого это" (target audience) |
| V5-8 | 🟢 | Нет audit log для security events (approve, edit, delete — только approve сейчас) |
| V5-9 | 🟢 | Нет anomaly detection для cost (alert если >X₽ за час) |
| V5-10 | 🟢 | Структурные логи (JSON) — отложено с v3 |
| V5-11 | 🟢 | Нет cache headers для static — небольшие файлы, OK |
| V5-12 | 🟢 | Нет gzip для больших ответов |
| V5-13 | 🟢 | Тестов мало для edge cases (что если БД удалена, что если файл corrupted) |

### Свод v1-v4 (напоминание)
- v1-v4: 67 замечаний, 40 закрыто, 27 отложено
- 219/219 тестов
- 11 деплоев на production
- Готовность к пилоту 27 июля: 98%

---

## План v5

**Сделать в этом цикле (приоритеты):**
1. ✅ V5-1: backup restore test (КРИТИЧНО — backup бесполезен если нельзя restore)
2. ✅ V5-3: indexes на details (быстрый fix для performance)
3. ✅ V5-4: healthcheck для LLM/Telegram/SMTP (полезно для monitoring)
4. ✅ V5-6: admin guide (документация для Сергея)
5. ✅ V5-7: README target audience
6. ✅ V5-8: audit log для edit/delete events
7. ✅ V5-9: cost anomaly detection (alert если >50₽/час)
8. ✅ V5-12: gzip middleware (легко, полезно)

**Отложены (с обоснованием):**
- ⏸ V5-2 (FK constraints): рискованно сейчас, может сломать импорт
- ⏸ V5-5 (soft-delete details): требует много изменений, OK для пилота
- ⏸ V5-10 (JSON logs): отложено
- ⏸ V5-11 (cache headers): не критично
- ⏸ V5-13 (больше edge case тестов): OK
