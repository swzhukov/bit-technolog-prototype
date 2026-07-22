"""
evidence.py — «Норма с доказательством» (Sprint 5).

Киллер-фича: каждая норма имеет источник (эталон / аналог / догадка AI)
и светофор (зелёный/жёлтый/красный/серый).

Использует:
- services.rag.find_analogs (поиск аналогов в эталонах)
- repositories.db (для обновления source операции)

Принцип (из разбора v2):
- Ступень 4 ML-лестницы: петля обратной связи
- Каждая операция ТК привязана к источнику нормы
- Технолог видит: «эта норма — из эталона / аналога / догадки AI»
"""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from repositories import db
from services.rag import find_analogs, AnalogMatch, invalidate_cache

logger = logging.getLogger(__name__)


# ============================================================
# ИСТОЧНИКИ НОРМЫ
# ============================================================

class Source(str, Enum):
    FACTORY_DATA = "factory_data"      # Из утверждённого ТП
    ANALOG_ESTIMATE = "analog_estimate"  # Оценка по аналогам
    AI_GUESS = "ai_guess"              # Предположение AI
    MANUAL = "manual"                   # Вручную технологом


SOURCE_LABELS = {
    Source.FACTORY_DATA.value: "Эталон",
    Source.ANALOG_ESTIMATE.value: "По аналогу",
    Source.AI_GUESS.value: "Предположение AI",
    Source.MANUAL.value: "Вручную",
}


# ============================================================
# СВЕТОФОР
# ============================================================

class EvidenceLevel(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    GRAY = "gray"


LEVEL_LABELS = {
    EvidenceLevel.GREEN.value: "Подтверждено",
    EvidenceLevel.YELLOW.value: "Похоже на правду",
    EvidenceLevel.RED.value: "Предположение AI",
    EvidenceLevel.GRAY.value: "Нет данных",
}


@dataclass
class OperationEvidence:
    """Доказательство для одной операции."""
    operation_id: int
    op_number: int
    op_name: str
    time_per_unit_min: float
    source: str
    evidence_level: str
    source_label: str
    level_label: str
    analogs: List[AnalogMatch]
    note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "op_number": self.op_number,
            "op_name": self.op_name,
            "time_per_unit_min": self.time_per_unit_min,
            "source": self.source,
            "evidence_level": self.evidence_level,
            "source_label": self.source_label,
            "level_label": self.level_label,
            "analogs": [
                {
                    "etalon_designation": a.etalon_designation,
                    "etalon_name": a.etalon_name,
                    "operation_name": a.operation_name,
                    "similarity": a.similarity,
                    "time_per_unit_min": a.time_per_unit_min,
                    "reason": a.reason,
                }
                for a in self.analogs
            ],
            "note": self.note,
        }


# ============================================================
# СБОРКА ДОКАЗАТЕЛЬСТВ ДЛЯ ОПЕРАЦИЙ
# ============================================================

def collect_evidence_for_tech_card(tech_card_id: int) -> List[OperationEvidence]:
    """Собрать доказательства для всех операций ТК.

    Алгоритм:
    1. Загрузить ТК и операции
    2. Для каждой операции:
       a. Если source=factory_data (эталон) → 🟢 зелёный
       b. Иначе ищем аналоги в RAG
       c. Если аналог 🟢 (similarity >0.9) → 🟡 жёлтый
       d. Если аналог 🟡 (similarity 0.5-0.9) → 🟡 жёлтый
       e. Иначе → 🔴 красный
    3. Если вообще нет аналогов → ⚪ серый
    """
    tc = db.get_tech_card_full(tech_card_id)
    if not tc:
        return []

    evidences = []
    for op in tc.get("operations", []):
        op_id = op.get("id")
        op_num = op.get("op_number", 0)
        op_name = op.get("name", "")
        tpu = op.get("time_per_unit_min", 0) or 0
        existing_source = op.get("source") or Source.AI_GUESS.value

        # Если source = factory_data — это готовое подтверждение
        if existing_source == Source.FACTORY_DATA.value:
            evidences.append(OperationEvidence(
                operation_id=op_id,
                op_number=op_num,
                op_name=op_name,
                time_per_unit_min=tpu,
                source=Source.FACTORY_DATA.value,
                evidence_level=EvidenceLevel.GREEN.value,
                source_label=SOURCE_LABELS[Source.FACTORY_DATA.value],
                level_label=LEVEL_LABELS[EvidenceLevel.GREEN.value],
                analogs=[],
                note="Норма взята из утверждённого ТП-эталона",
            ))
            continue

        # Иначе — ищем аналоги
        material = None
        for m in op.get("materials", []):
            if m.get("code"):
                material = m["code"]
                break

        analogs = find_analogs(
            operation_name=op_name,
            material=material,
            top_k=3,
        )

        if not analogs:
            # Нет аналогов
            evidences.append(OperationEvidence(
                operation_id=op_id,
                op_number=op_num,
                op_name=op_name,
                time_per_unit_min=tpu,
                source=Source.AI_GUESS.value,
                evidence_level=EvidenceLevel.GRAY.value,
                source_label=SOURCE_LABELS[Source.AI_GUESS.value],
                level_label=LEVEL_LABELS[EvidenceLevel.GRAY.value],
                analogs=[],
                note="В базе эталонов нет аналогов. Норма — гипотеза AI, требует подтверждения технолога.",
            ))
        elif analogs[0].evidence_level == EvidenceLevel.GREEN.value:
            # Есть очень похожий аналог — берём его время
            best = analogs[0]
            evidences.append(OperationEvidence(
                operation_id=op_id,
                op_number=op_num,
                op_name=op_name,
                time_per_unit_min=tpu,
                source=Source.ANALOG_ESTIMATE.value,
                evidence_level=EvidenceLevel.YELLOW.value,
                source_label=SOURCE_LABELS[Source.ANALOG_ESTIMATE.value],
                level_label=LEVEL_LABELS[EvidenceLevel.YELLOW.value],
                analogs=analogs,
                note=f"Норма похожа на аналог: {best.etalon_designation} (сходство {best.similarity*100:.0f}%). Подтвердите или скорректируйте.",
            ))
        elif analogs[0].evidence_level == EvidenceLevel.YELLOW.value:
            evidences.append(OperationEvidence(
                operation_id=op_id,
                op_number=op_num,
                op_name=op_name,
                time_per_unit_min=tpu,
                source=Source.ANALOG_ESTIMATE.value,
                evidence_level=EvidenceLevel.YELLOW.value,
                source_label=SOURCE_LABELS[Source.ANALOG_ESTIMATE.value],
                level_label=LEVEL_LABELS[EvidenceLevel.YELLOW.value],
                analogs=analogs,
                note=f"Слабый аналог. Технологу рекомендуется проверить.",
            ))
        else:
            evidences.append(OperationEvidence(
                operation_id=op_id,
                op_number=op_num,
                op_name=op_name,
                time_per_unit_min=tpu,
                source=Source.AI_GUESS.value,
                evidence_level=EvidenceLevel.RED.value,
                source_label=SOURCE_LABELS[Source.AI_GUESS.value],
                level_label=LEVEL_LABELS[EvidenceLevel.RED.value],
                analogs=analogs,
                note="Предположение AI. Эталонов в базе нет.",
            ))

    return evidences


