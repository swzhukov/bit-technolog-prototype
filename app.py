"""
БИТ.Технолог — Прототип v0.1
AI-помощник технолога для ускорения создания техкарт.

Запуск: python app.py
Открыть: http://localhost:8080
"""

import os
import json
import io
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment
load_dotenv()
LLM_API_URL = os.getenv("LLM_API_URL", "https://api.1bitai.ru/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash-thinking")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

# Auto-enable demo mode if API key is empty
if not LLM_API_KEY and not DEMO_MODE:
    log_msg = "No LLM_API_KEY set — auto-enabling DEMO_MODE"
    print(f"[WARN] {log_msg}")
    DEMO_MODE = True

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("bit-technolog")

# FastAPI app
app = FastAPI(title="БИТ.Технолог — Прототип", version="0.1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Local imports
from prompts import TECH_CARD_PROMPT
from mock_data import MOCK_DETAILS
from few_shot import FEW_SHOT_4C85941A

with open("equipment.json", "r", encoding="utf-8") as f:
    EQUIPMENT = json.load(f)

with open("structure.json", "r", encoding="utf-8") as f:
    STRUCTURE = json.load(f)

# Database
DB_PATH = "bit_technolog.db"


def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS drafts (
            detail_id TEXT PRIMARY KEY,
            llm_output TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            human_edits TEXT
        );

        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detail_id TEXT,
            action TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT
        );
    """)
    conn.close()


def get_draft(detail_id: str) -> Optional[dict]:
    """Get draft from DB"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT llm_output, status FROM drafts WHERE detail_id = ?",
        (detail_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return {"output": json.loads(row[0]), "status": row[1]}
    return None


def save_draft(detail_id: str, llm_output: dict, status: str = "draft"):
    """Save draft to DB"""
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO drafts (detail_id, llm_output, status, created_at, updated_at)
           VALUES (?, ?, ?, COALESCE((SELECT created_at FROM drafts WHERE detail_id = ?), ?), ?)""",
        (detail_id, json.dumps(llm_output, ensure_ascii=False), status, detail_id, now, now)
    )
    conn.commit()
    conn.close()


def add_history(detail_id: str, action: str, details: dict = None):
    """Add history entry"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO history (detail_id, action, details) VALUES (?, ?, ?)",
        (detail_id, action, json.dumps(details or {}, ensure_ascii=False))
    )
    conn.commit()
    conn.close()


# Pydantic models
class GenerateRequest(BaseModel):
    detail_id: str
    answers: Optional[dict] = None


# Routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "details": MOCK_DETAILS,
        "demo_mode": DEMO_MODE,
        "llm_model": LLM_MODEL
    })


@app.get("/detail/{detail_id}", response_class=HTMLResponse)
async def detail(request: Request, detail_id: str):
    detail_obj = next((d for d in MOCK_DETAILS if d["id"] == detail_id), None)
    if not detail_obj:
        raise HTTPException(404, "Detail not found")

    draft_data = get_draft(detail_id)

    return templates.TemplateResponse("detail.html", {
        "request": request,
        "detail": detail_obj,
        "draft": draft_data["output"] if draft_data else None,
        "status": draft_data["status"] if draft_data else "new",
        "demo_mode": DEMO_MODE,
        "llm_model": LLM_MODEL
    })


