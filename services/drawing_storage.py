"""
Sprint 7 D1: Drawing storage service.

Хранит загруженные чертежи в /data/drawings/ с UUID именами.
Метаданные в таблице drawings.
"""
import os
import uuid
import logging
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Папка для чертежей
DRAWINGS_DIR = Path("/opt/beget/bit-technolog/data/drawings")  # type: ignore
# В Docker volume: /app/data/drawings (для контейнера)
DRAWINGS_DIR_DOCKER = Path("/app/data/drawings")

# Поддерживаемые форматы
ALLOWED_FORMATS = {
    "pdf": ["application/pdf", ".pdf"],
    "png": ["image/png", ".png"],
    "jpg": ["image/jpeg", "image/jpg", ".jpg", ".jpeg"],
}
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}

# Максимальный размер (50 MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


def get_drawings_dir() -> Path:
    """Получить путь к папке чертежей (с учётом Docker)."""
    if DRAWINGS_DIR_DOCKER.exists():
        return DRAWINGS_DIR_DOCKER
    return DRAWINGS_DIR


def detect_format(filename: str, content_type: Optional[str] = None) -> str:
    """Определить формат файла по имени и content-type.
    
    Returns: 'pdf' | 'png' | 'jpg' или raises ValueError.
    """
    ext = Path(filename).suffix.lower()
    
    if ext == ".pdf":
        return "pdf"
    elif ext in (".png",):
        return "png"
    elif ext in (".jpg", ".jpeg"):
        return "jpg"
    
    if content_type:
        ct = content_type.lower()
        if "pdf" in ct:
            return "pdf"
        if "png" in ct:
            return "png"
        if "jpeg" in ct or "jpg" in ct:
            return "jpg"
    
    raise ValueError(f"Unsupported format: {filename} ({content_type})")


def save_upload(filename: str, content: bytes, content_type: Optional[str] = None) -> dict:
    """Сохранить загруженный файл.
    
    Returns: dict с полями:
    - uuid: уникальный ID
    - file_path: абсолютный путь
    - format: pdf/png/jpg
    - file_size_bytes: размер
    - original_filename: имя от пользователя
    """
    if len(content) == 0:
        raise ValueError("Empty file")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {len(content)} bytes (max {MAX_FILE_SIZE})")
    
    fmt = detect_format(filename, content_type)
    file_uuid = str(uuid.uuid4())
    ext = "." + fmt
    drawings_dir = get_drawings_dir()
    drawings_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = drawings_dir / f"{file_uuid}{ext}"
    file_path.write_bytes(content)
    
    return {
        "uuid": file_uuid,
        "file_path": str(file_path),
        "format": fmt,
        "file_size_bytes": len(content),
        "original_filename": filename,
    }


def create_drawing_row(
    uuid_str: str,
    file_path: str,
    original_filename: str,
    fmt: str,
    file_size_bytes: int,
    uploaded_by: int,
) -> int:
    """Создать запись в таблице drawings. Returns: id новой записи."""
    from repositories import db
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO drawings (uuid, file_path, original_filename, format, file_size_bytes, uploaded_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (uuid_str, file_path, original_filename, fmt, file_size_bytes, uploaded_by),
    )
    conn.commit()
    return cur.lastrowid or 0


def get_drawing(drawing_id: int) -> Optional[dict]:
    """Получить чертеж по ID."""
    from repositories import db
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM drawings WHERE id = ?", (drawing_id,))
    row = cur.fetchone()
    if not row:
        return None
    return dict(row)


def get_drawing_by_uuid(uuid_str: str) -> Optional[dict]:
    """Получить чертеж по UUID."""
    from repositories import db
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM drawings WHERE uuid = ?", (uuid_str,))
    row = cur.fetchone()
    if not row:
        return None
    return dict(row)


def update_drawing(drawing_id: int, **fields) -> None:
    """Обновить поля чертежа."""
    if not fields:
        return
    from repositories import db
    conn = db.get_connection()
    cur = conn.cursor()
    
    # Whitelist полей
    allowed = {
        "ocr_status", "ocr_text", "ocr_error", "ocr_duration_ms", "ocr_at",
        "llm_status", "llm_extracted_json", "llm_error", "llm_duration_ms", "llm_at",
        "item_id", "item_created_id", "item_creation_status",
    }
    safe_fields = {k: v for k, v in fields.items() if k in allowed}
    if not safe_fields:
        return
    
    set_clause = ", ".join(f"{k} = ?" for k in safe_fields.keys())
    values = list(safe_fields.values()) + [drawing_id]
    cur.execute(
        f"UPDATE drawings SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        values,
    )
    conn.commit()


def list_drawings(uploaded_by: Optional[int] = None, limit: int = 50) -> list:
    """Список чертежей (опционально фильтр по user)."""
    from repositories import db
    conn = db.get_connection()
    cur = conn.cursor()
    if uploaded_by is not None:
        cur.execute(
            "SELECT * FROM drawings WHERE uploaded_by = ? ORDER BY uploaded_at DESC LIMIT ?",
            (uploaded_by, limit),
        )
    else:
        cur.execute(
            "SELECT * FROM drawings ORDER BY uploaded_at DESC LIMIT ?",
            (limit,),
        )
    return [dict(r) for r in cur.fetchall()]
