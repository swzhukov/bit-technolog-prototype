# Sprint 6 День 3 — D1+D2(частично)+D3+D4

**HEAD на prod:** `c25c250` (D1)

## D1: shared state через SQLite ✅
- Создан `services/state.py` (session_create/get/delete, rate_limit_check)
- Создан `migrations/003_shared_state.sql` (sessions, rate_limit_buckets)
- `app.py`: get_current_user/_create_session/_rate_limit_check/_logout используют state
- **Почему SQLite а не Redis:** Redis не установлен на Beget (shared hosting)
- **Verify:** sessions count=1 (мой login), /products=200, /health=200

## D2: multi-worker (частично) ⚠️
- Попытка: --workers 2 → uvicorn killed
- **Решение:** оставил --workers 1 (предыдущее значение)
- **Альтернатива:** 2 uvicorn на разных портах + nginx upstream (отложено)
- **Статус:** state готов (D1), workers=1, scale up когда нагрузка вырастет

## D3: cron backup ✅
- `cp deploy/backup.sh /usr/local/bin/bit-technolog-backup && chmod +x`
- `crontab -e`: `0 3 * * * /usr/local/bin/bit-technolog-backup >> /var/log/bit-technolog-backup.log 2>&1`
- Verify: backup создан, 17 файлов, encryption: false (gpg не настроен)

## D4: logrotate ✅
- `cp deploy/logrotate-bit-technolog /etc/logrotate.d/bit-technolog`
- `logrotate -d` — config valid
- bit-technolog.err.log уже 1.6MB → будет rotate daily

## Итог
- **D1 ✅, D2 ⚠️, D3 ✅, D4 ✅**
- HEAD: c25c250
- Service file /etc/systemd/system/bit-technolog.service: workers=1
- Crontab: 5 задач (n8n, ram_watchdog, weekly, verify, backup)

## Коммиты
- 3652d84 Sprint 6 / D1: shared state через SQLite
- (D3, D4 — изменения на prod, не в репо)