@app.post("/api/generate")
async def generate(detail_id: str = Form(...)):
    """Generate draft via LLM (or mock in demo mode). Accepts form-data (htmx default)."""
    detail_obj = next((d for d in MOCK_DETAILS if d["id"] == detail_id), None)
    if not detail_obj:
        return HTMLResponse(
            f'<span style="color:red">❌ Деталь {detail_id} не найдена</span>',
            status_code=404
        )

    # DEMO MODE: return mock response based on detail
    if DEMO_MODE:
        log.info(f"Demo mode: generating mock draft for {detail_id}")
        llm_output = generate_mock_draft(detail_obj)
        add_history(detail_id, "generated_mock", {"mode": "demo"})
    else:
        # Real LLM call via OpenAI-compatible API
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url=LLM_API_URL,
                api_key=LLM_API_KEY,
                timeout=LLM_TIMEOUT
            )

            from string import Template
            prompt = Template(TECH_CARD_PROMPT).substitute(
                properties_json=json.dumps(detail_obj, indent=2, ensure_ascii=False),
                equipment_json=json.dumps(EQUIPMENT, indent=2, ensure_ascii=False),
                structure_json=json.dumps(STRUCTURE, indent=2, ensure_ascii=False),
                few_shot_json=json.dumps(FEW_SHOT_4C85941A, indent=2, ensure_ascii=False)
            )

            log.info(f"Calling {LLM_MODEL} via {LLM_API_URL}...")
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "Ты — опытный технолог-сварщик. Генерируешь техкарты по свойствам деталей. Всегда возвращаешь валидный JSON без markdown-обёртки."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=8000
            )
            llm_output_text = response.choices[0].message.content
            # Strip markdown code fences if any
            llm_output_text = llm_output_text.strip()
            if llm_output_text.startswith("```"):
                lines = llm_output_text.split("\n")
                llm_output_text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else llm_output_text
                if llm_output_text.startswith("json"):
                    llm_output_text = llm_output_text[4:].lstrip()
            llm_output = json.loads(llm_output_text)
            add_history(detail_id, "generated", {
                "model": LLM_MODEL,
                "tokens_in": response.usage.prompt_tokens if response.usage else None,
                "tokens_out": response.usage.completion_tokens if response.usage else None
            })
        except Exception as e:
            log.error(f"LLM error: {e}")
            error_msg = str(e).replace("<", "&lt;").replace(">", "&gt;")[:200]
            return HTMLResponse(
                f'<span style="color:red">❌ Ошибка LLM: {error_msg}</span>',
                status_code=500
            )

    save_draft(detail_id, llm_output, "draft")
    return HTMLResponse('<span style="color:green">✅ Готово! Перезагружаю...</span>')


