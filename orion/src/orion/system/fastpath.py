"""Exact answers without a model call for questions a solver settles on its own: plain arithmetic, one
equation in one variable, and small linear systems. Anything else returns ``None`` and goes to a model.

Inputs are checked against a strict character set (digits, operators, parentheses, single-letter
variables) before SymPy parses them, and exponent towers are refused so no input can stall the server.
"""

from __future__ import annotations

import re
from decimal import Decimal
from tokenize import TokenError

import sympy
from sympy.parsing.sympy_parser import (convert_xor, implicit_multiplication_application, parse_expr, rationalize,
                                        standard_transformations)

TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor, rationalize)
LEAD = re.compile(r"^\s*(?:please\s+)?(?:compute|calculate|evaluate|simplify|what\s+is|what's|find)\s*:?\s*", re.I)
ARITHMETIC = re.compile(r"^[\d\s+\-*/().^×÷]+$")
HAS_OPERATION = re.compile(r"[\d)]\s*(?:\*\*|[+\-*/^×÷])\s*[-\d(]")
SOLVE_ONE = re.compile(r"^\s*solve(?:\s+for\s+([a-z]))?\s*:?\s*(.+?)\s*\.?\s*$", re.I)
SYSTEM = re.compile(r"^\s*solve\s+the\s+system\s*:?\s*(.+?)\s*$", re.I | re.S)
THEN = re.compile(r",?\s*then\s+give\s+the\s+value\s+of\s+(.+?)\s*\.?\s*$", re.I)
SIDE = re.compile(r"^[\d\s+\-*/().^a-z]+$")
MAX_LEN = 200


def _safe(expr: str) -> bool:
    return len(expr) <= MAX_LEN and len(re.findall(r"\^|\*\*", expr)) <= 1 and not re.search(r"[a-z]{2,}", expr) \
        and not re.search(r"\d{31,}", expr) and not re.search(r"(?:\^|\*\*)\s*\(?\s*-?\d{4,}", expr)


def _parse(expr: str, variables: set[str] = frozenset()):
    expr = expr.replace("×", "*").replace("÷", "/")
    expr = re.sub(r"(\d)\s*([a-z])", r"\1*\2", expr)  # "0x" would otherwise tokenize as a hex literal
    return parse_expr(expr, local_dict={v: sympy.Symbol(v) for v in variables}, transformations=TRANSFORMS)


def _fmt(value) -> str:
    value = sympy.nsimplify(value)
    if value.is_Integer:
        return str(value)
    if value.is_Rational:
        q = value.q
        for f in (2, 5):
            while q % f == 0:
                q //= f
        return format(Decimal(value.p) / Decimal(value.q), "f") if q == 1 else f"{value.p}/{value.q}"
    return str(value)


def _question(text: str) -> str:
    return re.split(r"\n\s*\n", text.strip(), maxsplit=1)[0].strip()


def _arithmetic(q: str) -> str | None:
    body = LEAD.sub("", q).rstrip("?.= ").strip()
    if not ARITHMETIC.match(body) or not HAS_OPERATION.search(body) or not _safe(body):
        return None
    value = _parse(body)
    if not value.is_number or not value.is_finite:
        return None
    answer = _fmt(value)
    return f"{body} = {answer}\n#### {answer}"


def _equation(eq: str, variables: set[str]):
    if eq.count("=") != 1:
        return None
    lhs, rhs = (s.strip() for s in eq.split("="))
    if not lhs or not rhs or not SIDE.match(lhs) or not SIDE.match(rhs) or not _safe(lhs) or not _safe(rhs):
        return None
    if not set(re.findall(r"[a-z]", eq)) <= variables:
        return None
    return sympy.Eq(_parse(lhs, variables), _parse(rhs, variables))


def _one_equation(q: str) -> str | None:
    m = SOLVE_ONE.match(q)
    if not m:
        return None
    eq = m.group(2)
    letters = set(re.findall(r"[a-z]", eq))
    if len(letters) != 1 or (m.group(1) and m.group(1) not in letters):
        return None
    var = letters.pop()
    parsed = _equation(eq, {var})
    if parsed is None or parsed in (sympy.true, sympy.false):
        return None
    x = sympy.Symbol(var)
    poly = (parsed.lhs - parsed.rhs).as_poly(x)
    if poly is None or poly.degree() < 1 or poly.degree() > 4:
        return None
    roots = sorted((r for r in sympy.solve(parsed, x) if r.is_real), key=float)
    if not roots:
        return None
    answers = [_fmt(r) for r in roots]
    return f"{' or '.join(f'{var} = {a}' for a in answers)}\n#### {', '.join(answers)}"


def _system(q: str) -> str | None:
    m = SYSTEM.match(q)
    if not m:
        return None
    body, target = m.group(1), None
    if t := THEN.search(body):
        body, target = body[: t.start()], t.group(1).strip()
    parts = [p.strip().rstrip(".") for p in re.split(r"\n|\s+and\s+|;", body) if p.strip()]
    variables = set(re.findall(r"[a-z]", " ".join(parts)))
    if not 2 <= len(parts) <= 4 or len(variables) != len(parts):
        return None
    eqs = [_equation(p, variables) for p in parts]
    if any(e is None or e in (sympy.true, sympy.false) for e in eqs):
        return None
    symbols = [sympy.Symbol(v) for v in sorted(variables)]
    if any((e.lhs - e.rhs).as_poly(*symbols) is None or (e.lhs - e.rhs).as_poly(*symbols).total_degree() != 1 for e in eqs):
        return None
    solutions = sympy.solve(eqs, symbols, dict=True)
    if len(solutions) != 1 or set(solutions[0]) != set(symbols) or not all(v.is_number for v in solutions[0].values()):
        return None
    sol = solutions[0]
    shown = ", ".join(f"{s} = {_fmt(sol[s])}" for s in symbols)
    if target is None:
        return f"{shown}\n#### {', '.join(f'{s}={_fmt(sol[s])}' for s in symbols)}"
    if not SIDE.match(target) or not _safe(target) or not set(re.findall(r"[a-z]", target)) <= variables:
        return None
    value = _parse(target, variables).subs(sol)
    if not value.is_number:
        return None
    return f"{shown}, so {target} = {_fmt(value)}\n#### {_fmt(value)}"


def solve_directly(text: str) -> str | None:
    q = _question(text)
    if not q or len(q) > 600:
        return None
    for solver in (_system, _one_equation, _arithmetic):
        try:
            if (answer := solver(q)) is not None:
                return answer
        except (sympy.SympifyError, SyntaxError, TokenError, TypeError, ValueError, ZeroDivisionError, OverflowError, NotImplementedError):
            return None
    return None