# ============================================================
# ОБНОВЛЕНИЕ ОПЕРАЦИИ (от технолога)
# ============================================================

def update_operation_evidence(
    operation_id: int,
    new_time: float,
    user: str,
    note: str = "",
) -> bool:
    """Технолог подтвердил или скорректировал норму.

    После подтверждения:
    1. Обновить time_per_unit_min
    2. Поставить source = factory_data
    3. Записать в edits (для петли обратной связи)
    4. Обновить evidence_json
    """
    op = db.query_one("SELECT * FROM operations WHERE id = ?", (operation_id,))
    if not op:
        return False

    old_time = op["time_per_unit_min"] or 0
    if abs(new_time - old_time) < 0.001:
        return True  # без изменений

    # Запись в edits
    db.execute("""
        INSERT INTO edits (operation_id, field, old_value, new_value, user, reason)
        VALUES (?, 'time_per_unit_min', ?, ?, ?, ?)
    """, (operation_id, str(old_time), str(new_time), user, note))

    # Обновление операции
    db.execute("""
        UPDATE operations
        SET time_per_unit_min = ?, source = 'factory_data', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (new_time, operation_id))

    return True


# ============================================================
# СВОДКА ДЛЯ DASHBOARD
# ============================================================

def tech_card_evidence_summary(tech_card_id: int) -> Dict[str, Any]:
    """Сводка по операциям ТК для дашборда."""
    evidences = collect_evidence_for_tech_card(tech_card_id)
    total = len(evidences)
    if total == 0:
        return {"total": 0, "green": 0, "yellow": 0, "red": 0, "gray": 0, "green_pct": 0}

    green = sum(1 for e in evidences if e.evidence_level == EvidenceLevel.GREEN.value)
    yellow = sum(1 for e in evidences if e.evidence_level == EvidenceLevel.YELLOW.value)
    red = sum(1 for e in evidences if e.evidence_level == EvidenceLevel.RED.value)
    gray = sum(1 for e in evidences if e.evidence_level == EvidenceLevel.GRAY.value)
    green_pct = round(green * 100 / total)

    return {
        "total": total,
        "green": green,
        "yellow": yellow,
        "red": red,
        "gray": gray,
        "green_pct": green_pct,
    }


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    print("=== Evidence (Норма с доказательством) ===")

    # Найдём ТК
    tc = db.query_one("SELECT id FROM tech_cards ORDER BY id DESC LIMIT 1")
    if not tc:
        print("Нет ТК в БД")
        sys.exit(0)

    print(f"ТК ID: {tc['id']}")
    evidences = collect_evidence_for_tech_card(tc["id"])
    for e in evidences:
        print(f"  {e.evidence_level:5s} {e.level_label:25s} | {e.op_number:03d} {e.op_name[:40]}")
        for a in e.analogs:
            print(f"           └ {a.etalon_designation} → {a.operation_name[:30]} (sim={a.similarity*100:.0f}%)")

    summary = tech_card_evidence_summary(tc["id"])
    print(f"\nСводка: {summary}")
