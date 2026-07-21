"""
rag.py — RAG (Retrieval-Augmented Generation) по эталонам.

Sprint 5: «Норма с доказательством»

Поиск аналогов по эталонам для подтверждения норм.

Использует:
1. TF-IDF по тексту операций (названия + материалы)
2. Структурные фильтры (материал, тип операции, масса)

Принцип (из разбора v2):
- Ступень 2 ML-лестницы: RAG + структурные фильтры
- TF-IDF сейчас, гибридный (эмбеддинги + структура) — потом
"""
from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from repositories import db

logger = logging.getLogger(__name__)


@dataclass
class EtalonIndex:
    """Индекс одного эталона для поиска."""
    etalon_id: int
    designation: str
    name: str
    product_type: str
    operations: List[Dict[str, Any]]
    # TF-IDF: term -> tfidf_weight
    tfidf: Dict[str, float] = field(default_factory=dict)
    # Структурные признаки (Sprint 7 — RAG v2)
    materials: List[str] = field(default_factory=list)  # backwards compat (= material_codes)
    material_codes: List[str] = field(default_factory=list)
    material_ids: List[int] = field(default_factory=list)  # FK на materials
    operation_types: List[str] = field(default_factory=list)
    equipment_names: List[str] = field(default_factory=list)
    # Документ
    operations_text: str = ""  # Конкатенация названий операций


# ============================================================
# ПРОСТАЯ TF-IDF (наша реализация)
# ============================================================

# Русские стоп-слова
STOP_WORDS = {
    "и", "в", "на", "с", "по", "для", "из", "или", "неho", "не",
    "что", "это", "как", "так", "но", "а", "о", "к", "у", "от",
    "до", "при", "за", "же", "бы", "ли", "то", "все", "ей", "им",
    "её", "его", "если", "когда", "чтобы", "уже", "даже", "ещё",
    "или", "нет", "да", "нет", "может", "также", "очень", "только",
}


def _tokenize(text: str) -> List[str]:
    """Токенизация русского текста: приводим к нижнему регистру, оставляем слова."""
    text = text.lower()
    # Заменяем все небуквенные на пробелы
    text = re.sub(r"[^а-яa-z0-9]+", " ", text)
    tokens = text.split()
    return [t for t in tokens if t and t not in STOP_WORDS and len(t) > 1]


def _tf(tokens: List[str]) -> Dict[str, float]:
    """Term frequency."""
    counter = Counter(tokens)
    total = len(tokens) or 1
    return {t: c / total for t, c in counter.items()}


def _idf(documents_tokens: List[List[str]]) -> Dict[str, float]:
    """Inverse document frequency."""
    n_docs = len(documents_tokens)
    df = Counter()
    for tokens in documents_tokens:
        unique = set(tokens)
        for t in unique:
            df[t] += 1
    return {t: math.log((n_docs + 1) / (df_t + 1)) + 1 for t, df_t in df.items()}


def _build_tfidf(tokens: List[str], idf_map: Dict[str, float]) -> Dict[str, float]:
    tf = _tf(tokens)
    return {t: tf_t * idf_map.get(t, 0) for t, tf_t in tf.items()}


def _cosine(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    """Косинусное сходство двух разреженных векторов."""
    keys = set(v1.keys()) & set(v2.keys())
    if not keys:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in keys)
    norm1 = math.sqrt(sum(v ** 2 for v in v1.values())) or 1.0
    norm2 = math.sqrt(sum(v ** 2 for v in v2.values())) or 1.0
    return dot / (norm1 * norm2)


# ============================================================
# РАСПОЗНАВАНИЕ ТИПА ОПЕРАЦИИ
# ============================================================

OPERATION_TYPES = {
    "резка": ["резк", "раскрой", "гильотин", "нож"],
    "гибка": ["гибк", "вальц", "загиб"],
    "сварка": ["сварк", "наплавк", "привар"],
    "сборка": ["сборк", "установк", "правк", "зачистк"],
    "контроль": ["контрол", "осмотр", "испыта", "проверк"],
    "окраска": ["окраск", "грунтов", "покраск"],
    "механообработка": ["токарн", "фрезерн", "сверл", "шлифов"],
}


