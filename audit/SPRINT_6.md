# Sprint 6 — после пилота 27.07.2026

**Длительность:** 2 недели (28.07 — 10.08)
**Цель:** превратить пилот в полноценный продакшн для ежедневной работы 4+ технологов
**HEAD на старте Sprint 6:** `b43e69d` (M38-v6) — 0 замечаний в 2 циклах ✅
**Метрика успеха:** 0 ручных фиксов, поддержка multi-worker, audit-trail операций, форма создания детали

## УЧАСТНИКИ

| Роль | Кто | Фокус |
|------|-----|-------|
| Технолог | tarrietsky | фидбэк по UX, баг-репорты |
| Гл. технолог | vorobyev | фидбэк по workflow, approve |
| Нач. цеха | golubev | фидбэк по РС, видимость |
| Admin | techadmin | настройка, мониторинг |

## УЖЕ СДЕЛАНО (на момент старта Sprint 6)

- ✅ **C2: Форма создания детали** (M38-c4, commit `3329fb2` + `829be5b`)
  - 10 полей, валидация (5 случаев), RBAC (3 editor роли, chief=403)
  - 6 тестов на prod
- ✅ **152-ФЗ полностью** (M38-v6, commit `4f44bcd`)
  - 8 мест user.display_name → user.username в БД
  - Миграция 70 строк в существующих данных
  - Workshop_chief больше не видит ФИО коллег
- ✅ **RBAC на /notices/new (GET)** (M38-v6, commit `18b8b0a`)
  - Был UX-баг: workshop_chief видел форму
- ✅ **Auto-tests**: TR.py 42/42, UI_SMOKE.py 0 замечаний, 5 сценариев работы технологом

## БЭКЛОГ (10 задач, 4 эпика)

### EPIC A: Стабилизация после пилота (день 1-2)

| # | Задача | Размер | Приоритет | Зависит от | Статус |
|---|--------|--------|-----------|------------|--------|
| A1 | Сбор фидбэка 4 пилотных пользователей (голосом) | S | MUST | — | TODO |
| A2 | Баг-фиксы из пилота (ожидаем 5-10) | M | MUST | A1 | TODO |
| A3 | Cleanup mock data из БД (тестовые items, drafts) | S | MUST | — | TODO |
| A4 | Документация для пилота — обновить USER_GUIDE.md | S | MUST | — | TODO |

### EPIC B: Audit & History (день 3-5)

| # | Задача | Размер | Приоритет | Зависит от | Статус |
|---|--------|--------|-----------|------------|--------|
| B1 | **Транзакция в api_approve** (атомарность INSERT etalon + UPDATE tech_card) | M | MUST | — | TODO |
| B2 | **IP + User-Agent в audit_logins** (передать request в authenticate) | S | MUST | — | TODO |
| B3 | **`history` table — писать audit-trail** во все mutation endpoints | M | MUST | — | TODO |
| B4 | UI для просмотра history (admin/main_tech) — `/audit` page | M | SHOULD | B3 | TODO |

### EPIC C: UX-задачи (день 5-8)

