# Гайд для администратора — БИТ.Технолог

> **Дата:** 2026-07-19
> **Для кого:** Сергей (админ на стороне Техинкома) — отвечает за работоспособность системы в пилотный период (27 июля 2026 - август 2026).

---

## 0. ⚠️ Критично: 152-ФЗ (Российский GDPR)

### Что мы храним
- **ФИО пользователей** (pilot_users: display_name)
- **IP-адреса** (audit_logins: ip)
- **User-Agent** (audit_logins: user_agent)
- **Контент LLM-промтов** (llm_calls: system_prompt, user_prompt) — может содержать детали
- **История действий** (history: details) — кто что менял

### Retention policy (V6-5)
| Таблица | Срок хранения | Начало очистки |
|---|---|---|
| `audit_logins` | 180 дней (6 мес) | автоматически (ежемесячно) |
| `llm_calls` | 90 дней (3 мес) | автоматически |
| `history` | 365 дней (1 год) | автоматически |

Ручная очистка: `python -c "from app import cleanup_old_records; print(cleanup_old_records())"`

### Backup encryption (V6-3)
- Если настроен `BACKUP_GPG_RECIPIENT` — backup шифруется gpg
- Без gpg — backup НЕ зашифрован (риск при взломе VPS!)
- Рекомендация: настроить gpg до пилота

### Права субъекта данных (если попросят)
- **Право на информацию** — этот раздел
- **Право на удаление** — пока нет UI, но можно SQL: `DELETE FROM pilot_users WHERE username='X'`
- **Право на портативность** — `/api/export/all` возвращает всю БД в JSON
- **Согласие** — формальные согласия не собираем, но это внутрикорпоративный инструмент (сотрудники Техинкома)

### Что НЕ делаем
- Не передаём данные третьим лицам (YandexGPT — облако, но провайдер подчиняется 152-ФЗ)
- Не используем cookies для tracking (только session cookies)

---

## 0.1 ⚠️ Sandbox wipe

### Проблема
**Mavis работает в cloud sandbox, который может быть очищен между сессиями.**
После wipe:
- ❌ SSH ключи к Beget VPS теряются
- ❌ LLM_API_KEY (если был в .env) — нет, он в БД через Fernet
- ❌ Cookies и сессии
- ❌ Загруженные файлы

### Что сохраняется
- ✅ GitHub репозиторий (полный код)
- ✅ Код в /workspace (на момент wipe — может быть в архиве)
- ✅ Production VPS (Beget) — независим от sandbox

### Что делать если wipe
1. Подключиться к Beget заново (пароль в твоём хранилище, не в sandbox)
2. `cd /opt/beget/bit-technolog && git pull` — код всегда актуален
3. Если LLM key потерялся — `/admin/settings` показывает masked значение, но проще ввести заново
4. Если backup не делался в этом цикле — используй предыдущий

---

## 1. Доступы

### Production сервер
- **URL:** `http://217.114.7.5:8081`
- **Логин:** `user`
- **Пароль:** `secret123` (хранится в `/root/.mavis/secrets/beget_ssh`)
- **SSH:** `ssh root@seefeesnahurid.beget.app` (пароль там же)

### GitHub
- **Репозиторий:** https://github.com/swzhukov/bit-technolog-prototype
- **Доступ:** push есть у Сергея

### Telegram (если настроишь)
- BotFather → создай бота → получи токен
- Получи свой chat_id через @userinfobot
- Введи в `/admin/settings` → TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID

### LLM (YandexGPT)
- **Yandex Cloud:** https://console.yandex.cloud
- **Сервисный аккаунт:** создать, дать роль `ai.languageModels.user`
- **API key:** скопировать, ввести в `/admin/settings` → LLM_API_KEY

---

## 2. Роли и пользователи

