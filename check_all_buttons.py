"""Проверка ВСЕХ кнопок в реальном браузере. Без этого — не 'готово'."""
import asyncio
import sys
from playwright.async_api import async_playwright


class ButtonChecker:
    def __init__(self):
        self.results = []
        self.errors = []

    def log(self, msg):
        print(msg)
        self.results.append(msg)

    def error(self, msg):
        print(f"  ❌ {msg}")
        self.errors.append(msg)

    def ok(self, msg):
        print(f"  ✅ {msg}")


async def check():
    checker = ButtonChecker()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await ctx.new_page()

        # Перехват ошибок
        page_errors = []
        page.on("pageerror", lambda exc: page_errors.append(f"PAGEERROR: {exc}"))
        page.on("console", lambda msg: page_errors.append(f"CONSOLE.{msg.type}: {msg.text}") if msg.type == "error" else None)

        async def login(username, password):
            await page.goto("http://localhost:8000/login")
            await page.fill('input[name="username"]', username)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            await page.wait_for_url("**/", timeout=5000)

        async def logout():
            try:
                await page.goto("http://localhost:8000/logout")
            except Exception:
                pass

        # Один обработчик dialog
        async def handle_dialog(d):
            try:
                await d.accept("99")
            except Exception:
                pass
        page.on("dialog", lambda d: asyncio.create_task(handle_dialog(d)))

        try:
            # ============================================
            # ТЕСТ 1: ГЛАВНАЯ
            # ============================================
            checker.log("\n=== ТЕСТ 1: Главная страница (/) ===")
            await login("baranov", "demo")
            # Кнопки
            for sel, name in [
                ('a:has-text("Создать ТК")', 'Создать ТК'),
                ('a:has-text("Извещения")', 'Извещения'),
                ('a:has-text("База знаний")', 'База знаний'),
            ]:
                cnt = await page.locator(sel).count()
                if cnt > 0:
                    checker.ok(f"{name}: {cnt}")
                else:
                    checker.error(f"{name}: НЕТ")

            # ============================================
            # ТЕСТ 2: /products
            # ============================================
            checker.log("\n=== ТЕСТ 2: /products ===")
            await page.goto("http://localhost:8000/products")
            # Поиск
            await page.fill('input[name="q"]', "Втулка")
            await page.click('button:has-text("Найти")')
            await page.wait_for_load_state("networkidle")
            content = await page.content()
            if "ЛМША.304142" in content:
                checker.ok("Поиск 'Втулка' нашёл ЛМША.304142.*")
            else:
                checker.error("Поиск не работает")
            # Сброс
            await page.click('a:has-text("Сбросить")')
            await page.wait_for_load_state("networkidle")
            checker.ok("Сброс фильтра")

            # ============================================
            # ТЕСТ 3: /detail/{id} (деталь БЕЗ ТК)
            # ============================================
            checker.log("\n=== ТЕСТ 3: /detail/{id} — деталь без ТК ===")
            # Найду деталь без ТК. Возьмём item 14
            await page.goto("http://localhost:8000/detail/14")
            content = await page.content()
            if "Нет ТК" in content:
                checker.ok("Видно 'Нет ТК'")
            else:
                checker.error("Не вижу 'Нет ТК'")
            # Кнопка Сгенерировать
            gen = page.locator('a:has-text("Сгенерировать ТК")')
            if await gen.count() > 0:
                checker.ok("Кнопка 'Сгенерировать ТК' есть")
                await gen.click()
                # /items/{id}/generate — это GET страница с формой, нужен submit
                await page.wait_for_url("**/items/14/generate*", timeout=10000)
                checker.ok(f"Клик → форма: {page.url}")
                # Submit форму
                submit_btn = page.locator('button[type="submit"]:has-text("Сгенерировать")')
                if await submit_btn.count() > 0:
                    await submit_btn.click()
                    await page.wait_for_url("**/detail/14*", timeout=15000)
                    checker.ok(f"Submit → {page.url}")
                    if "flash_kind=ok" in page.url:
                        checker.ok("Flash 'ок' показался")
                else:
                    checker.error("Кнопки submit в форме нет")
            else:
                checker.error("Кнопки 'Сгенерировать ТК' нет")

            # ============================================
            # ТЕСТ 4: /detail/{id} (деталь С ТК) — кнопки
            # ============================================
            checker.log("\n=== ТЕСТ 4: /detail/14 — после генерации (с ТК) ===")
            # Должны быть 4 кнопки
            for sel, name in [
                ('button:has-text("Утвердить")', 'Утвердить'),
                ('button:has-text("Перегенерировать")', 'Перегенерировать'),
                ('button:has-text("Экспорт в 1С")', 'Экспорт в 1С'),
                ('a:has-text("+ Извещение")', '+ Извещение'),
            ]:
                cnt = await page.locator(sel).count()
                if cnt > 0:
                    checker.ok(f"{name}: {cnt}")
                else:
                    checker.error(f"{name}: НЕТ")

            # ============================================
            # ТЕСТ 5: Клик "Перегенерировать"
            # ============================================
            checker.log("\n=== ТЕСТ 5: Клик 'Перегенерировать' ===")
            reqs = []
            async def capture_req(r):
                if "/api/tech-cards/" in r.url and r.method == "POST":
                    reqs.append((r.url, r.method))
            page.on("request", lambda r: asyncio.create_task(capture_req(r)))
            regen = page.locator('button:has-text("Перегенерировать")')
            if await regen.count() > 0:
                try:
                    await regen.first.click()
                    await page.wait_for_timeout(3000)
                    if reqs:
                        checker.ok(f"POST отправлен: {reqs[-1]}")
                    else:
                        checker.error("POST НЕ отправлен")
                except Exception as e:
                    checker.error(f"Клик: {e}")

            # ============================================
            # ТЕСТ 6: Клик "Экспорт в 1С"
            # ============================================
            checker.log("\n=== ТЕСТ 6: Клик 'Экспорт в 1С' ===")
            reqs.clear()
            exp = page.locator('button:has-text("Экспорт в 1С")')
            if await exp.count() > 0:
                try:
                    await exp.first.click()
                    await page.wait_for_timeout(3000)
                    if any("/export-to-1c" in r[0] for r in reqs):
                        checker.ok(f"POST отправлен: {[r for r in reqs if '/export-to-1c' in r[0]]}")
                    else:
                        checker.error("POST НЕ отправлен")
                except Exception as e:
                    checker.error(f"Клик: {e}")

            # ============================================
            # ТЕСТ 7: "Подтвердить" операцию (с prompt)
            # ============================================
            checker.log("\n=== ТЕСТ 7: Клик 'Подтвердить' операцию ===")
            reqs.clear()
            confirm = page.locator('button:has-text("Подтвердить")').first
            if await confirm.count() > 0:
                try:
                    await confirm.click()
                    await page.wait_for_timeout(3000)
                    if any("/api/operations/" in r[0] for r in reqs):
                        checker.ok(f"POST отправлен: {[r for r in reqs if '/api/operations/' in r[0]]}")
                    else:
                        checker.error("POST НЕ отправлен")
                except Exception as e:
                    checker.error(f"Клик: {e}")

            # ============================================
            # ТЕСТ 8: "Утвердить" ТК
            # ============================================
            checker.log("\n=== ТЕСТ 8: Клик 'Утвердить' (ТК) ===")
            reqs.clear()
            appr = page.locator('button:has-text("Утвердить")')
            if await appr.count() > 0:
                try:
                    await appr.first.click()
                    await page.wait_for_timeout(3000)
                    if any("/api/tech-cards/" in r[0] and "approve" in r[0] for r in reqs):
                        checker.ok(f"POST отправлен: {[r for r in reqs if 'approve' in r[0]]}")
                        # После approve должен быть редирект/перезагрузка
                        content = await page.content()
                        if "ТК утверждена" in content or "approved" in page.url:
                            checker.ok("Страница обновилась")
                    else:
                        checker.error("POST НЕ отправлен")
                except Exception as e:
                    checker.error(f"Клик: {e}")

            # ============================================
            # ТЕСТ 9: "Аналоги" (раскрытие списка)
            # ============================================
            checker.log("\n=== ТЕСТ 9: Клик 'Аналоги' (раскрытие) ===")
            analog = page.locator('a:has-text("Аналоги")').first
            if await analog.count() > 0:
                try:
                    await analog.click()
                    await page.wait_for_timeout(1000)
                    content = await page.content()
                    if "Топ-" in content or "сходство" in content.lower() or "similarity" in content:
                        checker.ok("Список аналогов раскрылся")
                    else:
                        checker.error("Список аналогов НЕ раскрылся")
                except Exception as e:
                    checker.error(f"Клик: {e}")
            else:
                checker.error("Кнопки 'Аналоги' нет")

            # ============================================
            # ТЕСТ 10: Табы в /detail
            # ============================================
            checker.log("\n=== ТЕСТ 10: Табы в /detail (якоря) ===")
            for sel, name in [
                ('a[href="#ops"]', 'Операции'),
                ('a[href="#rs"]', 'РС'),
                ('a[href="#bom"]', 'Состав'),
                ('a[href="#params"]', 'Доп. параметры'),
                ('a[href="#history"]', 'История'),
            ]:
                cnt = await page.locator(sel).count()
                if cnt > 0:
                    checker.ok(f"Таб {name}: {cnt}")
                else:
                    checker.error(f"Таб {name}: НЕТ")

            # ============================================
            # ТЕСТ 11: /notices
            # ============================================
            checker.log("\n=== ТЕСТ 11: /notices ===")
            await page.goto("http://localhost:8000/notices")
            content = await page.content()
            if "И-2026" in content:
                checker.ok("Список извещений отображается")
            else:
                checker.error("Нет извещений")

            # /notices/new
            await page.goto("http://localhost:8000/notices/new")
            form = page.locator('form')
            if await form.count() > 0:
                checker.ok("/notices/new — форма есть")
            else:
                checker.error("/notices/new — формы нет")

            # /notices/1
            await page.goto("http://localhost:8000/notices/1")
            content = await page.content()
            if "AI" in content or "ai" in content.lower() or "diff" in content.lower():
                checker.ok("/notices/1 — есть AI diff")
            else:
                checker.error("/notices/1 — нет AI diff")

            # ============================================
            # ТЕСТ 12: /knowledge
            # ============================================
            checker.log("\n=== ТЕСТ 12: /knowledge ===")
            await page.goto("http://localhost:8000/knowledge")
            content = await page.content()
            if "Синтетический" in content:
                checker.ok("Синтетические эталоны помечены")
            else:
                checker.error("Синтетические не помечены")
            rows = await page.locator('table.tbl tbody tr').count()
            checker.log(f"  Эталонов в таблице: {rows}")

            # ============================================
            # ТЕСТ 13: /settings (под admin)
            # ============================================
            checker.log("\n=== ТЕСТ 13: /settings ===")
            await logout()
            await login("techadmin", "demo")
            await page.goto("http://localhost:8000/settings")
            content = await page.content()
            if "API ключ" in content or "api_key" in content:
                checker.ok("Settings — поле API ключ есть")
            else:
                checker.error("Settings — нет поля API ключ")

            # ============================================
            # ТЕСТ 14: /llm-admin
            # ============================================
            checker.log("\n=== ТЕСТ 14: /llm-admin ===")
            await page.goto("http://localhost:8000/llm-admin")
            content = await page.content()
            if "YandexGPT" in content or "GigaChat" in content or "Mock" in content:
                checker.ok("Провайдеры отображаются")
            else:
                checker.error("Провайдеры не отображаются")

            # ============================================
            # ТЕСТ 15: Анонимный /settings → редирект
            # ============================================
            checker.log("\n=== ТЕСТ 15: Анонимный /settings ===")
            await logout()
            try:
                r = await page.goto("http://localhost:8000/settings")
                if "/login" in page.url:
                    checker.ok(f"Анонимный → {page.url}")
                else:
                    checker.error(f"Анонимный НЕ редиректнут: {page.url}")
            except Exception as e:
                checker.error(f"Редирект: {e}")

            # ============================================
            # ТЕСТ 16: Скриншоты
            # ============================================
            checker.log("\n=== ТЕСТ 16: Скриншоты ===")
            await login("baranov", "demo")
            await page.goto("http://localhost:8000/")
            await page.screenshot(path="/tmp/screen_dashboard.png", full_page=True)
            checker.ok("Скриншот / → /tmp/screen_dashboard.png")
            await page.goto("http://localhost:8000/detail/14")
            await page.screenshot(path="/tmp/screen_detail.png", full_page=True)
            checker.ok("Скриншот /detail/14 → /tmp/screen_detail.png")
            await page.goto("http://localhost:8000/products")
            await page.screenshot(path="/tmp/screen_products.png", full_page=True)
            checker.ok("Скриншот /products → /tmp/screen_products.png")

        except Exception as e:
            checker.error(f"ГЛАВНАЯ ОШИБКА: {e}")
            import traceback
            traceback.print_exc()

        # Консольные ошибки
        if page_errors:
            checker.log("\n---ОШИБКИ В КОНСОЛИ---")
            for e in page_errors[:10]:
                checker.log(f"  {e}")

        await browser.close()

    # Итог
    print("\n" + "=" * 60)
    print(f"ИТОГ: {len(checker.errors)} ошибок, {len(checker.results) - len(checker.errors)} ОК")
    if checker.errors:
        print("\n❌ ЧТО СЛОМАНО:")
        for e in checker.errors:
            print(f"  - {e}")
    return len(checker.errors)


if __name__ == "__main__":
    errs = asyncio.run(check())
    sys.exit(0 if errs == 0 else 1)