| # | Задача | Размер | Приоритет | Зависит от | Статус |
|---|--------|--------|-----------|------------|--------|
| C1 | **FK inline-edit** для workshop_id, equipment_id, profession_id (select'ы) | L | MUST | — | TODO |
| ~~C2~~ | ~~Форма создания новой детали~~ | L | MUST | — | **DONE M38-c4** |
| C3 | **Diff между версиями ТК** (draft_versions) | M | SHOULD | B3 | TODO |
| C4 | Bulk approve — утвердить 5+ ТК за раз | M | COULD | — | TODO |
| C5 | Full-text search в /products | M | COULD | — | TODO |

### EPIC D: Production hardening (день 8-10)

| # | Задача | Размер | Приоритет | Зависит от | Статус |
|---|--------|--------|-----------|------------|--------|
| D1 | **In-memory state → Redis** (`_sessions`, `_rate_limit_buckets`, `_llm_semaphore`) | L | MUST | — | TODO |
| D2 | Multi-worker (uvicorn --workers 2-4) | M | MUST | D1 | TODO |
| D3 | Cron backup (уже есть deploy/backup.sh, добавить в crontab) | S | MUST | — | TODO |
| D4 | Logrotate (уже есть deploy/logrotate-bit-technolog, активировать) | S | MUST | — | TODO |
| D5 | **TLS self-signed → let's encrypt** (для офиса) | M | SHOULD | — | TODO |
| D6 | **HttpGateway** для 1С:ERP (реальный, не FileGateway) | L | COULD | — | TODO |
| D7 | YandexGPT как backup (если 1bitai.ru упал) | M | COULD | — | TODO |
| D8 | PDF export RS (сейчас только XML) | M | COULD | — | TODO |

## ПЛАН ПО ДНЯМ (4 дня в неделю, 4-6 часов = ~50 ч)

| День | Sprint день | Что делаем | Ожидаемый результат |
|------|-------------|------------|---------------------|
| **1 (23.07)** | D1 | A3: cleanup mock data, A4: USER_GUIDE, B2: IP/UA в audit | БД чистая, audit безопасности |
| **2 (24.07)** | D2 | A1+A2: фидбэк + баг-фиксы (если пилот был) | 0 багов из пилота |
| **3 (25.07)** | D3 | B1: транзакция api_approve, B3: history audit-trail | Атомарность + audit log |
| **4 (28.07)** | D4 | B3 продолжение, B4: /audit page | UI для админа |
| **5 (29.07)** | D5 | C1: FK inline-edit | Технолог меняет workshop/equipment/profession |
| **6 (30.07)** | D6 | D1: Redis для state, D2: multi-worker test | 2-4 worker |
| **7 (31.07)** | D7 | D3: cron backup, D4: logrotate | Ежедневный backup, логи не переполняют |
| **8 (01.08)** | D8 | C3: diff версий, D5: TLS | Diff + let's encrypt |
| **9 (04.08)** | D9 | C4: bulk approve (если время), C5: search (если время) | Полировка |

**ИТОГО:** ~50 часов

## ПРИОРИТЕТЫ (MoSCoW)

**MUST (8 задач, ~30 часов):**
- A1, A2, A3, A4 (стабилизация) — DONE A3+A4
- B1, B2, B3 (audit)
- C1 (FK inline-edit)
- D1, D2, D3, D4 (prod hardening)

**SHOULD (4 задачи, ~15 часов):**
- B4 (audit UI)
- C3 (diff версий)
- D5 (TLS)
- D6 (HttpGateway) — **отложено** (нет у клиента)

**COULD (3 задачи, ~15 часов):**
- C4 (bulk approve)
- C5 (search)
- D7, D8 (LLM backup, PDF) — **отложено**

## ОТКРЫТЫЕ ВОПРОСЫ

1. **Redis на Beget VPS** — установлен ли? (если нет — нужен 1 день на setup)
2. **Домен для TLS** — есть или используем IP?
3. **1С:ERP endpoint** — есть ли у клиента HTTP-сервис? (D6 отложен)
4. **YandexGPT API ключ** — есть ли для backup?
5. **Backup storage** — достаточно ли `/opt/beget/backups/` или внешнее хранилище?

## РЕСУРСЫ

- **Документация**: `/workspace/audit/CARTE.md`, `FINDINGS_V1..V6.md`
- **Каркас системы**: `/workspace/bit-technolog-prototype/`
- **Деплой**: `deploy/*.sh` (backup, health_check, logrotate, tls_setup)
- **wiki**: `https://github.com/swzhukov/llm_manifest` (ENVIRONMENT.md, MISTAKES.md)

## РИТМ СПРИНТА

- **Понедельник** — kickoff, приоритизация
- **Среда** — mid-sprint sync, статус, ре-приоритизация
- **Пятница** — review, demo, ретро
- **Ежедневно** — 1 коммит минимум (atomic, deployable)

## SUCCESS CRITERIA

Sprint 6 считается успешным, если:
1. Все MUST задачи завершены (A1-A4, B1-B3, C1, D1-D4) — A3+A4+DONE
2. 0 регрессий в RBAC matrix
3. 0 багов, требующих ручного вмешательства
4. Backup восстанавливается из verify_backup.sh
5. Multi-worker запускается и обслуживает 50+ users
6. Любой технолог может создать деталь за 3-5 мин (C2) ✅
7. История операций доступна через UI (B4)
