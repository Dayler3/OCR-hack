"""Гибридный RAG по «Положению о приёме документов»: BM25 (rank-bm25) +
эмбеддинги rubert-tiny2 (опционально, sentence-transformers).

Ответственность движка: по вопросу студента и типу документа найти
релевантный пункт Положения. Нет пункта с достаточной релевантностью —
None → ветка «Ответа нет» (NO_INFO)."""
import json
import logging
from pathlib import Path
from typing import List, Optional

import numpy as np
from rapidfuzz import fuzz

from app.config import settings

logger = logging.getLogger(__name__)

# Косинусы rubert-tiny2: нерелевантные пары дают 0.34–0.50 (анизотропия
# пространства), релевантные — 0.58+. Ниже пола — считаем шумом.
SEMANTIC_FLOOR = 0.52

# Слова, не несущие узкой темы вопроса: если кроме них ничего нет, вопрос «общий»
# («проверьте мой документ», «подойдет ли?») и допустим выбор правила по типу документа.
GENERIC_WORDS = {
    "проверьте", "проверить", "проверка", "мой", "моя", "мою", "мне",
    "всё", "все", "верно", "правильно", "порядке", "порядок", "ли", "как", "что",
    "документ", "документы", "документа", "справка", "справку", "справки",
    "заявление", "заявления", "этот", "эту", "это", "прошу", "подскажите",
    "могу", "можно", "хватит", "достаточно", "подойдет", "подходит",
    "примут", "годна", "годится", "принять", "сдать", "нужна", "нужно",
    "хочу", "оформить", "взять", "получить", "зачесть", "зачтут",
}


def _is_generic_question(question: str) -> bool:
    tokens = [t for t in question.lower().replace("ё", "е").split() if len(t) > 2]
    tokens = [t.strip(".,!?;:«»\"()") for t in tokens]
    return bool(tokens) and all(t in GENERIC_WORDS for t in tokens)


def _topic_matches(topic: str, q: str) -> bool:
    t = topic.lower().replace("ё", "е")
    if t in q or fuzz.partial_ratio(t, q) >= settings.fuzz_threshold:
        return True
    for word in t.split():
        if len(word) >= 5 and word[:5] in q:
            return True
    return False


class Rule:
    def __init__(self, payload: dict):
        self.rule_id: str = payload["rule_id"]
        self.text: str = payload["text"]
        self.doc_types: List[str] = payload.get("doc_types", [])
        self.mandatory_fields: List[str] = payload.get("mandatory_fields", [])
        self.topics: List[str] = payload.get("topics", [])


class RagEngine:
    def __init__(self, regulations_path: Optional[Path] = None):
        path = Path(regulations_path or settings.regulations_path)
        with open(path, "r", encoding="utf-8") as f:
            self.rules: List[Rule] = [Rule(r) for r in json.load(f)["rules"]]

        from rank_bm25 import BM25Okapi
        self._bm25_texts = [f"{r.rule_id} {r.text} {' '.join(r.topics)}" for r in self.rules]
        self._bm25 = BM25Okapi([self._tokenize(t) for t in self._bm25_texts])

        self._embedder = None
        self._embeddings = None

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [t for t in text.lower().replace("ё", "е").split() if len(t) > 1]

    # --- эмбеддинги (лениво, опционально) ---

    def _ensure_embeddings(self):
        if self._embeddings is not None or not settings.enable_embeddings:
            return
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("cointegrated/rubert-tiny2")
            self._embedder = model
            self._embeddings = model.encode(
                self._bm25_texts, normalize_embeddings=True, show_progress_bar=False,
            )
        except Exception as exc:
            logger.info("Эмбеддинги недоступны, работает BM25: %s", exc)
            self._embeddings = None

    def _semantic_scores(self, question: str) -> Optional[List[float]]:
        self._ensure_embeddings()
        if self._embedder is None or self._embeddings is None:
            return None
        q = self._embedder.encode([question], normalize_embeddings=True, show_progress_bar=False)
        scores = (self._embeddings @ q.T).reshape(-1)
        scores[scores < SEMANTIC_FLOOR] = 0.0  # отсечка семантического шума
        return scores.tolist()

    # --- публичный API ---

    def retrieve(self, question: str, doc_type: Optional[str] = None) -> Optional[Rule]:
        """Пункт Положения с гибридным скором >= порога, иначе None.

        Приоритет отдаётся пунктам, привязанным к типу документа (когда он
        известен): скор домножается на 1.5 — тип это сильный сигнал."""
        if not question or not question.strip():
            if doc_type:
                for r in self.rules:
                    if doc_type in r.doc_types and r.mandatory_fields:
                        return r
            return None

        bm25_scores = np.array(self._bm25.get_scores(self._tokenize(question)))
        if float(bm25_scores.max()) > 0:
            bm25_scores = bm25_scores / float(bm25_scores.max())  # 0..1
        else:
            bm25_scores = np.zeros(len(self.rules))

        sem = self._semantic_scores(question)
        sem_scores = (
            np.array(sem) if sem else np.zeros(len(self.rules))
        )
        if float(sem_scores.max()) > 0:
            sem_scores = sem_scores / float(sem_scores.max())

        # топический бонус: якорные фразы и стемы пункта в вопросе
        topic_bonus = np.zeros(len(self.rules))
        q = question.lower().replace("ё", "е")
        for i, rule in enumerate(self.rules):
            if any(_topic_matches(t, q) for t in rule.topics):
                topic_bonus[i] = 0.4

        # «Общий» вопрос («проверьте мой документ») при известном типе —
        # проверяем по правилу этого типа, текстовый сигнал не нужен
        generic_specific = [
            i for i, r in enumerate(self.rules)
            if doc_type and doc_type in r.doc_types and r.mandatory_fields
        ] if (doc_type and _is_generic_question(question)) else []

        # Гейт релевантности: без текстового сигнала (лексика/эмбеддинги/темы)
        # пункт не считается покрывающим вопрос — иначе тип документа
        # вытягивал бы нерелевантные пункты выше порога (ветка NO_INFO)
        base = 0.5 * bm25_scores + 0.5 * sem_scores
        if not generic_specific and base.max() < settings.rag_relevance_threshold \
                and topic_bonus.max() == 0.0:
            logger.info("RAG: нет текстового сигнала → NO_INFO")
            return None

        # Правило, привязанное к типу и имеющее обязательные поля, важнее
        # общего пункта «на все типы» без полей (типа п. 4.1)
        type_bonus = np.array([
            ((0.5 if rule.mandatory_fields else 0.2)
             if doc_type and doc_type in rule.doc_types else 0.0)
            for rule in self.rules
        ])

        scores = base + topic_bonus + type_bonus
        if generic_specific:
            scores[generic_specific] += 1.0  # общий вопрос → решает тип
        best_idx = int(np.argmax(scores))
        if scores[best_idx] < settings.rag_relevance_threshold:
            logger.info("RAG: релевантность %.3f < порога %s → NO_INFO",
                        scores[best_idx], settings.rag_relevance_threshold)
            return None
        return self.rules[best_idx]
