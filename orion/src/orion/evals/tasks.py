"""Task definitions. A task yields ``EvalItem``s and scores a response with a verifier; it never
looks at the model. Standard benchmarks (GSM8K-Platinum, MATH-500, MMLU-Pro, IFEval, HumanEval+,
MBPP+) get loaders here once their files are approved and present; until then only ORION's own
procedural sets are available, and reports say so.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from orion.synth.math import INSTRUCTION
from orion.verify.math import verify_math


@dataclass
class EvalItem:
    id: str
    messages: list[dict[str, str]]
    gold: str
    group: str = "all"
    level: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Score:
    ok: bool
    extracted: str | None
    details: dict[str, Any] = field(default_factory=dict)


class SynthMathTask:
    """ORION procedural math held-out set (data/raw/synth_math/test.jsonl)."""

    name = "synth-math"
    standard_benchmark = False

    def __init__(self, path: str | Path, limit: int | None = None):
        rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
        self.rows = rows[:limit] if limit else rows

    def items(self) -> list[EvalItem]:
        return [EvalItem(id=r["id"], messages=[{"role": "user", "content": f"{r['problem']}\n{INSTRUCTION}"}],
                         gold=r["answer"], group=r["family"], level=r.get("level")) for r in self.rows]

    def score(self, item: EvalItem, response: str) -> Score:
        v = verify_math(response, item.gold)
        return Score(v.ok, v.extracted, {"extraction": v.extraction, "comparison": v.comparison})


class JsonlMathTask(SynthMathTask):
    """Generic math JSONL with ``question``/``answer`` fields (e.g. GSM8K-style files)."""

    def __init__(self, path: str | Path, name: str, question_field: str = "question", answer_field: str = "answer",
                 limit: int | None = None, standard_benchmark: bool = True):
        super().__init__(path, limit)
        self.name, self.standard_benchmark = name, standard_benchmark
        self.q, self.a = question_field, answer_field

    def items(self) -> list[EvalItem]:
        out = []
        for i, r in enumerate(self.rows):
            gold = str(r[self.a])
            if "####" in gold:  # GSM8K solutions end with "#### <answer>"
                gold = gold.split("####")[-1].strip()
            out.append(EvalItem(id=str(r.get("id", i)), messages=[{"role": "user", "content": f"{r[self.q]}\n{INSTRUCTION}"}],
                                gold=gold, group=str(r.get("category", r.get("level", "all")))))
        return out
