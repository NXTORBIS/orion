"""Hard-example mining and empirical difficulty (project brief §17–18).

Empirical difficulty of an item = 1 − pass rate of the current model(s) over stored evaluation
runs. Buckets: L1 basic (≥ 0.9 pass) … L5 frontier (0 pass). Mining returns the families /
groups where the model fails most, so the next data round is targeted there instead of on
examples the model already solves. Every input is a stored eval output file; nothing is guessed.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

LEVELS = [(0.9, 1), (0.7, 2), (0.4, 3), (0.01, 4), (-1.0, 5)]


def level_for(pass_rate: float) -> int:
    for threshold, level in LEVELS:
        if pass_rate >= threshold:
            return level
    return 5


def load_runs(paths: list[str | Path]) -> dict[str, list[dict[str, Any]]]:
    """item id -> list of {ok, group, response, gold} across runs."""
    by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                by_item[r["id"]].append({"ok": bool(r["ok"]), "group": r.get("group", "all"), "level": r.get("level"),
                                         "response": r.get("response", ""), "gold": r.get("gold"), "run": str(p)})
    return by_item


def empirical_difficulty(by_item: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    out = {}
    for item_id, rows in by_item.items():
        rate = sum(r["ok"] for r in rows) / len(rows)
        out[item_id] = {"pass_rate": rate, "level": level_for(rate), "group": rows[0]["group"], "n_runs": len(rows)}
    return out


def mine(by_item: dict[str, list[dict[str, Any]]], top_k: int = 5) -> dict[str, Any]:
    diff = empirical_difficulty(by_item)
    by_group: dict[str, list[float]] = defaultdict(list)
    for d in diff.values():
        by_group[d["group"]].append(d["pass_rate"])
    group_fail = {g: {"n": len(v), "pass_rate": sum(v) / len(v), "fail_rate": 1 - sum(v) / len(v)} for g, v in by_group.items()}
    weakest = sorted(group_fail.items(), key=lambda kv: -kv[1]["fail_rate"])[:top_k]
    buckets = defaultdict(int)
    for d in diff.values():
        buckets[f"L{d['level']}"] += 1
    failures = [{"id": i, **d} for i, d in diff.items() if d["pass_rate"] < 1.0]
    return {"buckets": dict(sorted(buckets.items())), "weakest_groups": weakest, "failed_items": sorted(failures, key=lambda x: x["pass_rate"])[:200],
            "targets": {g: max(1, round(4 * v["fail_rate"])) for g, v in weakest}}  # relative oversampling weights for the next data round


def report_md(m: dict[str, Any]) -> str:
    lines = ["| Bucket | Items |", "|---|---|"] + [f"| {b} | {n} |" for b, n in m["buckets"].items()]
    lines += ["", "| Weakest group | n | Pass rate | Oversampling weight |", "|---|---|---|---|"]
    lines += [f"| {g} | {v['n']} | {100 * v['pass_rate']:.0f}% | {m['targets'][g]}x |" for g, v in m["weakest_groups"]]
    return "\n".join(lines)
