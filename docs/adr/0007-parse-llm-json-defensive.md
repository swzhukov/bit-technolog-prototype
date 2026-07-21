# ADR-0007: parse_llm_json — устойчивый парсинг JSON из LLM

**Дата:** 2026-05-15
**Статус:** Accepted
**Контекст:** LLM 50% времени возвращает валидный JSON, 30% — JSON в markdown code block, 15% — текст + JSON в конце, 5% — полная каша. Нужно парсить все варианты.

## Решение

Функция `parse_llm_json(text)` в `app.py:99` пробует 4 стратегии по очереди:
1. **Raw** — `json.loads(text)`
2. **Strip ```json** — убрать markdown code block
3. **Strip ```** — убрать любой code block
4. **First { to last }** — вырезать JSON из текста

Если ни одна не сработала — `raise ValueError`.

Плюс wrapper `parse_llm_json_safe()` (M30) — возвращает `{}` при любой ошибке.

## Обоснование

**Плюсы:**
- LLM-сбой не валит UX (parse_llm_json_safe для не-критичных мест)
- Покрывает 95%+ реальных ответов LLM
- Простая логика, легко отлаживать

**Минусы:**
- Может вырезать неправильный JSON (если LLM вернёт несколько JSON'ов)
- Нет валидации схемы (только синтаксис)

## Где используется

- `app.py:generate` — парсит результат LLM для сохранения в `drafts.llm_output`
- `app.py:api_refine` — парсит уточнённую ТК
- `app.py:api_analyze` — парсит быстрый черновик

## Тестирование

4 теста в `test_app.py`:
- `test_parse_llm_json_valid` — чистый JSON
- `test_parse_llm_json_with_markdown` — ```json ... ```
- `test_parse_llm_json_with_preamble` — "Вот ваша ТК: {..."
- `test_parse_llm_json_invalid_returns_empty` (safe) — "not json" → {}
- `test_parse_llm_json_strict_raises` (strict) — "not json" → ValueError

## Связанные

- ADR-0005: специализированные промты (формат JSON в них)
- ADR-0008: CSRF на все POST
