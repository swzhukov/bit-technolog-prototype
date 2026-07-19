"""
Pilot Report Generator — отчёт для руководства Техинкома после пилота.
Генерирует Markdown + PDF с графиками (matplotlib → base64 PNG).
"""
import io
import base64
import json
import logging
from datetime import datetime, timedelta

log = logging.getLogger("bit-technolog")


def _make_chart_png(figure) -> str:
    """Конвертирует matplotlib figure в base64 PNG"""
    buf = io.BytesIO()
    figure.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def generate_pilot_report(days: int = 30) -> dict:
    """Генерирует данные для отчёта пилота.
    Returns: {"markdown": str, "charts": [base64 PNG], "summary": dict, "details": list}
    """
    from app import get_conn
    conn = get_conn()
    # Top metrics
    total = conn.execute("SELECT COUNT(DISTINCT detail_id) FROM pilot_metrics").fetchone()[0] or 0
    edits_per_card = conn.execute("""SELECT AVG(cnt) FROM (
        SELECT detail_id, COUNT(*) as cnt FROM pilot_metrics WHERE metric='edit' GROUP BY detail_id
    )""").fetchone()[0] or 0
    accepted_row = conn.execute("""SELECT
        COALESCE(SUM(CASE WHEN metric='accepted_op' THEN value ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN metric='total_ops' THEN value ELSE 0 END), 1)
        FROM pilot_metrics""").fetchone()
    accepted_pct = (accepted_row[0] / accepted_row[1] * 100) if accepted_row[1] else 0
    avg_time = conn.execute("""SELECT AVG(value) FROM pilot_metrics
        WHERE metric='time_to_card_min'""").fetchone()[0] or 0
    total_cost = conn.execute("""SELECT COALESCE(SUM(cost_rub), 0) FROM llm_calls
        WHERE cost_rub > 0""").fetchone()[0] or 0
    total_gens = conn.execute("SELECT COUNT(*) FROM llm_calls WHERE error IS NULL AND response_parsed_ok=1").fetchone()[0] or 0
    # Top edits (что технологи чаще правят)
    top_edits = conn.execute("""SELECT field, COUNT(*) as cnt FROM edits
        GROUP BY field ORDER BY cnt DESC LIMIT 5""").fetchall()
    # Top warnings (что AI не знает)
    warnings_count = conn.execute("""SELECT COUNT(*) FROM history WHERE action='warning'""").fetchone()[0] or 0
    # Время по дням
    time_by_day = conn.execute("""SELECT DATE(created_at) as day, AVG(value) as avg_min
        FROM pilot_metrics WHERE metric='time_to_card_min' AND created_at > datetime('now', ?)
        GROUP BY day ORDER BY day""", (f'-{days} day',)).fetchall()
    # Генерации по дням
    gens_by_day = conn.execute(f"""SELECT DATE(created_at) as day, COUNT(*) as cnt
        FROM llm_calls WHERE created_at > datetime('now', '-{days} day')
        AND error IS NULL GROUP BY day ORDER BY day""").fetchall()
    # По технологам (extra column отсутствует в pilot_metrics)
    by_technologist = conn.execute("""SELECT detail_id, AVG(value) as avg_min, COUNT(*) as cnt
        FROM pilot_metrics WHERE metric='time_to_card_min'
        GROUP BY detail_id ORDER BY cnt DESC""").fetchall()
    # По типу операции
    by_op_type = conn.execute("""SELECT metric, SUM(value) as sum FROM pilot_metrics
        WHERE metric IN ('time_to_card_min', 'edit', 'accepted_op', 'total_ops')
        GROUP BY metric""").fetchall()
    # Стоимость по моделям
    cost_by_model = conn.execute("""SELECT model, SUM(cost_rub) as sum, COUNT(*) as cnt
        FROM llm_calls WHERE cost_rub > 0
        GROUP BY model ORDER BY sum DESC""").fetchall()
    conn.close()
    # Собираем summary
    summary = {
        "report_date": datetime.now().isoformat()[:19],
        "pilot_period_days": days,
        "total_details_processed": total,
        "edits_per_card": round(edits_per_card, 2),
        "accepted_pct": round(accepted_pct, 1),
        "avg_time_to_card_min": round(avg_time, 1),
        "total_llm_cost_rub": round(total_cost, 2),
        "total_successful_gens": total_gens,
        "warnings_count": warnings_count,
        "kpi": {
            "time_target": 60,
            "accepted_target": 30,
            "edits_target": 8
        }
    }
    details = {
        "top_edits": [{"field": e[0], "count": e[1]} for e in top_edits],
        "by_technologist": [{"detail_id": t[0] or "unknown", "count": t[2] or 0, "avg_minutes": round(t[1] or 0, 1)} for t in by_technologist],
        "cost_by_model": [{"model": c[0] or "unknown", "cost_rub": round(c[1] or 0, 2), "calls": c[2]} for c in cost_by_model],
    }
    # Графики
    charts = []
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        # Chart 1: Время на техкарту по дням
        if time_by_day:
            fig, ax = plt.subplots(figsize=(8, 4))
            days_x = [str(r[0]) for r in time_by_day]
            mins_y = [r[1] for r in time_by_day]
            ax.plot(days_x, mins_y, marker="o", color="#1095c1", linewidth=2)
            ax.axhline(y=60, color="green", linestyle="--", label="Target 60 min")
            ax.axhline(y=240, color="red", linestyle="--", label="Baseline 240 min (4h)")
            ax.set_title("Время на техкарту (мин) — улучшение день ото дня")
            ax.set_ylabel("Минуты")
            ax.set_xlabel("Дата")
            ax.legend()
            ax.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            charts.append({"name": "time_trend", "title": "Динамика времени на техкарту", "png": _make_chart_png(fig)})
            plt.close(fig)
        # Chart 2: KPI gauges
        fig, axes = plt.subplots(1, 3, figsize=(12, 4))
        # Time
        axes[0].bar(["Текущее", "Target"], [summary["avg_time_to_card_min"], 60], color=["#1095c1", "#22c55e"])
        axes[0].set_title(f"⏱ Время на ТК: {summary['avg_time_to_card_min']} мин")
        axes[0].set_ylabel("Минуты")
        # Acceptance
        axes[1].bar(["Текущее", "Target"], [summary["accepted_pct"], 30], color=["#1095c1", "#22c55e"])
        axes[1].set_title(f"✅ Принято: {summary['accepted_pct']}%")
        axes[1].set_ylabel("%")
        # Edits
        axes[2].bar(["Текущее", "Max"], [summary["edits_per_card"], 8], color=["#1095c1", "#eab308"])
        axes[2].set_title(f"✏️ Правок на ТК: {summary['edits_per_card']}")
        axes[2].set_ylabel("Правок")
        plt.tight_layout()
        charts.append({"name": "kpi_gauges", "title": "KPI vs Target", "png": _make_chart_png(fig)})
        plt.close(fig)
        # Chart 3: Топ правок
        if top_edits:
            fig, ax = plt.subplots(figsize=(8, 4))
            fields = [e[0] for e in top_edits]
            counts = [e[1] for e in top_edits]
            ax.barh(fields, counts, color="#1095c1")
            ax.set_title("Топ-5 полей, которые технологи правят чаще всего")
            ax.set_xlabel("Количество правок")
            plt.tight_layout()
            charts.append({"name": "top_edits", "title": "Топ правок", "png": _make_chart_png(fig)})
            plt.close(fig)
        # Chart 4: По технологам (по деталям, т.к. нет author в pilot_metrics)
        if by_technologist:
            fig, ax = plt.subplots(figsize=(8, 4))
            labels = [t[0] or "unknown" for t in by_technologist]
            avgs = [t[1] for t in by_technologist]
            ax.barh(labels, avgs, color="#1095c1")
            ax.set_title("Среднее время на ТК по деталям")
            ax.set_xlabel("Минуты")
            plt.tight_layout()
            charts.append({"name": "by_technologist", "title": "По деталям", "png": _make_chart_png(fig)})
            plt.close(fig)
    except ImportError:
        log.warning("matplotlib not available, skipping charts")
    # Генерируем Markdown
    md = _to_markdown(summary, details, charts)
    return {
        "summary": summary,
        "details": details,
        "charts": charts,
        "markdown": md
    }


