"""
llm.py — модуль работы с LLM (v0.4.9, F15).
Выделено из app.py.
Содержит: get_llm_client (singleton OpenAI), parse_llm_json, log_llm_call.
"""
import os
import json
import logging
import time

log = logging.getLogger("bit-technolog")

# Defaults (если .env не задан)
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_API_URL = os.getenv("LLM_API_URL", "https://llm.api.cloud.yandex.net/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt://b1gj791m9sc92argfa0q/yandexgpt/latest")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

# Lazy-init singleton
_LLM_CLIENT = None


def get_llm_client():
    """Lazy-init OpenAI client. Читает ключ из БД (get_setting) с fallback на .env.
    Если ключ изменился в админке — клиент пересоздаётся автоматически."""
    from settings import get_setting
    global _LLM_CLIENT
    api_key = get_setting("LLM_API_KEY", LLM_API_KEY)
    api_url = get_setting("LLM_API_URL", LLM_API_URL)
    demo = get_setting("DEMO_MODE", "false" if not DEMO_MODE else "true").lower() == "true"
    if demo:
        return None
    # Пересоздать клиент если ключ/url изменились
    if _LLM_CLIENT is not None:
        cached = getattr(_LLM_CLIENT, "_bit_key", None)
        cached_url = getattr(_LLM_CLIENT, "_bit_url", None)
        if cached != api_key or cached_url != api_url:
            log.info("LLM key/url changed in admin — recreating client")
            _LLM_CLIENT = None
    if _LLM_CLIENT is None:
        from openai import OpenAI
        _LLM_CLIENT = OpenAI(
            base_url=api_url,
            api_key=api_key,
            timeout=LLM_TIMEOUT
        )
        _LLM_CLIENT._bit_key = api_key
        _LLM_CLIENT._bit_url = api_url
    return _LLM_CLIENT


def parse_llm_json(text: str) -> dict:
    """Устойчивый парсинг JSON из LLM-ответа.
    Стратегии: raw -> strip ```json -> strip ``` -> first { to last }."""
    if not text or not text.strip():
        raise ValueError("empty LLM response")
    s = text.strip()
    # 1. Raw
    try:
        return json.loads(s)
    except Exception:
        pass
    # 2. Strip ```json ... ```
    if s.startswith("```"):
        lines = s.split("\n", 1)
        s2 = lines[1] if len(lines) > 1 else ""
        if s2.rstrip().endswith("```"):
            s2 = s2.rstrip()[:-3].rstrip()
        try:
            return json.loads(s2)
        except Exception:
            pass
        if s2.lower().startswith("json"):
            s2 = s2[4:].lstrip()
            try:
                return json.loads(s2)
            except Exception:
                pass
    # 3. Extract from first { to last }
    first = s.find("{")
    last = s.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidate = s[first:last+1]
        try:
            return json.loads(candidate)
        except Exception:
            pass
    raise ValueError(f"could not parse JSON from LLM response (first 200 chars): {s[:200]}")


def log_llm_call(detail_id: str, model: str, system_prompt: str, user_prompt: str,
                 response_text: str, response_parsed_ok: int, tokens_in: int = 0,
                 tokens_out: int = 0, duration_ms: int = 0, cost_rub: float = 0,
                 error: str = ""):
    """Логирование LLM-вызова в таблицу llm_calls (для аналитики и аудита)"""
    from db import get_conn
    conn = get_conn()
    try:
        conn.execute("""INSERT INTO llm_calls
            (detail_id, model, system_prompt, user_prompt, response_text, response_parsed_ok,
             tokens_in, tokens_out, duration_ms, cost_rub, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (detail_id, model, system_prompt[:5000], user_prompt[:5000],
             response_text[:5000] if response_text else "", response_parsed_ok,
             tokens_in, tokens_out, duration_ms, cost_rub, error[:1000] if error else ""))
        conn.commit()
    except Exception as e:
        log.error(f"log_llm_call failed: {e}")
    finally:
        conn.close()


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Грубая оценка стоимости в рублях.
    YandexGPT ~ 0.04₽ за 1K токенов (mix input/output)."""
    # YandexGPT Lite: ~0.02₽/1K input, ~0.04₽/1K output
    # YandexGPT Pro: ~0.06₽/1K input, ~0.12₽/1K output
    if "lite" in (model or "").lower():
        rate_in, rate_out = 0.02, 0.04
    else:
        rate_in, rate_out = 0.06, 0.12
    return round((tokens_in / 1000 * rate_in) + (tokens_out / 1000 * rate_out), 4)
