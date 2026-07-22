"""
LLMProvider — интерфейс для всех LLM.

ADR-0011 Принцип П6: LLMProvider интерфейс + 3 реализации +
назначение модели на задачу (отдельное право llm_admin).

Реализации:
- YandexGPTProvider — реальный Yandex Cloud
- MockLLMProvider — заглушка (когда API ключ невалиден)
- GigaChatProvider — заглушка (для будущей интеграции)

Выбор модели:
- llm_model_assignments хранит (task_type, llm_provider_id, model_name)
- LLMProviderRegistry берёт активного провайдера на задачу
"""
from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from repositories import db

logger = logging.getLogger(__name__)

MASTER_KEY_PATH = Path(__file__).parent.parent / ".master_key"


def _get_fernet():
    """Fernet для шифрования API-ключей."""
    from cryptography.fernet import Fernet
    if not MASTER_KEY_PATH.exists():
        MASTER_KEY_PATH.write_bytes(Fernet.generate_key())
    return Fernet(MASTER_KEY_PATH.read_bytes())


def encrypt_api_key(api_key: str) -> str:
    return _get_fernet().encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    return _get_fernet().decrypt(encrypted.encode()).decode()


# ============================================================
# ИСКЛЮЧЕНИЯ
# ============================================================

class LLMError(Exception):
    """Базовая ошибка LLM."""


class LLMAuthError(LLMError):
    """Ошибка авторизации (401/403)."""


class LLMRateLimit(LLMError):
    """Превышен rate limit (429)."""


class LLMTimeout(LLMError):
    """Таймаут запроса."""


# ============================================================
# РЕЗУЛЬТАТ ВЫЗОВА
# ============================================================

@dataclass
class LLMResult:
    """Результат одного вызова LLM."""
    content: str
    structured: Optional[Dict[str, Any]] = None
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_rub: float = 0.0
    duration_ms: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)

    def parse_json(self) -> Dict[str, Any]:
        """Парсит content как JSON. Если ошибка — возвращает {}."""
        try:
            return json.loads(self.content)
        except (json.JSONDecodeError, TypeError):
            return {}


# ============================================================
# ИНТЕРФЕЙС LLMProvider
# ============================================================

class LLMProvider(ABC):
    """Базовый интерфейс для всех LLM."""

    name: str = "base"
    display_name: str = "Base LLM"

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = 4000,
        model: Optional[str] = None,
        response_format: str = "text",  # "text" | "json"
    ) -> LLMResult:
        """Сгенерировать текст."""

    def get_cost_per_1k(self, model: Optional[str] = None) -> tuple:
        """Возвращает (input_price, output_price) в рублях за 1K токенов."""
        return (0.0, 0.0)


# ============================================================
# MOCK PROVIDER
# ============================================================

