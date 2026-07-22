"""
E2E runner — прогон сценариев под 4 ролями.
См. docs/e2e/SCENARIOS.md

Запуск:
  python3 test/e2e_runner.py [--url http://217.114.7.5:8081] [--roles all] [--screenshots]

Возвращает 0 если всё OK, 1 если есть падения.
"""
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from playwright.async_api import async_playwright, Page, BrowserContext, TimeoutError as PWTimeout

URL = "http://217.114.7.5:8081"
ROLES = [
    ("techadmin", "admin"),
    ("vorobyev", "main_technologist"),
    ("tarrietsky", "technologist"),
    ("golubev", "workshop_chief"),
]

@dataclass
class Step:
    name: str
    action: str
    expect: str
    ok: bool = False
    err: str = ""

@dataclass
class Scenario:
    code: str
    title: str
    roles: List[str]  # какие роли должны пройти
    steps: List[Step] = field(default_factory=list)

@dataclass
class Report:
    scenarios: List[Scenario]
    started_at: float
    url: str
    total: int = 0
    failed: int = 0
    duration_sec: float = 0

    def add_result(self, code: str, role: str, ok: bool, err: str = ""):
        for sc in self.scenarios:
            if sc.code == code:
                step = Step(name=f"[{role}] {sc.code}", action="", expect="", ok=ok, err=err)
                sc.steps.append(step)
                if not ok:
                    self.failed += 1
                self.total += 1
                return

async def login(page: Page, username: str, password: str = "demo"):
    await page.goto(f"{URL}/login")
    await page.fill('input[name="username"]', username)
    await page.fill('input[name="password"]', password)
    await page.click('button[type="submit"], input[type="submit"]')
    await page.wait_for_load_state("networkidle")

async def logout(context: BrowserContext):
    await context.clear_cookies()

async def get_status(page: Page, path: str) -> int:
    """GET page → return HTTP status."""
    try:
        resp = await page.goto(f"{URL}{path}", wait_until="domcontentloaded", timeout=10000)
        return resp.status if resp else 0
    except Exception as e:
        return 0

async def get_text(page: Page, selector: str) -> str:
    try:
        el = await page.query_selector(selector)
        if el:
            return (await el.text_content() or "").strip()
    except Exception:
        pass
    return ""

async def has_text(page: Page, text: str) -> bool:
    body = await page.content()
    return text in body

async def run_scenario_s01_login(page: Page, role: str, report: Report):
    """S01: Логин / Logout"""
    try:
        # 1. / без cookie → redirect to /login
        await page.context.clear_cookies()
        await page.goto(f"{URL}/")
        await page.wait_for_load_state("domcontentloaded")
        if "/login" not in page.url:
            report.add_result("S01", role, False, f"no redirect to /login, got {page.url}")
            return
        # 2. wrong password
        await page.fill('input[name="username"]', "wrong")
        await page.fill('input[name="password"]', "wrong")
        await page.click('button[type="submit"], input[type="submit"]')
        await page.wait_for_load_state("domcontentloaded")
        body = await page.content()
        if "Invalid" not in body and "неверн" not in body.lower() and "401" not in body:
            report.add_result("S01", role, False, "wrong password not rejected")
            return
        # 3. correct login
        await login(page, role)
        if "/login" in page.url:
            report.add_result("S01", role, False, "login redirect failed")
            return
        report.add_result("S01", role, True)
    except Exception as e:
        report.add_result("S01", role, False, str(e)[:200])

async def run_scenario_s02_products(page: Page, role: str, report: Report):
    """S02: Список изделий /products"""
    try:
        s = await get_status(page, "/products")
        if s != 200:
            report.add_result("S02", role, False, f"HTTP {s}")
            return
        body = await page.content()
        # No techno-bs
        if "Концепция универсальной" in body:
            report.add_result("S02", role, False, "Концепция универсальной still present")
            return
        # Should see items
        if "301314" not in body and "301712" not in body:
            report.add_result("S02", role, False, "no items rendered")
            return
        # Filter "Покупное"
        await page.goto(f"{URL}/products?level=purchased")
        await page.wait_for_load_state("domcontentloaded")
        report.add_result("S02", role, True)
    except Exception as e:
        report.add_result("S02", role, False, str(e)[:200])

