"""
Sprint 7 D2: OCR pipeline для чертежей.

PDF → PNG (через pdftoppm) → tesseract → text.
PNG/JPG → напрямую tesseract.
"""
import os
import subprocess
import logging
import tempfile
import time
from pathlib import Path
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Tesseract languages
TESSERACT_LANG = "rus"  # русский

# Resolution для PDF→PNG
PDF_DPI = 300


def _run_subprocess(cmd: list, timeout: int = 60) -> Tuple[int, str, str]:
    """Run subprocess, return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout after {timeout}s"
    except FileNotFoundError as e:
        return -1, "", f"command not found: {e}"


def pdf_to_png(pdf_path: str, output_dir: str, dpi: int = PDF_DPI) -> Optional[str]:
    """Конвертировать PDF в PNG (первая страница).
    
    Returns: path to PNG file or None if failed.
    """
    pdf_p = Path(pdf_path)
    if not pdf_p.exists():
        logger.error(f"pdf_to_png: file not found: {pdf_path}")
        return None
    
    # pdftoppm output format: {basename}-{page}.png
    output_template = os.path.join(output_dir, "page")
    cmd = [
        "pdftoppm",
        "-r", str(dpi),
        "-png",
        "-f", "1",  # first page only
        "-l", "1",  # last page = 1
        str(pdf_p),
        output_template,
    ]
    rc, stdout, stderr = _run_subprocess(cmd, timeout=30)
    if rc != 0:
        logger.error(f"pdftoppm failed: {stderr}")
        return None
    
    # Find first generated PNG
    png_files = sorted(Path(output_dir).glob("page-*.png"))
    if not png_files:
        logger.error(f"pdftoppm produced no PNGs in {output_dir}")
        return None
    return str(png_files[0])


def image_ocr(image_path: str, lang: str = TESSERACT_LANG, timeout: int = 60) -> Tuple[bool, str, str]:
    """OCR через tesseract.
    
    Returns: (success, text_or_error, "")
    """
    img_p = Path(image_path)
    if not img_p.exists():
        return False, "", f"file not found: {image_path}"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_base = os.path.join(tmpdir, "ocr")
        cmd = [
            "tesseract",
            str(img_p),
            output_base,
            "-l", lang,
            "--oem", "3",  # default LSTM
            "--psm", "6",  # assume uniform block of text
        ]
        rc, stdout, stderr = _run_subprocess(cmd, timeout=timeout)
        if rc != 0:
            return False, stderr or f"tesseract exit {rc}", ""
        
        # Read output file
        output_file = output_base + ".txt"
        if not os.path.exists(output_file):
            return False, "tesseract produced no output file", ""
        
        with open(output_file, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        return True, text, ""


def process_drawing(drawing_id: int, file_path: str, fmt: str) -> dict:
    """Полный OCR pipeline для чертежа.
    
    Returns: dict с полями:
    - success: bool
    - text: распознанный текст
    - error: ошибка (если была)
    - duration_ms: время
    """
    start = time.time()
    
    try:
        if fmt == "pdf":
            # Конвертировать PDF в PNG
            with tempfile.TemporaryDirectory() as tmpdir:
                png_path = pdf_to_png(file_path, tmpdir)
                if not png_path:
                    return {
                        "success": False,
                        "text": "",
                        "error": "PDF→PNG conversion failed",
                        "duration_ms": int((time.time() - start) * 1000),
                    }
                ok, text, error = image_ocr(png_path)
        else:
            # PNG/JPG — напрямую
            ok, text, error = image_ocr(file_path)
        
        duration_ms = int((time.time() - start) * 1000)
        if not ok:
            return {
                "success": False,
                "text": "",
                "error": error,
                "duration_ms": duration_ms,
            }
        return {
            "success": True,
            "text": text,
            "error": "",
            "duration_ms": duration_ms,
        }
    except Exception as e:
        logger.exception("OCR pipeline failed")
        return {
            "success": False,
            "text": "",
            "error": f"OCR failed: {e}",
            "duration_ms": int((time.time() - start) * 1000),
        }
