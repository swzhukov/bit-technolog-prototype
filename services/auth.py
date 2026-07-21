"""
auth.py — авторизация (5 ролей по прототипу v0.6).

ADR-0011: Роли из прототипа (5 ролей):
1. technologist       — технолог (Баранов, Голубев, Воробьев)
2. main_technologist  — главный технолог
3. workshop_chief     — начальник цеха
4. tech_admin         — технический администратор (настройка профилей РС, НЕ LLM)
5. llm_admin          — LLM-администратор (назначение моделей)

В препилоте — простая Basic Auth. В пилоте — login-форма.
"""
import hashlib
import secrets
from dataclasses import dataclass
from functools import wraps
from typing import Optional

from repositories import db

# ============================================================
# РОЛИ
# ============================================================

ROLES = {
    "technologist": {
        "display": "Технолог",
        "icon": "👤",
        "permissions": [
            "view_tech_cards",
            "edit_own_tech_cards",
            "approve_own_tech_cards",
            "view_resource_specs",
            "view_etalons",
            "view_work_history",
        ],
    },
    "main_technologist": {
        "display": "Главный технолог",
        "icon": "🔧",
        "permissions": [
            "view_tech_cards",
            "edit_tech_cards",
            "approve_tech_cards",
            "approve_etalons",
            "manage_tech_rules",
            "view_resource_specs",
            "edit_resource_specs",
            "view_etalons",
            "view_work_history",
            "view_change_notices",
        ],
    },
    "workshop_chief": {
        "display": "Начальник цеха",
        "icon": "🏭",
        "permissions": [
            "view_tech_cards",
            "approve_tech_cards",
            "view_resource_specs",
            "view_change_notices",
            "view_etalons",
        ],
    },
    "tech_admin": {
        "display": "Тех. администратор",
        "icon": "⚙️",
        "permissions": [
            "view_all",
            "edit_all",
            "manage_rs_profiles",
            "manage_llm_providers",
            "manage_llm_model_assignments",
            "manage_changelog",
            "view_audit_logins",
            "view_llm_calls",
        ],
    },
    "llm_admin": {
        "display": "LLM администратор",
        "icon": "🤖",
        "permissions": [
            "view_llm_calls",
            "manage_llm_providers",
            "manage_llm_model_assignments",
        ],
    },
}


def has_permission(role: str, permission: str) -> bool:
    """Проверить, есть ли у роли право."""
    r = ROLES.get(role, {})
    return permission in r.get("permissions", [])


# ============================================================
# USERS
# ============================================================

@dataclass
class User:
    id: int
    username: str
    role: str
    display_name: str
    email: str = ""
    is_active: bool = True

    @property
    def role_display(self) -> str:
        return ROLES.get(self.role, {}).get("display", self.role)

    @property
    def role_icon(self) -> str:
        return ROLES.get(self.role, {}).get("icon", "👤")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "role_display": self.role_display,
            "role_icon": self.role_icon,
            "display_name": self.display_name,
            "email": self.email,
        }


def hash_password(password: str) -> str:
    """SHA-256 + salt (простая реализация для препилота)."""
    salt = "bit_technolog_2026"
    return hashlib.sha256((salt + password).encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return secrets.compare_digest(hash_password(password), password_hash)


def authenticate(username: str, password: str, ip: str = "", user_agent: str = "") -> Optional[User]:
    """Проверить логин/пароль. Возвращает User или None."""
    row = db.query_one(
        "SELECT * FROM pilot_users WHERE username = ? AND is_active = 1",
        (username,)
    )
    if not row:
        _log_login(username, ip, user_agent, 0, "user_not_found")
        return None
    if not verify_password(password, row["password_hash"]):
        _log_login(username, ip, user_agent, 0, "wrong_password")
        return None
    _log_login(username, ip, user_agent, 1, "ok")
    # Обновим last_login
    db.execute("UPDATE pilot_users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
    return User(
        id=row["id"],
        username=row["username"],
        role=row["role"],
        display_name=row["display_name"],
        email=row["email"] or "",
        is_active=bool(row["is_active"]),
    )


def _log_login(username: str, ip: str, ua: str, success: int, reason: str):
    try:
        db.execute(
            "INSERT INTO audit_logins (username, ip, user_agent, success, reason) VALUES (?, ?, ?, ?, ?)",
            (username, ip[:64], ua[:256], success, reason),
        )
    except Exception:
        pass


# ============================================================
# DEMO USERS (для препилота)
# ============================================================

DEMO_USERS = [
    # (username, password, role, display_name, email)
    ("baranov",     "demo",  "main_technologist", "Баранов А.Н.", "baranov@tehinkom.ru"),
    ("golubev",     "demo",  "workshop_chief",    "Голубев П.В.", "golubev@tehinkom.ru"),
    ("vorobyev",    "demo",  "main_technologist", "Воробьев И.Ф.", "vorobyev@tehinkom.ru"),
    ("tarrietsky",  "demo",  "technologist",      "Тарлецкий А.С.", "tarrietsky@tehinkom.ru"),
    ("techadmin",   "demo",  "tech_admin",        "Тех. администратор", "admin@tehinkom.ru"),
    ("llmadmin",    "demo",  "llm_admin",         "LLM администратор", "llm@tehinkom.ru"),
]


def seed_users(verbose: bool = True) -> int:
    """Создать демо-пользователей (если ещё нет)."""
    db.init_db()
    loaded = 0
    for username, password, role, display_name, email in DEMO_USERS:
        existing = db.query_one("SELECT id FROM pilot_users WHERE username = ?", (username,))
        if existing:
            continue
        db.insert_and_get_id("pilot_users", {
            "username": username,
            "password_hash": hash_password(password),
            "role": role,
            "display_name": display_name,
            "email": email,
            "is_active": 1,
        })
        if verbose:
            print(f"✅ user: {username} ({role})")
        loaded += 1
    return loaded


# ============================================================
# DEPENDENCY для FastAPI
# ============================================================

# В FastAPI: from fastapi import Depends, Request
# Используется так:
#
#   def get_current_user(request: Request) -> Optional[User]:
#       auth = request.headers.get("authorization", "")
#       if not auth.startswith("Basic "):
#           return None
#       import base64
#       try:
#           creds = base64.b64decode(auth[6:]).decode()
#           username, password = creds.split(":", 1)
#           return authenticate(username, password)
#       except Exception:
#           return None
#
#   def require_role(*roles):
#       def decorator(func):
#           @wraps(func)
#           async def wrapper(*args, current_user: Optional[User] = Depends(get_current_user), **kwargs):
#               if not current_user:
#                   raise HTTPException(401, "Authentication required")
#               if current_user.role not in roles:
#                   raise HTTPException(403, f"Required role: {roles}")
#               return await func(*args, current_user=current_user, **kwargs)
#           return wrapper
#       return decorator