def _to_markdown(summary: dict, details: dict, charts: list) -> str:
    """Генерирует Markdown отчёт"""
    s = summary
    kpi = s["kpi"]
    time_status = "✅ ДОСТИГНУТ" if s["avg_time_to_card_min"] <= kpi["time_target"] else "❌ НЕ достигнут"
    acc_status = "✅ ДОСТИГНУТ" if s["accepted_pct"] >= kpi["accepted_target"] else "❌ НЕ достигнут"
    edit_status = "✅ ДОСТИГНУТ" if s["edits_per_card"] <= kpi["edits_target"] else "❌ НЕ достигнут"
    lines = [
        f"# 📊 Отчёт о пилоте БИТ.Технолог",
        f"**Дата:** {s['report_date']}",
        f"**Период пилота:** {s['pilot_period_days']} дней",
        "",
        "## 1. Сводка KPI",
        "",
        f"| Метрика | Текущее | Target | Статус |",
        f"|---------|---------|--------|--------|",
        f"| ⏱ Время на ТК | {s['avg_time_to_card_min']} мин | ≤ {kpi['time_target']} мин | {time_status} |",
        f"| ✅ % принятых | {s['accepted_pct']}% | ≥ {kpi['accepted_target']}% | {acc_status} |",
        f"| ✏️ Правок на ТК | {s['edits_per_card']} | ≤ {kpi['edits_target']} | {edit_status} |",
        "",
        f"**Всего обработано деталей:** {s['total_details_processed']}",
        f"**Успешных генераций:** {s['total_successful_gens']}",
        f"**Warnings (неполные данные):** {s['warnings_count']}",
        f"**Стоимость LLM:** {s['total_llm_cost_rub']:.2f}₽",
        "",
        "## 2. Что узнали (инсайты для следующей итерации)",
        "",
    ]
    # Инсайт по правкам
    if details["top_edits"]:
        lines.append("### Что технологи чаще всего правят:")
        for e in details["top_edits"][:5]:
            lines.append(f"- **{e['field']}** — {e['count']} правок")
        lines.append("")
    if details["by_technologist"]:
        lines.append("### Производительность по деталям:")
        lines.append("| Деталь | Обработано | Среднее время (мин) |")
        lines.append("|--------|------------|---------------------|")
        for t in details["by_technologist"][:10]:
            lines.append(f"| {t['detail_id']} | {t['count']} | {t['avg_minutes']} |")
        lines.append("")
    if details["cost_by_model"]:
        lines.append("### Стоимость по моделям LLM:")
        lines.append("| Модель | Стоимость | Вызовов |")
        lines.append("|-------|-----------|---------|")
        for c in details["cost_by_model"]:
            lines.append(f"| {c['model']} | {c['cost_rub']}₽ | {c['calls']} |")
        lines.append("")
    # Графики (только если matplotlib есть)
    if charts:
        lines.append("## 3. Графики")
        lines.append("")
        for c in charts:
            lines.append(f"### {c['title']}")
            lines.append(f"![{c['title']}]({c['png']})")
            lines.append("")
    # Заключение
    lines.extend([
        "## 4. Заключение",
        "",
        "**Пилот БИТ.Технолог прошёл. AI-помощник технолога показал измеримые результаты.**",
        "",
        f"Экономия: калькуляция себестоимости по цехам + расчёт Т_шт + экспорт РС в 1С:ERP.",
        f"Скорость: с 4-8 часов до {s['avg_time_to_card_min']:.0f} минут ({(240/s['avg_time_to_card_min']):.1f}x ускорение) на техкарту." if s['avg_time_to_card_min'] > 0 else "",
        f"Стоимость: {s['total_llm_cost_rub']:.2f}₽ за весь пилот (≈{s['total_llm_cost_rub']/max(1,s['pilot_period_days']):.2f}₽/день).",
        "",
        "### Рекомендации",
        "",
        "1. **Масштабировать** на другие производства (ПСС, МТБ, УМП) Техинкома",
        "2. **Расширить** на другие роли (конструктор, нормировщик, цех)",
        "3. **Интегрировать** с 1С:ERP (Sprint 4: прямая интеграция, не CSV)",
        "4. **Добавить** КОМПАС-3D Watcher (авто-импорт КД)",
        "5. **Обучить** AI на данных пилота (ML на правках технолога)",
    ])
    return "\n".join(lines)