class MockLLMProvider(LLMProvider):
    """Заглушка для случая, когда API ключ невалиден или отсутствует.

    Возвращает детерминированный ответ на основе входного промта.
    Используется в препилоте и при недоступности реального LLM.
    """

    name = "mock"
    display_name = "MOCK (без реального LLM)"

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = 4000,
        model: Optional[str] = None,
        response_format: str = "text",
    ) -> LLMResult:
        start = time.time()
        # Имитация задержки LLM (2 сек)
        time.sleep(0.1)

        # Генерируем ответ на основе типа задачи (ищем в system)
        content = self._generate_by_task(prompt, system, response_format)
        duration_ms = int((time.time() - start) * 1000)

        return LLMResult(
            content=content,
            model="mock-1",
            input_tokens=len(prompt) // 4,
            output_tokens=len(content) // 4,
            cost_rub=0.0,
            duration_ms=duration_ms,
        )

    def _generate_by_task(self, prompt: str, system: str, response_format: str) -> str:
        """Генерирует ответ на основе типа задачи (определяем по system/prompt)."""
        p = (prompt + " " + system).lower()

        # Извещение diff (ПЕРВЫМ — иначе "техкарт" ниже срабатывает)
        if "извещен" in p and "diff" in p:
            return json.dumps(self._mock_notice_diff(), ensure_ascii=False, indent=2)

        # Техкарта генерация
        if "сгенерируй" in p or ("создай" in p and "техкарт" in p):
            return json.dumps(self._mock_tech_card(), ensure_ascii=False, indent=2)

        # Чертёж OCR
        if "распознай" in p or "ocr" in p:
            return json.dumps(self._mock_ocr_result(), ensure_ascii=False, indent=2)

        # Уточняющий вопрос
        if "уточни" in p or "вопрос" in p:
            return json.dumps(self._mock_clarification(), ensure_ascii=False, indent=2)

        # Обоснование нормы
        if "обоснован" in p and "норм" in p:
            return json.dumps(self._mock_evidence(), ensure_ascii=False, indent=2)

        # Default
        return json.dumps({"status": "ok", "mock": True}, ensure_ascii=False)

    def _mock_tech_card(self) -> Dict[str, Any]:
        return {
            "operations": [
                {"op_number": 5, "name": "Заготовительная (раскрой)", "workshop": "01",
                 "equipment": "Гильотинные ножницы НГ-6,3×2500", "profession": "Резчик 3р",
                 "time_setup_min": 6, "time_per_unit_min": 12, "materials": [{"code": "09Г2С", "qty_kg": 8.5}]},
                {"op_number": 10, "name": "Гибка", "workshop": "01",
                 "equipment": "Пресс гидравлический П6330", "profession": "Гибщик 4р",
                 "time_setup_min": 8, "time_per_unit_min": 18},
                {"op_number": 15, "name": "Сварка", "workshop": "02",
                 "equipment": "Полуавтомат сварочный ПДГ-508", "profession": "Электросварщик 5р",
                 "time_setup_min": 12, "time_per_unit_min": 35,
                 "materials": [{"code": "Св-08Г2С", "qty_kg": 1.2, "unit": "кг"}]},
                {"op_number": 20, "name": "Зачистка швов", "workshop": "02",
                 "equipment": "УШМ", "profession": "Слесарь 3р",
                 "time_setup_min": 4, "time_per_unit_min": 15},
                {"op_number": 25, "name": "Контроль качества", "workshop": "04",
                 "equipment": "Стол ОТК", "profession": "Контролёр 3р",
                 "time_setup_min": 5, "time_per_unit_min": 8},
            ],
            "total_time_min": 121,
            "warnings": ["Тшт операции 015 (сварка) — уточните по аналогам"],
        }

    def _mock_ocr_result(self) -> Dict[str, Any]:
        return {
            "title": "Чертёж детали (распознано из PDF)",
            "operations": [
                {"op_number": 5, "name": "Резка", "confidence": 0.92},
                {"op_number": 10, "name": "Гибка", "confidence": 0.88},
                {"op_number": 15, "name": "Сварка", "confidence": 0.95},
            ],
            "warnings": ["Не удалось распознать материал (стр. 3)"],
        }

    def _mock_notice_diff(self) -> Dict[str, Any]:
        return {
            "changes": [
                {"field": "material", "was": "09Г2С", "now": "10ХСНД",
                 "impact": "Увеличилась масса на 8%, пересмотр Тпз на 5%"},
                {"field": "welding_mode", "was": "режим 1", "now": "режим 2",
                 "impact": "Тпз операции 015 увеличить на 8%"},
            ],
            "affected_operations": [15, 20],
            "recommendation": "Проверьте операции 015 и 020 (сварка). Возможно увеличение Тпз на 8% и пересмотр Тшт по аналогам 10ХСНД.",
        }

    def _mock_clarification(self) -> Dict[str, Any]:
        return {
            "questions": [
                {"code": "weld_type", "question": "Тип сварки (MIG/MAG/TIG)?", "default": "MIG"},
                {"code": "thickness", "question": "Толщина основного металла, мм?", "default": "6"},
            ]
        }

    def _mock_evidence(self) -> Dict[str, Any]:
        return {
            "norm_value": 0.35,
            "source": "analog_estimate",
            "analogs": [
                {"designation": "ЛМША.301314.020", "value": 0.38, "similarity": 0.92},
                {"designation": "ЛМША.301314.030", "value": 0.32, "similarity": 0.85},
            ],
            "evidence_level": "yellow",
            "comment": "Жёлтый уровень — похоже на правду, но подтвердите",
        }


