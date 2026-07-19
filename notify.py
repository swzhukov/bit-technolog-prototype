"""
notify.py — модуль уведомлений (v0.4.9, F15).
Выделено из app.py.
Содержит: send_email, send_telegram, notify_workflow.
Credentials читаются динамически через get_setting() с fallback на .env.
"""
import os
import logging

log = logging.getLogger("bit-technolog")

# Defaults (если .env не задан, но в БД тоже нет)
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
NOTIFY_EMAIL_FROM = os.getenv("NOTIFY_EMAIL_FROM", "bit-technolog@tehnocom.local")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send_email(to: str, subject: str, body: str) -> bool:
    """Отправка email. Если SMTP не настроен — dry-run.
    Credentials из БД (get_setting), fallback на .env."""
    from settings import get_setting
    host = get_setting("SMTP_HOST", SMTP_HOST)
    port = int(get_setting("SMTP_PORT", str(SMTP_PORT)) or 587)
    user = get_setting("SMTP_USER", SMTP_USER)
    pwd = get_setting("SMTP_PASS", SMTP_PASS)
    frm = get_setting("NOTIFY_EMAIL_FROM", NOTIFY_EMAIL_FROM)
    if not host or not user:
        log.info(f"[DRY-RUN EMAIL] to={to} subject={subject}")
        return True
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = frm
        msg["To"] = to
        with smtplib.SMTP(host, port) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)
        return True
    except Exception as e:
        log.error(f"email send failed: {e}")
        return False


def send_telegram(text: str) -> bool:
    """Отправка в Telegram. Если токен не настроен — dry-run."""
    from settings import get_setting
    token = get_setting("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    chat_id = get_setting("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)
    if not token or not chat_id:
        log.info(f"[DRY-RUN TELEGRAM] {text[:100]}")
        return True
    try:
        import urllib.request
        import urllib.parse
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        log.error(f"telegram send failed: {e}")
        return False


def notify_workflow(detail_id: str, event: str, assignee: str = "", extra: str = ""):
    """Уведомление о workflow-событии (email + telegram)."""
    subject = f"БИТ.Технолог: {event} по {detail_id}"
    body = f"Деталь: {detail_id}\nСобытие: {event}\n{('Исполнитель: ' + assignee) if assignee else ''}\n{extra}"
    if assignee and "@" in assignee:
        send_email(assignee, subject, body)
    send_telegram(f"🔔 {subject}\n{body[:200]}")
