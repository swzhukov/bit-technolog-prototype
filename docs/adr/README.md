# ADR — Architecture Decision Records

Здесь записаны **ключевые архитектурные решения** проекта БИТ.Технолог.

## Что такое ADR

ADR (Architecture Decision Records) — это способ документировать важные технические решения: **что решили**, **почему**, **какие последствия**, **когда пересматривать**.

Стандарт: [https://adr.github.io/](https://adr.github.io/)

## Список

| # | Решение | Статус | Дата |
|---|---------|--------|------|
| [0001](0001-use-sqlite-not-postgres.md) | SQLite вместо PostgreSQL | Accepted | 2026-04-15 |
| [0002](0002-on-prem-yandexgpt.md) | YandexGPT (on-premise) | Accepted | 2026-04-20 |
| [0003](0003-rag-tfidf-not-vector-db.md) | RAG через TF-IDF (on-prem) | Accepted | 2026-04-25 |
| [0004](0004-monolith-not-microservices.md) | Монолит (не микросервисы) | Accepted | 2026-05-01 |
| [0005](0005-specialized-prompts.md) | 7 специализированных промтов | Accepted | 2026-05-10 |
| [0006](0006-real-workshops-in-prompts.md) | Реальные цеха в LLM промте (M28) | Accepted | 2026-07-20 |
| [0007](0007-parse-llm-json-defensive.md) | parse_llm_json — устойчивый парсинг | Accepted | 2026-05-15 |
| [0008](0008-csrf-required.md) | CSRF на все POST | Accepted | 2026-05-20 |
| [0009](0009-graphify-knowledge-graph.md) | graphify для навигации (M29) | Accepted | 2026-07-21 |

## Когда создавать ADR

- Выбрал технологию (БД, фреймворк, LLM, vector DB)
- Изменил архитектурный паттерн (монолит → микросервисы, sync → async)
- Принял security/compliance решение
- Выбрал между vendor lock-in vs open-source
- **НЕ** создавать ADR для: мелких рефакторов, bug fixes, новых фич (это в CHANGELOG)

## Шаблон

```markdown
# ADR-NNNN: <заголовок>

**Дата:** YYYY-MM-DD
**Статус:** Proposed | Accepted | Deprecated | Superseded by NNNN
**Контекст:** <1-2 предложения — что за проблема>

## Решение
Что выбрали

## Обоснование
Почему (таблица альтернатив если есть)

## Последствия
**Плюсы:** ...
**Минусы:** ...

## Когда пересматривать
Триггеры для пересмотра решения
```
