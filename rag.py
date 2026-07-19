"""Sprint 2: RAG (Retrieval-Augmented Generation) на TF-IDF + cosine similarity.

Подход: on-prem, без внешних API. Использует scikit-learn TfidfVectorizer +
cosine similarity. Метаданные хранятся в SQLite (таблица details + drafts).

Преимущества:
- Полностью локальный (on-prem ready для ГОЗ)
- Бесплатный (без OpenAI API)
- Быстрый (для 50-1000 техкарт — мгновенно)
- Прозрачный (можно посмотреть какие слова важны)

Ограничения:
- TF-IDF не понимает синонимы (нужен sentence-transformers/OpenAI для этого)
- Маленький корпус (<50) даёт плохое ранжирование
- Это baseline — в Sprint 5 (enterprise) можно заменить на OpenAI embeddings
"""
import os
import json
import pickle
import logging
import re
from typing import List, Dict, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app import get_conn, MOCK_DETAILS

log = logging.getLogger("rag")
INDEX_DIR = os.path.join(os.path.dirname(__file__), ".rag")
VECTORIZER_PATH = os.path.join(INDEX_DIR, "vectorizer.pkl")
MATRIX_PATH = os.path.join(INDEX_DIR, "tfidf_matrix.pkl")
IDS_PATH = os.path.join(INDEX_DIR, "ids.pkl")
METADATA_PATH = os.path.join(INDEX_DIR, "metadata.pkl")

# ========== F16.2: Лемматизация (pymorphy2) и маппинг синонимов ==========
_MORPH = None
_MORPH_ERROR = None

def _get_morph():
    """Lazy-init pymorphy2. Если недоступен — fallback без лемматизации."""
    global _MORPH, _MORPH_ERROR
    if _MORPH is not None or _MORPH_ERROR:
        return _MORPH
    try:
        import pymorphy2
        _MORPH = pymorphy2.MorphAnalyzer()
        log.info("pymorphy2 loaded — лемматизация включена")
    except Exception as e:
        _MORPH_ERROR = str(e)
        log.warning(f"pymorphy2 недоступен ({e}) — лемматизация отключена")
    return _MORPH


# Маппинг синонимов для машиностроения (F16.2)
_SYNONYMS = {
    # Марки сталей (часто взаимозаменяемые)
    "ст3": "сталь3", "ст 3": "сталь3", "сталь3": "сталь3", "сталь 3": "сталь3",
    "ст3сп": "сталь3", "ст3пс": "сталь3", "ст3кп": "сталь3",
    "09г2с": "низколегир", "09г2с-15": "низколегир", "09г2с-12": "низколегир",
    # Термообработка
    "закалка": "термообработка", "отпуск": "термообработка", "отжиг": "термообработка",
    "ц": "цементация", "твч": "поверхностнаязакалка",
    # Сварка
    "mig": "полуавтсварка", "mag": "полуавтсварка", "tig": "аргонодуг",
    "рдс": "ручнаядуг", "mma": "ручнаядуг",
    # Оборудование (синонимы)
    "кедр": "инверторсварка", "тдф": "трансформаторсварка",
    "верстак": "слесарныйверстак", "тиски": "слесарныйверстак",
    # Покрытия
    "грунт": "грунтовка", "гф-021": "грунтовка", "гф021": "грунтовка",
    "пф-115": "эмаль", "пф115": "эмаль",
    "оцинковка": "цинковое", "горячийцинк": "цинковое",
    # Конструктивные элементы
    "кронштейн": "кронштейн", "упор": "кронштейн", "опора": "кронштейн",
    "косынка": "косынка", "ребро": "косынка",
    # Заготовки
    "лист": "листовой", "плита": "листовой", "полоса": "листовой",
    "труба": "трубный", "профиль": "трубный",
    "пруток": "сортовой", "круг": "сортовой", "квадрат": "сортовой",
}


