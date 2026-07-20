# FAQ — Часто задаваемые вопросы

> **Версия:** v0.4.12 (2026-07-20)
> **Для кого:** все пользователи

---

## Содержание

- [Общие вопросы](#общие-вопросы)
- [О системе](#о-системе)
- [Для технолога](#для-технолога)
- [Для админа](#для-админа)
- [Для разработчика](#для-разработчика)
- [История версий](#история-версий)
- [Как сообщить о баге](#как-сообщить-о-баге)

---

## Общие вопросы

### Что такое БИТ.Технолог?

AI-помощник технолога для создания техкарт на детали в 1С:ERP. Помогает технологу
создать техкарту в 5–10 раз быстрее, чем вручную.

### Для кого это?

Для заводов, которые производят детали (особенно серийные) и где технолог тратит
много времени на рутинное создание ТК.

### Первая инсталляция — где?

ООО «ПК Техинком-Центр» (Москва, пожарные автоцистерны). Пилот 27 июля 2026.

### Сколько стоит?

- Лицензия: MIT (бесплатно)
- LLM: ~200₽/день на 1-3 активных технологов
- Сервер: ~500₽/месяц (Beget VPS 2 vCPU / 2 ГБ RAM)

### Можно использовать в другом заводе?

Да, MIT лицензия. Потребуется:
1. Адаптировать few-shot (3 эталонных примера)
2. Адаптировать синонимы материалов (лемматизация)
3. Залить исторические ТК (50-100) для RAG
4. Настроить экономику (ставки цехов)
5. Обучить пользователей

---

## О системе

### Какой AI используется?

YandexGPT Lite через OpenAI-совместимый API. Можно заменить на OpenAI/Anthropic/etc.

### А это безопасно? Данные уходят в Yandex?

Да, текстовый промт с описанием детали уходит в YandexGPT API. Это **обязательно**
для генерации. Варианты:
- Использовать on-premise LLM (Llama 3 70B) — в планах (F14)
- Использовать гибрид: on-premise для черновиков, YandexGPT для финала

### А что с 152-ФЗ?

См. [`19-security-compliance.md`](19-security-compliance.md). Короткий ответ:
на текущей версии **ФИО не хранятся** (только роли), это **не ПДн**.

### Как часто обновляется?

По необходимости. Цикл:
1. Куратор пишет фичи/баги
2. Разработчик делает + тестирует + коммитит
3. deploy.sh на сервере обновляет автоматически
4. Тесты прогоняются (252/252 ✓)

### А если интернет пропадёт?

Система **on-premise** — без интернета работает 100% функций, **кроме**:
- Генерация через YandexGPT (требует интернет)
- Telegram-алерты (не критично)
- Обновления через `git pull`

В demo-режиме (`DEMO_MODE=true`) генерация работает **без интернета** (используется
локальный эвристический mock).

---

## Для технолога

### Как создать первую деталь?

1. Главная → `＋ Деталь`
2. Заполните **обязательно**: обозначение, наименование, модель (шасси), материал, размер, масса
3. Поверхностная обработка — опционально (но без неё AI не предложит операции окраски)
4. `💾 Сохранить`
5. Откроется карточка детали
6. AI-помощник (открыт по умолчанию) → `🤔 Уточнить` → `⚡ Draft` → `✨ Полная ТК`
7. `✅ Утвердить` (4 галочки в чеклисте)
8. `📤 Загрузить` или `📊 Excel` (для 1С)

### Сколько времени занимает создание ТК?

- **Без системы (в Excel):** 1-2 часа на деталь
- **С системой (3-step flow):** 15-30 минут (включая проверку AI)
- **С системой (кнопка "Сгенерировать"):** 5-10 минут (быстрее, но менее точно)

### AI выдаёт мусор, что делать?

1. **Проверьте** входные данные — чем точнее обозначение, наименование, материал, тем лучше
2. **Используйте 3-step flow** (Уточнить → Draft → Полная ТК) — AI учитывает ваши ответы
3. **Добавьте правила** в "Правила технолога" (например, "Не использовать нержавейку")
4. **Сообщите куратору** — добавим в few-shot

### Как вернуть утверждённую ТК в работу?

1. Откройте деталь в статусе `🟢 Утверждён`
2. `Вернуть в работу` (красная кнопка)
3. Укажите причину
4. Деталь вернётся в статус `🟡 Проект ТК`
5. Отредактируйте, утвердите заново

### Как сравнить 2 версии ТК?

1. Откройте деталь
2. URL: `/detail/{id}/diff/1/3` (сравнить v1 и v3)
3. Откроется diff — зелёным добавлено, красным удалено

### Можно ли редактировать утверждённую ТК?

**Нет** (это by design — защита от случайных изменений).

**Workaround:** вернуть в работу через `Вернуть в работу` → отредактировать → утвердить заново.

### Как удалить деталь?

**Прямого удаления нет** (для безопасности данных).

**Workaround:** пометить как `deleted` через прямой SQL:
```sql
-- через sqlite3 или Python
UPDATE details SET deleted_at = DATETIME('now') WHERE id = 'd-xxx';
```
(в будущем добавим soft-delete UI)

---

## Для админа

### Как добавить YandexGPT API key?

1. Переключитесь в роль **Админ**
2. **Настройки** (`/admin/settings`) → группа **LLM (YandexGPT)**
3. Введите `LLM_API_KEY` (из https://console.yandex.cloud/)
4. Введите `LLM_FOLDER_ID`
5. Сохраните
6. Проверьте `/health` — `dependencies.llm` должен быть `"ok"` или `"auth_error"`

### Как сделать бэкап вручную?

```bash
cd /opt/beget/bit-technolog
bash backup.sh
ls -lh /opt/beget/backups/ | tail -5
```

Или через UI: **Админ → Бэкап → Скачать .db**

### Как восстановить из бэкапа?

```bash
sudo systemctl stop bit-technolog
LATEST=$(ls -t /opt/beget/backups/bit_technolog_*.db.gz | head -1)
gunzip -c "$LATEST" > /opt/beget/bit-technolog/bit_technolog.db
sudo systemctl start bit-technolog
curl http://localhost:8081/health
```

### Как посмотреть, кто сколько потратил LLM?

1. **LLM-вызовы** (`/admin/llm-calls`)
2. Фильтр по `days=7` (последняя неделя)
3. Сортировка по `cost_rub DESC`

Или **Пилот → Отчёт** (`/pilot/report?days=30`)

### Как очистить старые логи?

Автоматически (cron `cleanup_old_records`):
- `audit_logins` > 180 дней
- `llm_calls` > 90 дней
- `history` > 365 дней

Вручную:
```bash
cd /opt/beget/bit-technolog
./venv/bin/python -c "
from admin import cleanup_old_records
print(cleanup_old_records())
"
```

### Что делать, если сервис не стартует?

См. [`18-troubleshooting.md`](18-troubleshooting.md) § Универсальная диагностика.

Короткий план:
1. `sudo journalctl -u bit-technolog -n 50` — посмотреть ошибки
2. `curl http://localhost:8081/health` — проверить
3. `sqlite3 bit_technolog.db "PRAGMA integrity_check;"` — проверить БД
4. `sudo systemctl restart bit-technolog` — перезапустить
5. Если не помогло — собрать `diagnostics.txt` (см. troubleshooting)

### Как обновить систему?

```bash
cd /opt/beget/bit-technolog
sudo -u bit-technolog bash deploy.sh
```

deploy.sh автоматически: git pull → pip install → pytest → restart.

### Как откатиться на старую версию?

```bash
cd /opt/beget/bit-technolog
sudo -u bit-technolog git log --oneline -10   # выбрать коммит
sudo -u bit-technolog git checkout abc1234
sudo systemctl restart bit-technolog
```

---

## Для разработчика

### Как добавить новый endpoint?

См. [`13-developer-guide.md`](13-developer-guide.md) § "Как добавить endpoint".

Короткий план:
1. Добавить функцию в `app.py` (или в новый модуль)
2. Зарегистрировать: `@app.post("/api/my-endpoint")`
3. RBAC: проверить роль в начале
4. Тест: добавить в `test_app.py`
5. Запустить: `pytest test_app.py -q`

### Как добавить новую роль?

1. `app.py` → `ROLES` — добавить новую роль
2. `app.py` → role-based access — добавить проверки в endpoints
3. `templates/base.html` → добавить option в `<select id="role-switcher">`
4. `templates/index.html` → добавить в quick-role кнопки (если нужно)
5. `docs/14-roles-user-guide.md` → описать роль
6. Тесты в `test_app.py`

### Как изменить UI?

1. `templates/*.html` — изменить разметку
2. `static/style.css` — стили
3. `static/htmx.min.js` — НЕ трогать (это библиотека)
4. Тесты: `check_all_roles.py` для визуальной проверки

### Как добавить новую таблицу в БД?

1. `db.py` → `init_db()` → добавить `CREATE TABLE IF NOT EXISTS ...`
2. Если нужны индексы — добавить `CREATE INDEX IF NOT EXISTS ...`
3. Функции для CRUD: добавить в `db.py`
4. Тесты: проверка создания/чтения/удаления

### Где логи?

- `/var/log/bit-technolog/app.log` — все логи (JSON)
- `sudo journalctl -u bit-technolog` — systemd journal
- `/admin/errors` — последние 50 ошибок (V8-18)

### Как дебажить?

```python
# В Python
import logging
log = logging.getLogger("bit-technolog")
log.info("что-то произошло", extra={"detail_id": "d-xxx"})

# В консоли
cd /opt/beget/bit-technolog
sudo -u bit-technolog ./venv/bin/python -c "
import app
# ... дебаг
"
```

---

## История версий

### v0.4.12 (2026-07-20) — BUG-2026-07-20-02
- **AI-блок виден для новых деталей** (раньше был внутри `{% if draft %}`, невидим)
- 7/7 ролей проверены через `check_all_roles.py`
- 253/253 тестов passing

### v0.4.11 (2026-07-20) — BUG-2026-07-20-01
- **Визуальный badge роли** в header (цветной, с иконкой)
- **3 кнопки быстрой смены роли** на главной (для показа клиенту)
- Cookie `bit_role` убрана `HttpOnly` (JS может читать)
- 252/252 тестов passing

### v0.4.10 (2026-07-19) — BUG-2026-07-19-01/02
- **RBAC** на `/api/generate`, `/api/analyze`, `/api/draft-fast`, `/api/refine` (403 для не-technologist)
- AI-блок скрыт для `normirovshchik/quality/constructor/workshop_chief`
- `surface_treatment=None` → TypeError fix (None-safe)
- 247/247 тестов passing

### v0.4.9 (2026-07-19) — F15.7 + v8 аудит
- **admin.py** через APIRouter (admin endpoints вынесены, -116 строк в app.py)
- Error 500 с debugging ID (8-char UUID)
- Логотип Техинкома в print.html
- 244/244 тестов passing

### v0.4.8 (2026-07-19) — v7 аудит
- flake8 fix, logrotate конфиг, LICENSE (MIT + 14 компонентов)
- Issue templates, health_check.sh, importers validation
- 236/236 тестов passing

### v0.4.7 (2026-07-18) — v6 аудит
- 152-ФЗ compliance guide, backup encryption (gpg), retention policy
- Filter save в localStorage, aria-label, глобальный JS error handler
- JSON логи, now_msk() timezone-aware, developer guide
- 225/225 тестов passing

### v0.4.5-v0.4.6 (2026-07-17) — v5/v4 аудит
- Backup verify, indexes, /health dependencies, logrotate
- LLM cost check, 429 при 100% лимита, favicon, version в /health
- 219/219 тестов passing

### v0.4.0-v0.4.4 (2026-07-15) — v1-v3 аудиты
- CSP middleware, rate limiting, indexes
- CSRF opt-in, MISTAKES.md, e2e tests
- 194/194 → 212 тестов passing

### v0.3.x (2026-07-10) — Demo-ready
- Базовый функционал: создание, генерация, утверждение, экспорт
- 3-step UX (Уточнить → Draft → Полная ТК)
- RAG (TF-IDF + cosine + hybrid)
- Few-shot (сварка, гидравлика, электрика)
- Лемматизация (pymorphy2, 30+ синонимов)
- Экономика (process-based pricing)
- Pre-approve checklist (4 пункта)
- Self-timer + auto-metrics

### v0.1-v0.2 (2026-06-25 — 2026-07-05) — Прототип
- Базовая архитектура: FastAPI + Jinja2 + HTMX + SQLite
- Справочники (оборудование, материалы, ИОТ, бенчмарки)
- Импорт (JSON, Excel, PDF)
- 1С CSV экспорт
- Печатная форма с QR

---

## Как сообщить о баге

### Если нашли баг

**1. Проверьте, что это не известная проблема:**
- [`18-troubleshooting.md`](18-troubleshooting.md) — типичные проблемы
- [GitHub Issues](https://github.com/your-org/bit-technolog-prototype/issues) — известные баги

**2. Соберите информацию:**
- Что делали (шаги для воспроизведения)
- Что ожидали
- Что получилось
- Скриншот (если UI)
- Версия (`/health` → `version` + `git_commit`)

**3. Сообщите одним из способов:**

- **Telegram** — куратору (Сергей Жуков) — быстро
- **GitHub Issue** — через [bug_report.md template](../.github/ISSUE_TEMPLATE/bug_report.md) — для документирования
- **Email** — admin@tehincom.ru (если настроен)

**4. Severity:**
- 🔴 **Critical** — сервис не работает, потеря данных
- 🟠 **High** — основная функция не работает
- 🟡 **Medium** — работает, но неудобно
- 🟢 **Low** — косметика

**5. Если баг CRITICAL** (потеря данных, безопасность):
- Немедленно сообщите куратору (Telegram)
- Не перезапускайте сервис (может потерять логи)
- Сделайте бэкап: `bash backup.sh` (с uid процесса)

---

## Как предложить фичу

1. **Сначала проверьте roadmap** — [`10-product-fit-and-roadmap.md`](10-product-fit-and-roadmap.md)
2. **Опишите use case** — зачем нужно, какую проблему решает
3. **Оцените impact** — сколько пользователей, как часто
4. **Создайте feature request** в GitHub (через template)
5. **Обсудите с куратором** перед реализацией

---

## См. также

- [`00-README.md`](00-README.md) — главный README со всей навигацией
- [`14-roles-user-guide.md`](14-roles-user-guide.md) — руководство по 7 ролям
- [`15-api-reference.md`](15-api-reference.md) — полный API
- [`18-troubleshooting.md`](18-troubleshooting.md) — troubleshooting
- [`19-security-compliance.md`](19-security-compliance.md) — 152-ФЗ
