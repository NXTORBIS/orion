"""Blind pairwise comparison (project brief §20).

Stored outputs from several systems on the same prompts are turned into anonymised, randomly
ordered pairs ("A" vs "B"). Judges — humans through a JSONL file, or a judge model through a
callable — never see system names. Verdicts are unblinded afterwards and summarised with
bootstrap confidence intervals. Nothing here can produce a score without real judgements.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .metrics import bootstrap_ci

CRITERIA = ["correctness", "reasoning", "completeness", "instruction_following", "overall"]


def load_outputs(path: str | Path, system: str) -> dict[str, dict[str, Any]]:
    rows = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            rows[r["id"]] = {"system": system, "prompt": r["prompt"], "response": r["response"], "gold": r.get("gold")}
    return rows


def make_pairs(outputs: dict[str, dict[str, dict[str, Any]]], seed: int = 0) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    """outputs: system -> {item_id -> row}. Returns (blinded pairs, key mapping pair_id -> {'A': system, 'B': system})."""
    rng = random.Random(seed)
    systems = sorted(outputs)
    pairs, key = [], {}
    for i, s1 in enumerate(systems):
        for s2 in systems[i + 1:]:
            for item_id in sorted(set(outputs[s1]) & set(outputs[s2])):
                a, b = (s1, s2) if rng.random() < 0.5 else (s2, s1)
                pid = f"{item_id}:{len(pairs)}"
                pairs.append({"pair_id": pid, "prompt": outputs[s1][item_id]["prompt"], "gold": outputs[s1][item_id].get("gold"),
                              "A": outputs[a][item_id]["response"], "B": outputs[b][item_id]["response"]})
                key[pid] = {"A": a, "B": b}
    rng.shuffle(pairs)
    return pairs, key


def write_judging_file(pairs: list[dict[str, Any]], path: str | Path) -> None:
    """Human judging: fill `verdict` per criterion with "A", "B" or "tie"."""
    with open(path, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps({**p, "verdicts": {c: None for c in CRITERIA}}, ensure_ascii=False) + "\n")


def judge_with_model(pairs: list[dict[str, Any]], judge: Callable[[str, str, str, str | None], dict[str, str]]) -> list[dict[str, Any]]:
    """judge(prompt, A, B, gold) -> {criterion: "A"|"B"|"tie"}. Position bias is reduced by also judging the swapped order."""
    out = []
    for p in pairs:
        v1 = judge(p["prompt"], p["A"], p["B"], p.get("gold"))
        v2 = judge(p["prompt"], p["B"], p["A"], p.get("gold"))
        swapped = {c: {"A": "B", "B": "A"}.get(v, v) for c, v in v2.items()}
        verdicts = {c: (v1.get(c) if v1.get(c) == swapped.get(c) else "tie") for c in CRITERIA}
        out.append({**p, "verdicts": verdicts})
    return out


def unblind(judged: list[dict[str, Any]], key: dict[str, dict[str, str]]) -> dict[str, Any]:
    wins: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))  # criterion -> system -> [1/0.5/0]
    head_to_head: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for p in judged:
        k = key[p["pair_id"]]
        for c, v in (p.get("verdicts") or {}).items():
            if v not in ("A", "B", "tie"):
                continue
            for side in ("A", "B"):
                wins[c][k[side]].append(1.0 if v == side else 0.5 if v == "tie" else 0.0)
            if c == "overall":
                if v == "tie":
                    head_to_head[k["A"]][k["B"]] += 0
                else:
                    head_to_head[k[v]][k["A" if v == "B" else "B"]] += 1
    summary = {c: {s: {"n": len(vals), "win_rate": sum(vals) / len(vals), "ci": bootstrap_ci([x for x in vals])}
                   for s, vals in sysmap.items()} for c, sysmap in wins.items()}
    return {"by_criterion": summary, "head_to_head_overall_wins": {a: dict(b) for a, b in head_to_head.items()},
            "judged_pairs": sum(1 for p in judged if any(v in ("A", "B", "tie") for v in (p.get("verdicts") or {}).values()))}


def scorecard_md(result: dict[str, Any]) -> str:
    lines = ["| Criterion | System | n | Win rate | 95% CI |", "|---|---|---|---|---|"]
    for c, sysmap in result["by_criterion"].items():
        for s, v in sorted(sysmap.items(), key=lambda kv: -kv[1]["win_rate"]):
            lines.append(f"| {c} | {s} | {v['n']} | {100 * v['win_rate']:.1f}% | [{100 * v['ci'][0]:.1f}%, {100 * v['ci'][1]:.1f}%] |")
    lines.append(f"\nJudged pairs: {result['judged_pairs']}. Win rate counts a tie as half a win; systems were anonymised and order-randomised.")
    return "\n".join(lines)