def _apply_synonyms(text: str) -> str:
    """Заменяет синонимы на канонические термины."""
    t = " " + text.lower() + " "
    for syn, canon in _SYNONYMS.items():
        # word boundary
        t = re.sub(rf"\b{re.escape(syn)}\b", canon, t)
    return t.strip()


def _lemmatize_text(text: str) -> str:
    """F16.2: лемматизация + синонимы для русского технического текста.
    Возвращает нормализованный текст для лучшего TF-IDF matching."""
    morph = _get_morph()
    t = _apply_synonyms(text.lower())
    if not morph:
        return t
    words = re.findall(r"[а-яёa-z0-9\-]+", t)
    lemmas = []
    for w in words:
        # Пропускаем числа и короткие слова
        if w.replace("-", "").isdigit() or len(w) < 3:
            lemmas.append(w)
            continue
        try:
            # Первое нормальное значение (NOUN, ADJF, INFN etc.)
            parses = morph.parse(w)
            if parses and parses[0].score > 0.3:
                lemmas.append(parses[0].normal_form)
            else:
                lemmas.append(w)
        except Exception:
            lemmas.append(w)
    return " ".join(lemmas)


def _ensure_index_dir():
    os.makedirs(INDEX_DIR, exist_ok=True)


def _build_text(detail: dict, draft_output: Optional[dict] = None) -> str:
    """Собирает текстовое представление детали для индексации.
    Включает: designation, name, model, material, chassis, surface_treatment,
    типы операций, материалы операций, equipment."""
    parts = [
        detail.get("designation", ""),
        detail.get("name", ""),
        detail.get("model", ""),
        detail.get("chassis", ""),
        detail.get("material", ""),
        detail.get("surface_treatment", ""),
    ]
    if draft_output:
        for op in draft_output.get("operations", []):
            parts.append(str(op.get("name", "")))
            parts.append(str(op.get("department", "")))
            parts.append(str(op.get("equipment", "")))
            for mat in op.get("materials", []):
                if isinstance(mat, dict):
                    parts.append(str(mat.get("name", "")))
                    if mat.get("gost"):
                        parts.append(str(mat["gost"]))
                else:
                    parts.append(str(mat))
            # Профессия и разряд
            if op.get("profession_code"):
                parts.append(f"{op.get('profession_code')} {op.get('profession_grade','')}р")
        for w in draft_output.get("warnings", []):
            parts.append(str(w.get("concern", "")))
    return " ".join(p for p in parts if p).strip()


def _build_indexed_text(detail: dict, draft_output: Optional[dict] = None) -> str:
    """F16.2: возвращает лемматизированный + синонимы-нормализованный текст.
    Используется для TF-IDF индексации. Для оригинального текста (search) — _build_text."""
    raw = _build_text(detail, draft_output)
    return _lemmatize_text(raw)


def _build_metadata(detail: dict) -> dict:
    """Метаданные для гибридного скоринга"""
    return {
        "designation": detail.get("designation", ""),
        "name": detail.get("name", ""),
        "material": detail.get("material", ""),
        "chassis": detail.get("chassis", ""),
        "surface_treatment": detail.get("surface_treatment", ""),
        "mass_kg": detail.get("mass_kg", 0),
    }


def _equipment_set(draft_output: Optional[dict]) -> set:
    if not draft_output:
        return set()
    return {op.get("equipment", "") for op in draft_output.get("operations", []) if op.get("equipment")}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b) if (a | b) else 0.0


def hybrid_score(sim: float, query_material: str, cand_material: str,
                 query_eq: set, cand_eq: set, query_mass: float, cand_mass: float) -> float:
    """Итоговый скор: 0.5*sim + 0.2*material_match + 0.2*equipment + 0.1*mass_proximity"""
    mat = 1.0 if query_material and query_material == cand_material else 0.3
    eq = jaccard(query_eq, cand_eq)
    if query_mass and cand_mass:
        diff = abs(query_mass - cand_mass) / max(query_mass, cand_mass, 1.0)
        mass = max(0.0, 1.0 - diff)
    else:
        mass = 0.5
    return 0.5 * sim + 0.2 * mat + 0.2 * eq + 0.1 * mass


