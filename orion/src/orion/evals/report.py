"""Markdown scorecards built only from stored summaries — nothing is typed in by hand."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def pct(v: float) -> str:
    return f"{100 * v:.1f}%"


def ci_str(ci: tuple[float, float] | list[float]) -> str:
    return f"[{pct(ci[0])}, {pct(ci[1])}]"


def scorecard(summaries: list[dict[str, Any]], comparison: dict[str, Any] | None = None) -> str:
    lines = ["| Model | Task | n | Accuracy | 95% CI | No answer | Items/min |", "|---|---|---|---|---|---|---|"]
    for s in summaries:
        std = "" if s.get("standard_benchmark") else " (ORION procedural, not a standard benchmark)"
        lines.append(f"| {s['model']} | {s['task']}{std} | {s['n']} | {pct(s['accuracy'])} | {ci_str(s['ci'])} | "
                     f"{s.get('no_answer_extracted', 0)} | {s.get('items_per_minute', 0)} |")
    if comparison:
        c = comparison
        verdict = ("**improvement (CI excludes 0)**" if c["significant"] and c["diff"] > 0 else
                   "**regression (CI excludes 0)**" if c["significant"] else "no significant difference (CI includes 0)")
        lines += ["", f"Paired difference (after − before): {100 * c['diff']:+.1f} points, 95% CI "
                      f"[{100 * c['ci'][0]:+.1f}, {100 * c['ci'][1]:+.1f}], wins {c['wins']} / losses {c['losses']} / ties {c['ties']} "
                      f"on n = {c['n']} → {verdict}."]
    return "\n".join(lines)


def group_table(summary: dict[str, Any], key: str = "by_group", title: str = "family") -> str:
    lines = [f"| {title} | n | Accuracy | 95% CI |", "|---|---|---|---|"]
    for g, v in summary.get(key, {}).items():
        lines.append(f"| {g} | {v['n']} | {pct(v['accuracy'])} | {ci_str(v['ci'])} |")
    return "\n".join(lines)


def paired_group_table(before: dict[str, Any], after: dict[str, Any], key: str = "by_group", title: str = "family") -> str:
    lines = [f"| {title} | n | Before | After | Δ points |", "|---|---|---|---|---|"]
    for g in sorted(set(before.get(key, {})) | set(after.get(key, {}))):
        b, a = before[key].get(g), after[key].get(g)
        if b and a:
            lines.append(f"| {g} | {a['n']} | {pct(b['accuracy'])} | {pct(a['accuracy'])} | {100 * (a['accuracy'] - b['accuracy']):+.1f} |")
    return "\n".join(lines)


def load_summary(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
