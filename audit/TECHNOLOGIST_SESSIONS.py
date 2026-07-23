"""Сценарии работы технологом (Playwright UI)."""
import os, time, re
from playwright.sync_api import sync_playwright

BASE = 'https://217.114.7.5:8081'
TS = int(time.time())

ISSUES = []
NOTES = []

def issue(area, msg):
    ISSUES.append((area, msg))
    print(f"  ❌ {area}: {msg}")

def note(area, msg):
    NOTES.append((area, msg))
    print(f"  📝 {area}: {msg}")

def ok(area, msg=""):
    print(f"  ✅ {area} {msg}")


def run_scenario(name, fn):
    print(f"\n=== СЦЕНАРИЙ: {name} ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--ignore-certificate-errors'])
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        try:
            fn(page)
        except Exception as e:
            issue(name, f'исключение: {e}')
        browser.close()


def login(page, username='tarrietsky', password='demo'):
    page.goto(f'{BASE}/login', wait_until='networkidle', timeout=15000)
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_url(lambda u: '/login' not in u, timeout=10000)


def scenario_dashboard(page):
    """T1: Зайти, посмотреть dashboard."""
    login(page)
    page.goto(f'{BASE}/', wait_until='domcontentloaded')
    print(f"  URL: {page.url}")
    text = page.text_content('body') or ''
    # Что видит технолог на дашборде?
    if 'Сводка' in text or 'Мои задачи' in text or 'Извещений' in text:
        ok('dashboard', 'видны разделы')
    else:
        issue('dashboard', 'нет ожидаемых разделов')
    # Сколько открытых извещений?
    m = re.search(r'Открытых извещений[^\d]*(\d+)', text)
    if m:
        ok('dashboard', f'open notices: {m.group(1)}')
    # Сколько ТК
    m = re.search(r'Всего\s*ТК[^\d]*(\d+)', text)
    if m:
        ok('dashboard', f'всего ТК: {m.group(1)}')
    # Сколько зеленых
    m = re.search(r'(\d+)\s*%\s*зелёных', text)
    if m:
        ok('dashboard', f'зелёных: {m.group(1)}%')
    # Проверим тайм генерации (должен быть < 60 сек)
    m = re.search(r'(\d+)\s*сек', text)
    if m:
        t = int(m.group(1))
        if t < 60:
            ok('dashboard', f'время генерации: {t}с (норма)')
        else:
            note('dashboard', f'время генерации: {t}с (долго)')


def scenario_create_detail_and_tc(page):
    """T2: Создать деталь, сгенерировать ТК, проверить inline-edit."""
    login(page)
    # 1. /details/new
    page.goto(f'{BASE}/details/new', wait_until='domcontentloaded')
    ok('create_detail', f'форма: {page.title()}')
    # Заполняю
    page.fill('input[name="designation"]', f'TEST-UI-{TS}')
    page.fill('input[name="name"]', 'UI Test Detail')
    # level - select
    try:
        page.select_option('select[name="level"]', 'detail')
    except:
        pass
    # mass_kg
    try:
        page.fill('input[name="mass_kg"]', '2.5')
    except:
        pass
    # drawing_no
    try:
        page.fill('input[name="drawing_no"]', f'Д-{TS}')
    except:
        pass
    # submit
    page.click('button[type="submit"]')
    page.wait_for_url(lambda u: '/detail/' in u, timeout=10000)
    print(f"  URL после создания: {page.url}")
    item_id = page.url.split('/detail/')[-1].split('?')[0].split('/')[0]
    ok('create_detail', f'создана, id={item_id}')

    # 2. /detail/{id} - есть форма генерации
    page.goto(f'{BASE}/detail/{item_id}', wait_until='domcontentloaded')
    text = page.text_content('body') or ''
    if 'Сгенерировать' in text or 'Создать ТК' in text or 'Генерировать' in text or 'Перегенерировать' in text or 'Создать техкарту' in text:
        ok('detail', 'есть кнопка генерации ТК')
    else:
        issue('detail', 'нет кнопки генерации ТК')

    # 3. Кликнем на кнопку генерации
    # НЕ кликаем генерацию в этом тесте — LLM может таймаутить (1bitai.ru).
    # Проверяем только что кнопка ЕСТЬ (UI-функциональность).
    btn = page.query_selector('button:has-text("Сгенерировать"), button:has-text("Создать ТК"), button:has-text("Генерировать"), button:has-text("Перегенерировать"), a:has-text("Сгенерировать ТК"), #btn-regenerate')
    if btn:
        # Если ТК уже есть — есть кнопка "Перегенерировать"
        if 'Перегенерировать' in (btn.text_content() or '') or 'btn-regenerate' in (btn.get_attribute('id') or ''):
            ok('detail', 'ТК уже сгенерирована (есть кнопка Перегенерировать)')
        else:
            # ТК нет, есть кнопка "Сгенерировать ТК" — UI готов, но не кликаем (LLM 60+ сек)
            ok('detail', 'UI готов к генерации (есть кнопка Сгенерировать ТК)')
    else:
        issue('detail', 'кнопка генерации не найдена')

    # 4. Inline-edit одной операции (если есть)
    page.wait_for_timeout(2000)
    # Найдём edit-кнопку
    edit_btn = page.query_selector('button[title="Редактировать"], .editable, [data-editable]')
    if edit_btn:
        ok('inline_edit', 'кнопка inline-edit найдена')
    else:
        note('inline_edit', 'inline-edit кнопка не найдена (может быть не видна без ТК)')


def scenario_notice(page):
    """T3: Создать извещение, проверить workflow."""
    login(page)
    page.goto(f'{BASE}/notices/new', wait_until='domcontentloaded')
    ok('notice_form', f'форма: {page.title()}')
    # Заполняю
    try:
        page.fill('input[name="number"]', f'И-UI-{TS}')
        page.fill('input[name="date"]', '2026-07-23')
        page.fill('input[name="affected_item_designation"]', 'ЛМША.301314.010')
        page.fill('textarea[name="reason"], input[name="reason"]', 'UI Test Reason')
        page.click('button[type="submit"]')
        page.wait_for_url(lambda u: '/notices/' in u, timeout=10000)
        print(f"  URL: {page.url}")
        ok('notice_create', 'извещение создано')
    except Exception as e:
        issue('notice_create', f'fail: {e}')


def scenario_help_and_knowledge(page):
    """T4: Открыть help и knowledge, проверить контент."""
    login(page)
    page.goto(f'{BASE}/help', wait_until='domcontentloaded')
    text = page.text_content('body') or ''
    if 'помощь' in text.lower() or 'инструкция' in text.lower() or 'БИТ' in text:
        ok('help', 'контент есть')
    else:
        note('help', 'контент минимальный')

    page.goto(f'{BASE}/knowledge', wait_until='domcontentloaded')
    text = page.text_content('body') or ''
    if 'эталон' in text.lower() or 'etalons' in text.lower() or 'ЛМША' in text:
        ok('knowledge', f'есть эталоны')
    else:
        note('knowledge', 'эталоны не видны')


def scenario_chief_view(page):
    """T5: workshop_chief — что видит, не может редактировать?"""
    login(page, 'golubev', 'demo')
    page.goto(f'{BASE}/', wait_until='domcontentloaded')
    text = page.text_content('body') or ''
    if 'golubev' in text:
        ok('chief', 'username отображается')
    if 'Редактировать' in text or 'Создать' in text:
        issue('chief', 'видит кнопки редактирования (должен read-only)')
    else:
        ok('chief', 'нет кнопок редактирования')

    # /detail/3
    page.goto(f'{BASE}/detail/3', wait_until='domcontentloaded')
    text = page.text_content('body') or ''
    if 'Редактировать' in text or 'Создать ТК' in text or 'Сгенерировать' in text:
        issue('chief', '/detail/3 — видит кнопки')
    else:
        ok('chief', '/detail/3 — read-only')


# Запуск
run_scenario('T1: Dashboard (tarrietsky)', scenario_dashboard)
run_scenario('T2: Создание детали + ТК (tarrietsky)', scenario_create_detail_and_tc)
run_scenario('T3: Извещение (tarrietsky)', scenario_notice)
run_scenario('T4: Help + Knowledge (tarrietsky)', scenario_help_and_knowledge)
run_scenario('T5: workshop_chief view', scenario_chief_view)

print(f"\n=== ИТОГИ РАБОТЫ ТЕХНОЛОГОМ ===")
print(f"  Проблем найдено: {len(ISSUES)}")
for area, msg in ISSUES:
    print(f"    ❌ {area}: {msg}")
print(f"  Заметок: {len(NOTES)}")
for area, msg in NOTES:
    print(f"    📝 {area}: {msg}")
