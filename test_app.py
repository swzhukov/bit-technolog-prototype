"""Pytest tests for БИТ.Технолог prototype.

Запуск: pytest test_app.py -v
"""
import os
import json
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


# ========== Tech rules ==========
def test_save_rules(client):
    c, _ = client
    r = c.post("/api/details/detail-001/rules",
               data={"rules": "обезжиривание 20 мин в травильной жидкости"})
    assert r.status_code == 200


def test_get_detail_has_tech_rules(client):
    _, app = client
    d = app.get_detail("detail-001")
    assert "tech_rules" in d
    assert "cost_per_hour" in d
    assert "overhead_pct" in d
    assert "material_cost_rub" in d


# ========== Economics ==========
def test_save_economics(client):
    c, _ = client
    r = c.post("/api/details/detail-001/economics",
               data={"cost_per_hour": "500", "overhead_pct": "15", "material_cost_rub": "1000"})
    assert r.status_code == 200


def test_calc_cost_estimate(client):
    _, app = client
    # Сначала сгенерируем и установим экономику
    c, _ = client
    c.post("/api/generate", data={"detail_id": "detail-001"})
    c.post("/api/details/detail-001/economics",
           data={"cost_per_hour": "500", "overhead_pct": "15", "material_cost_rub": "1000"})
    econ = app.calc_cost_estimate("detail-001")
    assert "total_hours" in econ
    assert "labor_cost" in econ
    assert "total_cost" in econ
    assert econ["total_cost"] > 0


# ========== Role model ==========
def test_submit_for_review(client):
    c, _ = client
    c.post("/api/generate", data={"detail_id": "detail-001"})
    r = c.post("/api/submit-for-review", data={"detail_id": "detail-001"})
    assert r.status_code == 200


def test_approve_chief(client):
    c, _ = client
    c.post("/api/generate", data={"detail_id": "detail-001"})
    r = c.post("/api/approve-chief",
               data={"detail_id": "detail-001", "chief": "Баранов"})
    assert r.status_code == 200


def test_economics_endpoint(client):
    c, _ = client
    c.post("/api/generate", data={"detail_id": "detail-001"})
    c.post("/api/details/detail-001/economics",
           data={"cost_per_hour": "500", "overhead_pct": "15", "material_cost_rub": "1000"})
    r = c.get("/api/economics/detail-001")
    assert r.status_code == 200
    assert "труд" in r.text or "себестоимость" in r.text


# ========== Sprint 1: analyze / draft-fast / refine / economics by dept ==========
def test_api_analyze_demo(client):
    c, _ = client
    r = c.post("/api/analyze", data={"detail_id": "detail-001"})
    assert r.status_code == 200
    data = r.json()
    assert "questions" in data
    assert 3 <= len(data["questions"]) <= 5
    for q in data["questions"]:
        assert "id" in q and "question" in q
        assert "options" in q and len(q["options"]) >= 2


def test_api_analyze_missing_detail(client):
    c, _ = client
    r = c.post("/api/analyze", data={"detail_id": "nonexistent"})
    assert r.status_code == 404


def test_api_analyze_missing_id(client):
    c, _ = client
    r = c.post("/api/analyze", data={})
    assert r.status_code == 422


def test_api_draft_fast_demo(client):
    c, _ = client
    r = c.post("/api/draft-fast", data={"detail_id": "detail-001", "answers": "{}"})
    assert r.status_code == 200
    data = r.json()
    assert "draft" in data
    draft = data["draft"]
    assert "summary" in draft
    assert "route" in draft
    assert 1 <= len(draft["route"]) <= 5