### 7 ролей
| Роль | Доступ | Кто |
|---|---|---|
| `technologist` | Генерация, правка, отправка на проверку | Технологи Баранова |
| `main_technologist` | + утверждение, запись в 1С | Гл. технолог (Баранов) |
| `normirovshchik` | Только просмотр + экономика | Нормировщик (если есть) |
| `constructor` | Только просмотр | Конструктор (КБ) |
| `workshop_chief` | + утверждение как начальник цеха | Нач. цеха (Голубев) |
| `quality` | Только правка + замечания | Контролёр ОТК |
| `admin` | Всё | Сергей (админ) |

### Создание пользователей
1. Переключи роль на `🛡 Админ` (header справа)
2. `/admin/users` → заполни username + password + role
3. Минимум 6 символов в пароле

### Безопасность
- Пароли хешируются bcrypt (или sha256+salt если bcrypt недоступен)
- CSRF защита по умолчанию
- Все входы логируются в `audit_logins` → `/admin/login-log`

---

## 3. Ежедневные задачи

### Утро (10 мин)
- Открой `/pilot` — посмотри метрики
- Открой `/admin/llm-calls` — проверь ошибки LLM за вчера
- Если красные ошибки > 5 — посмотри что сломалось (rate limit? ключ?)

### Вечер (5 мин)
- Открой `/admin/login-log` — все ли ожидаемые люди входили
- Если кто-то чужой — смени пароль, проверь что делал

---

## 4. Что делать если сломалось

### Сервис не отвечает
```bash
ssh root@seefeesnahurid.beget.app
systemctl status bit-technolog
systemctl restart bit-technolog
tail -50 /var/log/bit-technolog.err.log
curl http://127.0.0.1:8081/health
```

### LLM не отвечает (ошибки в /admin/llm-calls)
1. Проверь `LLM_API_KEY` в `/admin/settings`
2. Если ключ правильный — подожди 5 мин (YandexGPT API может быть недоступен)
3. Увеличь `LLM_TIMEOUT` (по умолчанию 60 сек)
4. Включи `DEMO_MODE=true` если нужно протестировать UI без LLM

### RAG не работает (rag_status=empty/error)
1. `/admin` → RAG-метрика показывает сколько ТК в индексе
2. Если 0 — нужны утверждённые ТК (RAG пустой пока)
3. `/admin` → "Переиндексировать RAG" (ручной trigger)
4. Если ошибка — посмотри `tail -50 /var/log/bit-technolog.err.log | grep rag`

### БД повреждена
```bash
# Остановить сервис
systemctl stop bit-technolog

# Восстановить из последнего backup
cp /opt/beget/backups/bit-technolog/db-2026-07-19_*.db /opt/beget/bit-technolog/bit_technolog.db

# Запустить
systemctl start bit-technolog
```

### Забыли пароль админа
```bash
ssh root@seefeesnahurid.beget.app
sqlite3 /opt/beget/bit-technolog/bit_technolog.db
> UPDATE pilot_users SET password_hash='sha256$salt$hash' WHERE username='user';
> .quit
```
Или через `/admin/users` (если есть другой admin).

---

## 5. Бэкапы

### Где хранятся
- `/opt/beget/backups/bit-technolog/` — последние 14 дней
- `db-YYYY-MM-DD_HHMM.db` — БД (SQLite backup через .backup)
- `rag-YYYY-MM-DD_HHMM.tar.gz` — RAG-индекс
- `drawings-YYYY-MM-DD_HHMM.tar.gz` — загруженные чертежи
- `env-YYYY-MM-DD_HHMM` — .env (настройки)

### Расписание
- **0 3 \* \* \*** — backup (ежедневно в 3:00)
- **0 4 \* \* \*** — verify (ежедневно в 4:00) — restore в /tmp + integrity_check

### Проверить вручную
```bash
/opt/beget/bit-technolog/verify_backup.sh
# → OK: integrity=ok, details=25, drafts=5, users=3
```

### Где скачать
- На сервере в `/opt/beget/backups/bit-technolog/`
- Скачать можно через scp/sftp

---

## 6. Обновление (deploy)

### Автоматическое
```bash
ssh root@seefeesnahurid.beget.app
cd /opt/beget/bit-technolog
./deploy.sh
```

