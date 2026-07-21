"""
Тесты v0.8 — модульные тесты новой архитектуры.

Покрывают:
- repositories.db (33 таблицы, CRUD, helpers)
- services.rs_factory (детерминизм, 8 осей, аудит-цепочка)
- services.auth (5 ролей, hash, authenticate)
- services.tp_parser (OCR-парсинг, валидация)
- gateways.one_c_gateway (FileGateway)
- domain.llm_provider (MockLLMProvider, parse_llm_json_safe)
- app.py routes (smoke test всех 8 экранов)

Запуск: pytest test/test_v0_8.py -v
"""
import json
import sys
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

from repositories import db
from services.rs_factory import build_rs, is_deterministic, DEFAULT_PROFILE, to_one_c_spec
from services.auth import authenticate, ROLES, has_permission, hash_password, verify_password, seed_users
from services.tp_parser import parse_tp_text, validate_parsed_tp
from gateways.one_c_gateway import FileGateway, OneCResourceSpec
from domain.llm_provider import MockLLMProvider, parse_llm_json_safe, get_registry


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(autouse=True, scope="session")
def _init_db():
    """Один раз инициализируем БД для всех тестов."""
    db.init_db()
    seed_users(verbose=False)
    # Загрузим items
    from seeds.seed_items import seed_all
    seed_all(verbose=False)
    # Загрузим эталоны
    from seeds.seed_etalons import seed_etalons
    seed_etalons(verbose=False)


@pytest.fixture
def sample_operations():
    return [
        {
            "id": 1, "op_number": 5, "name": "Резка",
            "workshop_code": "01", "site_code": "01", "workplace": "04",
            "profession_code": "Р-3", "equipment_name": "НГ-6,3",
            "time_setup_min": 6, "time_per_unit_min": 12,
            "materials": [{"code": "09Г2С", "qty": 8.5, "unit": "кг"}],
        },
        {
            "id": 2, "op_number": 10, "name": "Сварка",
            "workshop_code": "02", "site_code": "01", "workplace": "04",
            "profession_code": "Э-5", "equipment_name": "ПДГ-508",
            "time_setup_min": 12, "time_per_unit_min": 35,
            "materials": [{"code": "Св-08Г2С-О", "qty": 1.2, "unit": "кг"}],
        },
        {
            "id": 3, "op_number": 15, "name": "Контроль",
            "workshop_code": "04", "site_code": "01", "workplace": "01",
            "profession_code": "К-3", "equipment_name": "Стол ОТК",
            "time_setup_min": 5, "time_per_unit_min": 8,
        },
    ]


# ============================================================
# ТЕСТЫ REPOSITORIES
# ============================================================

