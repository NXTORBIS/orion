"""Task definitions. A task yields ``EvalItem``s and scores a response with a verifier; it never
looks at the model. Standard benchmarks (GSM8K-Platinum, MATH-500, MMLU-Pro, IFEval, HumanEval+,
MBPP+) get loaders here; custom tasks can be added as Task subclasses with a ``name`` field,
``items()`` generator, and ``score(item, response)`` verifier.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from orion.synth.math import INSTRUCTION
from orion.synth.science import PROBLEM_GENERATORS as SCIENCE_GENERATORS
from orion.verify.math import verify_math
from orion.verify.code import verify_code_execution
from orion.verify.toolcall import verify_api_call


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


# Science Task (Phase C.1)

class ScienceTask(SynthMathTask):
    """ORION procedural science problems (physics, chemistry, biology)."""

    name = "synth-science"
    standard_benchmark = False

    def __init__(self, path: str | Path, limit: int | None = None):
        super().__init__(path, limit)

    def items(self) -> list[EvalItem]:
        return [EvalItem(
            id=r["id"],
            messages=[{"role": "user", "content": f"{r['problem']}\n{INSTRUCTION}"}],
            gold=r["answer"],
            group=r["family"],
            level=r.get("level"),
            meta={
                "domain": r.get("domain"),
                "concepts": r.get("concepts", []),
                "verifier_type": r.get("verifier_type")
            }
        ) for r in self.rows]

    def score(self, item: EvalItem, response: str) -> Score:
        verifier_type = item.meta.get("verifier_type", "numerical")
        if verifier_type == "numerical":
            v = verify_math(response, item.gold)
            return Score(v.ok, v.extracted, {"extraction": v.extraction, "comparison": v.comparison})
        elif verifier_type == "symbolic":
            # Symbolic comparison (for algebra)
            return Score(item.gold.lower() in response.lower(), response[:50], {"expected": item.gold})
        else:
            # Conceptual: check if response contains key concepts
            concepts = item.meta.get("concepts", [])
            contains_concepts = sum(1 for c in concepts if c.lower() in response.lower())
            ok = contains_concepts >= len(concepts) * 0.5
            return Score(ok, response[:50], {"matched_concepts": contains_concepts})


# Standard Benchmark Loaders (Phases A.1)

class GSM8KPlatinumTask(JsonlMathTask):
    """GSM8K-Platinum: grade-school math word problems (MATH-Hard subset)."""

    def __init__(self, path: str | Path, limit: int | None = None):
        super().__init__(path, name="gsm8k-platinum", question_field="question", answer_field="answer",
                        limit=limit, standard_benchmark=True)


class MathTask(JsonlMathTask):
    """MATH-500: high-school and competition mathematics."""

    def __init__(self, path: str | Path, limit: int | None = None):
        super().__init__(path, name="math-500", question_field="problem", answer_field="solution",
                        limit=limit, standard_benchmark=True)

    def score(self, item: EvalItem, response: str) -> Score:
        # MATH uses symbolic answer format; extract and compare
        v = verify_math(response, item.gold)
        return Score(v.ok, v.extracted, {"extraction": v.extraction, "comparison": v.comparison})


class MMluProTask:
    """MMLU-Pro: Multiple-choice knowledge benchmark (57 subjects)."""

    name = "mmlu-pro"
    standard_benchmark = True

    def __init__(self, path: str | Path, limit: int | None = None):
        self.rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
        self.rows = self.rows[:limit] if limit else self.rows

    def items(self) -> list[EvalItem]:
        out = []
        for i, r in enumerate(self.rows):
            q = r.get("question", r.get("text", ""))
            choices = r.get("options", [])
            choice_text = "\n".join([f"{chr(65+j)}) {c}" for j, c in enumerate(choices)])
            content = f"{q}\n\n{choice_text}\n\nAnswer:"

            # Gold answer is the letter (A, B, C, D, E)
            answer_idx = r.get("answer", r.get("correct_choice", 0))
            gold = chr(65 + answer_idx)

            out.append(EvalItem(
                id=str(r.get("id", i)),
                messages=[{"role": "user", "content": content}],
                gold=gold,
                group=r.get("subject", "all"),
                meta={"subject": r.get("subject", "unknown")}
            ))
        return out

    def score(self, item: EvalItem, response: str) -> Score:
        # Extract first letter from response
        response_upper = response.strip().upper()
        match = re.search(r"[A-E]", response_upper)
        extracted = match.group(0) if match else None
        ok = extracted == item.gold if extracted else False
        return Score(ok, extracted, {"expected": item.gold})


class HumanEvalPlusTask:
    """HumanEval+: Code synthesis with test-case verification."""

    name = "humaneval-plus"
    standard_benchmark = True

    def __init__(self, path: str | Path, limit: int | None = None):
        self.rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
        self.rows = self.rows[:limit] if limit else self.rows

    def items(self) -> list[EvalItem]:
        out = []
        for i, r in enumerate(self.rows):
            prompt = r.get("prompt", "")
            out.append(EvalItem(
                id=str(r.get("task_id", i)),
                messages=[{"role": "user", "content": prompt}],
                gold=r.get("canonical_solution", ""),
                group="all",
                meta={
                    "test_cases": r.get("test", r.get("tests", "")),
                    "entry_point": r.get("entry_point", "solution")
                }
            ))
        return out

    def score(self, item: EvalItem, response: str) -> Score:
        # Verify code execution against test cases
        test_cases = item.meta.get("test_cases", "")
        entry_point = item.meta.get("entry_point", "solution")

        result = verify_code_execution(response, test_cases, entry_point)
        return Score(result.ok, response[:100], {"passed": result.passed, "total": result.total})


class MBPP_PlusTask:
    """MBPP+: Mostly Basic Python Programming (harder version with extra tests)."""

    name = "mbpp-plus"
    standard_benchmark = True

    def __init__(self, path: str | Path, limit: int | None = None):
        self.rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
        self.rows = self.rows[:limit] if limit else self.rows

    def items(self) -> list[EvalItem]:
        out = []
        for i, r in enumerate(self.rows):
            prompt = r.get("text", f"Write a Python function: {r.get('description', '')}")
            out.append(EvalItem(
                id=str(r.get("task_id", i)),
                messages=[{"role": "user", "content": prompt}],
                gold=r.get("code", ""),
                group=r.get("category", "all"),
                meta={
                    "test_cases": r.get("test_list", []),
                    "test_setup": r.get("test_setup_code", "")
                }
            ))
        return out

    def score(self, item: EvalItem, response: str) -> Score:
        # Verify code execution with MBPP test cases
        test_cases = item.meta.get("test_cases", [])
        result = verify_code_execution(response, "\n".join(test_cases) if isinstance(test_cases, list) else test_cases)
        return Score(result.ok, response[:100], {"passed": result.passed, "total": result.total})


class IFEvalTask:
    """IFEval: Instruction Following Evaluation (500 held-out instructions)."""

    name = "ifeval"
    standard_benchmark = True

    def __init__(self, path: str | Path, limit: int | None = None):
        self.rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
        self.rows = self.rows[:limit] if limit else self.rows

    def items(self) -> list[EvalItem]:
        out = []
        for i, r in enumerate(self.rows):
            instruction = r.get("instruction", "")
            constraints = r.get("constraints", [])

            out.append(EvalItem(
                id=str(r.get("instruction_id", i)),
                messages=[{"role": "user", "content": instruction}],
                gold="n/a",  # No fixed gold; scoring checks constraint compliance
                group="instruction-following",
                meta={
                    "constraints": constraints,
                    "input": r.get("input", "")
                }
            ))
        return out

    def score(self, item: EvalItem, response: str) -> Score:
        # Check if response violates any constraints
        constraints = item.meta.get("constraints", [])
        violations = []

        for constraint in constraints:
            c_type = constraint.get("type", "")
            c_value = constraint.get("value", "")

            if c_type == "length":
                max_len = c_value
                if len(response) > max_len:
                    violations.append(f"Exceeds max length {max_len} (got {len(response)})")
            elif c_type == "contains":
                if c_value not in response:
                    violations.append(f"Missing required substring: {c_value}")
            elif c_type == "not_contains":
                if c_value in response:
                    violations.append(f"Contains forbidden substring: {c_value}")
            elif c_type == "starts_with":
                if not response.startswith(c_value):
                    violations.append(f"Must start with: {c_value}")
            elif c_type == "ends_with":
                if not response.endswith(c_value):
                    violations.append(f"Must end with: {c_value}")
            elif c_type == "language":
                # Placeholder for language checking
                pass

        ok = len(violations) == 0
        return Score(ok, response[:100], {"violations": violations})


# Sequences Task

class SequencesTask(SynthMathTask):
    """ORION procedural sequence problems (arithmetic, geometric, Fibonacci, polynomial)."""

    name = "synth-sequences"
    standard_benchmark = False

    def score(self, item: EvalItem, response: str) -> Score:
        v = verify_math(response, item.gold)
        return Score(v.ok, v.extracted, {"extraction": v.extraction, "comparison": v.comparison})


# Systems Task

class SystemsTask(SynthMathTask):
    """ORION procedural systems of equations (2x2, 3x3)."""

    name = "synth-systems"
    standard_benchmark = False

    def score(self, item: EvalItem, response: str) -> Score:
        v = verify_math(response, item.gold)
        return Score(v.ok, v.extracted, {"extraction": v.extraction, "comparison": v.comparison})


# Coding Task

class CodingTask(SynthMathTask):
    """ORION procedural coding problems (algorithms, debugging, design)."""

    name = "synth-coding"
    standard_benchmark = False

    def items(self) -> list[EvalItem]:
        return [EvalItem(
            id=r["id"],
            messages=[{"role": "user", "content": f"{r['problem']}\nAnswer:"}],
            gold=r["answer"],
            group=r["family"],
            level=r.get("level"),
            meta={"category": r.get("category")}
        ) for r in self.rows]

    def score(self, item: EvalItem, response: str) -> Score:
        gold = item.gold.lower().strip()
        resp = response.lower().strip()
        ok = gold in resp or resp in gold or resp.startswith(gold[:20])
        return Score(ok, response[:100], {"expected": gold})


# Reasoning Task

class ReasoningTask(SynthMathTask):
    """ORION reasoning problems (logic, analogies, common sense, causality)."""

    name = "synth-reasoning"
    standard_benchmark = False

    def items(self) -> list[EvalItem]:
        return [EvalItem(
            id=r["id"],
            messages=[{"role": "user", "content": f"{r['problem']}\nAnswer:"}],
            gold=r["answer"],
            group=r["family"],
            level=r.get("level"),
            meta={"reasoning_type": r.get("reasoning_type")}
        ) for r in self.rows]

    def score(self, item: EvalItem, response: str) -> Score:
        gold = item.gold.lower().strip()
        resp = response.lower().strip()
        ok = gold in resp or resp in gold or (len(gold) > 5 and gold[:5] in resp)
        return Score(ok, response[:100], {"expected": gold})


# Knowledge Task

class KnowledgeTask(SynthMathTask):
    """ORION knowledge problems (history, geography, culture, science facts)."""

    name = "synth-knowledge"
    standard_benchmark = False

    def items(self) -> list[EvalItem]:
        return [EvalItem(
            id=r["id"],
            messages=[{"role": "user", "content": f"{r['problem']}\nAnswer:"}],
            gold=r["answer"],
            group=r["family"],
            level=r.get("level"),
            meta={"domain": r.get("domain")}
        ) for r in self.rows]

    def score(self, item: EvalItem, response: str) -> Score:
        gold = item.gold.lower().strip()
        resp = response.lower().strip()
        ok = gold in resp or resp in gold or (len(gold) > 3 and gold.split()[0] in resp)
        return Score(ok, response[:100], {"expected": gold})


# Instruction Task

class InstructionTask(SynthMathTask):
    """ORION instruction-following problems (format, constraints, tone, multi-turn)."""

    name = "synth-instruction"
    standard_benchmark = False

    def items(self) -> list[EvalItem]:
        return [EvalItem(
            id=r["id"],
            messages=[{"role": "user", "content": r['problem']}],
            gold=r["answer"],
            group=r["family"],
            level=r.get("level"),
            meta={"instruction_type": r.get("instruction_type")}
        ) for r in self.rows]

    def score(self, item: EvalItem, response: str) -> Score:
        gold = item.gold.lower().strip()
        resp = response.lower().strip()
        # Instruction following: check if key elements are present
        ok = len(resp) > 10 and (gold[:30].lower() in resp or resp[:30].lower() in gold)
        return Score(ok, response[:100], {"expected": gold})


# Task Registry

TASK_REGISTRY = {
    "synth-math": SynthMathTask,
    "synth-science": ScienceTask,
    "synth-sequences": SequencesTask,
    "synth-systems": SystemsTask,
    "synth-coding": CodingTask,
    "synth-reasoning": ReasoningTask,
    "synth-knowledge": KnowledgeTask,
    "synth-instruction": InstructionTask,
    "gsm8k-platinum": GSM8KPlatinumTask,
    "math-500": MathTask,
    "mmlu-pro": MMluProTask,
    "humaneval-plus": HumanEvalPlusTask,
    "mbpp-plus": MBPP_PlusTask,
    "ifeval": IFEvalTask,
}


def load_task(name: str, path: str | Path, limit: int | None = None) -> Any:
    """Load a task by name from registry."""
    if name not in TASK_REGISTRY:
        raise ValueError(f"Unknown task: {name}. Available: {list(TASK_REGISTRY.keys())}")
    return TASK_REGISTRY[name](path, limit)
