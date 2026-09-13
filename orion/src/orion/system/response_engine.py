"""Response engine: generate -> verify -> improve -> finalize (project brief §23).

For hard questions several candidates are generated and ranked by *independent* checks:
a verifier when one applies (math answer extraction and cross-checking with a calculator tool,
Python syntax/tests for code), and self-consistency (agreement of extracted final answers)
otherwise. If the best candidate fails its check, one repair round feeds the failure back to the
model. The user sees only the finalized answer; the candidates, verdicts and repair feedback stay
in the internal trace.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from orion.verify.code import run_python
from orion.verify.math import extract_final_answer, normalize_answer

THINK = re.compile(r"<think>.*?</think>\s*", re.S)
TOOL_CALL_BLOCK = re.compile(r"<tool_call>.*?</tool_call>\s*", re.S)
PY_FENCE = re.compile(r"```(?:python|py)\n(.*?)```", re.S)


@dataclass
class Candidate:
    text: str
    verdict: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


@dataclass
class EngineResult:
    text: str
    candidates: list[Candidate]
    verification: dict[str, Any]
    repaired: bool = False


def finalize_text(text: str) -> str:
    """Strip internal reasoning and tool-call scaffolding from the user-visible answer."""
    return TOOL_CALL_BLOCK.sub("", THINK.sub("", text)).strip()


def check_math(text: str, checker=None) -> dict[str, Any]:
    ans, how = extract_final_answer(text)
    v: dict[str, Any] = {"kind": "math", "answer": ans, "extraction": how, "ok": ans is not None and how != "none"}
    if ans is not None and checker is not None:
        try:
            v["checker"] = checker(text, ans)
            v["ok"] = bool(v["checker"].get("ok", v["ok"]))
        except Exception as e:  # checker problems never crash the engine
            v["checker"] = {"error": f"{type(e).__name__}: {e}"}
    return v


def check_code(text: str, tests: str | list[str] | None = None, timeout: float = 10.0) -> dict[str, Any]:
    blocks = PY_FENCE.findall(text)
    if not blocks:
        return {"kind": "code", "ok": False, "reason": "no python code block"}
    code = blocks[-1]
    try:
        compile(code, "<candidate>", "exec")
    except SyntaxError as e:
        return {"kind": "code", "ok": False, "reason": f"syntax error: {e.msg} (line {e.lineno})"}
    if tests:
        program = code + "\n\n" + ("\n".join(tests) if isinstance(tests, list) else tests) + "\n"
        r = run_python(program, timeout=timeout)
        return {"kind": "code", "ok": r.ok, "reason": None if r.ok else (r.stderr.strip().splitlines() or ["tests failed"])[-1][:300],
                "timed_out": r.timed_out}
    return {"kind": "code", "ok": True, "reason": "syntax ok; no tests supplied"}


class ResponseEngine:
    def __init__(self, backend, max_tokens: int = 768, sample_temperature: float = 0.7):
        self.backend, self.max_tokens, self.sample_temperature = backend, max_tokens, sample_temperature

    def _generate(self, messages: list[dict[str, str]], n: int) -> list[Candidate]:
        cands = [Candidate(self.backend.chat(messages, max_tokens=self.max_tokens, temperature=0.0))]
        for _ in range(n - 1):
            cands.append(Candidate(self.backend.chat(messages, max_tokens=self.max_tokens, temperature=self.sample_temperature)))
        return cands

    def _verify(self, cands: list[Candidate], intent: str, checker=None, tests=None) -> None:
        for c in cands:
            if intent == "math":
                c.verdict = check_math(c.text, checker)
            elif intent == "code":
                c.verdict = check_code(c.text, tests)
            else:
                c.verdict = {"kind": "none", "ok": True}
        if intent == "math":  # self-consistency: agreement of extracted answers
            votes = Counter(normalize_answer(c.verdict["answer"]) for c in cands if c.verdict.get("answer"))
            for c in cands:
                a = c.verdict.get("answer")
                agreement = votes[normalize_answer(a)] / len(cands) if a else 0.0
                c.verdict["agreement"] = round(agreement, 3)
                c.score = (2.0 if c.verdict.get("checker", {}).get("ok") else 0.0) + (1.0 if c.verdict["ok"] else 0.0) + agreement
        else:
            for c in cands:
                c.score = 1.0 if c.verdict.get("ok") else 0.0

    def run(self, messages: list[dict[str, str]], intent: str = "chat", n_candidates: int = 1, checker=None, tests=None) -> EngineResult:
        cands = self._generate(messages, max(1, n_candidates))
        self._verify(cands, intent, checker, tests)
        best = max(cands, key=lambda c: c.score)
        repaired = False
        if not best.verdict.get("ok", True):
            feedback = best.verdict.get("checker", {}).get("reason") or best.verdict.get("reason") or "no final answer was found"
            repair = messages + [{"role": "assistant", "content": best.text},
                                 {"role": "user", "content": f"Your previous answer failed a check: {feedback}. "
                                                             f"Fix it and give the complete corrected answer."}]
            fixed = Candidate(self.backend.chat(repair, max_tokens=self.max_tokens, temperature=0.0))
            self._verify([fixed], intent, checker, tests)
            cands.append(fixed)
            if fixed.score >= best.score:
                best, repaired = fixed, True
        return EngineResult(finalize_text(best.text), cands, best.verdict, repaired)