def generate_mock_draft(detail_obj: dict) -> dict:
    """Generate a mock draft based on the detail properties"""
    material = detail_obj.get("material", "")
    model = detail_obj.get("model", "")
    mass = detail_obj.get("mass_kg", 0)
    surface = detail_obj.get("surface_treatment", "")

    # Heuristic: welding operations for steel details
    is_steel = material and "Сталь" in material
    is_shtamp = "оцинковка" in surface

    operations = []
    route = []
    step = 0

    if is_steel and not is_shtamp:
        # Steel with painting - has welding operations
        step += 1
        operations.append({
            "name": "010 Подготовительная",
            "equipment": None,
            "duration_hours": 0.2,
            "duration_source": "экспертная оценка",
            "confidence": 70,
            "materials": ["проволока Св-08Г2С-О 1,0 ГОСТ 2246-70"],
            "control_points": [],
            "gosts": [],
            "department": "Сварочно-сборочный КТ",
            "workplace": "01/01/04"
        })
        route.append({"step": step, "operation": "010 Подготовительная", "duration_hours": 0.2})

        # Welding operations
        welding_ops = [
            ("015 Сборка под сварку", 0.5, 90, "аналог: ЛМША.301314.020"),
            ("020 Сварка", 0.6, 92, "аналог: ЛМША.301314.020"),
            ("025 Сборка", 0.7, 85, "аналог: ЛМША.301314.020"),
            ("030 Сварка", 0.6, 85, "аналог: ЛМША.301314.020"),
        ]

        for name, dur, conf, src in welding_ops:
            step += 1
            operations.append({
                "name": name,
                "equipment": "Кедр-300",
                "duration_hours": dur,
                "duration_source": src,
                "confidence": conf,
                "materials": [],
                "control_points": ["ОТК визуальный"],
                "gosts": ["ГОСТ 3.1404-86"],
                "department": "Сварочно-сборочный КТ",
                "workplace": "01/01/04"
            })
            route.append({"step": step, "operation": name, "duration_hours": dur})

        # Painting
        step += 1
        operations.append({
            "name": "035 Покраска",
            "equipment": "Камера покрасочная",
            "duration_hours": 0.8,
            "duration_source": "экспертная оценка",
            "confidence": 75,
            "materials": ["грунт ГФ-021", "эмаль ПФ-115"],
            "control_points": ["ОТК визуальный", "контроль толщины покрытия"],
            "gosts": ["ГОСТ 9.402", "ГОСТ 9.410"],
            "department": "Покраска",
            "workplace": "01/07/01"
        })
        route.append({"step": step, "operation": "035 Покраска", "duration_hours": 0.8})

    elif is_shtamp:
        # Galvanized - no welding, simpler
        operations.append({
            "name": "010 Раскрой",
            "equipment": "Плазменный рез HyperTherm",
            "duration_hours": 0.1,
            "duration_source": "экспертная оценка",
            "confidence": 80,
            "materials": [],
            "control_points": ["ОТК визуальный"],
            "gosts": ["ГОСТ 9.402"],
            "department": "Лазерная резка",
            "workplace": "01/01/01"
        })
        route.append({"step": 1, "operation": "010 Раскрой", "duration_hours": 0.1})

        operations.append({
            "name": "015 Гибка",
            "equipment": "Гибочный станок",
            "duration_hours": 0.15,
            "duration_source": "экспертная оценка",
            "confidence": 75,
            "materials": [],
            "control_points": ["ОТК визуальный"],
            "gosts": [],
            "department": "Гибка",
            "workplace": "01/01/03"
        })
        route.append({"step": 2, "operation": "015 Гибка", "duration_hours": 0.15})

    # Summary
    total_hours = sum(op["duration_hours"] for op in operations)

    # Reasoning
    reasoning = {
        "operations_choice": f"Операции выбраны на основе типа материала ({material}) и характера детали ({detail_obj.get('name', '')}). Аналог: ЛМША.301314.020 (упор продольный).",
        "duration_estimates": f"Расчёт по аналогам из ведомости трудоёмкости Техинкома. Масса детали {mass} кг.",
        "equipment_choice": f"Кедр-300 — основной сварочный аппарат (если применимо). Плазменный HyperTherm — для раскроя листа.",
        "risks": "Точность операций 015-035 — 80-92% (по аналогу). Требуется проверка технолога."
    }

    # Warnings
    warnings = []
    if surface == "покраска":
        warnings.append({
            "type": "ambiguous",
            "quote": "surface_treatment: 'покраска'",
            "concern": "Не указан тип краски (порошковая/жидкая) и грунтовка",
            "question": "Какой тип краски? Требуется ли грунтовка перед покраской?"
        })
    if "Сталь 3" in material:
        warnings.append({
            "type": "ambiguous",
            "quote": f"material: '{material}'",
            "concern": "Сталь 3 — устаревшее обозначение. Возможно, Ст3сп, Ст3пс, Ст3кп?",
            "question": "Какая марка стали точно?"
        })

    # Questions
    questions = []
    if surface == "покраска":
        questions.append({
            "id": "Q1",
            "topic": "покраска",
            "question": "Тип покраски?",
            "options": ["порошковая", "жидкая (эмаль ПФ-115)", "жидкая (грунт + эмаль)", "не знаю"],
            "default": "жидкая (грунт + эмаль)",
            "impact_if_changed": "Порошковая быстрее, но дороже оборудование"
        })
    questions.append({
        "id": "Q2",
        "topic": "термообработка",
        "question": f"Требуется ли термообработка для {material}?",
        "options": ["да, закалка+отпуск", "да, только отпуск", "нет, не требуется", "не знаю"],
        "default": "нет, не требуется",
        "impact_if_changed": "Термообработка добавит 1.5-3 ч"
    })

    return {
        "summary": {
            "total_operations": len(operations),
            "total_hours": round(total_hours, 2),
            "prep_hours": 0.2,
            "complexity": "средняя" if mass > 5 else "низкая",
            "closest_analog": "ЛМША.301314.020" if is_steel else None
        },
        "route": route,
        "operations": operations,
        "reasoning": reasoning,
        "warnings": warnings,
        "questions": questions
    }


