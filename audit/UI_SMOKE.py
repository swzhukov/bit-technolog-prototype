"""UI Smoke test через Playwright. Базовые проверки UI."""
import os, re
from playwright.sync_api import sync_playwright

BASE = 'https://217.114.7.5:8081'

USERS = ['techadmin', 'vorobyev', 'tarrietsky', 'golubev']

ISSUES = []

def check(name, cond, msg=""):
    sym = '✅' if cond else '❌'
    print(f"  {sym} {name} {msg}")
    if not cond:
        ISSUES.append((name, msg))

def login(page, username):
    page.goto(f'{BASE}/login', wait_until='networkidle', timeout=15000)
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', 'demo')
    page.click('button[type="submit"]')
    page.wait_for_url(lambda u: '/login' not in u, timeout=10000)

def get_status(page, path):
    """GET path, return HTTP status."""
    resp = page.goto(f'{BASE}{path}', wait_until='domcontentloaded', timeout=10000)
    return resp.status if resp else -1

def smoke(username):
    print(f"\n=== {username} ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--ignore-certificate-errors'])
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()

        # Login
        try:
            login(page, username)
            check(f'{username}: login OK', page.url.rstrip('/') == BASE)
        except Exception as e:
            check(f'{username}: login', False, f'fail: {e}')
            browser.close()
            return

        # Dashboard
        status = get_status(page, '/')
        check(f'{username}: / 200', status == 200, f'got {status}')
        text = page.text_content('body') or ''
        check(f'{username}: / нет ФИО', 'Баранов А.Н.' not in text and 'Воробьев И.Ф.' not in text and 'Голубев П.В.' not in text and 'Тарлецкий А.С.' not in text)
        check(f'{username}: / есть username', username in text)
        emoji = re.findall(r'[😀-🙏✅❌⏭🔍⚙️📦🏭⚡🟢🔴🟡]', text)
        check(f'{username}: / нет emoji', not emoji, f'найдены {emoji[:3]}' if emoji else '')

        # Products
        status = get_status(page, '/products')
        check(f'{username}: /products 200', status == 200, f'got {status}')
        text = page.text_content('body') or ''
        check(f'{username}: /products нет ФИО', 'Баранов' not in text and 'Воробьев' not in text)

        # Detail
        status = get_status(page, '/detail/3')
        check(f'{username}: /detail/3 200', status == 200, f'got {status}')

        # Knowledge
        status = get_status(page, '/knowledge')
        text = page.text_content('body') or ''
        check(f'{username}: /knowledge 200', status == 200, f'got {status}')
        check(f'{username}: /knowledge нет ФИО', 'Баранов' not in text and 'Воробьев' not in text)

        # Notices
        status = get_status(page, '/notices')
        text = page.text_content('body') or ''
        check(f'{username}: /notices 200', status == 200, f'got {status}')
        check(f'{username}: /notices нет ФИО', 'Баранов' not in text and 'Воробьев' not in text and 'Тарлецкий' not in text and 'Голубев' not in text)

        # Help
        status = get_status(page, '/help')
        check(f'{username}: /help 200', status == 200, f'got {status}')

        # /rs
        status = get_status(page, '/rs')
        check(f'{username}: /rs 200', status == 200, f'got {status}')

        # RBAC checks
        if username != 'golubev':
            status = get_status(page, '/details/new')
            check(f'{username}: /details/new 200', status == 200, f'got {status}')
        else:
            status = get_status(page, '/details/new')
            check(f'{username}: /details/new → 403', status == 403, f'got {status}')

        if username == 'techadmin':
            status = get_status(page, '/llm-admin')
            check(f'{username}: /llm-admin 200', status == 200, f'got {status}')
        else:
            status = get_status(page, '/llm-admin')
            check(f'{username}: /llm-admin → 403', status == 403, f'got {status}')

        if username in ('techadmin', 'vorobyev'):
            status = get_status(page, '/metrics')
            check(f'{username}: /metrics 200', status == 200, f'got {status}')
        else:
            status = get_status(page, '/metrics')
            check(f'{username}: /metrics → 403', status == 403, f'got {status}')

        if username in ('techadmin', 'vorobyev'):
            status = get_status(page, '/profiles')
            check(f'{username}: /profiles 200', status == 200, f'got {status}')
        else:
            status = get_status(page, '/profiles')
            check(f'{username}: /profiles → 403', status == 403, f'got {status}')

        if username == 'techadmin':
            status = get_status(page, '/settings')
            check(f'{username}: /settings 200', status == 200, f'got {status}')

        if username != 'golubev':
            status = get_status(page, '/notices/new')
            check(f'{username}: /notices/new 200', status == 200, f'got {status}')
        else:
            status = get_status(page, '/notices/new')
            check(f'{username}: /notices/new → 403', status == 403, f'got {status}')

        browser.close()


for u in USERS:
    smoke(u)

print(f"\n=== ИТОГО ===")
if ISSUES:
    print(f"❌ {len(ISSUES)} замечаний:")
    for name, msg in ISSUES:
        print(f"  {name} {msg}")
else:
    print("✅ 0 замечаний")
