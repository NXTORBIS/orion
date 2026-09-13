"""Retrieval: chunking, BM25 keyword search, optional dense vectors, hybrid fusion, reranking,
metadata filters and citations.

    query -> [BM25 | dense] -> reciprocal-rank fusion -> filter -> rerank -> evidence with [n] citations

The dense index is optional and pluggable (any ``embed(texts) -> list[list[float]]``); without an
embedding model the retriever is keyword-only and says so in ``describe()``.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from orion.data.text import words


@dataclass
class Chunk:
    doc_id: str
    chunk_id: int
    text: str
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.doc_id}#{self.chunk_id}"


@dataclass
class Hit:
    chunk: Chunk
    score: float
    source: str  # "bm25" | "dense" | "hybrid"


def chunk_text(text: str, max_words: int = 200, overlap: int = 40) -> list[str]:
    toks = text.split()
    if len(toks) <= max_words:
        return [text.strip()] if text.strip() else []
    out, start = [], 0
    while start < len(toks):
        out.append(" ".join(toks[start : start + max_words]))
        if start + max_words >= len(toks):
            break
        start += max_words - overlap
    return out


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.chunks: list[Chunk] = []
        self.tf: list[Counter[str]] = []
        self.df: Counter[str] = Counter()
        self.lengths: list[int] = []

    def add(self, chunk: Chunk) -> None:
        toks = words(chunk.text)
        self.chunks.append(chunk)
        self.tf.append(Counter(toks))
        self.lengths.append(len(toks))
        for t in set(toks):
            self.df[t] += 1

    def search(self, query: str, k: int = 10) -> list[Hit]:
        if not self.chunks:
            return []
        q = words(query)
        n = len(self.chunks)
        avg = sum(self.lengths) / n
        scores = defaultdict(float)
        for term in set(q):
            df = self.df.get(term)
            if not df:
                continue
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            for i, tf in enumerate(self.tf):
                f = tf.get(term)
                if f:
                    scores[i] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.lengths[i] / avg))
        top = sorted(scores.items(), key=lambda kv: -kv[1])[:k]
        return [Hit(self.chunks[i], s, "bm25") for i, s in top]


class DenseIndex:
    def __init__(self, embed: Callable[[list[str]], list[list[float]]]):
        self.embed = embed
        self.chunks: list[Chunk] = []
        self.vectors: list[list[float]] = []

    def add_many(self, chunks: list[Chunk]) -> None:
        vecs = self.embed([c.text for c in chunks])
        for c, v in zip(chunks, vecs):
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            self.chunks.append(c)
            self.vectors.append([x / norm for x in v])

    def search(self, query: str, k: int = 10) -> list[Hit]:
        if not self.chunks:
            return []
        q = self.embed([query])[0]
        qn = math.sqrt(sum(x * x for x in q)) or 1.0
        q = [x / qn for x in q]
        sims = [(sum(a * b for a, b in zip(q, v)), i) for i, v in enumerate(self.vectors)]
        return [Hit(self.chunks[i], s, "dense") for s, i in sorted(sims, reverse=True)[:k]]


def reciprocal_rank_fusion(result_lists: list[list[Hit]], k: int = 60) -> list[Hit]:
    fused: dict[str, float] = defaultdict(float)
    chunks: dict[str, Chunk] = {}
    for hits in result_lists:
        for rank, h in enumerate(hits):
            fused[h.chunk.id] += 1.0 / (k + rank + 1)
            chunks[h.chunk.id] = h.chunk
    return [Hit(chunks[cid], s, "hybrid") for cid, s in sorted(fused.items(), key=lambda kv: -kv[1])]


def coverage_rerank(query: str, hits: list[Hit]) -> list[Hit]:
    """Cheap reranker: fraction of distinct query terms present in the chunk, as a tiebreak
    on top of fused scores. A cross-encoder reranker can replace this via ``Retriever.reranker``."""
    q = set(words(query))
    if not q:
        return hits
    rescored = []
    for h in hits:
        cov = len(q & set(words(h.chunk.text))) / len(q)
        rescored.append(Hit(h.chunk, h.score * (1 + cov), h.source))
    return sorted(rescored, key=lambda h: -h.score)


class Retriever:
    def __init__(self, embed: Callable[[list[str]], list[list[float]]] | None = None, max_words: int = 200, overlap: int = 40,
                 reranker: Callable[[str, list[Hit]], list[Hit]] | None = None):
        self.bm25 = BM25Index()
        self.dense = DenseIndex(embed) if embed else None
        self.max_words, self.overlap = max_words, overlap
        self.reranker = reranker or coverage_rerank
        self.docs: dict[str, dict[str, Any]] = {}

    def add_document(self, doc_id: str, text: str, meta: dict[str, Any] | None = None) -> int:
        chunks = [Chunk(doc_id, i, t, dict(meta or {})) for i, t in enumerate(chunk_text(text, self.max_words, self.overlap))]
        for c in chunks:
            self.bm25.add(c)
        if self.dense:
            self.dense.add_many(chunks)
        self.docs[doc_id] = {"chunks": len(chunks), "meta": meta or {}}
        return len(chunks)

    def retrieve(self, query: str, k: int = 5, filters: dict[str, Any] | None = None, candidates: int = 20) -> list[Hit]:
        lists = [self.bm25.search(query, candidates)]
        if self.dense:
            lists.append(self.dense.search(query, candidates))
        hits = reciprocal_rank_fusion(lists) if len(lists) > 1 else lists[0]
        if filters:
            hits = [h for h in hits if all(h.chunk.meta.get(key) == val for key, val in filters.items())]
        return self.reranker(query, hits)[:k]

    @staticmethod
    def format_evidence(hits: list[Hit]) -> str:
        if not hits:
            return "No relevant passages found."
        return "\n\n".join(f"[{i + 1}] (source: {h.chunk.doc_id}{', ' + h.chunk.meta['title'] if h.chunk.meta.get('title') else ''})\n{h.chunk.text}"
                           for i, h in enumerate(hits))

    @staticmethod
    def citations(hits: list[Hit]) -> list[dict[str, Any]]:
        return [{"n": i + 1, "doc_id": h.chunk.doc_id, "chunk": h.chunk.chunk_id, "meta": h.chunk.meta} for i, h in enumerate(hits)]

    def describe(self) -> dict[str, Any]:
        return {"documents": len(self.docs), "chunks": len(self.bm25.chunks), "dense": self.dense is not None,
                "mode": "hybrid (BM25 + dense, RRF)" if self.dense else "keyword-only (BM25)"}