@app.post("/api/approve")
async def approve(req: GenerateRequest):
    """Approve draft"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE drafts SET status = 'approved', updated_at = ? WHERE detail_id = ?",
        (datetime.now().isoformat(), req.detail_id)
    )
    conn.commit()
    conn.close()
    add_history(req.detail_id, "approved")
    return {"status": "approved"}


@app.post("/api/send-to-1c")
async def send_to_1c(req: GenerateRequest):
    """MOCK: write RS to 1C:ERP"""
    add_history(req.detail_id, "sent_to_1c_mock", {
        "message": "РС записана в 1С:ERP (mock)",
        "timestamp": datetime.now().isoformat()
    })
    return {"status": "sent", "message": "РС записана в 1С:ERP (mock)"}


@app.post("/api/export/excel")
async def export_excel(detail_id: str = Form(...)):
    """Export to Excel"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    detail_obj = next((d for d in MOCK_DETAILS if d["id"] == detail_id), None)
    draft_data = get_draft(detail_id)
    if not detail_obj or not draft_data:
        raise HTTPException(400, "No draft to export")

    draft = draft_data["output"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Техкарта"

    # Header
    ws["A1"] = f"Техкарта: {detail_obj['designation']} — {detail_obj['name']}"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:F1")
    ws["A1"].alignment = Alignment(horizontal="center")

    # Properties
    ws["A3"] = "Материал"
    ws["B3"] = detail_obj.get("material", "")
    ws["A4"] = "Масса, кг"
    ws["B4"] = detail_obj.get("mass_kg", "")
    ws["A5"] = "Шасси"
    ws["B5"] = detail_obj.get("chassis", "")
    ws["A6"] = "Модель"
    ws["B6"] = detail_obj.get("model", "")
    for r in range(3, 7):
        ws[f"A{r}"].font = Font(bold=True)

    # Operations table
    ws["A8"] = "№"
    ws["B8"] = "Операция"
    ws["C8"] = "Оборудование"
    ws["D8"] = "Время, ч"
    ws["E8"] = "Источник"
    ws["F8"] = "Уверенность"
    for col in "ABCDEF":
        cell = ws[f"{col}8"]
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")

    for i, op in enumerate(draft.get("operations", []), 1):
        row = 8 + i
        ws.cell(row=row, column=1, value=i)
        ws.cell(row=row, column=2, value=op.get("name", ""))
        ws.cell(row=row, column=3, value=op.get("equipment", "") or "—")
        ws.cell(row=row, column=4, value=op.get("duration_hours", 0))
        ws.cell(row=row, column=5, value=op.get("duration_source", ""))
        ws.cell(row=row, column=6, value=f"{op.get('confidence', 0)}%")

    # Adjust column widths
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 25
    ws.column_dimensions["D"].width = 12
    ws.column_dimensions["E"].width = 25
    ws.column_dimensions["F"].width = 15

    # Save to buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    # Transliterate filename for ASCII-safe Content-Disposition
    import re
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    raw_name = f"{detail_obj['designation']}"
    ascii_name = ''.join(translit_map.get(c.lower(), c) for c in raw_name)
    ascii_name = re.sub(r'[^a-zA-Z0-9._-]', '_', ascii_name)

    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{ascii_name}.xlsx"'}
    )


