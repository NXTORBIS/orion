"""Rule-based spam, boilerplate and low-quality text filters.

Rules follow the Gopher (Rae et al., 2021) and C4 (Raffel et al., 2020) heuristics. Thresholds
are configurable, and every drop records which rule fired. Word-level rules only apply to
languages written with spaces between words; the English stop-word rule only applies to
records that language ID labelled English. C4's "drop pages containing '{'" rule is omitted on
purpose because it deletes code.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .schema import Record, RecordStage
from .text import words

NO_SPACE_SCRIPTS = ("Hani", "Hans", "Hant", "Jpan", "Thai", "Khmr", "Laoo", "Mymr", "Tibt")
STOPWORDS_EN = {"the", "be", "to", "of", "and", "that", "have", "with"}
BOILERPLATE_LINE = re.compile(
    r"javascript|terms of use|privacy policy|cookie policy|uses cookies|use of cookies|use cookies", re.I
)
SPAM_TERMS = re.compile(
    r"\b(casino|viagra|cialis|payday loans?|buy now|click here|free shipping|limited[- ]time offer"
    r"|porn|xxx|crypto giveaway|work from home)\b",
    re.I,
)
URL = re.compile(r"https?://\S+|www\.\S+")
SYMBOL_RUN = re.compile(r"#+|\.{3,}|…")


@dataclass
class HeuristicConfig:
    min_words: int = 50
    max_words: int = 100_000
    mean_word_len: tuple[float, float] = (3.0, 10.0)
    max_symbol_ratio: float = 0.10  # ('#', '...') per word
    max_bullet_lines: float = 0.90
    max_ellipsis_lines: float = 0.30
    min_alpha_words: float = 0.80
    min_stopwords: int = 2
    max_dup_line_frac: float = 0.30
    max_dup_line_chars: float = 0.20
    max_top_ngram_chars: tuple[float, float, float] = (0.20, 0.18, 0.16)  # 2-, 3-, 4-grams
    max_dup_ngram_chars: tuple[float, ...] = (0.15, 0.14, 0.13, 0.12, 0.11, 0.10)  # 5- to 10-grams
    max_urls_per_100_words: float = 5.0
    max_spam_terms_per_1k_words: float = 5.0


def top_ngram_char_frac(ws: list[str], n: int) -> float:
    """Fraction of word characters covered by the single most frequent n-gram."""
    if len(ws) < n:
        return 0.0
    gram, count = Counter(tuple(ws[i : i + n]) for i in range(len(ws) - n + 1)).most_common(1)[0]
    if count < 2:
        return 0.0
    return sum(map(len, gram)) * count / max(1, sum(map(len, ws)))


def dup_ngram_char_frac(ws: list[str], n: int) -> float:
    """Fraction of word characters inside n-grams that occur more than once."""
    if len(ws) < n:
        return 0.0
    grams = [tuple(ws[i : i + n]) for i in range(len(ws) - n + 1)]
    counts = Counter(grams)
    covered = [False] * len(ws)
    for i, g in enumerate(grams):
        if counts[g] > 1:
            covered[i : i + n] = [True] * n
    return sum(len(w) for w, c in zip(ws, covered) if c) / max(1, sum(map(len, ws)))


def check(text: str, lang: str = "", cfg: HeuristicConfig | None = None) -> str | None:
    """Return the first failed rule as a human-readable reason, or None if the text passes."""
    c = cfg or HeuristicConfig()
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return "empty"
    spaced = not lang.endswith(NO_SPACE_SCRIPTS)
    ws = words(text)
    n_words = len(ws)

    if spaced:
        if n_words < c.min_words:
            return f"too short ({n_words} words)"
        if n_words > c.max_words:
            return f"too long ({n_words} words)"
        mwl = sum(map(len, ws)) / n_words
        if not c.mean_word_len[0] <= mwl <= c.mean_word_len[1]:
            return f"mean word length {mwl:.1f}"
        symbols = len(SYMBOL_RUN.findall(text)) / n_words  # a run such as "####" counts as one symbol
        if symbols > c.max_symbol_ratio:
            return f"symbol-to-word ratio {symbols:.2f}"
        tokens = text.split()
        alpha = sum(1 for t in tokens if any(ch.isalpha() for ch in t)) / max(1, len(tokens))
        if alpha < c.min_alpha_words:
            return f"alphabetic-word fraction {alpha:.2f}"
        if lang.startswith("eng"):
            stop = len(STOPWORDS_EN.intersection(ws))
            if stop < c.min_stopwords:
                return f"only {stop} English stop words"
        urls = len(URL.findall(text)) * 100 / n_words
        if urls > c.max_urls_per_100_words:
            return f"{urls:.1f} URLs per 100 words"
        spam = len(SPAM_TERMS.findall(text)) * 1000 / n_words
        if spam > c.max_spam_terms_per_1k_words:
            return f"{spam:.1f} spam terms per 1k words"

    bullets = sum(1 for line in lines if line.lstrip().startswith(("•", "*", "-", "–", "·"))) / len(lines)
    if bullets > c.max_bullet_lines:
        return f"bullet-line fraction {bullets:.2f}"
    ellipsis = sum(1 for line in lines if line.rstrip().endswith(("...", "…"))) / len(lines)
    if ellipsis > c.max_ellipsis_lines:
        return f"ellipsis-line fraction {ellipsis:.2f}"

    line_counts = Counter(lines)
    dup_lines = sum(k - 1 for k in line_counts.values() if k > 1)
    if dup_lines / len(lines) > c.max_dup_line_frac:
        return f"duplicate-line fraction {dup_lines / len(lines):.2f}"
    dup_chars = sum(len(line) * (k - 1) for line, k in line_counts.items() if k > 1)
    if dup_chars / max(1, sum(map(len, lines))) > c.max_dup_line_chars:
        return f"duplicate-line character fraction {dup_chars / sum(map(len, lines)):.2f}"

    if spaced:
        for n, limit in zip((2, 3, 4), c.max_top_ngram_chars):
            if (f := top_ngram_char_frac(ws, n)) > limit:
                return f"top {n}-gram covers {f:.2f} of characters"
        for n, limit in zip(range(5, 11), c.max_dup_ngram_chars):
            if (f := dup_ngram_char_frac(ws, n)) > limit:
                return f"duplicated {n}-grams cover {f:.2f} of characters"
    return None


class HeuristicFilter(RecordStage):
    name = "heuristics"

    def __init__(self, cfg: HeuristicConfig | None = None):
        self.cfg = cfg or HeuristicConfig()

    def apply(self, r: Record) -> None:
        lines = r.text.splitlines()
        kept = [line for line in lines if not BOILERPLATE_LINE.search(line)]
        if len(kept) != len(lines):
            r.meta["boilerplate_lines_removed"] = len(lines) - len(kept)
            r.text = "\n".join(kept)
        if "lorem ipsum" in r.text.casefold():
            return r.drop(self.name, "lorem ipsum placeholder text")
        if reason := check(r.text, r.meta.get("lang", ""), self.cfg):
            r.drop(self.name, reason)