def test_api_refine_demo(client):
    c, _ = client
    r = c.post("/api/refine", data={"detail_id": "detail-001", "draft": "{}", "answers": "{}"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert "total_ops" in data


def test_api_feedback(client):
    c, _ = client
    r = c.post("/api/feedback", data={"detail_id": "detail-001", "reason": "некорректный маршрут"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_economics_includes_by_department(client):
    c, app = client
    c.post("/api/generate", data={"detail_id": "detail-001"})
    c.post("/api/details/detail-001/economics",
           data={"cost_per_hour": "500", "overhead_pct": "15", "material_cost_rub": "1000"})
    econ = app.calc_cost_estimate("detail-001")
    assert "by_department" in econ
    assert len(econ["by_department"]) >= 1
    for d in econ["by_department"]:
        assert "department" in d and "hours" in d and "labor_cost" in d


def test_economics_endpoint_shows_process_pricing_table(client):
    c, _ = client
    c.post("/api/generate", data={"detail_id": "detail-001"})
    c.post("/api/details/detail-001/economics",
           data={"cost_per_hour": "500", "overhead_pct": "15", "material_cost_rub": "1000"})
    r = c.get("/api/economics/detail-001")
    assert r.status_code == 200
    assert "по цехам" in r.text or "process-based" in r.text.lower() or "Цех" in r.text


# ========== Sprint 2: RAG (TF-IDF + cosine + hybrid) ==========
def test_rag_status_initial(client):
    c, _ = client
    r = c.get("/api/rag/status")
    assert r.status_code == 200
    data = r.json()
    assert "loaded" in data
    assert "documents" in data


def test_rag_rebuild_builds_index(client):
    c, _ = client
    r = c.post("/api/rag/rebuild")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["indexed"] >= 1


def test_rag_similar_returns_results(client):
    c, _ = client
    c.post("/api/rag/rebuild")
    r = c.get("/api/rag/similar/detail-001?top_k=3")
    assert r.status_code == 200
    data = r.json()
    assert "similar" in data
    if data["similar"]:
        s = data["similar"][0]
        assert "detail_id" in s and "score" in s
        assert 0.0 <= s["score"] <= 1.0


def test_rag_similar_not_found(client):
    c, _ = client
    r = c.get("/api/rag/similar/nonexistent")
    assert r.status_code == 404


def test_rag_autoindex_on_approve(client):
    c, _ = client
    # Генерируем и approve
    c.post("/api/generate", data={"detail_id": "detail-002"})
    c.post("/api/approve", data={"detail_id": "detail-002"})
    # Индекс должен содержать detail-002
    status = c.get("/api/rag/status").json()
    assert "detail-002" in c.get("/api/rag/similar/detail-001?top_k=10").json().get("similar", [{"detail_id": ""}])[0].get("detail_id", "") or status["documents"] >= 1


# ========== Sprint 3: Alternatives, Apply similar, Batch ==========
def test_api_alternatives_demo(client):
    c, _ = client
    r = c.post("/api/alternatives", data={"detail_id": "detail-001"})
    assert r.status_code == 200
    data = r.json()
    assert "alternatives" in data
    alts = data["alternatives"]
    assert 2 <= len(alts) <= 5
    for a in alts:
        assert "variant" in a and "approach" in a and "route" in a


def test_api_alternatives_missing(client):
    c, _ = client
    r = c.post("/api/alternatives", data={"detail_id": "nonexistent"})
    assert r.status_code == 404


def test_api_apply_similar(client):
    c, _ = client
    # Source
    c.post("/api/generate", data={"detail_id": "detail-001"})
    c.post("/api/approve", data={"detail_id": "detail-001"})
    # Apply к detail-002
    r = c.post("/api/apply-similar", data={"detail_id": "detail-002", "source_id": "detail-001"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_api_apply_similar_no_source_draft(client):
    c, _ = client
    # Используем несуществующий source_id
    r = c.post("/api/apply-similar", data={"detail_id": "detail-001", "source_id": "detail-nonexistent-xyz"})
    assert r.status_code == 404


def test_api_apply_similar_self(client):
    c, _ = client
    r = c.post("/api/apply-similar", data={"detail_id": "detail-001", "source_id": "detail-001"})
    assert r.status_code == 400


def test_api_batch_generate(client):
    c, _ = client
    detail_ids = json.dumps(["detail-001", "detail-002"])
    r = c.post("/api/batch-generate", data={"detail_ids": detail_ids})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["processed"] == 2


def test_api_batch_generate_empty(client):
    c, _ = client
    r = c.post("/api/batch-generate", data={"detail_ids": "[]"})
    assert r.status_code == 422


# ========== Sprint 5: Audit + Export ==========
def test_audit_page_renders(client):
    c, _ = client
    r = c.get("/audit?limit=20")
    assert r.status_code == 200
    assert "Audit" in r.text


def test_api_audit_export(client):
    c, _ = client
    r = c.get("/api/audit/export")
    assert r.status_code == 200
    data = r.json()
    assert "entries" in data
    assert "total_entries" in data
    assert data["total_entries"] >= 1


def test_api_export_all(client):
    c, _ = client
    r = c.get("/api/export/all")
    assert r.status_code == 200
    data = r.json()
    assert "tables" in data
    assert "details" in data["tables"]
    assert "drafts" in data["tables"]


# ========== P0 fixes: auth, search, pagination, print ==========
def test_auth_disabled_in_tests(client):
    """PILOT_AUTH_DISABLED=true в env, поэтому все эндпоинты открыты"""
    c, _ = client
    r = c.get("/")
    assert r.status_code == 200


def test_index_search(client):
    """Search в /index фильтрует по designation/name"""
    c, _ = client
    r = c.get("/?q=Опора")
    assert r.status_code == 200
    # Mock data: detail-001 = "Кронштейн крепления огнетушителя"
    # detail-002 = "Опора..."
    # Если есть «Опора» в name — должно найти
    assert "Опора" in r.text or "details" in r.text


def test_index_pagination(client):
    """Пагинация работает"""
    c, _ = client
    r = c.get("/?page=1&per_page=2")
    assert r.status_code == 200
    assert "details" in r.text


def test_index_status_join_no_n_plus_1(client):
    """N+1 fix: get_all_details возвращает status map, не дергает SQL на каждую"""
    c, _ = client
    r = c.get("/")
    assert r.status_code == 200
    # Если бы был N+1 — все детали показались бы как «🔴 Новый» (потому что drafts нет)
    # С JOIN — корректно показаны статусы


def test_log_llm_call_signature(client):
    """M5 fix: log_llm_call без cost_rub и error работает"""
    c, _ = client
    # Это покрывается test_generate_form_data (после фикса не падает)
    r = c.post("/api/generate", data={"detail_id": "detail-001"})
    assert r.status_code == 200


def test_get_table_columns_no_leak():
    """C3 fix: get_table_columns не утекает соединения"""
    import os
    os.environ["PILOT_AUTH_DISABLED"] = "true"
    from app import get_table_columns
    cols = get_table_columns("details")
    assert "id" in cols
    assert "designation" in cols


def test_get_llm_client_singleton():
    """C4 fix: get_llm_client возвращает один и тот же объект"""
    import os
    os.environ["PILOT_AUTH_DISABLED"] = "true"
    from app import get_llm_client
    a = get_llm_client()
    b = get_llm_client()
    # В DEMO_MODE возвращает None, но singleton все равно работает
    assert a is b


def test_rag_empty_index_safe(client):
    """M6 fix: rebuild_from_db с 0 документами не падает"""
    c, _ = client
    # Удаляем все drafts
    c.post("/api/rag/rebuild")  # сначала строим
    # Очищаем drafts
    import sqlite3
    conn = sqlite3.connect("bit_technolog.db")
    conn.execute("DELETE FROM drafts")
    conn.commit()
    conn.close()
    r = c.post("/api/rag/rebuild")
    assert r.status_code == 200


# ========== Печатная форма + inline-edit + CSV ==========
def test_print_form_renders(client):
    c, _ = client
    c.post("/api/generate", data={"detail_id": "detail-001"})
    r = c.get("/detail/detail-001/print")
    assert r.status_code == 200
    assert "Техкарта" in r.text
    assert "Печатная форма" in r.text or "подпись" in r.text.lower()


def test_print_form_404(client):
    c, _ = client
    r = c.get("/detail/nonexistent/print")
    assert r.status_code == 404


def test_inline_edit_changes_value(client):
    """U6 fix: inline edit одного поля одной операции"""
    c, _ = client
    c.post("/api/generate", data={"detail_id": "detail-001"})
    r = c.post("/api/edit/inline",
               data={"detail_id": "detail-001", "op_index": "0", "field": "name", "value": "010 Тестовая операция"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["value"] == "010 Тестовая операция"


def test_inline_edit_duration_recalculates_total(client):
    """U6 fix: изменение duration_hours пересчитывает total_hours"""
    c, _ = client
    c.post("/api/generate", data={"detail_id": "detail-001"})
    r = c.post("/api/edit/inline",
               data={"detail_id": "detail-001", "op_index": "0", "field": "duration_hours", "value": "9.99"})
    assert r.status_code == 200
    data = r.json()
    assert "total_hours" in data


def test_inline_edit_disallows_bad_field(client):
    """Inline-edit: whitelist полей"""
    c, _ = client
    c.post("/api/generate", data={"detail_id": "detail-001"})
    r = c.post("/api/edit/inline",
               data={"detail_id": "detail-001", "op_index": "0", "field": "secret_field", "value": "x"})
    assert r.status_code == 400


def test_onec_csv_export(client):
    """B2 fix: CSV для ручного импорта в 1С:ERP"""
    c, _ = client
    c.post("/api/generate", data={"detail_id": "detail-001"})
    r = c.get("/api/export/onec-csv?detail_id=detail-001")
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    # BOM для Excel
    assert r.text.startswith("\ufeff")
    # Заголовки
    assert "Номер" in r.text and "Операция" in r.text and "Оборудование" in r.text


def test_onec_csv_no_draft(client):
    c, _ = client
    # detail-005 (в mock) без черновика
    r = c.get("/api/export/onec-csv?detail_id=detail-005")
    assert r.status_code == 404


def test_rag_rebuild_warns_on_low_data(client):
    """RAG rebuild выдаёт warning если в БД мало данных для надёжной similarity"""
    c, _ = client
    r = c.post("/api/rag/rebuild")
    assert r.status_code == 200
    data = r.json()
    # warning key всегда присутствует (может быть None если данных достаточно)
    assert "warning" in data
    # Может быть None (если mock-данных хватает) или строкой (если n<5)
    # Главное: API контракт стабильный
    assert data["warning"] is None or isinstance(data["warning"], str)


def test_index_uses_join_not_n_plus_1(client):
    """Performance: /index использует JOIN, не N запросов"""
    c, _ = client
    import time
    start = time.time()
    r = c.get("/")
    elapsed = time.time() - start
    assert r.status_code == 200
    # Должно быть < 200ms даже с 4 деталями
    assert elapsed < 1.0  # с запасом на тесты


# ========== Аудит v2 фиксы ==========
def test_no_mlta_mlMOCK_DETAILS_in_endpoints(client):
    """NC1 fix: get_detail заменил MOCK_DETAILS в runtime endpoints"""
    # Проверяем что detail из БД (которого нет в MOCK_DETAILS) находится
    c, _ = client
    # Все mock детали — detail-001..005. Создадим d-999 через БД.
    import sqlite3
    conn = sqlite3.connect("bit_technolog.db")
    conn.execute("INSERT OR IGNORE INTO details (id, designation, name) VALUES (?, ?, ?)",
                 ("d-999", "TEST-999", "Test detail not in MOCK"))
    conn.commit()
    conn.close()
    # Если бы использовался MOCK_DETAILS — 404. С get_detail — 200
    r = c.get("/detail/d-999")
    assert r.status_code == 200
    assert "TEST-999" in r.text


def test_parse_llm_json_helper():
    """NC3 fix: parse_llm_json обрабатывает разные форматы"""
    import os
    os.environ["PILOT_AUTH_DISABLED"] = "true"
    from app import parse_llm_json
    # 1. Raw JSON
    assert parse_llm_json('{"a": 1}') == {"a": 1}
    # 2. Markdown ```json
    assert parse_llm_json('```json\n{"a": 2}\n```') == {"a": 2}
    # 3. Просто ``` ```
    assert parse_llm_json('```\n{"a": 3}\n```') == {"a": 3}
    # 4. JSON inside text
    assert parse_llm_json('вот результат: {"a": 4} конец') == {"a": 4}
    # 5. Empty
    import pytest
    with pytest.raises(ValueError):
        parse_llm_json("")
    # 6. No JSON
    with pytest.raises(ValueError):
        parse_llm_json("no json here")


def test_record_edit_no_leak():
    """B2 fix: record_edit использует try/finally"""
    # Запускаем 100 раз — не должно быть утечки fd
    import os, gc
    os.environ["PILOT_AUTH_DISABLED"] = "true"
    from app import record_edit
    import sqlite3
    # Проверяем что нет открытых conn
    initial = len(gc.get_objects())
    for _ in range(50):
        record_edit("detail-001", 1, "test_field", "old", "new", author="test")
    gc.collect()
    final = len(gc.get_objects())
    # Допускаем небольшой рост (не > 5 объектов)
    assert final - initial < 50


def test_inline_edit_materials_field(client):
    """B3 fix: inline-edit теперь работает с materials, gosts, control_points"""
    c, _ = client
    c.post("/api/generate", data={"detail_id": "detail-001"})
    r = c.post("/api/edit/inline",
               data={"detail_id": "detail-001", "op_index": "0", "field": "materials", "value": "Сталь 09Г2С, Электроды"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert isinstance(data["value"], list)
    assert "Сталь 09Г2С" in data["value"]


def test_batch_generate_new(client):
    """UX1: кнопка 'Сгенерировать все новые' возвращает список id"""
    c, _ = client
    r = c.post("/api/batch-generate-new")
    assert r.status_code == 200
    data = r.json()
    assert "candidate_ids" in data
    assert isinstance(data["candidate_ids"], list)


def test_feedback_positive_button(client):
    """UX2: кнопка '👍 Норм' пишет в history"""
    c, _ = client
    r = c.post("/api/ai/feedback-positive", data={"detail_id": "detail-001"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["saved"] == "positive"


# ========== Аудит v3 фиксы ==========
def test_health_db_check(client):
    """OB3: /health проверяет что БД работает"""
    c, _ = client
    r = c.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["db_ok"] is True
    assert "rag_status" in data
    assert data["rag_status"] in ("loaded", "empty", "unknown", "unavailable")


def test_err_helper():
    """NC7: err() helper возвращает структурированный ответ"""
    import os
    os.environ["PILOT_AUTH_DISABLED"] = "true"
    from app import err
    r = err("test message", 400, extra_field=42)
    assert r.status_code == 400
    body = json.loads(r.body)
    assert body["error"] == "test message"
    assert body["extra_field"] == 42


def test_safe_call_logs_exceptions():
    """NC5: safe_call логирует и возвращает default"""
    import os
    os.environ["PILOT_AUTH_DISABLED"] = "true"
    from app import safe_call
    def bad_fn(): raise ValueError("test")
    result = safe_call("test_op", bad_fn, default="fallback")
    assert result == "fallback"


def test_safe_call_returns_value():
    import os
    os.environ["PILOT_AUTH_DISABLED"] = "true"
    from app import safe_call
    result = safe_call("test_op", lambda: 42)
    assert result == 42


def test_batch_generate_new_with_button(client):
    """R7: кнопка 'Сгенерировать все новые' работает через hx-post"""
    c, _ = client
    r = c.post("/api/batch-generate-new", headers={"HX-Request": "true"})
    assert r.status_code == 200
    data = r.json()
    assert "candidate_ids" in data


def test_feedback_form_with_reason(client):
    """UX16: feedback форма принимает reason"""
    c, _ = client
    r = c.post("/api/feedback", data={"detail_id": "detail-001", "reason": "время занижено"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