@app.post("/api/export/pdf")
async def export_pdf(detail_id: str = Form(...)):
    """Export reasoning to PDF (for management)"""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    detail_obj = next((d for d in MOCK_DETAILS if d["id"] == detail_id), None)
    draft_data = get_draft(detail_id)
    if not detail_obj or not draft_data:
        raise HTTPException(400, "No draft to export")

    draft = draft_data["output"]
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Try to register a unicode font
    try:
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont("Helvetica"))
        font = "Helvetica"
    except Exception:
        font = "Helvetica"

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, height - 2*cm, f"Обоснование ТК")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2*cm, height - 3*cm, f"{detail_obj['designation']} — {detail_obj['name']}")

    # Properties
    c.setFont("Helvetica-Bold", 11)
    y = height - 4.5*cm
    c.drawString(2*cm, y, "Характеристики детали:")
    c.setFont("Helvetica", 10)
    y -= 0.6*cm
    c.drawString(2*cm, y, f"Материал: {detail_obj.get('material', '')}")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Масса: {detail_obj.get('mass_kg', '')} кг")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Шасси: {detail_obj.get('chassis', '')}")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Модель: {detail_obj.get('model', '')}")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Покрытие: {detail_obj.get('surface_treatment', '')}")

    # Summary
    y -= 1*cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, y, "Сводка")
    c.setFont("Helvetica", 10)
    y -= 0.6*cm
    summary = draft.get("summary", {})
    c.drawString(2*cm, y, f"Операций: {summary.get('total_operations', 0)}")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Общее время: {summary.get('total_hours', 0)} ч")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Подг. время: {summary.get('prep_hours', 0)} ч")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Сложность: {summary.get('complexity', '')}")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Ближайший аналог: {summary.get('closest_analog', '') or 'нет'}")

    # Reasoning
    y -= 1*cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, y, "Обоснование решений")
    c.setFont("Helvetica", 9)
    y -= 0.6*cm
    reasoning = draft.get("reasoning", {})
    for key, value in reasoning.items():
        c.setFont("Helvetica-Bold", 10)
        c.drawString(2*cm, y, f"{key}:")
        y -= 0.5*cm
        c.setFont("Helvetica", 9)
        # Wrap text
        words = str(value).split()
        line = ""
        for word in words:
            if len(line) + len(word) + 1 < 95:
                line += " " + word if line else word
            else:
                c.drawString(2*cm, y, line)
                y -= 0.45*cm
                line = word
        if line:
            c.drawString(2*cm, y, line)
            y -= 0.5*cm
        y -= 0.2*cm

    c.save()
    buffer.seek(0)

    # Transliterate filename for ASCII-safe Content-Disposition
    import re
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    raw_name = f"{detail_obj['designation']}_reasoning"
    ascii_name = ''.join(translit_map.get(c.lower(), c) for c in raw_name)
    ascii_name = re.sub(r'[^a-zA-Z0-9._-]', '_', ascii_name)

    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{ascii_name}.pdf"'}
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "demo_mode": DEMO_MODE,
        "model": LLM_MODEL,
        "api_url": LLM_API_URL if not DEMO_MODE else None,
        "details_count": len(MOCK_DETAILS)
    }


@app.get("/history/{detail_id}")
async def history(detail_id: str):
    """Get history for a detail (for debug)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT id, action, timestamp, details FROM history WHERE detail_id = ? ORDER BY id DESC LIMIT 50",
        (detail_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return {"history": [
        {"id": r[0], "action": r[1], "timestamp": r[2], "details": json.loads(r[3] or "{}")}
        for r in rows
    ]}


if __name__ == "__main__":
    init_db()
    log.info(f"Starting БИТ.Технолог (demo_mode={DEMO_MODE})")
    if DEMO_MODE:
        log.info("⚠️  DEMO MODE: no real LLM calls. Mock responses based on heuristics.")
    else:
        log.info(f"✓ LLM: {LLM_MODEL} via {LLM_API_URL}")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