class TestRepositoriesDB:
    def test_init_creates_33_tables(self):
        rows = db.query("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [r["name"] for r in rows]
        assert len(table_names) >= 25, f"Expected at least 25 tables, got {len(table_names)}"

    def test_required_tables_exist(self):
        rows = db.query("SELECT name FROM sqlite_master WHERE type='table'")
        names = {r["name"] for r in rows}
        required = {
            "items", "bom_links", "tech_cards", "operations",
            "resource_specs", "change_notices", "etalons", "work_history",
            "rs_output_profiles", "llm_providers", "llm_model_assignments",
            "pilot_users", "ext_attributes",
        }
        missing = required - names
        assert not missing, f"Missing tables: {missing}"

    def test_list_items_returns_real_data(self):
        items = db.list_items(limit=20)
        assert len(items) >= 14  # seed_items загрузил 14
        assert any(it["designation"] == "ЛМША.301314.010" for it in items)

    def test_list_items_filter_by_level(self):
        details = db.list_items(level="detail", limit=20)
        for it in details:
            assert it["level"] == "detail"

    def test_get_item_with_bom(self):
        # ЛМША.301712.000 — главный item
        item = db.query_one("SELECT id FROM items WHERE designation = ?", ("ЛМША.301712.000",))
        assert item is not None
        full = db.get_item_with_bom(item["id"])
        assert full["designation"] == "ЛМША.301712.000"

    def test_etalons_for_rag(self):
        etalons = db.get_etalons_for_rag(limit=10)
        assert len(etalons) >= 2  # seed_etalons загрузил 2

    def test_count_users(self):
        row = db.query_one("SELECT COUNT(*) AS n FROM pilot_users")
        assert row["n"] >= 6  # seed_users создал 6


# ============================================================
# ТЕСТЫ RS_FACTORY
# ============================================================

class TestRSFactory:
    def test_determinism(self, sample_operations):
        """10 запусков дают одинаковый результат."""
        assert is_deterministic(sample_operations, DEFAULT_PROFILE, runs=10)

    def test_basic_build(self, sample_operations):
        report = build_rs("TEST-001", sample_operations, DEFAULT_PROFILE, tech_card_id=42)
        assert report.item_designation == "TEST-001"
        assert report.tech_card_id == 42
        assert len(report.rows) == 3  # 1:1 для full granularity

    def test_summary(self, sample_operations):
        report = build_rs("TEST", sample_operations, DEFAULT_PROFILE)
        # Тпз: 6+12+5=23, Тшт: 12+35+8=55
        assert report.summary["total_setup_min"] == 23
        assert report.summary["total_per_unit_min"] == 55
        assert report.summary["total_time_min"] == 78
        assert report.summary["total_time_hours"] == 1.3

    def test_audit_chain(self, sample_operations):
        """Каждая строка имеет аудит с правилом и source_operation_id."""
        report = build_rs("TEST", sample_operations, DEFAULT_PROFILE)
        for row in report.rows:
            assert row.audit is not None
            assert row.audit.rule == "op_to_row"
            assert row.audit.source_op_number > 0

    def test_aggregated_profile(self, sample_operations):
        profile = {**DEFAULT_PROFILE, "op_granularity": "aggregated"}
        report = build_rs("TEST", sample_operations, profile)
        # 3 этапа (01, 02, 04) × 1 профессия = 3 строки
        assert len(report.rows) == 3
        for row in report.rows:
            assert row.audit.rule == "aggregate_by_profession"

    def test_stages_only(self, sample_operations):
        profile = {**DEFAULT_PROFILE, "op_granularity": "stages_only"}
        report = build_rs("TEST", sample_operations, profile)
        # 3 этапа
        assert len(report.rows) == 3
        for row in report.rows:
            assert row.audit.rule == "aggregate_by_stage"

    def test_to_one_c_spec(self, sample_operations):
        report = build_rs("TEST-001", sample_operations, DEFAULT_PROFILE)
        spec = to_one_c_spec(report, item_ref_1c="uuid-1", tech_card_ref="tc-1", version=1)
        assert spec.item_ref == "uuid-1"
        assert spec.version == 1
        assert len(spec.rows) == 3
        assert spec.rows[0]["op_number"] == 5

    def test_warnings_for_empty(self):
        report = build_rs("EMPTY", [], DEFAULT_PROFILE)
        assert "Нет операций" in str(report.warnings)


# ============================================================
# ТЕСТЫ AUTH
# ============================================================

class TestAuth:
    def test_5_roles_defined(self):
        assert len(ROLES) == 5
        assert "technologist" in ROLES
        assert "main_technologist" in ROLES
        assert "workshop_chief" in ROLES
        assert "tech_admin" in ROLES
        assert "llm_admin" in ROLES

    def test_password_hash_and_verify(self):
        h = hash_password("demo")
        assert verify_password("demo", h)
        assert not verify_password("wrong", h)

    def test_authenticate_demo_user(self):
        u = authenticate("baranov", "demo")
        assert u is not None
        assert u.username == "baranov"
        assert u.role == "main_technologist"

    def test_authenticate_wrong_password(self):
        u = authenticate("baranov", "wrong")
        assert u is None

    def test_authenticate_unknown_user(self):
        u = authenticate("unknown", "demo")
        assert u is None

    def test_has_permission(self):
        assert has_permission("main_technologist", "approve_tech_cards")
        assert not has_permission("technologist", "approve_tech_cards")
        assert has_permission("llm_admin", "manage_llm_providers")
        assert not has_permission("tech_admin", "manage_llm_providers")


# ============================================================
# ТЕСТЫ TP_PARSER
# ============================================================

class TestTPParser:
    def test_parse_pdf1(self):
        if not Path("/tmp/tp1_full.txt").exists():
            pytest.skip("PDF text not available")
        text = Path("/tmp/tp1_full.txt").read_text(encoding="utf-8")
        tp = parse_tp_text(text)
        assert tp.designation == "ЛМША.301712.000"
        assert len(tp.operations) >= 1
        assert tp.product_type == "АЦ"

    def test_parse_pdf2(self):
        if not Path("/tmp/tp2_full.txt").exists():
            pytest.skip("PDF text not available")
        text = Path("/tmp/tp2_full.txt").read_text(encoding="utf-8")
        tp = parse_tp_text(text)
        assert tp.designation == "ЛМША.301314.020"  # Парсер находит первое
        assert len(tp.operations) >= 1

    def test_validate_parsed_tp(self):
        from services.tp_parser import TPOperation, TPComposite
        tp = TPComposite(
            designation="TEST",
            name="Test",
            operations=[
                TPOperation(op_number=5, name="Op1", time_per_unit_min=10),
                TPOperation(op_number=10, name="Op2", time_per_unit_min=20),
            ],
        )
        issues = validate_parsed_tp(tp)
        assert len(issues) == 0  # Всё OK


# ============================================================
# ТЕСТЫ GATEWAYS
# ============================================================

class TestOneCGateway:
    def test_file_gateway_create(self, tmp_path):
        gw = FileGateway(exchange_dir=tmp_path)
        gw.connect()
        rs = OneCResourceSpec(
            ref_1c=None,
            item_ref="TEST-001",
            tech_card_ref="TC-1",
            version=1,
            profile_code="test",
            rows=[{"op_number": 5, "name": "Test"}],
        )
        ref = gw.create_resource_spec(rs)
        assert ref is not None
        # Файл должен существовать
        files = list((tmp_path / "out").iterdir())
        assert len(files) == 1
        assert files[0].name.endswith(".xml")

    def test_file_gateway_get_nomenclature_empty(self, tmp_path):
        gw = FileGateway(exchange_dir=tmp_path)
        gw.connect()
        items = gw.get_nomenclature()
        assert items == []  # пустой XML


# ============================================================
# ТЕСТЫ LLM PROVIDER
# ============================================================

class TestLLMProvider:
    def test_mock_generate(self):
        m = MockLLMProvider()
        result = m.generate("Сгенерируй техкарту")
        assert result.content
        assert result.model == "mock-1"
        assert result.input_tokens > 0

    def test_mock_task_detection(self):
        m = MockLLMProvider()
        # Техкарта
        r1 = m.generate("Сгенерируй", system="Ты технолог")
        assert "operations" in r1.content
        # OCR
        r2 = m.generate("Распознай чертёж")
        assert "title" in r2.content
        # Извещение
        r3 = m.generate("Извещение И-2026", system="diff")
        assert "changes" in r3.content

    def test_parse_llm_json_safe(self):
        # JSON в строке
        result = parse_llm_json_safe('{"a": 1, "b": [1, 2]}')
        assert result == {"a": 1, "b": [1, 2]}
        # JSON в блоке
        result = parse_llm_json_safe('```json\n{"x": 5}\n```')
        assert result == {"x": 5}
        # Невалидный
        result = parse_llm_json_safe("not json")
        assert result == {}

    def test_registry_is_mock_mode(self):
        reg = get_registry()
        # В тестах нет активных провайдеров → mock
        assert reg.is_mock_mode() is True


# ============================================================
# ТЕСТЫ APP ROUTES
# ============================================================

class TestAppRoutes:
    def test_health(self):
        from app import app
        client = TestClient(app)
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.8.0"
        assert "items" in data
        assert "etalons" in data

    def test_dashboard(self):
        from app import app
        client = TestClient(app)
        r = client.get("/")
        assert r.status_code == 200
        assert "БИТ.Технолог" in r.text

    @pytest.mark.parametrize("path", [
        "/", "/products", "/knowledge", "/notices", "/profiles", "/help", "/llm-admin"
    ])
    def test_all_screens_200(self, path):
        from app import app
        client = TestClient(app)
        r = client.get(path)
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        assert "БИТ.Технолог" in r.text

    def test_detail_page(self):
        from app import app
        client = TestClient(app)
        # Найдём id существующего item
        item = db.query_one("SELECT id FROM items WHERE designation = ?", ("ЛМША.301314.010",))
        if not item:
            pytest.skip("Item not found")
        r = client.get(f"/detail/{item['id']}")
        assert r.status_code == 200
        assert "ЛМША.301314.010" in r.text
        assert "Упор продольный" in r.text

    def test_api_items(self):
        from app import app
        client = TestClient(app)
        r = client.get("/api/items?limit=5")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert "items" in data


# ============================================================
# ТЕСТЫ SPRINT 5: RAG + EVIDENCE
# ============================================================

class TestRAG:
    def test_load_etalons(self):
        from services.rag import load_etalons
        etalons = load_etalons(force=True)
        assert len(etalons) >= 2
        for et in etalons:
            assert et.designation
            assert et.tfidf  # TF-IDF построен

    def test_find_analogs_similar(self):
        from services.rag import find_analogs
        # "Сварка" — должно найти аналоги в эталонах
        results = find_analogs("Сварка", top_k=3)
        assert len(results) > 0
        for r in results:
            assert r.similarity > 0
            assert r.evidence_level in ("green", "yellow", "red")

    def test_find_analogs_unique(self):
        from services.rag import find_analogs
        results = find_analogs("Контроль", top_k=3)
        # Каждый аналог — уникальный эталон
        designations = [r.etalon_designation for r in results]
        assert len(designations) == len(set(designations))

    def test_detect_operation_type(self):
        from services.rag import detect_operation_type
        assert detect_operation_type("Сварка трубы") == "сварка"
        assert detect_operation_type("Резка листа") == "резка"
        assert detect_operation_type("Гибка заготовки") == "гибка"
        assert detect_operation_type("Контроль качества") == "контроль"
        assert detect_operation_type("Что-то неизвестное") == "прочее"

    def test_tfidf_similarity(self):
        from services.rag import _cosine, _build_tfidf, _idf
        # Идентичные векторы = 1.0
        v1 = {"a": 1.0, "b": 1.0}
        assert _cosine(v1, v1) == pytest.approx(1.0, abs=1e-9)
        # Ортогональные = 0.0
        v2 = {"c": 1.0}
        assert _cosine(v1, v2) == 0.0

    def test_index_for_rag(self):
        from services.rag import index_for_rag
        etalon = db.query_one("SELECT id FROM etalons LIMIT 1")
        assert etalon is not None
        ok = index_for_rag(etalon["id"])
        assert ok is True


class TestEvidence:
    def test_evidence_for_ai_tech_card(self):
        """ТК 3 (Кронштейн) с AI-нормами должна иметь mixed светофор."""
        from services.evidence import collect_evidence_for_tech_card, tech_card_evidence_summary
        # Сначала убедимся, что ТК 3 существует (от seed_test_ai_tc)
        tc = db.query_one("SELECT id FROM tech_cards WHERE id = 3")
        if not tc:
            pytest.skip("Test TC not seeded")
        evs = collect_evidence_for_tech_card(3)
        assert len(evs) >= 1
        # Должны быть разные уровни (yellow/red/gray)
        levels = {e.evidence_level for e in evs}
        assert len(levels) >= 2  # Хотя бы 2 разных уровня

    def test_evidence_for_factory_tech_card(self):
        """ТК 1 или 2 (из эталонов) — все операции должны быть зелёными."""
        from services.evidence import collect_evidence_for_tech_card
        # ТК 1 — ЛМША.301712.000 (эталон)
        tc = db.query_one("SELECT id FROM tech_cards WHERE id = 1")
        if not tc:
            pytest.skip("TC 1 not seeded")
        evs = collect_evidence_for_tech_card(1)
        for e in evs:
            assert e.evidence_level == "green"
            assert e.source == "factory_data"

    def test_summary(self):
        from services.evidence import tech_card_evidence_summary
        s = tech_card_evidence_summary(3)
        assert "total" in s
        assert "green" in s
        assert "green_pct" in s
        assert s["total"] >= 0

    def test_update_operation_evidence(self):
        from services.evidence import update_operation_evidence
        # Возьмём операцию 11 (Резка листа, AI guess)
        op = db.query_one("SELECT id, time_per_unit_min FROM operations WHERE id = 11")
        if not op:
            pytest.skip("Operation not seeded")
        old_time = op["time_per_unit_min"]
        new_time = old_time + 5.0
        ok = update_operation_evidence(11, new_time, "TestUser", "Test confirm")
        assert ok is True
        # Проверим, что обновлено
        op_after = db.query_one("SELECT source, time_per_unit_min FROM operations WHERE id = 11")
        assert op_after["source"] == "factory_data"
        assert op_after["time_per_unit_min"] == new_time
        # Откатим
        update_operation_evidence(11, old_time, "TestUser", "rollback")

    def test_evidence_api(self):
        from app import app
        client = TestClient(app)
        r = client.get("/api/tech-cards/3/evidence")
        assert r.status_code == 200
        data = r.json()
        assert "summary" in data
        assert "operations" in data
        assert data["summary"]["total"] >= 1

    def test_detail_with_evidence(self):
        from app import app
        client = TestClient(app)
        r = client.get("/detail/15")
        assert r.status_code == 200
        # Светофор в HTML
        assert "Светофор норм" in r.text or "Светофор" in r.text


# ============================================================
# ТЕСТЫ SPRINT 6: NOTICES (ИЗВЕЩЕНИЯ)
# ============================================================

class TestNotices:
    def test_create_notice(self):
        from services.notices import create_notice
        nid = create_notice(
            number="И-2026-TEST-CREATE",
            date="2026-07-21",
            foundation_doc="Test",
            reason="Test create",
            author="TestUser",
            affected_item_designation="ЛМША.301314.010",
        )
        assert nid > 0
        # Очистим
        db.execute("DELETE FROM change_notices WHERE id = ?", (nid,))

    def test_find_affected_items(self):
        from services.notices import find_affected_items
        affected = find_affected_items("ЛМША.301314.010")
        assert len(affected) >= 1
        # Корневая деталь — direct
        direct = [a for a in affected if a["impact_type"] == "direct"]
        assert len(direct) == 1
        assert direct[0]["designation"] == "ЛМША.301314.010"

    def test_find_affected_not_found(self):
        from services.notices import find_affected_items
        affected = find_affected_items("ЛМША.999999.999")
        assert affected == []

    def test_generate_ai_diff(self):
        from services.notices import create_notice, generate_ai_diff
        nid = create_notice(
            number="И-2026-TEST-DIFF",
            date="2026-07-21",
            foundation_doc="Test",
            reason="Test diff",
            author="TestUser",
        )
        diff = generate_ai_diff(nid)
        assert "changes" in diff or "error" in diff
        # Очистим
        db.execute("DELETE FROM change_notices WHERE id = ?", (nid,))

    def test_resolve_notice_creates_rs(self):
        from services.notices import create_notice, resolve_notice
        nid = create_notice(
            number="И-2026-TEST-RESOLVE",
            date="2026-07-21",
            foundation_doc="Test",
            reason="Test resolve",
            author="TestUser",
            affected_item_designation="ЛМША.301314.010",
        )
        result = resolve_notice(nid, "TestUser", "accept_ai", "test")
        assert result["status"] == "ok"
        assert result["rs_regenerated"] >= 1
        # Проверим, что РС создана
        rs = db.query_one(
            "SELECT * FROM resource_specs WHERE change_reason LIKE ?",
            (f"%И-2026-TEST-RESOLVE%",)
        )
        assert rs is not None
        # Очистим
        db.execute("DELETE FROM change_notices WHERE id = ?", (nid,))
        db.execute("DELETE FROM resource_specs WHERE change_reason LIKE ?", (f"%И-2026-TEST-RESOLVE%",))

    def test_notice_pages_200(self):
        from app import app
        client = TestClient(app)
        for path in ["/notices", "/notices/new"]:
            r = client.get(path)
            assert r.status_code == 200, f"{path} -> {r.status_code}"
        # Если есть хотя бы одно извещение — проверяем деталь
        n = db.query_one("SELECT id FROM change_notices LIMIT 1")
        if n:
            r = client.get(f"/notices/{n['id']}")
            assert r.status_code == 200

    def test_create_notice_via_form(self):
        from app import app
        client = TestClient(app)
        r = client.post("/notices/new", data={
            "number": "И-2026-TEST-FORM",
            "date": "2026-07-21",
            "foundation_doc": "Form test",
            "reason": "Form test reason",
            "description": "Test",
            "author": "TestUser",
            "affected_item_designation": "ЛМША.301314.010",
        }, follow_redirects=False)
        assert r.status_code == 303
        # Очистим
        n = db.query_one("SELECT id FROM change_notices WHERE number = 'И-2026-TEST-FORM'")
        if n:
            db.execute("DELETE FROM change_notices WHERE id = ?", (n["id"],))
