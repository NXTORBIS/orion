"""Exact and near-duplicate removal.

Exact: SHA-256 of normalized text (NFKC, casefold, collapsed whitespace).
Near-duplicate: MinHash signatures over character 5-shingles with LSH banding (datasketch);
Jaccard threshold 0.8 by default. The first occurrence is kept; later duplicates are dropped
with a pointer to the kept record. Record ids must be unique within a run.
"""

from __future__ import annotations

from datasketch import MinHash, MinHashLSH

from .schema import Record, RecordStage
from .text import char_shingles, content_hash


class ExactDedup(RecordStage):
    name = "exact_dedup"

    def __init__(self) -> None:
        self.seen: dict[str, str] = {}

    def apply(self, r: Record) -> None:
        h = content_hash(r.text)
        r.meta["sha256"] = h
        if h in self.seen:
            return r.drop(self.name, f"exact duplicate of {self.seen[h]}")
        self.seen[h] = r.id


class NearDedup(RecordStage):
    name = "near_dedup"

    def __init__(self, threshold: float = 0.8, num_perm: int = 128, shingle: int = 5, seed: int = 1):
        self.lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self.num_perm, self.shingle, self.seed = num_perm, shingle, seed

    def signature(self, text: str) -> MinHash:
        m = MinHash(num_perm=self.num_perm, seed=self.seed)
        m.update_batch([s.encode("utf-8") for s in char_shingles(text, self.shingle)])
        return m

    def apply(self, r: Record) -> None:
        sig = self.signature(r.text)
        if hits := self.lsh.query(sig):
            return r.drop(self.name, f"near duplicate of {sorted(hits)[0]}")
        self.lsh.insert(r.id, sig)
