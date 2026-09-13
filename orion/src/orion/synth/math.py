"""Procedural mathematics: arithmetic, linear equations and systems, percentages, rates,
work problems, quadratics, number theory, probability, sequences, plane geometry,
trigonometry (special angles), calculus (polynomial derivatives and definite integrals)
and descriptive statistics.

Each template produces a problem, a worked solution ending in ``#### <answer>``, and a
canonical answer. The generator computes the answer one way (closed form / step-by-step) and a
verifier recomputes it another way (SymPy solve / sympify / enumeration); an item is emitted
only when both agree, and the method is recorded on the item.

Held-out protection: ``build_split`` draws train and test items from disjoint seed ranges and
drops any test problem whose text also occurs in train, so the evaluation set is never in the
training set (the data pipeline's 13-gram contamination filter then enforces it again).
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Callable

import sympy
from sympy import Rational, symbols

from orion.verify.math import equivalent

x, y = symbols("x y")

# Appended to every problem in both training prompts and evaluation prompts, so the base model
# and the trained model are asked in exactly the same way.
INSTRUCTION = "Solve the problem step by step and give the final answer on the last line as '#### <answer>'."


@dataclass
class SynthItem:
    id: str
    family: str
    level: int
    problem: str
    solution: str
    answer: str
    seed: int
    verified: bool = False
    verification: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        return f"Problem: {self.problem}\nSolution: {self.solution}"

    def to_sft(self) -> dict:
        return {"id": self.id, "family": self.family, "level": self.level,
                "prompt": [{"role": "user", "content": f"{self.problem}\n{INSTRUCTION}"}],
                "completion": [{"role": "assistant", "content": self.solution}]}


def _fmt(v: Fraction | int) -> str:
    v = Fraction(v)
    if v.denominator == 1:
        return str(v.numerator)
    if v.denominator in (2, 4, 5, 8, 10, 20, 25, 50, 100):
        return f"{float(v):g}"
    return f"{v.numerator}/{v.denominator}"


def _sym(v: Fraction) -> str:
    return "×" if v == "*" else v


# ---------------- templates: each returns (problem, solution_steps, answer, verify_fn) ----------------
def t_arithmetic(rng: random.Random):
    a, b, c = (rng.randint(2, 60) for _ in range(3))
    op1, op2 = rng.choice(["+", "-", "*"]), rng.choice(["+", "-", "*", "/"])
    if op2 == "/":
        c = rng.randint(2, 12)
        inner = eval(f"({a}{op1}{b})")
        inner = inner - (inner % c) if inner % c else inner
        # rebuild a so that (a op1 b) is divisible by c
        if op1 == "+":
            a = inner - b
        elif op1 == "-":
            a = inner + b
        else:
            a, b = c, inner // c if inner // c else 1
    expr_py = f"({a} {op1} {b}) {op2} {c}"
    inner_v = Fraction(eval(f"{a} {op1} {b}"))
    total = Fraction(eval(expr_py))
    shown = expr_py.replace("*", "×").replace("/", "÷")
    problem = f"Compute {shown}."
    steps = (f"First evaluate the parentheses: {a} {op1.replace('*', '×')} {b} = {_fmt(inner_v)}.\n"
             f"Then {_fmt(inner_v)} {op2.replace('*', '×').replace('/', '÷')} {c} = {_fmt(total)}.")
    return problem, steps, _fmt(total), lambda: _fmt(Fraction(str(sympy.sympify(expr_py)))), 1


def t_linear(rng: random.Random):
    sol = rng.randint(-12, 12)
    a, c = rng.sample(range(-9, 10), 2)
    while a == c or a == 0:
        a, c = rng.sample(range(-9, 10), 2)
    b = rng.randint(-30, 30)
    d = a * sol + b - c * sol
    lhs = f"{a}x {'+' if b >= 0 else '-'} {abs(b)}"
    rhs = f"{c}x {'+' if d >= 0 else '-'} {abs(d)}"
    problem = f"Solve for x: {lhs} = {rhs}."
    steps = (f"Move the x terms to one side: ({a} - {c})x = {d} - ({b}).\n"
             f"So {a - c}x = {d - b}.\nDivide both sides by {a - c}: x = {d - b}/{a - c} = {sol}.")
    verify = lambda: str(sympy.solve(sympy.Eq(a * x + b, c * x + d), x)[0])
    return problem, steps, str(sol), verify, 1 if abs(a) < 4 and abs(c) < 4 else 2


def t_system(rng: random.Random):
    xs, ys = rng.randint(-9, 9), rng.randint(-9, 9)
    while True:
        a, b, c, d = (rng.randint(-6, 6) for _ in range(4))
        if a * d - b * c != 0 and a and d:
            break
    e, f = a * xs + b * ys, c * xs + d * ys
    eq = lambda p, q, r: f"{p}x {'+' if q >= 0 else '-'} {abs(q)}y = {r}"
    problem = f"Solve the system {eq(a, b, e)} and {eq(c, d, f)}, then give the value of x + y."
    steps = (f"Multiply the first equation by {d} and the second by {b}, then subtract to eliminate y: "
             f"({a * d} - {b * c})x = {d * e} - {b * f}, so x = {xs}.\n"
             f"Substitute into the first equation: {a}·{xs} + {b}y = {e}, so y = {ys}.\nTherefore x + y = {xs + ys}.")
    verify = lambda: str(sum(sympy.solve([sympy.Eq(a * x + b * y, e), sympy.Eq(c * x + d * y, f)], [x, y]).values()))
    return problem, steps, str(xs + ys), verify, 2


def t_percent(rng: random.Random):
    price = rng.choice(range(20, 400, 5))
    pct = rng.choice([5, 10, 12, 15, 20, 25, 30, 40, 50])
    kind = rng.choice(["discount", "increase", "tax"])
    factor = Fraction(100 - pct if kind == "discount" else 100 + pct, 100)
    final = Fraction(price) * factor
    verb = {"discount": f"is discounted by {pct}%", "increase": f"is increased by {pct}%", "tax": f"has {pct}% tax added"}[kind]
    problem = f"A jacket priced at ${price} {verb}. What is the new price in dollars?"
    steps = (f"{pct}% of {price} is {_fmt(Fraction(price * pct, 100))}.\n"
             f"The new price is {price} {'-' if kind == 'discount' else '+'} {_fmt(Fraction(price * pct, 100))} = {_fmt(final)}.")
    verify = lambda: _fmt(Fraction(str(sympy.Rational(price) * sympy.Rational(int(factor * 100), 100))))
    return problem, steps, _fmt(final), verify, 1


def t_rate(rng: random.Random):
    v1, v2 = rng.choice([30, 40, 45, 50, 60, 75, 80, 90]), rng.choice([30, 40, 45, 50, 60, 75, 80, 90])
    d = math.lcm(v1, v2) * rng.randint(1, 3)
    t1, t2 = Fraction(d, v1), Fraction(d, v2)
    avg = Fraction(2 * d) / (t1 + t2)
    problem = (f"A car drives {d} km at {v1} km/h and returns along the same road at {v2} km/h. "
               f"What is its average speed for the whole trip, in km/h?")
    steps = (f"Outbound time: {d}/{v1} = {_fmt(t1)} h. Return time: {d}/{v2} = {_fmt(t2)} h.\n"
             f"Total distance {2 * d} km over {_fmt(t1 + t2)} h gives {2 * d}/{_fmt(t1 + t2)} = {_fmt(avg)} km/h.")
    verify = lambda: _fmt(Fraction(str(sympy.Rational(2 * v1 * v2, v1 + v2))))
    return problem, steps, _fmt(avg), verify, 2


def t_work(rng: random.Random):
    a, b = rng.sample(range(2, 13), 2)
    together = Fraction(a * b, a + b)
    problem = (f"Alice can paint a fence in {a} hours and Bob can paint the same fence in {b} hours. "
               f"Working together, how many hours do they need? Give an exact fraction if needed.")
    steps = (f"Alice paints 1/{a} of the fence per hour and Bob paints 1/{b} per hour.\n"
             f"Together they paint 1/{a} + 1/{b} = {a + b}/{a * b} per hour, so the job takes {a * b}/{a + b} = {_fmt(together)} hours.")
    verify = lambda: _fmt(Fraction(str(sympy.solve(sympy.Eq(x * (Rational(1, a) + Rational(1, b)), 1), x)[0])))
    return problem, steps, _fmt(together), verify, 2


def t_quadratic(rng: random.Random):
    r1, r2 = rng.sample(range(-9, 10), 2)
    b, c = -(r1 + r2), r1 * r2
    poly = f"x^2 {'+' if b >= 0 else '-'} {abs(b)}x {'+' if c >= 0 else '-'} {abs(c)}"
    ask = rng.choice(["larger", "smaller"])
    ans = max(r1, r2) if ask == "larger" else min(r1, r2)
    problem = f"Find the {ask} root of {poly} = 0."
    steps = (f"Factor: {poly} = (x - ({r1}))(x - ({r2})), so the roots are {r1} and {r2}.\n"
             f"The {ask} root is {ans}.")
    verify = lambda: str((max if ask == "larger" else min)(sympy.solve(x**2 + b * x + c, x)))
    return problem, steps, str(ans), verify, 2


def t_gcd_lcm(rng: random.Random):
    a, b = rng.randint(12, 180), rng.randint(12, 180)
    kind = rng.choice(["gcd", "lcm"])
    ans = math.gcd(a, b) if kind == "gcd" else math.lcm(a, b)
    name = "greatest common divisor" if kind == "gcd" else "least common multiple"
    fa, fb = sympy.factorint(a), sympy.factorint(b)
    pf = lambda f: " · ".join(f"{p}^{e}" if e > 1 else str(p) for p, e in sorted(f.items()))
    problem = f"What is the {name} of {a} and {b}?"
    steps = f"{a} = {pf(fa)} and {b} = {pf(fb)}.\nTaking the {'lowest' if kind == 'gcd' else 'highest'} power of each prime gives {ans}."
    verify = lambda: str(sympy.gcd(a, b) if kind == "gcd" else sympy.lcm(a, b))
    return problem, steps, str(ans), verify, 1


def t_modular(rng: random.Random):
    a, k, m = rng.randint(2, 30), rng.randint(2, 12), rng.choice([5, 7, 9, 11, 13, 17])
    ans = pow(a, k, m)
    r = a % m
    problem = f"What is the remainder when {a}^{k} is divided by {m}?"
    steps = (f"{a} ≡ {r} (mod {m}), so {a}^{k} ≡ {r}^{k} (mod {m}).\n"
             f"Reducing powers step by step modulo {m} gives {r}^{k} ≡ {ans} (mod {m}).")
    verify = lambda: str(sympy.Mod(sympy.Integer(a) ** k, m))
    return problem, steps, str(ans), verify, 2


def t_dice(rng: random.Random):
    kind = rng.choice(["sum", "at_least", "difference", "product_even"])
    outcomes = [(i, j) for i in range(1, 7) for j in range(1, 7)]
    if kind == "sum":
        s = rng.randint(3, 11)
        event, count = f"the two numbers sum to {s}", sum(1 for i, j in outcomes if i + j == s)
        closed = lambda: 6 - abs(s - 7)
    elif kind == "at_least":
        s = rng.randint(4, 11)
        event, count = f"the sum is at least {s}", sum(1 for i, j in outcomes if i + j >= s)
        closed = lambda: sum(6 - abs(t - 7) for t in range(s, 13))
    elif kind == "difference":
        d = rng.randint(0, 5)
        event, count = f"the two numbers differ by exactly {d}", sum(1 for i, j in outcomes if abs(i - j) == d)
        closed = lambda: 6 if d == 0 else 2 * (6 - d)
    else:
        m = rng.choice([2, 3, 4, 5, 6])
        event, count = f"the product of the two numbers is a multiple of {m}", sum(1 for i, j in outcomes if (i * j) % m == 0)
        closed = lambda: 36 - sum(1 for i in range(1, 7) for j in range(1, 7) if (i * j) % m != 0)
    p = Fraction(count, 36)
    problem = f"Two fair six-sided dice are rolled. What is the probability that {event}? Give a fraction in lowest terms."
    steps = f"There are 36 equally likely outcomes, and {count} of them satisfy the condition ({event}).\nSo the probability is {count}/36 = {_fmt(p)}."
    verify = lambda: _fmt(Fraction(closed(), 36))  # closed form / complement count vs. enumeration
    return problem, steps, _fmt(p), verify, 2


def t_sequence(rng: random.Random):
    a1, d, n = rng.randint(-10, 20), rng.randint(2, 9), rng.randint(5, 30)
    kind = rng.choice(["term", "sum"])
    an = a1 + (n - 1) * d
    total = n * (a1 + an) // 2
    problem = (f"An arithmetic sequence starts {a1}, {a1 + d}, {a1 + 2 * d}, ... "
               f"What is the {'value of its ' + str(n) + 'th term' if kind == 'term' else 'sum of its first ' + str(n) + ' terms'}?")
    steps = (f"The common difference is {d}, so the nth term is {a1} + (n - 1)·{d}.\n"
             + (f"For n = {n}: {a1} + {n - 1}·{d} = {an}." if kind == "term"
                else f"The {n}th term is {an}, and the sum is {n}·({a1} + {an})/2 = {total}."))
    k = symbols("k")
    verify = (lambda: str(sympy.Integer(a1 + (n - 1) * d))) if kind == "term" else (lambda: str(sympy.summation(a1 + (k - 1) * d, (k, 1, n))))
    return problem, steps, str(an if kind == "term" else total), verify, 1 if kind == "term" else 2


def t_geometry(rng: random.Random):
    shape = rng.choice(["rectangle", "triangle", "circle"])
    if shape == "rectangle":
        w, h = rng.randint(2, 30), rng.randint(2, 30)
        ask = rng.choice(["area", "perimeter"])
        ans = str(w * h if ask == "area" else 2 * (w + h))
        problem = f"A rectangle is {w} cm wide and {h} cm tall. What is its {ask} in {'square ' if ask == 'area' else ''}cm?"
        steps = f"{'Area = width × height = ' + str(w) + ' × ' + str(h) if ask == 'area' else 'Perimeter = 2 × (' + str(w) + ' + ' + str(h) + ')'} = {ans}."
        verify = lambda: str(sympy.Integer(w) * h if ask == "area" else 2 * (sympy.Integer(w) + h))
    elif shape == "triangle":
        a, b = rng.randint(3, 20), rng.randint(3, 20)
        c2 = a * a + b * b
        ans_v = sympy.sqrt(c2)
        problem = f"A right triangle has legs of length {a} and {b}. What is the length of its hypotenuse? Give an exact value."
        steps = f"By the Pythagorean theorem the hypotenuse is √({a}² + {b}²) = √{c2} = {ans_v}."
        ans = str(ans_v).replace("sqrt", "sqrt")
        verify = lambda: str(sympy.sqrt(sympy.Integer(a) ** 2 + sympy.Integer(b) ** 2))
    else:
        r = rng.randint(1, 15)
        ask = rng.choice(["area", "circumference"])
        ans_v = sympy.pi * r * r if ask == "area" else 2 * sympy.pi * r
        problem = f"A circle has radius {r}. What is its {ask}? Give the exact answer in terms of π."
        steps = f"{'Area = πr² = π·' + str(r) + '²' if ask == 'area' else 'Circumference = 2πr = 2π·' + str(r)} = {str(ans_v).replace('pi', 'π')}."
        ans = str(ans_v)
        verify = lambda: str(sympy.pi * sympy.Integer(r) ** 2 if ask == "area" else 2 * sympy.pi * sympy.Integer(r))
    return problem, steps, ans, verify, 1


_TRIG_EXACT = {
    ("sin", 0): "0", ("sin", 30): "1/2", ("sin", 45): "sqrt(2)/2", ("sin", 60): "sqrt(3)/2", ("sin", 90): "1",
    ("cos", 0): "1", ("cos", 30): "sqrt(3)/2", ("cos", 45): "sqrt(2)/2", ("cos", 60): "1/2", ("cos", 90): "0",
    ("tan", 0): "0", ("tan", 30): "sqrt(3)/3", ("tan", 45): "1", ("tan", 60): "sqrt(3)",
}
_TRIG_FN = {"sin": sympy.sin, "cos": sympy.cos, "tan": sympy.tan}


def t_trig(rng: random.Random):
    func = rng.choice(["sin", "cos", "tan"])
    deg = rng.choice([0, 30, 45, 60, 90] if func != "tan" else [0, 30, 45, 60])
    ans = _TRIG_EXACT[(func, deg)]
    problem = f"What is {func}({deg}°)? Give the exact value."
    steps = (f"{deg}° is a special angle: {func}({deg}°) = {ans} "
             f"(from the 30-60-90 and 45-45-90 triangles).")
    verify = lambda: str(sympy.simplify(_TRIG_FN[func](sympy.pi * deg / 180)))
    return problem, steps, ans, verify, 2


def _poly_str(coeffs: list[int]) -> str:
    """Render highest-degree-first integer coefficients, e.g. [3, 0, -2, 5] -> '3x^3 - 2x + 5'."""
    deg = len(coeffs) - 1
    parts = []
    for i, c in enumerate(coeffs):
        p = deg - i
        if c == 0:
            continue
        mag = "" if abs(c) == 1 and p > 0 else str(abs(c))
        if p == 0:
            term = mag or "0"
        elif p == 1:
            term = f"{mag}x"
        else:
            term = f"{mag}x^{p}"
        parts.append((c < 0, term))
    if not parts:
        return "0"
    out = parts[0][1] if not parts[0][0] else f"-{parts[0][1]}"
    for neg, term in parts[1:]:
        out += f" {'-' if neg else '+'} {term}"
    return out


def t_calculus(rng: random.Random):
    degree = rng.choice([2, 3])
    coeffs = [rng.choice([c for c in range(-5, 6) if c])] + [rng.randint(-5, 5) for _ in range(degree)]
    poly = _poly_str(coeffs)
    if rng.choice(["derivative", "integral"]) == "derivative":
        a = rng.randint(-3, 3)
        val = sum(k * c * a ** (k - 1) for k, c in
                  ((degree - i, c) for i, c in enumerate(coeffs) if degree - i > 0))
        problem = f"Let f(x) = {poly}. What is the derivative f'({a})?"
        steps = (f"f'(x) is found term by term with the power rule. "
                 f"Evaluating at x = {a} gives {val}.")
        expr = sum(c * x ** (degree - i) for i, c in enumerate(coeffs))
        verify = lambda: str(sympy.diff(expr, x).subs(x, a))
        return problem, steps, str(val), verify, 2
    a, b = sorted(rng.sample(range(-3, 5), 2))
    val = sum(Fraction(c) * (Fraction(b) ** (k + 1) - Fraction(a) ** (k + 1)) / (k + 1)
              for k, c in ((degree - i, c) for i, c in enumerate(coeffs)))
    problem = f"Let f(x) = {poly}. What is the definite integral of f from {a} to {b}?"
    steps = (f"Integrate term by term with the power rule to get the antiderivative F, "
             f"then F({b}) - F({a}) = {_fmt(val)}.")
    expr = sum(c * x ** (degree - i) for i, c in enumerate(coeffs))
    verify = lambda: _fmt(Fraction(str(sympy.integrate(expr, (x, a, b)))))
    return problem, steps, _fmt(val), verify, 3


def t_stats(rng: random.Random):
    n = rng.randint(5, 9)
    vals = rng.sample(range(1, 51), n)
    kind = rng.choice(["mean", "median"])
    if kind == "mean":
        ans = _fmt(Fraction(sum(vals), n))
        problem = f"What is the mean (average) of {', '.join(map(str, vals))}?"
        steps = f"Add the {n} values to get {sum(vals)}, then divide by {n}: {sum(vals)}/{n} = {ans}."
        verify = lambda: _fmt(sympy.Rational(sum(vals), n))
        return problem, steps, ans, verify, 1
    s = sorted(vals)
    mid = n // 2
    ans = str(s[mid]) if n % 2 else _fmt(Fraction(s[mid - 1] + s[mid], 2))
    problem = f"What is the median of {', '.join(map(str, vals))}?"
    steps = (f"Sort the values: {', '.join(map(str, s))}. "
             + (f"With {n} values the middle one is {ans}." if n % 2
                else f"With {n} values the median is the average of the two middle values "
                     f"({s[mid - 1]} + {s[mid]})/2 = {ans}."))
    verify = lambda: str(sympy.Rational(s[mid], 1)) if n % 2 else _fmt(sympy.Rational(s[mid - 1] + s[mid], 2))
    return problem, steps, ans, verify, 1


TEMPLATES: dict[str, Callable] = {
    "arithmetic": t_arithmetic, "linear": t_linear, "system": t_system, "percent": t_percent, "rate": t_rate,
    "work": t_work, "quadratic": t_quadratic, "gcd_lcm": t_gcd_lcm, "modular": t_modular, "dice": t_dice,
    "sequence": t_sequence, "geometry": t_geometry, "trig": t_trig, "calculus": t_calculus, "stats": t_stats,
}


def make_item(family: str, seed: int) -> SynthItem:
    rng = random.Random(f"{family}:{seed}")
    problem, steps, answer, verify, level = TEMPLATES[family](rng)
    try:
        independent = verify()
        ok, how = equivalent(independent, answer)
        note = f"{how}: generator={answer} verifier={independent}"
    except Exception as e:  # a generator bug must surface, never silently pass
        ok, note = False, f"verifier error: {type(e).__name__}: {e}"
    return SynthItem(id=f"synth-math-{family}-{seed}", family=family, level=level, problem=problem,
                     solution=f"{steps}\n#### {answer}", answer=answer, seed=seed, verified=ok, verification=note)


def generate(n: int, seed_start: int = 0, families: list[str] | None = None) -> tuple[list[SynthItem], dict[str, int]]:
    """Round-robin over families; returns (verified items, count of rejected items per family)."""
    fams = families or list(TEMPLATES)
    items, rejected = [], {f: 0 for f in fams}
    next_seed = {f: seed_start for f in fams}  # per-family counters keep the mix balanced despite rejections
    while len(items) < n:
        fam = fams[len(items) % len(fams)]
        item = make_item(fam, next_seed[fam])
        next_seed[fam] += 1
        if item.verified:
            items.append(item)
        else:
            rejected[fam] += 1
    return items, rejected


def build_split(n_train: int, n_test: int, seed_train: int = 0, seed_test: int = 1_000_000) -> tuple[list[SynthItem], list[SynthItem], dict]:
    train, rej_train = generate(n_train, seed_train)
    test, rej_test = generate(n_test + n_test // 2, seed_test)
    seen = {t.problem for t in train}
    disjoint = [t for t in test if t.problem not in seen]
    overlap_removed = len(test) - len(disjoint)
    test = disjoint[:n_test]
    return train, test, {"rejected_train": rej_train, "rejected_test": rej_test, "test_overlap_removed": overlap_removed}


def write_jsonl(items: list[SynthItem], path: str | Path, sft: bool = False) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for it in items:
            row = it.to_sft() if sft else {**asdict(it), "text": it.text}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