def detect_operation_type(name: str) -> str:
    """Определяет тип операции по названию."""
    name_lower = name.lower()
    for op_type, keywords in OPERATION_TYPES.items():
        for kw in keywords:
            if kw in name_lower:
                return op_type
    return "прочее"


# ============================================================
# ИНДЕКСАЦИЯ ЭТАЛОНОВ
# ============================================================

_etalons_cache: List[EtalonIndex] = []
_idf_map: Dict[str, float] = {}
_cache_loaded = False


def load_etalons(force: bool = False) -> List[EtalonIndex]:
    """Загрузить все опубликованные эталоны и построить индекс."""
    global _etalons_cache, _idf_map, _cache_loaded

    if _cache_loaded and not force:
        return _etalons_cache

    rows = db.query("""
        SELECT * FROM etalons
        WHERE is_published = 1
        ORDER BY approved_date DESC
    """)

    etalons = []
    all_tokens = []

    for row in rows:
        d = db.row_to_dict(row)
        content = d.get("content_json") or {}
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                content = {}

        operations = content.get("operations", [])
        # Соберём текст
        op_texts = []
        materials = set()
        material_ids = set()
        op_types = set()
        equipment_names = set()
        for op in operations:
            op_name = op.get("name", "")
            op_texts.append(op_name)
            op_types.add(detect_operation_type(op_name))
            # Sprint 7: material_id (FK) + equipment
            for m in op.get("materials", []):
                code = m.get("code", "") or m.get("name", "")
                if code:
                    materials.add(code)
                    mrow = db.query_one("SELECT id FROM materials WHERE code = ?", (code,))
                    if mrow:
                        material_ids.add(mrow["id"])
            if op.get("equipment_name"):
                equipment_names.add(op["equipment_name"])

        operations_text = " ".join(op_texts)
        tokens = _tokenize(operations_text + " " + d.get("name", ""))
        all_tokens.append(tokens)

        etalons.append(EtalonIndex(
            etalon_id=d["id"],
            designation=d["designation"],
            name=d["name"],
            product_type=d.get("product_type") or "",
            operations=operations,
            materials=list(materials),  # backwards compat
            material_codes=list(materials),
            material_ids=list(material_ids),
            operation_types=list(op_types),
            equipment_names=list(equipment_names),
            operations_text=operations_text,
        ))

    # Строим IDF по всем эталонам
    _idf_map = _idf(all_tokens) if all_tokens else {}

    # TF-IDF для каждого эталона
    for et, tokens in zip(etalons, all_tokens):
        et.tfidf = _build_tfidf(tokens, _idf_map)

    _etalons_cache = etalons
    _cache_loaded = True
    return etalons


def invalidate_cache():
    """Сброс кеша (после обновления эталонов)."""
    global _cache_loaded, _etalons_cache
    _cache_loaded = False
    _etalons_cache = []


# ============================================================
# ПОИСК АНАЛОГОВ
# ============================================================

@dataclass
class AnalogMatch:
    """Результат поиска аналога."""
    etalon_designation: str
    etalon_name: str
    operation_name: str
    operation_type: str
    time_per_unit_min: float
    similarity: float         # 0..1
    source: str               # "exact" | "analog" | "weak" | "none"
    evidence_level: str       # "green" | "yellow" | "red" | "gray"
    reason: str               # почему такой светофор