# ============================================================
# YANDEX GPT
# ============================================================

class YandexGPTProvider(LLMProvider):
    """Реальный Yandex Cloud LLM (gpt://)."""

    name = "yandexgpt"
    display_name = "YandexGPT"

    def __init__(self, api_key: str, folder_id: str = "", endpoint: str = ""):
        self.api_key = api_key
        self.folder_id = folder_id
        self.endpoint = endpoint or "gpt://"  # полный URI задаётся в настройках
        self.model_default = "yandexgpt/latest"

    def get_cost_per_1k(self, model: Optional[str] = None) -> tuple:
        # YandexGPT: ~0.40₽ за 1K токенов (input) + ~1.20₽ (output) = условно
        return (0.40, 1.20)

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = 4000,
        model: Optional[str] = None,
        response_format: str = "text",
    ) -> LLMResult:
        import requests

        start = time.time()
        model = model or self.model_default
        full_model_uri = self.endpoint + model if self.endpoint.startswith("gpt://") else model

        body = {
            "modelUri": full_model_uri,
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": str(max_tokens),
            },
            "messages": [],
        }
        if system:
            body["messages"].append({"role": "system", "text": system})
        body["messages"].append({"role": "user", "text": prompt})

        try:
            resp = requests.post(
                "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
                headers={
                    "Authorization": f"Api-Key {self.api_key}",
                    "x-folder-id": self.folder_id,
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=60,
            )
        except requests.Timeout as e:
            raise LLMTimeout(str(e))

        if resp.status_code == 401 or resp.status_code == 403:
            raise LLMAuthError(f"YandexGPT auth error: {resp.text[:200]}")
        if resp.status_code == 429:
            raise LLMRateLimit("Rate limit exceeded")
        if resp.status_code >= 400:
            raise LLMError(f"YandexGPT error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        text = data["result"]["alternatives"][0]["message"]["text"]
        usage = data.get("result", {}).get("usage", {})
        input_t = int(usage.get("inputTextTokens", 0))
        output_t = int(usage.get("completionTokens", 0))
        cost = (input_t * self.get_cost_per_1k()[0] + output_t * self.get_cost_per_1k()[1]) / 1000
        duration_ms = int((time.time() - start) * 1000)

        return LLMResult(
            content=text,
            model=model,
            input_tokens=input_t,
            output_tokens=output_t,
            cost_rub=cost,
            duration_ms=duration_ms,
            raw=data,
        )


# ============================================================
# GIGACHAT (заглушка для будущей интеграции)
# ============================================================

class GigaChatProvider(LLMProvider):
    """Заглушка для GigaChat (Сбер). Будет реализовано после пилота."""

    name = "gigachat"
    display_name = "GigaChat (Сбер) — заглушка"

    def __init__(self, api_key: str = "", endpoint: str = ""):
        self.api_key = api_key
        self.endpoint = endpoint

    def generate(self, prompt, system="", temperature=0.2, max_tokens=4000,
                 model=None, response_format="text") -> LLMResult:
        raise LLMError("GigaChat provider не реализован (заглушка). Используйте YandexGPT или Mock.")


# ============================================================
# OPENAI-COMPATIBLE (1bitai.ru, OpenRouter, proxy и т.п.)
# ============================================================

class OpenAIProvider(LLMProvider):
    """Универсальный OpenAI-compatible провайдер (1bitai.ru, OpenRouter, локальные прокси).

    M35o: добавлен для пилота 27.07 — поддержка 1bitai.ru (deepseek-v4-flash-thinking)
    и любых других OpenAI-совместимых API. Параметры api_url + api_key + model_name
    задаются через llm_providers (name='openai') + llm_model_assignments.
    """

    name = "openai"
    display_name = "OpenAI-compatible (1bitai.ru, OpenRouter, ...)"

    def __init__(self, api_key: str, endpoint: str = "", model: str = "gpt-4o-mini"):
        self.api_key = api_key
        # endpoint = полный base_url, например "https://api.1bitai.ru/v1"
        self.endpoint = endpoint.rstrip("/") if endpoint else "https://api.openai.com/v1"
        self.model = model

    def get_cost_per_1k(self, model: Optional[str] = None) -> tuple:
        # 1bitai.ru ~ 0.20₽ за 1K (input) + 0.60₽ (output). Провайдер-задаваемо
        return (0.20, 0.60)

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = 4000,
        model: Optional[str] = None,
        response_format: str = "text",
    ) -> LLMResult:
        from openai import OpenAI

        start = time.time()
        model = model or self.model
        client = OpenAI(api_key=self.api_key, base_url=self.endpoint, timeout=60.0)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            err = str(e)
            if "401" in err or "Unauthorized" in err or "auth" in err.lower():
                raise LLMAuthError(f"OpenAI auth error: {err[:200]}")
            if "429" in err or "rate" in err.lower():
                raise LLMRateLimit(f"Rate limit: {err[:200]}")
            if "timeout" in err.lower() or "timed out" in err.lower():
                raise LLMTimeout(f"Timeout: {err[:200]}")
            raise LLMError(f"OpenAI error: {err[:300]}")

        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        input_t = int(getattr(usage, "prompt_tokens", 0)) if usage else 0
        output_t = int(getattr(usage, "completion_tokens", 0)) if usage else 0
        cost = (input_t * self.get_cost_per_1k()[0] + output_t * self.get_cost_per_1k()[1]) / 1000
        duration_ms = int((time.time() - start) * 1000)

        return LLMResult(
            content=text,
            model=model,
            input_tokens=input_t,
            output_tokens=output_t,
            cost_rub=cost,
            duration_ms=duration_ms,
            raw=resp.model_dump() if hasattr(resp, "model_dump") else {},
        )


# ============================================================
# REGISTRY
# ============================================================

class LLMProviderRegistry:
    """Реестр провайдеров. Читает llm_providers и llm_model_assignments."""

    def __init__(self):
        self._cache: Dict[int, LLMProvider] = {}
        self._init_mock_provider()

    def _init_mock_provider(self):
        """Всегда есть mock provider (id=0 или -1)."""
        self._cache[-1] = MockLLMProvider()

    def get_for_task(self, task_type: str) -> LLMProvider:
        """Получить активного провайдера для типа задачи."""
        row = db.query_one("""
            SELECT ma.*, p.name AS provider_name, p.endpoint, p.api_key_enc
            FROM llm_model_assignments ma
            JOIN llm_providers p ON p.id = ma.llm_provider_id
            WHERE ma.task_type = ? AND ma.is_active = 1
            ORDER BY ma.id DESC LIMIT 1
        """, (task_type,))

        if not row:
            logger.warning(f"No model assignment for task {task_type}, using mock")
            return MockLLMProvider()

        provider_name = row["provider_name"]
        if provider_name == "mock":
            return MockLLMProvider()
        if provider_name == "yandexgpt":
            api_key = ""
            if row["api_key_enc"]:
                try:
                    api_key = decrypt_api_key(row["api_key_enc"])
                except Exception as e:
                    logger.error(f"Failed to decrypt API key: {e}")
                    return MockLLMProvider()
            folder_id = ""
            # Endpoint обычно "gpt://b1gj..."
            endpoint = row["endpoint"] or ""
            if endpoint.startswith("gpt://") and "/" in endpoint:
                folder_id = endpoint.split("/")[2] if len(endpoint.split("/")) > 2 else ""
            return YandexGPTProvider(api_key=api_key, folder_id=folder_id, endpoint=endpoint)
        if provider_name == "gigachat":
            return GigaChatProvider()
        if provider_name == "openai":
            api_key = ""
            if row["api_key_enc"]:
                try:
                    api_key = decrypt_api_key(row["api_key_enc"])
                except Exception as e:
                    logger.error(f"Failed to decrypt API key: {e}")
                    return MockLLMProvider()
            endpoint = row["endpoint"] or ""
            # model_name из assignment (model_name) перебивает дефолт провайдера
            return OpenAIProvider(api_key=api_key, endpoint=endpoint, model=row["model_name"] or "gpt-4o-mini")

        return MockLLMProvider()

    def is_mock_mode(self) -> bool:
        """Проверить, активен ли mock-провайдер для всех задач (для badge в UI)."""
        rows = db.query("""
            SELECT ma.*, p.name
            FROM llm_model_assignments ma
            JOIN llm_providers p ON p.id = ma.llm_provider_id
            WHERE ma.is_active = 1
        """)
        if not rows:
            return True
        return all(r["name"] == "mock" for r in rows)

    def daily_cost_estimate(self) -> float:
        """Примерная дневная стоимость LLM (по последним вызовам)."""
        row = db.query_one("""
            SELECT COALESCE(SUM(cost_rub), 0) AS total
            FROM llm_calls
            WHERE ts >= datetime('now', '-1 day')
        """)
        return float(row["total"]) if row else 0.0


# Singleton
_registry: Optional[LLMProviderRegistry] = None


def get_registry() -> LLMProviderRegistry:
    global _registry
    if _registry is None:
        _registry = LLMProviderRegistry()
    return _registry


# ============================================================
# CALL WRAPPER
# ============================================================

def call_llm(
    task_type: str,
    prompt: str,
    system: str = "",
    temperature: float = 0.2,
    max_tokens: int = 4000,
    response_format: str = "text",
    user: str = "system",
) -> LLMResult:
    """Удобный wrapper: получить провайдера по задаче + вызвать + залогировать.

    Все LLM-вызовы в системе идут через эту функцию.

    M37-#4: semaphore на 5 одновременных LLM-вызовов.
    Защита от runaway-клиента + защита 1bitai.ru от rate limit (RPS).
    """
    import threading
    global _llm_semaphore
    try:
        _llm_semaphore
    except NameError:
        _llm_semaphore = threading.Semaphore(5)

    registry = get_registry()
    provider = registry.get_for_task(task_type)

    with _llm_semaphore:
        # M37-#4: actual call wrapped by semaphore
        try:
            result = provider.generate(
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
            _log_call(task_type, provider.name, "", prompt, result, user, "ok", None)
            return result
        except LLMError as e:
            # Fallback на mock
            logger.warning(f"LLM error in {provider.name} for {task_type}: {e}, falling back to mock")
            result = MockLLMProvider().generate(prompt, system, temperature, max_tokens, response_format=response_format)
            _log_call(task_type, "mock", "", prompt, result, user, "fallback", str(e))
            return result
        except Exception as e:
            _log_call(task_type, provider.name, "", prompt, None, user, "error", str(e))
            raise


def _log_call(
    task_type: str,
    provider_name: str,
    model_name: str,
    prompt: str,
    result: Optional[LLMResult],
    user: str,
    status: str,
    error: Optional[str],
):
    """Записать вызов в llm_calls."""
    try:
        db.execute("""
            INSERT INTO llm_calls (task_type, llm_provider_id, model_name, prompt_hash,
                                    prompt_tokens, completion_tokens, cost_rub,
                                    duration_ms, user, status, error_message)
            VALUES (?, (SELECT id FROM llm_providers WHERE name = ? LIMIT 1), ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_type, provider_name, model_name,
            str(hash(prompt))[:32],
            result.input_tokens if result else 0,
            result.output_tokens if result else 0,
            result.cost_rub if result else 0.0,
            result.duration_ms if result else 0,
            user, status, error,
        ))
    except Exception as e:
        logger.error(f"Failed to log LLM call: {e}")


def parse_llm_json_safe(content: str) -> Dict[str, Any]:
    """Парсит JSON из ответа LLM. Если ошибка — пытается вытащить из блока ```json ... ```."""
    import re
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        pass
    # Ищем блок ```json ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", content, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return {}
