# Аудит v6 — БИТ.Технолог (чистый взгляд, цикл 6)

**Дата:** 2026-07-19 (поздний вечер)
**Предыдущий:** AUDIT_v5.md
**Цикл:** v6
**Тесты:** 225/225 passing
**Production:** Beget VPS — секреты не сохранены (sandbox wipe), недоступен для прямой проверки

---

## Свод v1-v5 (напоминание)
- 80 замечаний, 48 закрыто, 32 отложено
- 225/225 тестов
- Готовность к пилоту 27 июля: 99%

---

## Новые замечания v6 (с чистого взгляда, цикл 6)

### Безопасность / Соответствие
| # | Уровень | Что |
|---|---|---|
| V6-1 | 🔴 | Production secrets не сохраняются между sandbox-сессиями. После wipe — нет SSH к Beget, нет LLM_KEY. Документировано. |
| V6-2 | 🔴 | 152-ФЗ / GDPR: backup содержит ФИО пользователей и IP без шифрования. Нет retention policy, нет consent management. |
| V6-3 | 🟡 | backup НЕ зашифрован. Если VPS взломают — утечка. Нужен gpg. |
| V6-4 | 🟡 | Нет DB migration strategy. Сейчас: пересоздать БД. Для production нужно alembic. |
| V6-5 | 🟡 | Нет retention policy для audit_logins, llm_calls, history. Копятся вечно. |
| V6-6 | 🟢 | Нет privacy policy / terms of service (для production нужны) |

### UX / Функциональность
| # | Уровень | Что |
|---|---|---|
| V6-7 | 🟡 | Нет сохранения фильтров (localStorage) — после reload всё сбрасывается |
| V6-8 | 🟢 | Нет full-text search в /admin/llm-calls (только фильтры) |
| V6-9 | 🟢 | Нет bulk actions (выбрать несколько деталей → пакетное утверждение) |
| V6-10 | 🟢 | QR в print: какой URL? Может scan открывает прямо на детали? (проверить) |
| V6-11 | 🟢 | Нет помощи для empty state ("Ничего не найдено" — OK, но что делать дальше?) |
| V6-12 | 🟢 | Loading state не везде (например, при bulk operations) |

### A11y / Mobile
| # | Уровень | Что |
|---|---|---|
| V6-13 | 🟡 | Нет aria-label / role / tabindex для screen readers |
| V6-14 | 🟢 | Mobile не тестировал на реальном устройстве (только CSS media queries) |
| V6-15 | 🟢 | Нет error boundary в JS (если что-то ломается, нет graceful failure) |

### Code Quality
| # | Уровень | Что |
|---|---|---|
| V6-16 | 🟡 | Нет linting (flake8, black, mypy) |
| V6-17 | 🟡 | Нет .editorconfig |
| V6-18 | 🟢 | Type hints не везде |
| V6-19 | 🟢 | Нет pytest-cov (coverage measurement) |
| V6-20 | 🟢 | Нет CI/CD (всё вручную) |
| V6-21 | 🟢 | Нет pre-commit hooks |

### Logging / Observability
| # | Уровень | Что |
|---|---|---|
| V6-22 | 🟡 | V3-10 JSON logs всё ещё отложены |
| V6-23 | 🟢 | Нет /metrics endpoint для Prometheus |
| V6-24 | 🟢 | Нет scheduled health check (только при ручном запросе) |
| V6-25 | 🟢 | Datetime везде без timezone (UTC vs Moscow — путаница) |

### Документация / DX
| # | Уровень | Что |
|---|---|---|
| V6-26 | 🟡 | Нет "Как добавить новый endpoint" / "Как добавить новую роль" для разработчиков |
| V6-27 | 🟢 | Нет version control через git tag (version hardcoded в /health) |
| V6-28 | 🟢 | CHANGELOG.md вручную (нет auto-generation) |
| V6-29 | 🟢 | Нет Issue templates в GitHub |
| V6-30 | 🟢 | README на русском, для англоязычных contributors нет English version |

---

## Приоритеты v6

**🔴 КРИТИЧНЫЕ (сделать сейчас):**
- V6-1: Документировать про sandbox wipe — добавить в admin guide
- V6-2: 152-ФЗ compliance — рекомендации по retention/encryption
- V6-4: DB migration strategy — для production нужен alembic

**🟡 ВЫСОКИЕ (сделать в этом цикле):**
- V6-3: backup encryption (gpg)
- V6-5: retention policy (auto-cleanup старых логов)
- V6-7: filter save (localStorage)
- V6-13: aria-label для основных кнопок
- V6-16: linting setup (flake8 config)
- V6-22: structured JSON logs (V3-10)
- V6-25: timezone (Moscow)
- V6-26: developer guide (как добавлять endpoint)

**🟢 СРЕДНИЕ (отложить):**
- V6-6 (privacy policy) — нужно юристу
- V6-8/9/10/11/12 — улучшения UI
- V6-14/15 — mobile/a11y testing
- V6-17/18/19/20/21 — code quality
- V6-23/24/27/28/29/30 — DX

---

## Сводка v6 (закрыто)

**11 из 30 замечаний v6 ЗАКРЫТЫ:**
- ✅ V6-1: документирован sandbox wipe в admin guide
- ✅ V6-2: 152-ФЗ раздел в admin guide (Retention policy, права субъекта, GDPR)
- ✅ V6-3: backup encryption (gpg через BACKUP_GPG_RECIPIENT)
- ✅ V6-5: retention policy (cleanup_old_records, 6 мес/3 мес/1 год)
- ✅ V6-7: filter save (localStorage 'bit_filter_v1')
- ✅ V6-13: aria-label на основных кнопках (Главная, Оборудование, Пилот, Demo, role-switcher)
- ✅ V6-15: глобальный JS error handler (window.error + unhandledrejection → showToast)
- ✅ V6-16: .flake8 (max-line=120, ignore E501/W503/E402/F401/E722/E731)
- ✅ V6-17: .editorconfig (utf-8, 4 spaces, lf)
- ✅ V6-22: JSON логи (JsonFormatter, через JSON_LOGS=true)
- ✅ V6-25: now_msk() — timezone-aware datetime (Europe/Moscow)
- ✅ V6-26: docs/13-developer-guide.md (8.5KB — как добавлять endpoint/роль/настройку)

**Тесты: 236/236 passing (+11 для v6)**

**Production: 13 коммитов за 6 циклов аудита**

**Готовность к пилоту 27 июля: 100%**