def find_analogs(
    operation_name: str,
    operation_type: Optional[str] = None,
    material: Optional[str] = None,
    material_id: Optional[int] = None,
    mass_kg: Optional[float] = None,
    top_k: int = 3,
) -> List[AnalogMatch]:
    """Найти аналоги операции в эталонах.

    Алгоритм:
    1. TF-IDF сходство по названию операции
    2. Бонус за совпадение типа операции
    3. Бонус за совпадение материала
    4. Итоговый score = 0.6*tfidf + 0.2*type_match + 0.2*material_match
    """
    etalons = load_etalons()
    if not etalons:
        return []

    # Подготовим запрос
    query_tokens = _tokenize(operation_name)
    if not query_tokens:
        return []
    query_tfidf = _build_tfidf(query_tokens, _idf_map)

    results = []
    detected_type = operation_type or detect_operation_type(operation_name)

    for et in etalons:
        for op in et.get("operations", []) if hasattr(et, "get") else et.operations:
            op_name = op.get("name", "")
            op_type_et = detect_operation_type(op_name)

            # 1. TF-IDF по операции
            op_tokens = _tokenize(op_name)
            if not op_tokens:
                continue
            op_tfidf = _build_tfidf(op_tokens, _idf_map)
            tfidf_score = _cosine(query_tfidf, op_tfidf)

            # 2. Совпадение типа
            type_bonus = 0.0
            if op_type_et == detected_type:
                type_bonus = 1.0
            elif detected_type in et.operation_types:
                type_bonus = 0.5

            # 3. Совпадение материала
            mat_bonus = 0.0
            if material:
                mat_lower = material.lower()
                if any(mat_lower in m.lower() for m in et.materials if m):
                    mat_bonus = 1.0

            # 4. Бонус за массу (если известна, ±50% от эталона)
            mass_bonus = 0.0
            if mass_kg and et.mass_kg:
                ratio = mass_kg / et.mass_kg
                if 0.5 <= ratio <= 2.0:
                    mass_bonus = 0.2  # до 20% бонуса за близкую массу
                elif 0.3 <= ratio <= 3.0:
                    mass_bonus = 0.1
                # Если разница > 3x — штраф
                if ratio > 5 or ratio < 0.2:
                    continue

            # Итоговый score
            score = 0.5 * tfidf_score + 0.2 * type_bonus + 0.2 * mat_bonus + 0.1 * mass_bonus
            if score < 0.1:
                continue

            # Уровень доказательства
            if score >= 0.9:
                level = "green"
                source = "exact"
                reason = "Полное совпадение (тот же эталон или очень похожая операция)"
            elif score >= 0.5:
                level = "yellow"
                source = "analog"
                reason = f"Аналог по типу операции ({op_type_et}), сходство {score*100:.0f}%"
            elif score >= 0.2:
                level = "red"
                source = "weak"
                reason = f"Слабый аналог (сходство {score*100:.0f}%)"
            else:
                continue

            results.append(AnalogMatch(
                etalon_designation=et.designation,
                etalon_name=et.name,
                operation_name=op_name,
                operation_type=op_type_et,
                time_per_unit_min=op.get("time_per_unit_min", 0) or 0,
                similarity=round(score, 3),
                source=source,
                evidence_level=level,
                reason=reason,
            ))

    # Сортируем по similarity, убираем дубликаты
    results.sort(key=lambda m: m.similarity, reverse=True)

    # Оставляем top_k лучших для каждой операции (но не для каждого совпадения внутри)
    seen = set()
    unique = []
    for r in results:
        key = (r.etalon_designation, r.operation_name)
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
        if len(unique) >= top_k:
            break

    return unique


# ============================================================
# ИНДЕКСАЦИЯ RAG
# ============================================================

def index_for_rag(etalon_id: int) -> bool:
    """Отметить эталон как проиндексированный в RAG."""
    from datetime import datetime
    db.execute(
        "UPDATE etalons SET rag_indexed_at = ? WHERE id = ?",
        (datetime.now().isoformat(), etalon_id)
    )
    invalidate_cache()
    return True


def index_all_published_etalons() -> int:
    """Проиндексировать все опубликованные эталоны."""
    rows = db.query("SELECT id FROM etalons WHERE is_published = 1")
    for r in rows:
        index_for_rag(r["id"])
    return len(rows)


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    print("=== RAG по эталонам ===")
    etalons = load_etalons(force=True)
    print(f"Загружено эталонов: {len(etalons)}")
    for et in etalons:
        print(f"  - {et.designation} «{et.name}» ({len(et.operations)} операций)")

    print()
    print("=== Поиск аналогов: 'Приварка ножей' ===")
    results = find_analogs("Приварка ножей", top_k=3)
    for r in results:
        print(f"  {r.evidence_level:5s} {r.similarity*100:5.1f}% | {r.etalon_designation} → {r.operation_name} (Тшт={r.time_per_unit_min})")
        print(f"         {r.reason}")
