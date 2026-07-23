"""Shared state через SQLite (вместо in-memory).

Позволяет multi-worker без Redis.
- sessions: таблица sessions
- rate_limit_buckets: таблица rate_limit_buckets с auto-cleanup
"""
import time
import secrets
import sqlite3
from typing import Optional, Tuple
from repositories import db


# ============================================================
# SESSIONS
# ============================================================
def session_create(username: str) -> str:
    """Создать session для username, вернуть session_id."""
    sid = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO sessions (session_id, username, created_at, expires_at) VALUES (?, ?, datetime('now'), datetime('now', '+7 days'))",
        (sid, username)
    )
    return sid


def session_get(sid: str) -> Optional[str]:
    """Получить username по session_id, или None."""
    if not sid:
        return None
    row = db.query_one(
        "SELECT username FROM sessions WHERE session_id = ? AND expires_at > datetime('now')",
        (sid,)
    )
    return row["username"] if row else None


def session_delete(sid: str) -> None:
    """Удалить session."""
    if sid:
        db.execute("DELETE FROM sessions WHERE session_id = ?", (sid,))


# ============================================================
# RATE LIMIT
# ============================================================
def rate_limit_check(key: str, max_calls: int, window_sec: int) -> Tuple[bool, int]:
    """Проверить rate limit. Возвращает (ok, retry_after_sec).
    
    Args:
        key: уникальный ключ (например, "gen:user")
        max_calls: макс вызовов за окно
        window_sec: окно в секундах
    
    Returns:
        (True, 0) если OK
        (False, retry_after_sec) если превышен лимит
    """
    now = time.time()
    # Очищаем старые (> window_sec) записи
    db.execute(
        "DELETE FROM rate_limit_buckets WHERE key = ? AND ts < ?",
        (key, now - window_sec)
    )
    count = db.query_one(
        "SELECT COUNT(*) AS n FROM rate_limit_buckets WHERE key = ?",
        (key,)
    )["n"]
    if count >= max_calls:
        # Retry = сколько ждать до самого старого timestamp
        oldest = db.query_one(
            "SELECT MIN(ts) AS t FROM rate_limit_buckets WHERE key = ?",
            (key,)
        )
        if oldest and oldest["t"]:
            retry_after = int(window_sec - (now - oldest["t"])) + 1
        else:
            retry_after = 1
        return False, max(1, retry_after)
    db.execute(
        "INSERT INTO rate_limit_buckets (key, ts) VALUES (?, ?)",
        (key, now)
    )
    return True, 0
