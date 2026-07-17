"""Pytest tests for БИТ.Технолог prototype.

Запуск: pytest test_app.py -v
"""
import os
import sys
import tempfile
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Создаёт временную БД и запускает app"""
    # Изолированная БД
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Установим env ДО импорта app
    os.environ["DB_PATH"] = path
    os.environ["DEMO_MODE"] = "true"
    os.environ["LLM_DAILY_LIMIT_RUB"] = "10"

    sys.path.insert(0, os.path.dirname(__file__))
    import app as app_module
    # Явный init
    app_module.init_db()

    c = TestClient(app_module.app)
    c.__enter__() if hasattr(c, '__enter__') else None

    try:
        yield c, app_module
    finally:
        try:
            c.__exit__(None, None, None)
        except Exception:
            pass
        try:
            os.unlink(path)
        except Exception:
            pass


# ========== Health & basic ==========
def test_health(client):
    c, _ = client
    r = c.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["demo_mode"] is True


def test_index_page(client):
    c, _ = client
    r = c.get("/")
    assert r.status_code == 200
    assert "БИТ.Технолог" in r.text


def test_detail_page(client):
    c, _ = client
    r = c.get("/detail/detail-001")
    assert r.status_code == 200
    assert "КРН" in r.text or "Кронштейн" in r.text


def test_detail_404(client):
    c, _ = client
    r = c.get("/detail/nonexistent")
    assert r.status_code == 404


# ========== LLM Generation ==========
def test_generate_missing_detail_id(client):
    c, _ = client
    r = c.post("/api/generate", data={})
    assert r.status_code == 422


def test_generate_form_data(client):
    c, _ = client
    r = c.post("/api/generate", data={"detail_id": "detail-001"})
    assert r.status_code == 200


def test_generate_not_found(client):
    c, _ = client
    r = c.post("/api/generate", data={"detail_id": "nonexistent"})
    assert r.status_code == 404


# ========== Approve & send-to-1c ==========
def test_approve(client):
    c, _ = client
    r = c.post("/api/approve", data={"detail_id": "detail-001"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_send_to_1c(client):
    c, _ = client
    r = c.post("/api/send-to-1c", data={"detail_id": "detail-001"})
    assert r.status_code == 200
    assert r.json()["status"] == "sent"


# ========== Edit operations ==========
def test_edit_operation(client):
    c, _ = client
    # Сначала сгенерируем черновик
    c.post("/api/generate", data={"detail_id": "detail-003"})
    r = c.post("/api/edit/operation", data={
        "detail_id": "detail-003",
        "op_index": "0",
        "field": "duration_hours",
        "value": "0.5",
        "reason": "test"
    })
    assert r.status_code == 200, r.text


def test_add_operation(client):
    c, _ = client
    r = c.post("/api/edit/add-operation", data={
        "detail_id": "detail-001",
        "name": "TEST_OP",
        "duration_hours": "0.3"
    })
    assert r.status_code == 200


def test_delete_operation_invalid_index(client):
    c, _ = client
    r = c.post("/api/edit/delete-operation", data={
        "detail_id": "detail-001",
        "op_index": "99"
    })
    assert r.status_code in (200, 400)


# ========== CRUD pages ==========
def test_equipment_page(client):
    c, _ = client
    assert c.get("/equipment").status_code == 200


def test_materials_page(client):
    c, _ = client
    assert c.get("/materials").status_code == 200


def test_iot_page(client):
    c, _ = client
    assert c.get("/iot").status_code == 200


def test_benchmarks_page(client):
    c, _ = client
    assert c.get("/benchmarks").status_code == 200


def test_new_detail_form(client):
    c, _ = client
    assert c.get("/details/new").status_code == 200


# ========== Learning & metrics ==========
def test_learning_page(client):
    c, _ = client
    assert c.get("/learning").status_code == 200


def test_llm_debug_page(client):
    c, _ = client
    assert c.get("/llm-debug").status_code == 200


# ========== Cost tracking (unit tests) ==========
def test_daily_cost_structure(client):
    _, app = client
    dc = app.get_daily_cost()
    assert "date" in dc
    assert "total_rub" in dc
    assert "limit_rub" in dc
    assert "remaining_rub" in dc
    assert "exceeded" in dc
    assert isinstance(dc["exceeded"], bool)


def test_calc_cost_rub(client):
    _, app = client
    # 0 токенов = 0 руб
    assert app.calc_cost_rub(0, 0) == 0.0
    # 1000 input + 500 output = 0.40*1 + 1.20*0.5 = 1.00
    cost = app.calc_cost_rub(1000, 500)
    assert abs(cost - 1.00) < 0.01


# ========== Database helpers ==========
def test_get_detail_returns_dict_with_id(client):
    _, app = client
    d = app.get_detail("detail-001")
    assert d is not None
    assert "id" in d
    assert d["id"] == "detail-001"
    assert "designation" in d
    assert "name" in d


def test_get_all_details_has_ids(client):
    _, app = client
    details = app.get_all_details()
    assert len(details) > 0
    for d in details:
        assert "id" in d


# ========== Pilot metrics ==========
def test_record_metric(client):
    _, app = client
    app.record_metric("test-detail", "test_metric", 42.0, {"foo": "bar"})
    # No exception = pass


def test_pilot_metrics_endpoint(client):
    c, _ = client
    assert c.get("/pilot").status_code == 200


def test_pilot_time_form(client):
    c, _ = client
    r = c.post("/api/pilot/time", data={"detail_id": "test-1", "minutes": "45"}, follow_redirects=False)
    assert r.status_code in (200, 303)


def test_pilot_accepted_form(client):
    c, _ = client
    r = c.post("/api/pilot/accepted", data={
        "detail_id": "test-2", "total_ops": "10", "accepted_ops": "6"
    }, follow_redirects=False)
    assert r.status_code in (200, 303)


def test_pilot_metrics_after_activity(client):
    _, app = client
    # Сгенерируем черновик
    c, _ = client
    c.post("/api/generate", data={"detail_id": "detail-001"})
    # Утвердим
    c.post("/api/approve", data={"detail_id": "detail-001"})
    # Получим метрики
    metrics = app.get_pilot_metrics()
    assert "total_details_processed" in metrics
    assert "edits_per_card" in metrics
    assert "accepted_pct" in metrics
    assert "avg_time_to_card_min" in metrics
    assert metrics["kpi"]["time_target"] == 60
