# Sprint 6 День 2 — A3+A4+C1

**HEAD на prod:** `e658618`

## A3: cleanup mock data
- Backup: `data/bit_technolog_v0_8_pre-cleanup-a3-{ts}.db`
- Удалено: 5 test items, 5 test notices, 165 test history rows, 22 orphan pilot_runs
- После: 52 items, 2 pilot notices, 4 history записей (approve, update, confirm, create)
- Gotcha: bom_links имеет parent_item_id/child_item_id (НЕ item_id), edits — tech_card_id (НЕ item_id)

## A4: USER_GUIDE.md → v1.0
- v0.6 → v1.0 (production-ready)
- 4 роли (вместо 5)
- Сквозной сценарий технолога 5 мин
- 5 вкладок карточки детали
- 3 решения по извещению
- 152-ФЗ раздел
- FAQ

## C1: FK inline-edit (workshop_id, profession_id)
- detail.html: цех и профессия → `<select class="editable-select">` для user_can_edit
- options из workshops_list/equipment_list/professions_list (ctx)
- JS: change → POST /api/operations/{id}/update
- API уже поддерживал FK (whitelist allowed_fk)
- Gotcha: equipment.code → inventory_no (AS code)

## Verify
- 11 editable-select в /detail/3 (5 ops × 2 fields + 1 CSS)
- update workshop_id/profession_id → 200, в БД записано
- production работает

## Коммиты
- 470b621 Sprint 6 / A4
- 5a16158 Sprint 6 / C1
- af3f695 Sprint 6 / C1-fix (equipment.inventory_no)

## Backup файлы на prod
- data/bit_technolog_v0_8_pre-migration-v6.db
- data/bit_technolog_v0_8_pre-cleanup-a3-1784795442.db
- data/bit_technolog_v0_8_pre-cleanup-a3-1784795591.db
- data/bit_technolog_v0_8_pre-cleanup-a3-1784795636.db
- data/bit_technolog_v0_8_pre-cleanup-a3-1784795658.db
