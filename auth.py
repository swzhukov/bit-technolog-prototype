"""
auth.py — модуль аутентификации и ролей (v0.4.9, F15).
Выделено из app.py.
Содержит: ROLES dict, get_current_role, hash/verify_password, authenticate, log_login.
"""
import hashlib
import secrets
from typing import Optional

# ========== Роли ==========
ROLES = {
    "technologist": {
        "name": "Технолог",
        "default_view": "drafts",
        "can_edit": True,
        "can_approve": False,
        "can_manage_workflow": False
    },
    "main_technologist": {
        "name": "Главный технолог",
        "default_view": "approval_queue",
        "can_edit": True,
        "can_approve": True,
        "can_manage_workflow": True
    },
    "normirovshchik": {
        "name": "Нормировщик",
        "default_view": "economics",
        "can_edit": True,
        "can_approve": False,
        "can_manage_workflow": False
    },
    "constructor": {
        "name": "Конструктор",
        "default_view": "blueprints",
        "can_edit": False,
        "can_approve": False,
        "can_manage_workflow": False
    },
    "workshop_chief": {
        "name": "Начальник цеха",
        "default_view": "approved",
        "can_edit": False,
        "can_approve": True,
        "can_manage_workflow": False
    },
    "quality": {
        "name": "Контролёр ОТК",
        "default_view": "warnings",
        "can_edit": True,
        "can_approve": False,
        "can_manage_workflow": False
    },
    "admin": {
        "name": "Администратор",
        "default_view": "admin_dashboard",
        "can_edit": True,
        "can_approve": True,
        "can_manage_workflow": True,
        "can_admin": True
    }
}


def get_current_role(request) -> str:
    """Получает текущую роль из cookie. Default = technologist"""
    role = request.cookies.get("bit_role", "technologist")
    if role not in ROLES:
        role = "technologist"
    return role


def is_admin(request) -> bool:
    """Проверка что текущий пользователь — администратор"""
    return get_current_role(request) == "admin"


# ========== Хеширование паролей ==========
def hash_password(password: str) -> str:
    """bcrypt хеш пароля. Fallback на sha256+salt если bcrypt недоступен."""
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    except ImportError:
        salt = secrets.token_hex(16)
        h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
        return f"sha256${salt}${h}"


def verify_password(password: str, password_hash: str) -> bool:
    """Проверка пароля (поддерживает bcrypt и sha256$salt$hash)"""
    if not password_hash:
        return False
    try:
        import bcrypt
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ImportError:
        if password_hash.startswith("sha256$"):
            parts = password_hash.split("$", 2)
            if len(parts) != 3:
                return False
            salt, h = parts[1], parts[2]
            return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == h
    return False


def authenticate_pilot_user(username: str, password: str) -> Optional[dict]:
    """Аутентификация пользователя из БД. Возвращает dict или None.
    Также обновляет last_login при успехе."""
    from db import get_conn
    conn = get_conn()
    try:
        row = conn.execute("""SELECT id, username, password_hash, role, display_name, is_active
            FROM pilot_users WHERE username=? AND is_active=1""", (username,)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    if not verify_password(password, row[2]):
        return None
    # update last_login
    conn = get_conn()
    try:
        conn.execute("UPDATE pilot_users SET last_login=CURRENT_TIMESTAMP WHERE id=?", (row[0],))
        conn.commit()
    finally:
        conn.close()
    return {"id": row[0], "username": row[1], "role": row[3], "display_name": row[4]}


def log_login(username: str, ip: str, user_agent: str, success: bool):
    """Логирование попытки входа в audit_logins"""
    from db import get_conn
    conn = get_conn()
    try:
        conn.execute("""INSERT INTO audit_logins (username, ip, user_agent, success)
            VALUES (?, ?, ?, ?)""", (username, ip, user_agent, 1 if success else 0))
        conn.commit()
    finally:
        conn.close()
