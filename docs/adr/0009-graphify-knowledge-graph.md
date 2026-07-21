# ADR-0009: Knowledge graph через graphify для архитектурной навигации

**Дата:** 2026-07-21 (M29)
**Статус:** Accepted
**Контекст:** Проект растёт (22 модуля, 13 000 строк). Mavis каждый раз читает много файлов чтобы найти нужное. Сергей попросил "применить graphify".

## Решение

Используем [graphifyy](https://github.com/safishamsi/graphify) — CLI tool от safishamsi.
- `graphify . --code-only` — AST-парсинг, ~30 сек, без LLM
- `graphify cluster-only` — Leiden community detection + отчёт
- `graph.html` (1MB) — интерактивная визуализация (в git, скачать с GitHub)
- `graph.json` (1.1MB) — данные (в git, для запросов)
- `GRAPH_REPORT.md` (22 KB) — обзор community (в git)
- `SEMANTIC_NOTES.md` (мой файл) — обогащение графа на русском

## Обоснование

| Альтернатива | Плюсы | Минусы |
|--------------|-------|--------|
| **graphify** ✅ | Open-source, AST-only (без LLM), быстрый, интерактивный HTML | Требует Python 3.10-3.13 |
| Grep + read | Просто, без зависимостей | Нет связей, нет визуализации |
| Sourcegraph | Хороший UI, semantic | Тяжёлый, SaaS, дорого |
| ctags + cscope | Быстрый поиск | Нет визуализации, не "graph" |
| Ручная документация | Полный контроль | Устаревает, лень поддерживать |

## Что НЕ используем

- **LLM-семантика** graphify — нет ключа, и не нужен (Mavis сам LLM, может обогатить граф вручную через SEMANTIC_NOTES.md)
- **MCP-сервер** graphify — Mavis работает через Mavis infrastructure, не через MCP
- **Watch mode / git hooks** — добавляются, но не критично (Mavis обновляет граф вручную после своих изменений)

## Когда пересматривать

- Если проект станет >50 000 строк (graphify всё ещё справится, но визуализация тяжелее)
- Если появится semantic search (Mavis обогащает SEMANTIC_NOTES.md)
- Если нужен multi-repo graph (graphify умеет merge-graphs)
