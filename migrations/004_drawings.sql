-- Sprint 7 D1: Drawings table (uploaded чертежи + OCR + LLM extraction)
CREATE TABLE IF NOT EXISTS drawings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,                  -- для безопасного URL
    item_id INTEGER,                            -- FK к items (NULL пока не привязан)
    file_path TEXT NOT NULL,                    -- /data/drawings/{uuid}.pdf
    original_filename TEXT NOT NULL,            -- имя от пользователя
    format TEXT NOT NULL,                       -- pdf | png | jpg
    file_size_bytes INTEGER NOT NULL,
    
    -- OCR
    ocr_status TEXT DEFAULT 'pending',          -- pending | processing | done | failed
    ocr_text TEXT,                              -- полный текст от tesseract
    ocr_error TEXT,                             -- если failed
    ocr_duration_ms INTEGER,
    ocr_at TIMESTAMP,
    
    -- LLM extraction
    llm_status TEXT DEFAULT 'pending',          -- pending | processing | done | failed
    llm_extracted_json TEXT,                    -- JSON: {designation, name, material, ...}
    llm_error TEXT,
    llm_duration_ms INTEGER,
    llm_at TIMESTAMP,
    
    -- Auto-create item
    item_created_id INTEGER,                    -- FK к items (когда создан)
    item_creation_status TEXT DEFAULT 'pending',-- pending | done | failed
    
    -- Audit
    uploaded_by INTEGER NOT NULL,               -- pilot_users.id (без FK чтобы избежать конфликтов схемы)
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_drawings_uuid ON drawings(uuid);
CREATE INDEX IF NOT EXISTS idx_drawings_item_id ON drawings(item_id);
CREATE INDEX IF NOT EXISTS idx_drawings_uploaded_by ON drawings(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_drawings_ocr_status ON drawings(ocr_status);
CREATE INDEX IF NOT EXISTS idx_drawings_llm_status ON drawings(llm_status);
