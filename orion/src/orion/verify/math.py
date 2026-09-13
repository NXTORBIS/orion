"""Mathematical answer verification.

    response text -> extract final answer -> normalize -> compare with the reference
      1. exact string match after normalization
      2. numeric comparison (fractions and decimals) with a relative tolerance
      3. symbolic equivalence via SymPy (``simplify(pred - gold) == 0``)

Extraction understands the conventions ORION trains and evaluates with: a trailing
``#### <answer>`` line (GSM8K style), ``\\boxed{...}``, "final answer: ..." phrases, and as a last
resort the final number in the text. The verdict records which extraction and comparison
methods were used.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

import sympy
from sympy.parsing.sympy_parser import (convert_xor, implicit_multiplication_application, parse_expr,
                                        standard_transformations)

BOXED = re.compile(r"\\boxed\{((?:[^{}]|\{[^{}]*\})*)\}")
HASH = re.compile(r"####\s*([^\n]+)")
FINAL = re.compile(r"(?:final answer|the answer is|answer)\s*(?:is|=|:)?\s*\$?([^\n]+)", re.I)
NUMBER = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?(?:/\d+)?")
TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)


def extract_final_answer(text: str) -> tuple[str | None, str]:
    """Return (answer, method)."""
    for pat, name in ((HASH, "hash"), (BOXED, "boxed"), (FINAL, "phrase")):
        found = pat.findall(text)
        if found:
            return found[-1].strip(), name
    nums = NUMBER.findall(text)
    if nums:
        return nums[-1], "last-number"
    return None, "none"


def normalize_answer(s: str) -> str:
    s = s.strip().strip("*").strip()
    s = re.sub(r"\\text\{([^}]*)\}", r"\1", s)
    s = s.replace("$", "").replace("\\%", "%").replace("\\,", "").replace("\\left", "").replace("\\right", "")
    s = s.rstrip(".").strip()
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", s):
        s = s.replace(",", "")
    s = re.sub(r"\s+", " ", s)
    if s.endswith("%") and re.fullmatch(r"-?\d+(\.\d+)?%", s):
        s = s[:-1]
    return s.lower()


def to_number(s: str) -> Fraction | None:
    try:
        return Fraction(s.replace(" ", ""))
    except (ValueError, ZeroDivisionError):
        return None


def symbolic_equal(a: str, b: str) -> bool:
    try:
        pa = parse_expr(a.replace("^", "**"), transformations=TRANSFORMS)
        pb = parse_expr(b.replace("^", "**"), transformations=TRANSFORMS)
        return sympy.simplify(pa - pb) == 0
    except Exception:
        return False


def equivalent(pred: str, gold: str, rel_tol: float = 1e-6) -> tuple[bool, str]:
    p, g = normalize_answer(pred), normalize_answer(gold)
    if p == g:
        return True, "exact"
    pn, gn = to_number(p), to_number(g)
    if pn is not None and gn is not None:
        return abs(pn - gn) <= rel_tol * max(1, abs(gn)), "numeric"
    if pn is None and gn is None or (pn is None) != (gn is None):
        return symbolic_equal(p, g), "symbolic"
    return False, "numeric"


@dataclass
class MathVerdict:
    ok: bool
    extracted: str | None
    gold: str
    extraction: str
    comparison: str


def verify_math(response: str, gold: str) -> MathVerdict:
    extracted, how = extract_final_answer(response)
    if extracted is None:
        return MathVerdict(False, None, gold, how, "none")
    ok, cmp = equivalent(extracted, gold)
    return MathVerdict(ok, extracted, gold, how, cmp)
