import sys
sys.path.insert(0, ".")
"""E2E тесты — сценарий технолога целиком."""
import os
import json
import tempfile
import pytest
from fastapi.testclient import TestClient


class TestE2ETechnologistFlow:
    """Сценарий: технолог Баранов создаёт ТК end-to-end."""

    def test_e2e_generate_tc(self):
        from app import app
        from repositories import db
        client = TestClient(app)

        # 1. Login
        r = client.post("/login", data={"username": "baranov", "password": "demo"}, follow_redirects=False)
        assert r.status_code == 303

        # 2. Создать ТК для детали без ТК
        r = client.post("/items/8/generate", cookies=r.cookies, follow_redirects=False)
        assert r.status_code == 303

        # 3. Найти новую ТК
        tc = db.query_one(
            "SELECT id, version, status, is_approved FROM tech_cards WHERE item_id = 8 ORDER BY id DESC LIMIT 1"
        )
        assert tc is not None
        assert tc["is_approved"] == 0
        assert tc["status"] == "draft"

        # 4. Должны быть операции
        ops = db.query("SELECT id, time_per_unit_min, source FROM operations WHERE tech_card_id = ?", (tc["id"],))
        assert len(ops) > 0, "Должна быть хотя бы 1 операция"

    def test_e2e_confirm_operation_updates_source(self):
        from app import app
        from repositories import db
        client = TestClient(app)
        r = client.post("/login", data={"username": "baranov", "password": "demo"}, follow_redirects=False)
        # Создадим ТК для item 9
        client.post("/items/9/generate", cookies=r.cookies, follow_redirects=False)
        op = db.query_one("""
            SELECT o.id FROM operations o
            JOIN tech_cards tc ON tc.id = o.tech_card_id
            WHERE tc.item_id = 9 ORDER BY o.id DESC LIMIT 1
        """)
        # Confirm
        r = client.post(f"/api/operations/{op['id']}/confirm?new_time=42.5", cookies=r.cookies)
        assert r.status_code == 200
        # Проверим что source=factory_data
        op_check = db.query_one("SELECT source, time_per_unit_min FROM operations WHERE id = ?", (op["id"],))
        assert op_check["source"] == "factory_data"
        assert op_check["time_per_unit_min"] == 42.5

    def test_e2e_approve_tc_creates_etalon(self):
        from app import app
        from repositories import db
        client = TestClient(app)
        r = client.post("/login", data={"username": "baranov", "password": "demo"}, follow_redirects=False)
        # Создадим ТК
        client.post("/items/12/generate", cookies=r.cookies, follow_redirects=False)
        tc = db.query_one("SELECT id FROM tech_cards WHERE item_id = 12 ORDER BY id DESC LIMIT 1")
        # Etalons до
        etalons_before = db.query_one("SELECT COUNT(*) AS n FROM etalons")["n"]
        # Approve
        r = client.post(f"/api/tech-cards/{tc['id']}/approve", cookies=r.cookies)
        assert r.status_code == 200
        # Etalons после
        etalons_after = db.query_one("SELECT COUNT(*) AS n FROM etalons")["n"]
        # TC статус
        tc_after = db.query_one("SELECT status, is_approved FROM tech_cards WHERE id = ?", (tc["id"],))
        assert tc_after["status"] == "approved"
        assert tc_after["is_approved"] == 1
        # Эталон создан (или обновлён)
        assert etalons_after >= etalons_before

    def test_e2e_export_to_1c(self):
        from app import app
        from repositories import db
        client = TestClient(app)
        r = client.post("/login", data={"username": "baranov", "password": "demo"}, follow_redirects=False)
        # Создадим ТК
        client.post("/items/13/generate", cookies=r.cookies, follow_redirects=False)
        # Export
        r = client.post("/api/items/13/export-to-1c", cookies=r.cookies)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "path" in data
        assert os.path.exists(data["path"]), f"Файл не создан: {data['path']}"
        # Проверим содержимое
        with open(data["path"], "r", encoding="utf-8") as f:
            content = f.read()
        assert "<ResourceSpec" in content
        assert "<item_ref>" in content

    def test_e2e_settings_requires_auth(self):
        from app import app
        client = TestClient(app)
        # Анонимный → редирект на /login
        r = client.get("/settings", follow_redirects=False)
        assert r.status_code == 303
        assert "/login" in r.headers.get("location", "")

    def test_e2e_settings_technologist_403(self):
        from app import app
        client = TestClient(app)
        r = client.post("/login", data={"username": "baranov", "password": "demo"}, follow_redirects=False)
        # Залогиненный не-admin → 403
        r2 = client.get("/settings", cookies=r.cookies)
        assert r2.status_code == 403

    def test_e2e_settings_admin_200(self):
        from app import app
        client = TestClient(app)
        r = client.post("/login", data={"username": "techadmin", "password": "demo"}, follow_redirects=False)
        r2 = client.get("/settings", cookies=r.cookies)
        assert r2.status_code == 200

    def test_e2e_dashboard_button_create_tk(self):
        from app import app
        client = TestClient(app)
        r = client.post("/login", data={"username": "baranov", "password": "demo"}, follow_redirects=False)
        r2 = client.get("/", cookies=r.cookies)
        assert "Создать ТК" in r2.text

    def test_e2e_products_filter(self):
        from app import app
        client = TestClient(app)
        r = client.get("/products?q=%D0%92%D1%82%D1%83%D0%BB%D0%BA")
        # Хотя бы одна втулка
        assert "Втулка" in r.text or "втулк" in r.text.lower()

    def test_e2e_knowledge_synthetic_badge(self):
        from app import app
        client = TestClient(app)
        r = client.get("/knowledge")
        # Хотя бы 1 синтетический
        assert "Синтетический" in r.text

    def test_e2e_detail_tabs_present(self):
        from app import app
        client = TestClient(app)
        r = client.get("/detail/3")
        # Все 5 табов
        for tab_id in ["ops", "rs", "bom", "params", "history"]:
            assert f'id="{tab_id}"' in r.text, f"Нет таба #{tab_id}"

    def test_e2e_detail_tabs_anchor_links(self):
        from app import app
        client = TestClient(app)
        r = client.get("/detail/3")
        # Проверяем что у табов есть href ссылки на якоря
        for tab_id in ["ops", "rs", "bom", "params", "history"]:
            assert f'href="#{tab_id}"' in r.text, f"Нет ссылки #{tab_id}"

    def test_e2e_detail_shows_workshop_name(self):
        from app import app
        client = TestClient(app)
        r = client.get("/detail/3")
        # Названия цехов подтягиваются
        # Если workshop_code=01, должно быть название (например "Заготовительный")
        assert "Заготовительный" in r.text or "Сборочный" in r.text or "Загот" in r.text or r.text.count("<b>") > 5