async def run_scenario_s03_detail(page: Page, role: str, report: Report):
    """S03: Карточка изделия /detail/{id}"""
    try:
        s = await get_status(page, "/detail/3")
        if s != 200:
            report.add_result("S03", role, False, f"HTTP {s}")
            return
        body = await page.content()
        if "Втулка" not in body:
            report.add_result("S03", role, False, "item name not found")
            return
        if "editable" not in body:
            report.add_result("S03", role, False, "no .editable elements")
            return
        report.add_result("S03", role, True)
    except Exception as e:
        report.add_result("S03", role, False, str(e)[:200])

async def run_scenario_s04_generate(page: Page, role: str, report: Report):
    """S04: Генерация ТК (для make item) + 400 для buy"""
    try:
        # 1. make item — POST should work
        resp = await page.request.post(f"{URL}/items/3/generate", form_data={"input": ""}, max_redirects=0)
        if resp.status not in (200, 303, 302):
            report.add_result("S04", role, False, f"make item POST → {resp.status}")
            return
        # 2. buy item — POST should be 400
        resp2 = await page.request.post(f"{URL}/items/8/generate", form_data={"input": ""}, max_redirects=0)
        if resp2.status != 400:
            report.add_result("S04", role, False, f"buy item POST → {resp2.status}, expected 400")
            return
        report.add_result("S04", role, True)
    except Exception as e:
        report.add_result("S04", role, False, str(e)[:200])

