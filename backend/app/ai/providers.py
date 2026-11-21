"""Replaceable provider adapters.

The MVP runs with no paid API: a local TF-IDF similarity and template explanations.
To upgrade, set EMBEDDING_PROVIDER=sbert (needs `pip install sentence-transformers`) or
implement an LLMProvider for Claude/OpenAI/self-hosted models. The rest of the code only
talks to these interfaces.
"""
import math
import re
from collections import Counter

from ..config import settings

_TOKEN = re.compile(r"[a-z][a-z0-9+#.]{1,}")
_STOP = set(
    "the and for with from that this have has was were are you your our will into using used use "
    "of in on at to a an by as is it be or we i my me project projects work worked team".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


class TfidfSimilarity:
    name = "tfidf-1"

    def fit(self, corpus: list[str]) -> "TfidfSimilarity":
        n = len(corpus) or 1
        df = Counter()
        for doc in corpus:
            df.update(set(tokenize(doc)))
        self.idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}
        return self

    def _vec(self, text: str) -> dict[str, float]:
        tf = Counter(tokenize(text))
        return {t: c * self.idf.get(t, 1.0) for t, c in tf.items()}

    def similarity(self, a: str, b: str) -> float:
        va, vb = self._vec(a), self._vec(b)
        dot = sum(v * vb.get(t, 0.0) for t, v in va.items())
        na = math.sqrt(sum(v * v for v in va.values()))
        nb = math.sqrt(sum(v * v for v in vb.values()))
        return dot / (na * nb) if na and nb else 0.0


class SbertSimilarity:  # pragma: no cover - optional dependency
    name = "sbert-all-MiniLM-L6-v2"

    def __init__(self):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def fit(self, corpus: list[str]) -> "SbertSimilarity":
        return self

    def similarity(self, a: str, b: str) -> float:
        from sentence_transformers import util

        ea, eb = self.model.encode([a, b], convert_to_tensor=True)
        return float(util.cos_sim(ea, eb))


def get_similarity():
    if settings.embedding_provider == "sbert":
        return SbertSimilarity()
    return TfidfSimilarity()


class LLMProvider:
    """Interface for an optional LLM. Inputs are untrusted resume text: implementations must
    send it as data only, request schema-constrained JSON, and validate the output."""

    name = "none"

    def explain(self, evidence_summary: dict) -> str | None:
        return None


def get_llm() -> LLMProvider:
    return LLMProvider()
