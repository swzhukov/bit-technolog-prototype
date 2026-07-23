# 🗺️ CARTE v10 — Карта prod БИТ.Технолог (после Sprint 7)

**Дата:** 2026-07-23
**HEAD:** `6902cc9` (Sprint 7: bulk + cleanup + T6)
**URL:** `https://seefeesnahurid.beget.app/bit-technolog/`
**Architecture:** Docker (bit-technolog:1.0.0) + Traefik 3.6.5 + Let's Encrypt

## 🏗️ Архитектура (v10)

```
Internet
   │
   ├── Kaspersky Endpoint Security (НЕ блокирует — стандартный 443)
   │
   ▼
┌────────────────────────────────────────┐
│ Traefik 3.6.5                         │
│ 80 → 443 (redirect)                   │
│ ACME: Let's Encrypt (R12)             │
│ Routers:                               │
│   - n8n (Host=`seefeesnahurid.beget.app`, PathPrefix=`/`)
│   - bt  (Host=`seefeesnahurid.beget.app`, PathPrefix=`/bit-technolog`)  │
└────────────────────────────────────────┘
   │
   ▼
┌────────────────────────────────────────┐
│ Docker compose (n8n_traefik_net)      │
│  - bit-technolog:1.0.0 (FastAPI/uvicorn, 8081 internal)
│  - n8n (основной instance)
│  - postgres (n8n)
│  - redis (n8n)
└────────────────────────────────────────┘
   │
   ▼
┌────────────────────────────────────────┐
│ SQLite WAL (data/bit_technolog_v0_8.db)│
│  - 33 tables                          │
│  - 55 items (после cleanup)           │
│  - 50 tech_cards                      │
│  - 19 etalons                         │
│  - 57 equipment                       │
│  - 99 notices                         │
│  - 27 drawings (Sprint 7)             │
└────────────────────────────────────────┘
```

## 📊 Состояние prod (2026-07-23)

| Метрика | Значение |
|---------|----------|
| **HEAD** | `6902cc9` |
| **URL** | `https://seefeesnahurid.beget.app/bit-technolog/` |
| **SSL** | Let's Encrypt (валидный) |
| **Порт** | 443 (стандартный) |
| **Docker контейнер** | `bit-technolog:1.0.0` (healthy) |
| **Traefik** | 3.6.5, 80→443, ACME mytlschallenge |
| **Items** | 55 (после cleanup от 245) |
| **Tech cards** | 50 |
| **Etalons** | 19 |
| **Equipment** | 57 |
| **Notices** | 99 |
| **Drawings** | 27 (Sprint 7) |
| **Demo users** | 6 (techadmin, llmadmin, vorobyev, baranov, tarrietsky, golubev) |
| **Тесты** | 51/51 ✅ + 0 + 0 |
| **Cycles v9-v14** | 6 подряд 0 замечаний |

## 🆕 Sprint 7: Drawing Recognition

**Endpoints (новые):**
- `POST /api/drawings/upload` (multipart, PDF/PNG/JPG, max 50MB)
- `GET /api/drawings` (list, role-based)
- `GET /api/drawings/{id}`
- `POST /api/drawings/{id}/process` (OCR + LLM, ~45s)
- `POST /api/drawings/{id}/create-item`
- `POST /api/drawings/{id}/dismiss`
- `GET /drawings` (HTML list)
- `GET /drawings/upload` (HTML form)
- `GET /drawings/{id}/review` (HTML review screen)

**Services (новые):**
- `services/drawing_storage.py`
- `services/ocr_pipeline.py` (tesseract -l rus, ~15 sec)
- `services/drawing_to_item.py`
- `domain/drawing_extractor.py` (1bitai.ru + regex fallback, ~30 sec)

**Templates (новые):**
- `templates/drawings_list.html`
- `templates/drawing_upload.html` (drag & drop)
- `templates/drawing_review.html` (распознанные поля)

**Tests (новые):**
- TR.py: DRAW-01..DRAW-09 (9 тестов)
- TECHNOLOGIST_SESSIONS: T6 (9 ✅)
- BULK_DRAWINGS.py: 5 PDF quality assessment

**Tables (новые):**
- `drawings` (22 cols, 6 indexes, без FK)

## 📈 Метрики качества (Sprint 7)

**На реальных чертежах деталей:**
- Designation: 100% (1/1)
- Process time: 21s avg

**На спецификациях/планах:**
- Low (out of scope — это не детали)

## 🔐 Безопасность

- 152-ФЗ: `user.username` (login), НЕ `user.display_name` (ФИО)
- CSRF: все POST требуют `X-Requested-With: XMLHttpRequest`
- Rate limit: через SQLite (D1)
- Audit log: B3 (7 mutation endpoints)

## 💾 Backups

- `/opt/beget/backups/bit-technolog/` — daily cron (D3)
- `/opt/beget/backups/bit-technolog/pilot-27.07.2026/` — 3 копии перед пилотом
- `/opt/beget/backups/bit-technolog/db-pre-cleanup-final_*.db` — перед cleanup

## 📝 Известные TODO

- D7: YandexGPT folder_id='test' (нужен реальный от Сергея)
- D8: Bulk upload UI (пропущен для MVP)
- D10: Performance/кеш (пропущен для MVP)
- A2: bug-fix по фидбэку 4 пользователей

## 🧪 Tests

| Suite | Результат |
|-------|-----------|
| TR.py | 51/51 ✅ |
| UI_SMOKE | 0 замечаний |
| TECHNOLOGIST_SESSIONS | 0 замечаний, 1 заметка (норма) |
| BULK_DRAWINGS | 5 PDF processed, quality assessment |

## 🚀 Деплой

```bash
# На prod (root@seefeesnahurid.beget.app)
cd /opt/beget/bit-technolog
git pull --rebase origin main
docker compose build
docker compose up -d
docker exec bit-technolog curl -s http://localhost:8081/health
```

## 🔄 Rollback (если что-то критично)

```bash
# Остановить Docker
cd /opt/beget/bit-technolog
docker compose down

# Восстановить старый prod (uvicorn 8081)
systemctl start bit-technolog
systemctl start bit-technolog-http-redirect
# → вернётся https://217.114.7.5:8081/ (DEPRECATED)
```
