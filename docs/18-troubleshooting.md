# Troubleshooting — типичные проблемы и решения

> **Версия:** v0.4.12 (2026-07-20)
> **Аудитория:** админ Техинкома, разработчик

---

## Содержание

- [Проблемы с входом / ролями](#проблемы-с-входом--ролями)
- [Проблемы с генерацией AI](#проблемы-с-генерацией-ai)
- [Проблемы с UI](#проблемы-с-ui)
- [Проблемы с импортом/экспортом](#проблемы-с-импортомэкспортом)
- [Проблемы с производительностью](#проблемы-с-производительностью)
- [Проблемы с БД](#проблемы-с-бд)
- [Проблемы с деплоем](#проблемы-с-деплоем)
- [Проблемы с безопасностью](#проблемы-с-безопасностью)

---

## Проблемы с входом / ролями

### "Я переключил роль, но badge показывает старую"

**Причина:** в старых версиях cookie `bit_role` была с `HttpOnly`, JavaScript не мог её прочитать, и селектор сбрасывался на первую опцию.

**Решение:** обновитесь до v0.4.11+ (BUG-2026-07-20-01 fix). Cookie теперь без `HttpOnly`, badge в header обновляется всегда.

**Проверка:** откройте DevTools → Application → Cookies → найдите `bit_role`. Должна быть **без** флага `HttpOnly`.

---

### "Я в роли админа, но /admin возвращает 403"

**Причина:** cookie `bit_role` пустая или имеет несуществующую роль.

**Решение:**
1. Откройте селектор ролей в header
2. Выберите **🛡 Админ**
3. Подождите 600мс (reload)
4. Должен появиться красный badge **Админ**
5. Теперь `/admin` доступен

Если не помогло — почистите cookies для домена и повторите.

---

### "При переключении роли badge не обновляется"

**Причина:** JavaScript пытается перезагрузить страницу, но что-то блокирует.

**Решение:**
1. Откройте DevTools → Console
2. Ищите ошибки (особенно про `fetch` или `setTimeout`)
3. Если видите `Mixed Content` — откройте приложение по `http://` (не `https://`)
4. Если видите `CORS` — приложение и API на разных origin (не должно быть)

---

### "Пользователь говорит, что не может сменить роль"

**Причина:** старая версия (до v0.4.11) + cookie HttpOnly.

**Решение:** см. выше — обновитесь.

---

## Проблемы с генерацией AI

### "Генерация возвращает 429: daily_limit_exceeded"

**Причина:** дневной лимит LLM (200₽) исчерпан.

**Решение (3 варианта):**

1. **Подождать до завтра** — лимит сбрасывается в 00:00 МСК
2. **Увеличить лимит:** `/admin/settings` → `llm_daily_limit_rub` → `1000`
3. **Проверить, кто тратит:** `/admin/llm-calls` — сортировка по cost

**Проверка сколько осталось:** `/pilot` показывает "💰 X.XX₽ / 200₽ (Y%)"

---

### "Генерация возвращает 502 / timeout"

**Причина:** YandexGPT API не отвечает или таймаут 60 сек.

**Решение:**
1. Проверить статус YandexGPT: https://status.yandex.cloud/
2. Проверить API key: `/admin/settings` → `llm_api_key` (должен быть валидный)
3. Проверить folder_id: `/admin/settings` → `llm_folder_id`
4. Если YandexGPT лежит — система автоматически вернёт **mock-draft** через 60 сек (fallback в `app.py::generate()`)

---

### "AI генерирует ерунду / не те операции"

**Причина:** не хватает контекста в RAG или few-shot не подходит.

**Решение:**
1. Проверить RAG: `/pilot/learning` — если `rag_coverage < 50%`, добавьте детали
2. Залить **исторические ТК Техинкома** (50-100 штук) — куратор обещал 20 июля
3. Проверить few-shot: `few_shot.py` — если деталь не похожа на 3 эталона, AI "выдумывает"
4. Попробовать **другой тип детали** — может быть другая few-shot сработает

**Совет:** используйте 3-step flow (🤔 Уточнить → ⚡ Draft → ✨ Полная ТК). Полная ТК учитывает ваши ответы.

---

### "AI выдаёт операции не для того цеха"

**Причина:** модель путает цеха 1/2/3 (все 3 указаны в справочнике).

**Решение:**
1. Проверьте **department** в детали (если есть)
2. Используйте явные подсказки: в правилах технолога (`/detail/{id}` → "Правила технолога") напишите "Использовать только Цех 1"
3. Сообщите куратору — добавим в few-shot пример для этого цеха

---

### "Demo-режим вместо реального LLM"

**Причина:** `LLM_API_KEY` не задан или неверный.

**Решение:**
1. `/admin/settings` → группа **LLM (YandexGPT)**
2. Введите валидный API key
3. Сохраните
4. Перезапустите: `sudo systemctl restart bit-technolog`
5. Проверьте `/health` — `dependencies.llm` должен быть `"ok"` или `"auth_error"`, но **не** `"not_configured"`

---

## Проблемы с UI

### "В header нет селектора ролей"

**Причина:** старая версия (до v0.4.11).

**Решение:** обновитесь.

---

### "Кнопки утверждения не видны, хотя роль гл.технолог"

**Причина:** деталь в статусе `new` (без draft). Кнопка `Утвердить как гл. технолог` появляется только для `draft` или `approved`.

**Решение:** сначала сгенерируйте draft (AI-помощник → ⚡ Draft), потом утвердите как технолог (✅ Утвердить), потом появится `Утвердить как гл. технолог`.

---

### "AI-блок не виден для новой детали"

**Причина:** старая версия (до v0.4.12) — баг BUG-2026-07-20-02: AI-блок был внутри `{% if draft %}`, рендерился только если draft есть.

**Решение:** обновитесь до v0.4.12+.

---

### "Все кнопки маленькие / не тап-френдли на мобильном"

**Причина:** UI оптимизирован под desktop (1024+ px). Мобильная версия — в разработке (F16).

**Workaround:**
1. Используйте landscape ориентацию на планшете
2. Или desktop с большим экраном
3. В v0.5 (после пилота) будет полноценная мобильная версия

---

### "При нажатии '🤔 Уточнить' ничего не происходит"

**Причина:** JavaScript ошибка в DevTools.

**Решение:**
1. Откройте DevTools → Console
2. Найдите красные ошибки
3. Частая причина: `Mixed Content` (http/https конфликт) — откройте приложение по `http://`
4. Или `CORS` (если API на другом origin) — должно быть на одном

---

## Проблемы с импортом/экспортом

### "Импорт JSON возвращает 400 'invalid JSON'"

**Причина:** невалидный JSON (запятая в конце, кавычки неэкранированы).

**Решение:**
1. Проверьте JSON через `jq`: `cat details.json | jq`
2. Убедитесь, что нет trailing comma
3. Используйте UTF-8 кодировку без BOM

**Пример правильного JSON:**
```json
{
  "details": [
    {
      "designation": "АЦ-ХХХ",
      "name": "Деталь",
      "model": "АЦ-6,0-40",
      "chassis": "КАМАЗ-43118",
      "material": "Сталь 09Г2С",
      "size_mm": "100",
      "mass_kg": 5.0
    }
  ]
}
```

---

### "Импорт Excel возвращает 'mass_kg is not a number'"

**Причина:** в Excel колонка имеет текстовое значение (например, "5 кг" вместо "5").

**Решение:**
1. В Excel: `Формат ячеек → Число` (без "кг" в самой ячейке)
2. Или удалите единицы измерения, оставьте только числа
3. Или предварительно сохраните в CSV и импортируйте как JSON

---

### "PDF экспорт возвращает 500"

**Причина:** reportlab не может отрендерить (например, кириллица в шрифте).

**Решение:**
1. Проверьте логи: `sudo journalctl -u bit-technolog -n 50`
2. Убедитесь, что установлен шрифт с поддержкой кириллицы: `apt install fonts-liberation`
3. Перезапустите: `sudo systemctl restart bit-technolog`

---

### "1С CSV экспорт — неправильная кодировка"

**Причина:** 1С ожидает CP1251 или UTF-8-BOM.

**Решение:**
1. Откройте CSV в Excel: **Данные → Из текста → CP1251** (или UTF-8)
2. Или конвертните: `iconv -f UTF-8 -t CP1251 for_1c.csv > for_1c_cp1251.csv`

**Известное ограничение:** экспорт пока не настраивается (только UTF-8). В v0.5 добавим выбор кодировки.

---

## Проблемы с производительностью

### "Главная страница грузится 5+ секунд"

**Причина:** много деталей (>500) без индексов.

**Решение:**
1. Проверьте, что индексы созданы:
   ```sql
   sqlite3 /opt/beget/bit-technolog/bit_technolog.db "SELECT name FROM sqlite_master WHERE type='index';"
   ```
   Должны быть: `idx_details_model`, `idx_details_chassis`, `idx_details_status`, `idx_details_level`
2. Если нет — `ANALYZE;`
3. Если > 1000 деталей — добавьте пагинацию (в backlog)

---

### "Генерация draft 30-60 секунд"

**Причина:** YandexGPT Lite медленно обрабатывает длинный промт.

**Решение:**
1. Это нормально. Не прерывайте.
2. Используйте **3-step flow** для ускорения:
   - Шаг 1 (`🤔 Уточнить`) — 5-10 сек
   - Шаг 2 (`⚡ Draft`) — 10-15 сек (3 операции, 200 токенов)
   - Шаг 3 (`✨ Полная ТК`) — 30-60 сек (полный маршрут)
3. Если совсем медленно — проверьте статус YandexGPT

---

### "/admin/llm-calls зависает"

**Причина:** слишком много записей (1М+).

**Решение:**
1. Добавьте фильтр по дате: `/admin/llm-calls?days=7`
2. Retention policy (`cleanup_old_records`) должна очищать старше 90 дней
3. Если не сработало: `DELETE FROM llm_calls WHERE created_at < DATE('now', '-90 days');`

---

## Проблемы с БД

### "sqlite3: database is locked"

**Причина:** долгая транзакция (например, импорт 1000 деталей).

**Решение:**
1. Подождите 30-60 сек — транзакция завершится
2. Если не проходит — перезапустите сервис:
   ```bash
   sudo systemctl restart bit-technolog
   ```
3. **Не делайте** `kill -9` процесса uvicorn — это повредит WAL

---

### "БД повреждена (integrity_check != ok)"

**Причина:** аварийное завершение (kill -9, OOM killer, диск заполнен).

**Решение:**
1. **Попробовать восстановить:**
   ```bash
   sqlite3 bit_technolog.db ".recover" | sqlite3 recovered.db
   mv recovered.db bit_technolog.db
   ```
2. **Если не помогло — из бэкапа:**
   ```bash
   sudo systemctl stop bit-technolog
   LATEST=$(ls -t /opt/beget/backups/bit_technolog_*.db.gz | head -1)
   gunzip -c "$LATEST" > /opt/beget/bit-technolog/bit_technolog.db
   sudo systemctl start bit-technolog
   ```
3. **Если и бэкапа нет — позовите разработчика** (потеря данных)

---

### "БД растёт быстро (1+ ГБ)"

**Причина:** много логов `llm_calls` или `history` (без retention).

**Решение:**
1. Проверьте, что cron `cleanup_old_records` работает:
   ```bash
   cd /opt/beget/bit-technolog && ./venv/bin/python -c "from admin import cleanup_old_records; print(cleanup_old_records())"
   ```
2. Проверьте логи: `/var/log/bit-technolog/cleanup.log`
3. Если нужно срочно — запустите вручную:
   ```python
   # в Python
   from admin import cleanup_old_records
   cleanup_old_records()  # удалит: audit_logins > 180д, llm_calls > 90д, history > 365д
   ```

---

## Проблемы с деплоем

### "git pull не работает: Permission denied (publickey)"

**Причина:** SSH ключ не настроен или истёк.

**Решение:**
1. Проверьте: `ls -la /home/bit-technolog/.ssh/`
2. Должен быть файл `id_ed25519` (приватный) и `id_ed25519.pub` (публичный)
3. Если нет — сгенерируйте:
   ```bash
   sudo -u bit-technolog ssh-keygen -t ed25519 -N "" -f /home/bit-technolog/.ssh/id_ed25519
   ```
4. Добавьте публичный ключ в GitHub → Settings → Deploy keys
5. Проверьте: `sudo -u bit-technolog ssh -T git@github.com`

---

### "Тесты падают при деплое — deploy.sh откатывает"

**Причина:** в новом коде регрессия.

**Решение:**
1. Не паникуйте — deploy.sh **автоматически откатывает** на предыдущий коммит
2. Посмотрите, какие тесты упали: `sudo journalctl -u bit-technolog -n 200`
3. Исправьте код локально
4. Push → deploy.sh снова попробует
5. Если не понимаете — откатитесь вручную:
   ```bash
   cd /opt/beget/bit-technolog
   sudo -u bit-technolog git checkout main
   sudo systemctl restart bit-technolog
   ```

---

### "Сервис не стартует после обновления Python"

**Причина:** новые зависимости требуют другой Python (например, 3.12+).

**Решение:**
1. Установите нужную версию: `apt install python3.12`
2. Пересоздайте venv:
   ```bash
   cd /opt/beget/bit-technolog
   sudo -u bit-technolog rm -rf venv
   sudo -u bit-technolog python3.12 -m venv venv
   sudo -u bit-technolog venv/bin/pip install -r requirements.txt
   ```
3. Обновите systemd unit (`Environment="PATH=...venv/bin"`)

---

### "Sandbox wipe потерял SSH-пароль к серверу"

**Причина:** особенность Mavis — секреты между sandbox сессиями не сохраняются.

**Решение:**
1. Попросите куратора (Сергея) скинуть пароль в чат
2. Или восстановите из vcs backup: `cat /root/.mavis/secrets/beget_ssh`
3. Или используйте SSH по ключу (если настроен)

---

## Проблемы с безопасностью

### "Админ-панель доступна обычному пользователю"

**Причина:** баг в RBAC (не должно быть).

**Решение:**
1. Проверьте версию — все баги RBAC закрыты в v0.4.10+
2. Если обнаружили такой баг — **немедленно** сообщите разработчику
3. Workaround: установите `PILOT_AUTH_DISABLED=true` (выключит всех кроме admin)

---

### "CSRF ошибка при сохранении формы"

**Причина:** CSRF включен (по умолчанию в v0.4.10+), но в форме нет токена.

**Решение:**
1. Обновите страницу (`Ctrl+Shift+R` — hard reload)
2. Если не помогло — проверьте, что JavaScript не блокируется (cookies, расширения)
3. Workaround: `PILOT_CSRF_DISABLED=true` в `.env` (но **не** для production!)

---

### "Rate limit срабатывает слишком часто"

**Причина:** пользователь делает > 10 вызовов / минуту (нормально для тестирования).

**Решение:**
1. Подождите 60 сек
2. Или для тестов: `PILOT_RATELIMIT_DISABLED=true`
3. Если это реальный пользователь — увеличьте лимит в `app.py`:
   ```python
   @rate_limit(max_calls=20, period=60)  # было 10
   ```

---

## Универсальная диагностика

### Шаг 1: проверить сервис

```bash
sudo systemctl status bit-technolog
sudo journalctl -u bit-technolog -n 50
```

### Шаг 2: проверить /health

```bash
curl http://localhost:8081/health | jq
```

### Шаг 3: проверить БД

```bash
sqlite3 /opt/beget/bit-technolog/bit_technolog.db "PRAGMA integrity_check;"
sqlite3 /opt/beget/bit-technolog/bit_technolog.db "SELECT COUNT(*) FROM details;"
```

### Шаг 4: проверить .env

```bash
cat /opt/beget/bit-technolog/.env | grep -v "^#"
```

### Шаг 5: проверить логи

```bash
tail -50 /var/log/bit-technolog/app.log | python3 -c "
import json, sys
for line in sys.stdin:
    try:
        d = json.loads(line)
        if d.get('level') in ('ERROR', 'WARNING'):
            print(f\"[{d.get('ts')}] {d.get('level')}: {d.get('msg')}\")
    except: pass
"
```

### Шаг 6: перезапустить

```bash
sudo systemctl restart bit-technolog
sleep 3
curl http://localhost:8081/health
```

### Шаг 7: если ничего не помогло

Соберите диагностику и напишите разработчику:

```bash
# Создаёт файл diagnostics.txt с основной информацией
cd /opt/beget/bit-technolog
{
    echo "=== SYSTEM ==="
    uname -a
    cat /etc/os-release
    echo
    echo "=== SERVICE ==="
    sudo systemctl status bit-technolog --no-pager
    echo
    echo "=== HEALTH ==="
    curl -s http://localhost:8081/health
    echo
    echo
    echo "=== DB ==="
    sqlite3 bit_technolog.db "PRAGMA integrity_check; SELECT COUNT(*) FROM details; SELECT COUNT(*) FROM drafts;"
    echo
    echo "=== LAST 50 LOG LINES ==="
    tail -50 /var/log/bit-technolog/app.log
    echo
    echo "=== GIT ==="
    sudo -u bit-technolog git log --oneline -5
    echo
    echo "=== DISK ==="
    df -h /opt/beget/
} > diagnostics.txt

# Отправьте diagnostics.txt разработчику
```

---

## Экстренные контакты

- **Разработчик:** через Telegram PM (Сергей)
- **Хостер (Beget):** support@beget.com, +7 (812) 389-41-87
- **YandexGPT support:** через личный кабинет https://console.yandex.cloud/

---

## См. также

- [`19-security-compliance.md`](19-security-compliance.md) — что делать при инциденте
- [`17-deployment.md`](17-deployment.md) — полный deployment guide
- [`16-database-schema.md`](16-database-schema.md) — если проблема с БД
- [`20-faq.md`](20-faq.md) — FAQ