### Вручную
```bash
ssh root@seefeesnahurid.beget.app
cd /opt/beget/bit-technolog
git pull origin main
systemctl restart bit-technolog
sleep 4
curl http://127.0.0.1:8081/health
```

### Откат (если что-то сломалось)
```bash
cd /opt/beget/bit-technolog
git log --oneline -5    # посмотреть последние коммиты
git checkout <commit>   # откатиться
systemctl restart bit-technolog
```

---

## 7. Мониторинг

### /health (JSON)
```bash
curl http://217.114.7.5:8081/health | python3 -m json.tool
```
Показывает:
- `status`, `db_ok`, `rag_status`
- `version`, `uptime_sec`
- `dependencies`: llm / telegram / smtp статус
- `cost_anomaly`: recent cost + дневной лимит + anomalies

### Алерты (если что-то не так)
- **Telegram** — уведомления в настроенный чат (workflow events, errors)
- **email** — уведомления о workflow (если настроен SMTP)
- **Логи** — `/var/log/bit-technolog.log` + `/var/log/bit-technolog.err.log`

### Еженедельный отчёт
- **Каждый понедельник 9:00** — `weekly_report.sh` генерирует Markdown-отчёт за 7 дней
- Отправляет в Telegram (если настроен)

---

## 8. Лимиты и стоимость

### Дневной лимит LLM
- По умолчанию: **200₽/день** (настраивается в `/admin/settings`)
- Если > 80% — предупреждение
- Если 100% — LLM endpoints возвращают 429

### Anomaly detection
- Если > **50₽/час** — alert (anomaly)
- Если > 80% лимита за первые 6 часов — alert
- Видно в `/health → cost_anomaly`

### YandexGPT тарифы (примерно)
- YandexGPT Lite: ~0.02-0.04₽ / 1K токенов
- YandexGPT Pro: ~0.06-0.12₽ / 1K токенов
- 1 генерация = ~3-5₽ (8-15K токенов)
- 200₽ / день = ~40-60 генераций

---

## 9. Часто задаваемые вопросы

### Как посмотреть кто что менял?
- `/admin/llm-calls` — все LLM-вызовы (кто, когда, что спрашивал, что получил)
- `/admin/login-log` — все входы (кто, когда, IP, успех)
- `history` таблица — все действия с деталью (`/history/{detail_id}`)

### Как добавить нового технолога?
1. Переключи роль на `🛡 Админ`
2. `/admin/users` → username + password + role="technologist" → "Создать"
3. Сообщи ему пароль

### Как изменить LLM модель?
1. `/admin/settings` → LLM_MODEL
2. Варианты: `gpt://b1gj791m9sc92argfa0q/yandexgpt/latest` (Lite), `gpt://b1gj791m9sc92argfa0q/yandexgpt/rc` (Pro)
3. Сохранить → LLM client пересоздастся автоматически

### Что такое RAG и как он работает?
- RAG = поиск похожих техкарт для подсказки AI
- TF-IDF + cosine similarity (on-prem, без OpenAI)
- Индексирует утверждённые ТК автоматически
- Целевой порог: **30+ утверждённых ТК** для качественной работы
- См. `/admin` → "RAG-готовность"

### Как сделать экспорт в 1С?
1. В карточке утверждённой детали → "📤 Записать в 1С"
2. Сейчас: XML-экспорт в файл (прямой записи в 1С:ERP нет)
3. Прямая интеграция — F14, post-pilot (6-8 мес)

### Как работать с чертежами КОМПАС-3D?
- Сейчас: ручной ввод свойств через `/details/new`
- Watcher (авто-импорт из .frw/.cdw) — F12, post-pilot
- Если Баранов/Голубев скажут "срочно нужно" — обсудим приоритеты

---

## 10. Контакты

- **Разработчик:** Mavis (AI-ассистент)
- **Тех. лид:** Сергей
- **Серверная поддержка:** Beget (support@beget.com)

Вопросы → Mavis через Mavis-чат, или issue в GitHub.
