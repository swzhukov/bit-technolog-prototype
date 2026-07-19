"""
settings.py — модуль глобальных настроек (v0.4.9, F15).
Выделено из app.py.
Содержит: Fernet-шифрование, реестр настроек, get/set/delete setting.
"""
import os
import base64
import logging
from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger("bit-technolog")

# Мастер-ключ Fernet (из .env или сгенерированный)
def _get_or_create_master_key() -> bytes:
    """Получает или создаёт Fernet-ключ.
    Хранится в файле .master_key (chmod 600) рядом с .env.
    Если .env содержит FERNET_KEY — использует его."""
    env_key = os.getenv("FERNET_KEY", "").strip()
    if env_key:
        try:
            return base64.urlsafe_b64decode(env_key)
        except Exception:
            pass
    # Файл .master_key рядом с .env
    from db import DB_PATH
    key_path = os.path.join(os.path.dirname(DB_PATH) or ".", ".master_key")
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            return f.read()
    # Сгенерировать новый
    key = Fernet.generate_key()
    with open(key_path, "wb") as f:
        f.write(key)
    os.chmod(key_path, 0o600)
    return key


_FERNET = None


def _fernet() -> Fernet:
    global _FERNET
    if _FERNET is None:
        _FERNET = Fernet(_get_or_create_master_key())
    return _FERNET


SETTING_REGISTRY = [
    ("LLM_API_KEY", "secret", "", "YandexGPT API key", True),
    ("LLM_MODEL", "str", "gpt://b1gj791m9sc92argfa0q/yandexgpt/latest", "LLM model URI", False),
    ("LLM_API_URL", "str", "https://llm.api.cloud.yandex.net/v1", "OpenAI-compatible endpoint", False),
    ("LLM_DAILY_COST_LIMIT_RUB", "int", "200", "Дневной лимит LLM (₽)", False),
    ("DEMO_MODE", "bool", "false", "Демо-режим (без LLM)", False),
    ("TELEGRAM_BOT_TOKEN", "secret", "", "Telegram bot token (@BotFather)", True),
    ("TELEGRAM_CHAT_ID", "str", "", "Telegram chat ID для уведомлений", False),
    ("SMTP_HOST", "str", "", "SMTP хост (например, smtp.yandex.ru)", False),
    ("SMTP_PORT", "int", "587", "SMTP порт", False),
    ("SMTP_USER", "str", "", "SMTP пользователь", False),
    ("SMTP_PASS", "secret", "", "SMTP пароль", True),
    ("NOTIFY_EMAIL_FROM", "str", "bit-technolog@tehnocom.local", "Email отправителя", False),
    ("MAX_DRAWING_SIZE_MB", "int", "50", "Макс. размер чертежа (МБ)", False),
    ("MAX_IMPORT_SIZE_MB", "int", "100", "Макс. размер импорта (МБ)", False),
    ("PILOT_USERS", "str", "", "Basic Auth users (user:pass,user2:pass2)", True),
]


def _mask_value(value: str) -> str:
    """Маскирует секрет: первые 4 и последние 3 символа"""
    if not value or len(value) < 10:
        return "***" if value else ""
    return f"{value[:4]}...{value[-3:]}"


def _encrypt(value: str) -> bytes:
    if not value:
        return b""
    return _fernet().encrypt(value.encode("utf-8"))


def _decrypt(blob: bytes) -> str:
    if not blob:
        return ""
    try:
        return _fernet().decrypt(bytes(blob)).decode("utf-8")
    except (InvalidToken, Exception):
        return ""


def get_setting(key: str, default: str = "") -> str:
    """Получает настройку: сначала из БД, потом из .env, потом default.
    Устойчив к отсутствию таблицы app_settings (на свежей БД)."""
    from db import get_conn
    conn = None
    try:
        conn = get_conn()
        row = conn.execute("SELECT value_encrypted FROM app_settings WHERE key=?", (key,)).fetchone()
        if row and row[0]:
            val = _decrypt(row[0])
            if val:
                return val
    except Exception as e:
        log.debug(f"get_setting({key}) DB error (will fallback): {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    env_val = os.getenv(key, "")
    if env_val:
        return env_val
    return default


def set_setting(key: str, value: str, updated_by: str = "admin") -> bool:
    """Сохраняет настройку в БД (зашифрованно)"""
    from db import get_conn
    conn = get_conn()
    try:
        encrypted = _encrypt(value)
        masked = _mask_value(value) if value else ""
        conn.execute("""INSERT INTO app_settings (key, value_encrypted, value_masked, updated_at, updated_by)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_encrypted=excluded.value_encrypted,
                value_masked=excluded.value_masked,
                updated_at=CURRENT_TIMESTAMP,
                updated_by=excluded.updated_by""",
            (key, encrypted, masked, updated_by))
        conn.commit()
    except Exception as e:
        log.error(f"set_setting({key}) failed: {e}")
        return False
    finally:
        conn.close()
    return True


def delete_setting(key: str) -> bool:
    """Удаляет настройку (откат на .env/default)"""
    from db import get_conn
    conn = get_conn()
    try:
        conn.execute("DELETE FROM app_settings WHERE key=?", (key,))
        conn.commit()
    finally:
        conn.close()
    return True


def get_all_settings() -> list:
    """Возвращает список всех настроек с их текущими значениями (masked)"""
    result = []
    for key, stype, default, desc, is_secret in SETTING_REGISTRY:
        current = get_setting(key, default)
        result.append({
            "key": key, "type": stype, "default": default, "description": desc,
            "is_secret": is_secret,
            "value_set": bool(current),
            "value_masked": _mask_value(current) if (is_secret and current) else (current[:200] if current else "")
        })
    return result
