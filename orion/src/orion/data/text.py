"""Text normalization shared by dedup, contamination detection and heuristics."""

from __future__ import annotations

import hashlib
import re
import unicodedata

_WS = re.compile(r"\s+")
_WORD = re.compile(r"\w+", re.UNICODE)


def normalize(text: str) -> str:
    """NFKC, casefold, collapse whitespace — the canonical form for exact dedup."""
    return _WS.sub(" ", unicodedata.normalize("NFKC", text).casefold()).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def words(text: str) -> list[str]:
    """Casefolded word tokens (Unicode-aware); used for n-grams and word-level heuristics."""
    return _WORD.findall(unicodedata.normalize("NFKC", text).casefold())


def ngrams(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def char_shingles(text: str, k: int = 5) -> set[str]:
    """Character k-shingles over normalized text — robust for languages without spaces (zh, ja)."""
    t = normalize(text)
    return {t[i : i + k] for i in range(max(1, len(t) - k + 1))}
