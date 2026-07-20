# Deployment Guide — развёртывание БИТ.Технолог

> **Версия:** v0.4.12 (2026-07-20)
> **Целевая платформа:** Linux (Ubuntu 22.04 / Debian 11+)
> **Где развёрнут пилот:** Beget VPS (seefeesnahurid.beget.app:8081)

---

## Содержание

- [Требования к серверу](#требования-к-серверу)
- [Первоначальная установка](#первоначальная-установка)
- [Обновление системы](#обновление-системы)
- [Systemd service](#systemd-service)
- [Cron jobs](#cron-jobs)
- [Логи и logrotate](#логи-и-logrotate)
- [Reverse proxy (Nginx)](#reverse-proxy-nginx)
- [Мониторинг](#мониторинг)
- [Резервное копирование](#резервное-копирование)
- [Восстановление после сбоя](#восстановление-после-сбоя)

---

## Требования к серверу

### Минимум (пилот на 5-10 пользователей)

- **CPU:** 2 vCPU
- **RAM:** 2 ГБ
- **Диск:** 20 ГБ SSD
- **ОС:** Ubuntu 22.04 / Debian 11+
- **Сеть:** публичный IP, открыт порт 8081 (или 80/443 через Nginx)

### Рекомендуется (10-50 пользователей)

- **CPU:** 4 vCPU
- **RAM:** 4 ГБ
- **Диск:** 50 ГБ SSD
- **ОС:** Ubuntu 22.04 LTS
- **Сеть:** 100 Мбит/с

### Используется на пилоте (Beget VPS)

- **CPU:** 2 vCPU
- **RAM:** 2 ГБ
- **Диск:** 30 ГБ SSD
- **ОС:** Ubuntu 22.04
- **Сеть:** публичный IP, 100 Мбит/с
- **Цена:** ~500₽/месяц

---

## Первоначальная установка

### 1. Подготовка сервера

```bash
# Обновить систему
apt update && apt upgrade -y

# Установить Python 3.11+, pip, git, sqlite3, gpg
apt install -y python3.11 python3-pip git sqlite3 gnupg curl wget

# Создать пользователя
useradd -m -s /bin/bash bit-technolog
mkdir -p /opt/beget/bit-technolog
chown -R bit-technolog:bit-technolog /opt/beget/bit-technolog
```

### 2. Клонировать репозиторий

```bash
cd /opt/beget/bit-technolog
sudo -u bit-technolog git clone https://github.com/your-org/bit-technolog-prototype.git .

# Или если репозиторий приватный — настроить SSH ключ
sudo -u bit-technolog ssh-keygen -t ed25519 -N "" -f /home/bit-technolog/.ssh/id_ed25519
# Добавить публичный ключ в GitHub deploy keys
```

### 3. Установить зависимости

```bash
cd /opt/beget/bit-technolog
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**`requirements.txt`** (примерный состав):
```
fastapi==0.115.0
uvicorn[standard]==0.32.0
jinja2==3.1.4
python-multipart==0.0.20
pydantic==2.9.0
openai==1.55.0
httpx==0.27.2
qrcode[pil]==8.0
matplotlib==3.9.2
pymorphy2==0.9.1
reportlab==4.2.0
openpyxl==3.1.5
bcrypt==4.2.0
cryptography==43.0.0
python-dotenv==1.0.1
pytest==8.3.3
```

### 4. Создать `.env`

```bash
cp .env.vps.example .env
nano .env
```

**Содержимое `.env`:**
```bash
# LLM (YandexGPT)
LLM_API_KEY=your-yandexgpt-api-key
LLM_FOLDER_ID=your-folder-id
LLM_MODEL=yandexgpt-lite
LLM_DAILY_LIMIT_RUB=200.0

# Telegram (опционально, для алертов)
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# SMTP (опционально, для email-уведомлений)
SMTP_HOST=smtp.yandex.ru
SMTP_PORT=587
SMTP_USER=your-email@yandex.ru
SMTP_PASSWORD=your-app-password
SMTP_FROM=БИТ.Технолог <noreply@tehincom.ru>

# Backup
BACKUP_GPG_RECIPIENT=admin@tehincom.ru  # опционально

# Режим
DEMO_MODE=false
JSON_LOGS=true
PILOT_CSRF_DISABLED=false
PILOT_RATELIMIT_DISABLED=false
PILOT_AUTH_DISABLED=true   # для пилота без пароля

# Путь к БД
DB_PATH=/opt/beget/bit-technolog/bit_technolog.db

# Fernet master key (генерируется автоматически при первом запуске, если отсутствует)
FERNET_KEY_PATH=/opt/beget/bit-technolog/.master_key
```

### 5. Инициализировать БД

```bash
sudo -u bit-technolog ./venv/bin/python -c "
import app
app.init_db()
print('✅ DB initialized')
"
```

### 6. Засеять тестовые данные (опционально, для пилота)

```bash
sudo -u bit-technolog ./venv/bin/python -c "
import app
app.init_db()
# Засеять 25 деталей Техинкома
from techinkom_seed import seed_tehincom_details
n = seed_tehincom_details()
print(f'✅ Seeded {n} Техинком details')
"
```

### 7. Запустить через systemd

См. ниже раздел [Systemd service](#systemd-service).

### 8. Настроить cron jobs

См. ниже раздел [Cron jobs](#cron-jobs).

### 9. Настроить Nginx (опционально)

См. ниже раздел [Reverse proxy (Nginx)](#reverse-proxy-nginx).

### 10. Проверить

```bash
curl http://localhost:8081/health
# {"status":"ok","version":"0.4.12",...}
```

Открыть в браузере: `http://your-server-ip:8081/`

---

## Обновление системы

### Автоматически (через `deploy.sh`)

```bash
cd /opt/beget/bit-technolog
sudo -u bit-technolog bash deploy.sh
```

**Что делает `deploy.sh`:**
1. `git pull` (получает новый код)
2. `pip install -r requirements.txt` (обновляет зависимости)
3. `./venv/bin/python -m pytest test_app.py -q` (прогон тестов — если падают, откат)
4. `systemctl restart bit-technolog` (рестарт)
5. `sleep 3 && curl /health` (проверка)
6. Если ОК — коммит в git с тегом версии

### Вручную (если `deploy.sh` не сработал)

```bash
cd /opt/beget/bit-technolog
sudo -u bit-technolog git pull
sudo -u bit-technolog ./venv/bin/pip install -r requirements.txt --upgrade
sudo -u bit-technolog ./venv/bin/python -m pytest test_app.py -q
sudo systemctl restart bit-technolog
systemctl status bit-technolog
```

### Откат на предыдущую версию

```bash
cd /opt/beget/bit-technolog
sudo -u bit-technolog git log --oneline -10
sudo -u bit-technolog git checkout <commit-sha>
sudo -u bit-technolog ./venv/bin/pip install -r requirements.txt
sudo systemctl restart bit-technolog
```

---

## Systemd service

**Файл:** `/etc/systemd/system/bit-technolog.service`

```ini
[Unit]
Description=БИТ.Технолог — AI-помощник технолога
After=network.target

[Service]
Type=simple
User=bit-technolog
Group=bit-technolog
WorkingDirectory=/opt/beget/bit-technolog
Environment="PATH=/opt/beget/bit-technolog/venv/bin"
EnvironmentFile=/opt/beget/bit-technolog/.env
ExecStart=/opt/beget/bit-technolog/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8081 --workers 1
Restart=always
RestartSec=5
StandardOutput=append:/var/log/bit-technolog/app.log
StandardError=append:/var/log/bit-technolog/err.log

# Лимиты
LimitNOFILE=65536
MemoryMax=1G

# Безопасность
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/beget/bit-technolog /var/log/bit-technolog /opt/beget/backups

[Install]
WantedBy=multi-user.target
```

**Команды:**

```bash
# Перечитать конфиг
sudo systemctl daemon-reload

# Включить автозапуск
sudo systemctl enable bit-technolog

# Запустить
sudo systemctl start bit-technolog

# Статус
sudo systemctl status bit-technolog

# Логи в реальном времени
sudo journalctl -u bit-technolog -f

# Рестарт
sudo systemctl restart bit-technolog

# Стоп
sudo systemctl stop bit-technolog
```

---

## Cron jobs

**Файл:** `/etc/cron.d/bit-technolog`

```cron
# Ежедневный бэкап в 3:00
0 3 * * * bit-technolog cd /opt/beget/bit-technolog && bash backup.sh >> /var/log/bit-technolog/backup.log 2>&1

# Верификация бэкапа в 4:00
0 4 * * * bit-technolog cd /opt/beget/bit-technolog && bash verify_backup.sh >> /var/log/bit-technolog/verify.log 2>&1

# Еженедельный отчёт в Telegram (понедельник 9:00)
0 9 * * 1 bit-technolog cd /opt/beget/bit-technolog && bash weekly_report.sh >> /var/log/bit-technolog/weekly.log 2>&1

# Health-check каждые 5 минут + Telegram алерт
*/5 * * * * bit-technolog cd /opt/beget/bit-technolog && bash health_check.sh >> /var/log/bit-technolog/health.log 2>&1

# Retention policy (ежедневно 5:00) — очистка старых audit_logins, llm_calls, history
0 5 * * * bit-technolog cd /opt/beget/bit-technolog && ./venv/bin/python -c "from admin import cleanup_old_records; cleanup_old_records()" >> /var/log/bit-technolog/cleanup.log 2>&1
```

**После редактирования:**
```bash
sudo systemctl restart cron
```

---

## Логи и logrotate

**Расположение:** `/var/log/bit-technolog/`

**Файлы:**
- `app.log` — все логи (JSON если `JSON_LOGS=true`)
- `err.log` — ошибки (stderr)
- `backup.log` — логи бэкапа
- `verify.log` — логи верификации
- `weekly.log` — логи еженедельного отчёта
- `health.log` — логи health-check
- `cleanup.log` — логи retention

**Logrotate конфиг:** `/etc/logrotate.d/bit-technolog`

```
/var/log/bit-technolog/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 bit-technolog bit-technolog
    sharedscripts
    postrotate
        systemctl reload bit-technolog > /dev/null 2>/dev/null || true
    endscript
}
```

---

## Reverse proxy (Nginx)

**Файл:** `/etc/nginx/sites-available/bit-technolog`

```nginx
upstream bit_technolog_backend {
    server 127.0.0.1:8081;
}

server {
    listen 80;
    server_name seefeesnahurid.beget.app;

    # Редирект на HTTPS (если есть SSL)
    # return 301 https://$server_name$request_uri;

    location / {
        proxy_pass http://bit_technolog_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (если используется)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Таймауты
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Статика — Nginx сам отдаёт
    location /static/ {
        alias /opt/beget/bit-technolog/static/;
        expires 30d;
        access_log off;
    }

    # Здоровье — без логирования
    location /health {
        proxy_pass http://bit_technolog_backend;
        access_log off;
    }
}
```

**Активация:**
```bash
sudo ln -s /etc/nginx/sites-available/bit-technolog /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

**На Beget VPS:** порты 80/443 уже заняты docker-proxy, поэтому Nginx не используется — приложение слушает напрямую на 8081.

---

## Мониторинг

### Health-check endpoint

```bash
curl http://localhost:8081/health | jq
```

**Пример ответа:**
```json
{
  "status": "ok",
  "version": "0.4.12",
  "build_date": "2026-07-20",
  "git_commit": "a666645",
  "uptime_sec": 86400,
  "dependencies": {
    "llm": "ok",
    "telegram": "ok",
    "smtp": "not_configured"
  },
  "db": {
    "details_count": 25,
    "drafts_count": 18,
    "draft_versions_count": 47,
    "size_mb": 4.2
  },
  "cost_anomaly": "ok"
}
```

### Автоматический health-check (cron)

`health_check.sh`:
```bash
#!/bin/bash
# Каждые 5 минут проверяет /health и шлёт Telegram алерт если status != ok

HEALTH=$(curl -s http://localhost:8081/health)
STATUS=$(echo "$HEALTH" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status'))")

if [ "$STATUS" != "ok" ]; then
    # Шлём в Telegram
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_CHAT_ID}" \
      -d "text=🚨 БИТ.Технолог: /health вернул $STATUS%0A%0A\`$HEALTH\`" \
      -d "parse_mode=Markdown"
fi
```

### Мониторинг извне (опционально)

- **UptimeRobot** (https://uptimerobot.com/) — бесплатно, проверка `/health` каждые 5 мин
- **Healthchecks.io** (https://healthchecks.io/) — алерты если cron не сработал
- **Grafana + Prometheus** (overkill для пилота)

---

## Резервное копирование

### Стратегия

- **Ежедневно 3:00** — полный бэкап БД (SQLite `.db` файл)
- **Хранение:** 30 дней
- **Сжатие:** gzip
- **Шифрование:** опционально через gpg (BACKUP_GPG_RECIPIENT)
- **Верификация:** ежедневно 4:00 (проверка integrity)
- **Хранение вне сервера:** рекомендуется (S3, Yandex Object Storage)

### Скрипт `backup.sh`

```bash
#!/bin/bash
set -e

DB_PATH="/opt/beget/bit-technolog/bit_technolog.db"
BACKUP_DIR="/opt/beget/backups"
KEEP_DAYS=30
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M")
BACKUP_FILE="$BACKUP_DIR/bit_technolog_${TIMESTAMP}.db"

mkdir -p "$BACKUP_DIR"

# Безопасное копирование через sqlite3 .backup (атомарно)
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

# Сжатие
gzip "$BACKUP_FILE"
BACKUP_FILE="${BACKUP_FILE}.gz"

# Шифрование (если настроено)
if [ -n "$BACKUP_GPG_RECIPIENT" ]; then
    gpg --batch --yes --recipient "$BACKUP_GPG_RECIPIENT" \
        --encrypt "$BACKUP_FILE"
    rm "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE}.gpg"
fi

# Удаление старых
find "$BACKUP_DIR" -name "bit_technolog_*.db*" -mtime +$KEEP_DAYS -delete

# Лог
echo "$(date): Backup created: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))" >> /var/log/bit-technolog/backup.log
```

### Скрипт `verify_backup.sh`

```bash
#!/bin/bash
# Проверяет целостность последнего бэкапа

BACKUP_DIR="/opt/beget/backups"
LATEST=$(ls -t "$BACKUP_DIR"/bit_technolog_*.db* 2>/dev/null | head -1)

if [ -z "$LATEST" ]; then
    echo "No backups found"
    exit 1
fi

# Распаковка если нужно
if [[ "$LATEST" == *.gz ]]; then
    TMP=$(mktemp)
    gunzip -c "$LATEST" > "$TMP"
    TARGET="$TMP"
elif [[ "$LATEST" == *.gpg ]]; then
    echo "Encrypted backup — manual verification needed"
    exit 0
else
    TARGET="$LATEST"
fi

# Проверка через sqlite3
INTEGRITY=$(sqlite3 "$TARGET" "PRAGMA integrity_check;" 2>&1)
COUNT=$(sqlite3 "$TARGET" "SELECT COUNT(*) FROM details;" 2>&1)

echo "$(date): Latest: $LATEST, integrity=$INTEGRITY, details_count=$COUNT" >> /var/log/bit-technolog/verify.log

if [ "$INTEGRITY" != "ok" ]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_CHAT_ID}" \
      -d "text=🚨 БИТ.Технолог: backup integrity FAILED%0A$LATEST%0A%0A$INTEGRITY"
fi

# Очистка
if [ -n "$TMP" ]; then rm "$TMP"; fi
```

### Ручной бэкап (если нужно прямо сейчас)

```bash
cd /opt/beget/bit-technolog
bash backup.sh
ls -lh /opt/beget/backups/ | tail -5
```

### Восстановление из бэкапа

```bash
# Остановить сервис
sudo systemctl stop bit-technolog

# Бэкап текущей БД (на всякий случай)
cp /opt/beget/bit-technolog/bit_technolog.db /opt/beget/bit-technolog/bit_technolog.db.bak

# Восстановить
LATEST=$(ls -t /opt/beget/backups/bit_technolog_*.db.gz | head -1)
gunzip -c "$LATEST" > /opt/beget/bit-technolog/bit_technolog.db

# Проверить
sqlite3 /opt/beget/bit-technolog/bit_technolog.db "PRAGMA integrity_check;"
sqlite3 /opt/beget/bit-technolog/bit_technolog.db "SELECT COUNT(*) FROM details;"

# Запустить
sudo systemctl start bit-technolog
curl http://localhost:8081/health
```

---

## Восстановление после сбоя

### Сервис не запускается

```bash
# 1. Проверить статус
sudo systemctl status bit-technolog

# 2. Посмотреть логи
sudo journalctl -u bit-technolog -n 100

# 3. Проверить .env
cat /opt/beget/bit-technolog/.env

# 4. Проверить БД
sqlite3 /opt/beget/bit-technolog/bit_technolog.db "PRAGMA integrity_check;"

# 5. Запустить руками для диагностики
cd /opt/beget/bit-technolog
sudo -u bit-technolog ./venv/bin/python app.py
```

### БД повреждена

```bash
# Попробовать восстановить
sqlite3 /opt/beget/bit-technolog/bit_technolog.db ".recover" | sqlite3 recovered.db

# Если не помогло — из бэкапа
LATEST=$(ls -t /opt/beget/backups/bit_technolog_*.db.gz | head -1)
gunzip -c "$LATEST" > /opt/beget/bit-technolog/bit_technolog.db
```

### Диск заполнен

```bash
# Проверить
df -h

# Удалить старые бэкапы (если retention не сработал)
find /opt/beget/backups -name "*.db.gz" -mtime +60 -delete

# Удалить старые логи
find /var/log/bit-technolog -name "*.gz" -mtime +90 -delete
```

### Секреты утёкли (152-ФЗ)

См. [`19-security-compliance.md`](19-security-compliance.md) § Incident response.

---

## Sandbox wipe (особенность Mavis)

**Важно:** sandbox сессии Mavis **не сохраняют секреты** между запусками. Если вы
работаете через Mavis, SSH-пароль к серверу нужно **восстанавливать** через:

```bash
# Из vcs backup
cat /root/.mavis/secrets/beget_ssh

# Или из .env (НЕ рекомендуется, но допустимо)
cat /opt/beget/bit-technolog/.env | grep SSH
```

Подробнее — см. [`19-security-compliance.md`](19-security-compliance.md).

---

## См. также

- [`12-admin-guide.md`](12-admin-guide.md) — ежедневная работа админа
- [`16-database-schema.md`](16-database-schema.md) — схема БД
- [`19-security-compliance.md`](19-security-compliance.md) — безопасность
- [`18-troubleshooting.md`](18-troubleshooting.md) — типичные проблемы