class RAGIndex:
    """Singleton-style: загружается из файла, пересобирается при необходимости."""

    def __init__(self):
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.matrix = None  # sparse TF-IDF
        self.ids: List[str] = []  # detail_id в порядке строк матрицы
        self.metadata: Dict[str, dict] = {}  # detail_id -> metadata
        self.loaded = False

    def load(self):
        if not os.path.exists(VECTORIZER_PATH):
            log.info("No existing RAG index, will build on demand")
            self.loaded = False
            return
        try:
            with open(VECTORIZER_PATH, "rb") as f:
                self.vectorizer = pickle.load(f)
            with open(MATRIX_PATH, "rb") as f:
                self.matrix = pickle.load(f)
            with open(IDS_PATH, "rb") as f:
                self.ids = pickle.load(f)
            with open(METADATA_PATH, "rb") as f:
                self.metadata = pickle.load(f)
            self.loaded = True
            log.info(f"RAG index loaded: {len(self.ids)} documents")
        except Exception as e:
            log.warning(f"Failed to load RAG index: {e}")
            self.loaded = False

    def save(self):
        _ensure_index_dir()
        with open(VECTORIZER_PATH, "wb") as f:
            pickle.dump(self.vectorizer, f)
        with open(MATRIX_PATH, "wb") as f:
            pickle.dump(self.matrix, f)
        with open(IDS_PATH, "wb") as f:
            pickle.dump(self.ids, f)
        with open(METADATA_PATH, "wb") as f:
            pickle.dump(self.metadata, f)
        log.info(f"RAG index saved: {len(self.ids)} documents")

    def add_document(self, detail_id: str, text: str, metadata: dict):
        """Добавляет документ. Если уже есть — переиндексирует.
        F16.2: применяет лемматизацию к тексту."""
        if not text:
            return
        # F16.2: лемматизация + синонимы для индексации
        text = _lemmatize_text(text)
        if detail_id in self.metadata:
            self.remove_document(detail_id)
        # Добавляем в список
        new_doc = [text]
        if self.loaded and self.matrix is not None:
            new_vec = self.vectorizer.transform(new_doc)
            from scipy.sparse import vstack
            self.matrix = vstack([self.matrix, new_vec])
        else:
            # Первый документ — создаём vectorizer
            self.vectorizer = TfidfVectorizer(
                max_features=5000, ngram_range=(1, 2), min_df=1, lowercase=True
            )
            self.matrix = self.vectorizer.fit_transform(new_doc)
        self.ids.append(detail_id)
        self.metadata[detail_id] = metadata
        self.loaded = True

    def remove_document(self, detail_id: str):
        if detail_id not in self.ids:
            return
        idx = self.ids.index(detail_id)
        self.ids.pop(idx)
        # Удаляем строку из матрицы
        from scipy.sparse import vstack
        keep_indices = [i for i in range(self.matrix.shape[0]) if i != idx]
        if keep_indices:
            self.matrix = self.matrix[keep_indices]
        else:
            self.matrix = None
            self.loaded = False
        del self.metadata[detail_id]

    def search(self, query_text: str, query_metadata: dict, top_k: int = 5) -> List[Dict]:
        """Возвращает top-K похожих документов с hybrid scoring.
        Возвращает: [{"detail_id", "score", "metadata", "text_snippet"}, ...]"""
        if not self.loaded or self.matrix is None or len(self.ids) == 0:
            return []
        if not query_text.strip():
            return []
        try:
            q_vec = self.vectorizer.transform([query_text])
        except Exception as e:
            log.warning(f"Vectorize query failed: {e}")
            return []
        sims = cosine_similarity(q_vec, self.matrix).flatten()
        # Считаем hybrid score для каждого кандидата
        query_eq = set()  # в query нет черновика, поэтому только sim+material
        query_mass = query_metadata.get("mass_kg", 0)
        results = []
        for i, sim in enumerate(sims):
            if sim <= 0:
                continue
            cand_id = self.ids[i]
            cand_meta = self.metadata.get(cand_id, {})
            score = hybrid_score(
                sim=float(sim),
                query_material=query_metadata.get("material", ""),
                cand_material=cand_meta.get("material", ""),
                query_eq=query_eq,
                cand_eq=set(),  # equipment set требует черновика, для query нерелевантно
                query_mass=query_mass,
                cand_mass=cand_meta.get("mass_kg", 0)
            )
            results.append({
                "detail_id": cand_id,
                "score": round(float(score), 3),
                "raw_similarity": round(float(sim), 3),
                "metadata": cand_meta
            })
        results.sort(key=lambda x: -x["score"])
        return results[:top_k]

    def rebuild_from_db(self) -> int:
        """Перестраивает индекс из БД — все approved черновики + все детали (даже без черновика)."""
        conn = get_conn()
        # Берём все детали
        details = conn.execute("SELECT * FROM details").fetchall()
        if not details:
            conn.close()
            return 0
        # Получаем черновики
        drafts = {}
        for row in conn.execute("SELECT detail_id, llm_output FROM drafts").fetchall():
            try:
                drafts[row[0]] = json.loads(row[1])
            except Exception:
                continue
        # Строим
        self.vectorizer = TfidfVectorizer(
            max_features=5000, ngram_range=(1, 2), min_df=1, lowercase=True
        )
        texts = []
        self.ids = []
        self.metadata = {}
        cols = [d[1] for d in conn.execute("PRAGMA table_info(details)").fetchall()]
        for row in details:
            detail = dict(zip(cols, row))
            draft = drafts.get(detail["id"])
            text = _build_indexed_text(detail, draft)
            if text:
                texts.append(text)
                self.ids.append(detail["id"])
                self.metadata[detail["id"]] = _build_metadata(detail)
        if not texts:
            conn.close()
            return 0
        self.matrix = self.vectorizer.fit_transform(texts)
        self.loaded = True
        self.save()
        conn.close()
        log.info(f"RAG index rebuilt: {len(self.ids)} documents")
        return len(self.ids)


