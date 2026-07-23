"""Audit-trail: писать в history table все mutations."""
from typing import Optional, Any, Dict
import json
from repositories import db


def log_history(
    entity_type: str,
    entity_id: int,
    action: str,
    user: str = "system",
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Записать событие в audit-trail (history table).
    
    Args:
        entity_type: 'item' | 'tech_card' | 'operation' | 'notice' | 'etalon' | 'session'
        entity_id: ID сущности
        action: 'create' | 'update' | 'delete' | 'approve' | 'reject' | 'confirm' | 'export'
        user: username (login, НЕ ФИО — 152-ФЗ)
        details: dict с подробностями (или None)
    """
    try:
        details_json = json.dumps(details, ensure_ascii=False) if details else None
        db.execute(
            "INSERT INTO history (entity_type, entity_id, action, user, details_json) VALUES (?, ?, ?, ?, ?)",
            (entity_type, entity_id, action, user, details_json),
        )
    except Exception:
        # Audit log не должен ломать основной flow
        pass