async def run_scenario_s05_inline_edit(page: Page, role: str, report: Report):
    """S05: Inline-edit операции (POST /api/operations/{id}/update)"""
    try:
        # Get a real op_id from /detail/3
        await page.goto(f"{URL}/detail/3")
        await page.wait_for_load_state("domcontentloaded")
        op_id_str = await page.evaluate("""
() => {
    const span = document.querySelector('span.editable[data-field="time_per_unit_min"]');
    return span ? span.getAttribute('data-op') : null;
}
""")
        if not op_id_str:
            report.add_result("S05", role, False, "no .editable found")
            return
        op_id = int(op_id_str)
        # POST
        resp = await page.request.post(
            f"{URL}/api/operations/{op_id}/update",
            form_data={"field": "time_per_unit_min", "value": "99.9"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        if resp.status != 200:
            t = await resp.text()
            report.add_result("S05", role, False, f"POST → {resp.status}: {t[:200]}")
            return
        # Reset back
        await page.request.post(
            f"{URL}/api/operations/{op_id}/update",
            form_data={"field": "time_per_unit_min", "value": "10.0"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        report.add_result("S05", role, True)
    except Exception as e:
        report.add_result("S05", role, False, str(e)[:200])

async def run_scenario_s06_dashboard_learning(page: Page, role: str, report: Report):
    """S06: Дашборд с петлёй обратной связи (Q-001)"""
    try:
        s = await get_status(page, "/")
        if s != 200:
            report.add_result("S06", role, False, f"HTTP {s}")
            return
        body = await page.content()
        if "Петля обратной связи" not in body:
            report.add_result("S06", role, False, "no learning block")
            return
        report.add_result("S06", role, True)
    except Exception as e:
        report.add_result("S06", role, False, str(e)[:200])

async def run_scenario_s07_notices(page: Page, role: str, report: Report):
    """S07: Извещения /notices"""
    try:
        s = await get_status(page, "/notices")
        if s != 200:
            report.add_result("S07", role, False, f"HTTP {s}")
            return
        s2 = await get_status(page, "/notices/new")
        if s2 != 200:
            report.add_result("S07", role, False, f"/notices/new HTTP {s2}")
            return
        report.add_result("S07", role, True)
    except Exception as e:
        report.add_result("S07", role, False, str(e)[:200])

async def run_scenario_s08_profiles(page: Page, role: str, report: Report):
    """S08: Шаблоны маршрутов /profiles (бывший 'Профили выхода РС')"""
    try:
        s = await get_status(page, "/profiles")
        if s != 200:
            report.add_result("S08", role, False, f"HTTP {s}")
            return
        body = await page.content()
        if "Профили выхода РС" in body:
            report.add_result("S08", role, False, "old 'Профили выхода РС' still present")
            return
        if "Шаблоны" not in body and "маршрут" not in body:
            report.add_result("S08", role, False, "no 'Шаблоны' / 'маршрут' in profile page")
            return
        report.add_result("S08", role, True)
    except Exception as e:
        report.add_result("S08", role, False, str(e)[:200])

async def run_scenario_s09_llm_admin(page: Page, role: str, report: Report):
    """S09: LLM-админка — только admin"""
    try:
        s = await get_status(page, "/llm-admin")
        if role == "admin":
            if s != 200:
                report.add_result("S09", role, False, f"admin: HTTP {s}")
                return
        else:
            # 403 или redirect
            if s == 200:
                body = await page.content()
                if "403" not in body and "доступ" not in body.lower() and "denied" not in body.lower():
                    report.add_result("S09", role, False, f"non-admin got 200 without deny")
                    return
        report.add_result("S09", role, True)
    except Exception as e:
        report.add_result("S09", role, False, str(e)[:200])

async def run_scenario_s10_settings(page: Page, role: str, report: Report):
    """S10: Настройки /settings"""
    try:
        s = await get_status(page, "/settings")
        if role == "admin":
            if s != 200:
                report.add_result("S10", role, False, f"admin: HTTP {s}")
                return
        else:
            if s == 200:
                body = await page.content()
                if "403" not in body and "доступ" not in body.lower():
                    report.add_result("S10", role, False, f"non-admin got 200 without deny")
                    return
        report.add_result("S10", role, True)
    except Exception as e:
        report.add_result("S10", role, False, str(e)[:200])

async def run_scenario_s11_metrics(page: Page, role: str, report: Report):
    """S11: Метрики /metrics"""
    try:
        s = await get_status(page, "/metrics")
        if s != 200:
            report.add_result("S11", role, False, f"HTTP {s}")
            return
        report.add_result("S11", role, True)
    except Exception as e:
        report.add_result("S11", role, False, str(e)[:200])

async def run_scenario_s12_help(page: Page, role: str, report: Report):
    """S12: Помощь /help"""
    try:
        s = await get_status(page, "/help")
        if s != 200:
            report.add_result("S12", role, False, f"HTTP {s}")
            return
        report.add_result("S12", role, True)
    except Exception as e:
        report.add_result("S12", role, False, str(e)[:200])

async def run_scenario_s13_knowledge(page: Page, role: str, report: Report):
    """S13: База знаний /knowledge"""
    try:
        s = await get_status(page, "/knowledge")
        if s != 200:
            report.add_result("S13", role, False, f"HTTP {s}")
            return
        report.add_result("S13", role, True)
    except Exception as e:
        report.add_result("S13", role, False, str(e)[:200])

async def run_scenario_s14_details_new(page: Page, role: str, report: Report):
    """S14: /details/new (M36-fix2) — не должен быть 404"""
    try:
        s = await get_status(page, "/details/new")
        if s == 404:
            report.add_result("S14", role, False, "HTTP 404")
            return
        if s != 200:
            report.add_result("S14", role, False, f"HTTP {s}")
            return
        report.add_result("S14", role, True)
    except Exception as e:
        report.add_result("S14", role, False, str(e)[:200])

SCENARIOS = [
    ("S01", "Логин/Logout", ["admin", "main_technologist", "technologist", "workshop_chief"]),
    ("S02", "Список изделий /products", ["admin", "main_technologist", "technologist", "workshop_chief"]),
    ("S03", "Карточка изделия /detail/{id}", ["admin", "main_technologist", "technologist", "workshop_chief"]),
    ("S04", "Генерация ТК + 400 для покупного", ["admin", "main_technologist", "technologist"]),
    ("S05", "Inline-edit операции", ["admin", "main_technologist", "technologist"]),
    ("S06", "Дашборд с петлёй обратной связи", ["admin", "main_technologist", "technologist", "workshop_chief"]),
    ("S07", "Извещения /notices", ["admin", "main_technologist", "technologist"]),
    ("S08", "Шаблоны маршрутов /profiles", ["admin", "main_technologist"]),
    ("S09", "LLM-админка (admin only)", ["admin", "main_technologist", "technologist"]),
    ("S10", "Настройки /settings (admin)", ["admin", "main_technologist", "technologist"]),
    ("S11", "Метрики /metrics", ["admin", "main_technologist"]),
    ("S12", "Помощь /help", ["admin", "main_technologist", "technologist", "workshop_chief"]),
    ("S13", "База знаний /knowledge", ["admin", "main_technologist"]),
    ("S14", "/details/new (не 404)", ["admin", "main_technologist", "technologist"]),
]

HANDLERS = {
    "S01": run_scenario_s01_login,
    "S02": run_scenario_s02_products,
    "S03": run_scenario_s03_detail,
    "S04": run_scenario_s04_generate,
    "S05": run_scenario_s05_inline_edit,
    "S06": run_scenario_s06_dashboard_learning,
    "S07": run_scenario_s07_notices,
    "S08": run_scenario_s08_profiles,
    "S09": run_scenario_s09_llm_admin,
    "S10": run_scenario_s10_settings,
    "S11": run_scenario_s11_metrics,
    "S12": run_scenario_s12_help,
    "S13": run_scenario_s13_knowledge,
    "S14": run_scenario_s14_details_new,
}

async def run_role(p, role_name: str, username: str, report: Report, screenshots: bool):
    print(f"\n=== Роль: {username} ({role_name}) ===")
    browser = await p.chromium.launch(headless=True)
    try:
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        for code, _, roles in SCENARIOS:
            if role_name not in roles:
                continue
            print(f"  [{code}] ... ", end="", flush=True)
            before_failed = report.failed
            await HANDLERS[code](page, role_name, report)
            if screenshots and report.failed > before_failed:
                await page.screenshot(path=f"/tmp/audit_screens/e2e_{role_name}_{code}_FAIL.png", full_page=True)
            for sc in report.scenarios:
                if sc.code == code and sc.steps:
                    last = sc.steps[-1]
                    if last.ok:
                        print("OK")
                    else:
                        print(f"❌ {last.err[:100]}")
                        break
        await context.close()
    finally:
        await browser.close()

def render_report(report: Report) -> str:
    lines = [
        f"\n\n{'='*60}",
        f"E2E REPORT — {report.url}",
        f"{'='*60}\n",
    ]
    by_scenario = {}
    for sc in report.scenarios:
        by_scenario.setdefault(sc.code, []).extend(sc.steps)
    for code, title, _ in SCENARIOS:
        steps = by_scenario.get(code, [])
        if not steps:
            continue
        ok_count = sum(1 for s in steps if s.ok)
        total = len(steps)
        marker = "✅" if ok_count == total else "❌"
        lines.append(f"{marker} {code} {title}: {ok_count}/{total}")
        for s in steps:
            mark = "  ✓" if s.ok else "  ✗"
            err = f" — {s.err[:80]}" if s.err else ""
            lines.append(f"{mark} {s.name}{err}")
    lines.append(f"\n{'='*60}")
    lines.append(f"TOTAL: {report.total - report.failed}/{report.total} passed, {report.failed} failed")
    lines.append(f"Duration: {report.duration_sec:.1f}s")
    lines.append(f"{'='*60}\n")
    return "\n".join(lines)

async def main():
    url = URL
    screenshots = "--screenshots" in sys.argv
    report = Report(
        scenarios=[Scenario(c, t, r) for c, t, r in SCENARIOS],
        started_at=time.time(),
        url=url,
    )
    async with async_playwright() as p:
        for username, role_name in ROLES:
            await run_role(p, role_name, username, report, screenshots)
    report.duration_sec = time.time() - report.started_at
    text = render_report(report)
    print(text)
    Path("/tmp/e2e_report.md").write_text(text)
    Path("/tmp/e2e_report.json").write_text(json.dumps({
        "total": report.total,
        "failed": report.failed,
        "duration_sec": report.duration_sec,
        "scenarios": [
            {"code": c, "title": t, "roles": r, "results": [
                {"role": s.name.split("]")[0][1:], "ok": s.ok, "err": s.err}
                for s in [step for sc in report.scenarios if sc.code == c for step in sc.steps]
            ]}
            for c, t, r in SCENARIOS
        ]
    }, ensure_ascii=False, indent=2))
    return 0 if report.failed == 0 else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
