"""Structured-PII detection and redaction.

Detects identifiers that can be matched by pattern and confirmed by checksum or structure:
e-mail addresses, phone numbers, IPv4/IPv6 addresses, payment card numbers (Luhn), IBANs
(ISO 13616 mod-97) and US Social Security numbers.

Limitation (stated, not hidden): person names and street addresses need NER and are NOT
detected here. An NER-based detector (e.g. Presidio + spaCy) can be added as a later stage.
"""

from __future__ import annotations

import re
from collections import Counter

from .schema import Record, RecordStage
from .text import words

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-zA-Z]{2,}\b")
IPV4 = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
IPV6 = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b")
CARD = re.compile(r"(?<![\d-])\d(?:[ -]?\d){12,18}(?![\d-])")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?\b")
SSN = re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
PHONE = re.compile(r"(?<![\w+])(?:\+\d{1,3}[ .-]?)?(?:\(\d{1,4}\)[ .-]?)?\d{2,4}[ .-]\d{3,4}[ .-]\d{3,4}(?!\w)")


def luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def iban_ok(candidate: str) -> bool:
    s = candidate.replace(" ", "")
    if not 15 <= len(s) <= 34:
        return False
    return int("".join(str(int(c, 36)) for c in s[4:] + s[:4])) % 97 == 1


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def find_pii(text: str) -> list[tuple[int, int, str]]:
    """Return non-overlapping (start, end, kind) spans, earliest-first; checksums applied."""
    spans: list[tuple[int, int, str]] = []
    for m in EMAIL.finditer(text):
        spans.append((m.start(), m.end(), "EMAIL"))
    for m in IBAN.finditer(text):
        if iban_ok(m.group()):
            spans.append((m.start(), m.end(), "IBAN"))
    for m in CARD.finditer(text):
        d = _digits(m.group())
        if 13 <= len(d) <= 19 and len(set(d)) > 1 and luhn_ok(d):
            spans.append((m.start(), m.end(), "CARD_NUMBER"))
    for m in SSN.finditer(text):
        spans.append((m.start(), m.end(), "US_SSN"))
    for m in IPV4.finditer(text):
        spans.append((m.start(), m.end(), "IP_ADDRESS"))
    for m in IPV6.finditer(text):
        spans.append((m.start(), m.end(), "IP_ADDRESS"))
    for m in PHONE.finditer(text):
        if 10 <= len(_digits(m.group())) <= 15:
            spans.append((m.start(), m.end(), "PHONE"))
    # Earlier, then longer spans win; drop anything overlapping an accepted span.
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    accepted: list[tuple[int, int, str]] = []
    for s in spans:
        if not accepted or s[0] >= accepted[-1][1]:
            accepted.append(s)
    return accepted


def redact(text: str, spans: list[tuple[int, int, str]]) -> str:
    out, pos = [], 0
    for start, end, kind in spans:
        out.append(text[pos:start])
        out.append(f"<{kind}>")
        pos = end
    out.append(text[pos:])
    return "".join(out)


class PIIFilter(RecordStage):
    """Redact structured PII; drop documents so dense with PII they look like contact dumps."""

    name = "pii"

    def __init__(self, max_per_1k_words: float = 20.0):
        self.max_per_1k_words = max_per_1k_words

    def apply(self, r: Record) -> None:
        spans = find_pii(r.text)
        counts = Counter(kind for _, _, kind in spans)
        r.meta["pii"] = dict(counts)
        if not spans:
            return
        density = 1000 * len(spans) / max(1, len(words(r.text)))
        if density > self.max_per_1k_words:
            return r.drop(self.name, f"PII density {density:.1f} per 1k words")
        r.text = redact(r.text, spans)