# Глобальный singleton
_rag = RAGIndex()


def get_rag() -> RAGIndex:
    global _rag
    if not _rag.loaded:
        _rag.load()
    return _rag


def rag_search(detail: dict, top_k: int = 3) -> List[Dict]:
    """Удобный wrapper для поиска похожих техкарт"""
    rag = get_rag()
    if not rag.loaded:
        # Автоматически строим индекс если пустой
        rag.rebuild_from_db()
    text = _build_text(detail, None)
    metadata = _build_metadata(detail)
    return rag.search(text, metadata, top_k)


def rag_index_detail(detail_id: str):
    """Добавляет/обновляет документ в индексе. Вызывается при approve."""
    rag = get_rag()
    conn = get_conn()
    cols = [d[1] for d in conn.execute("PRAGMA table_info(details)").fetchall()]
    row = conn.execute("SELECT * FROM details WHERE id=?", (detail_id,)).fetchone()
    if not row:
        conn.close()
        return
    detail = dict(zip(cols, row))
    draft_row = conn.execute("SELECT * FROM drafts WHERE detail_id=?", (detail_id,)).fetchone()
    draft_output = None
    if draft_row:
        # cols для drafts: detail_id, llm_output, status, ...
        try:
            draft_output = json.loads(draft_row[1])
        except Exception:
            draft_output = None
    text = _build_text(detail, draft_output)
    metadata = _build_metadata(detail)
    if text:
        rag.add_document(detail_id, text, metadata)
        rag.save()
    conn.close()
