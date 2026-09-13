"""Version cards and the promotion gate.

Promotion rule (both must hold, on the frozen regression suite, item-paired):
  1. the candidate's overall accuracy beats the incumbent's with a 95% paired-bootstrap CI that
     excludes zero;
  2. no category's accuracy drops by more than its tolerance (default 2 points).
Anything else is archived with its results. A better model is never replaced by a worse one.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from orion.evals.metrics import paired_bootstrap_diff


@dataclass
class VersionCard:
    version: str                       # e.g. ORION-0.1
    weights: str                       # repo id or path of the underlying weights
    weights_owner: str                 # who trained the underlying weights (e.g. "Alibaba (Qwen3.5-0.8B-Base)")
    weights_license: str
    orion_modified: bool               # True only if ORION trained/changed the weights (adapter counts)
    adapter: str | None = None
    training_run_card: str | None = None
    dataset_version: str | None = None
    training_config: dict[str, Any] = field(default_factory=dict)
    evaluations: dict[str, Any] = field(default_factory=dict)   # task -> summary dict
    regression_suite: dict[str, Any] = field(default_factory=dict)  # task -> {item_id: ok}
    known_weaknesses: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    parent_version: str | None = None
    status: str = "candidate"          # candidate | current | archived | rejected
    promotion: dict[str, Any] = field(default_factory=dict)
    created_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def save_card(card: VersionCard, registry_dir: str | Path) -> Path:
    d = Path(registry_dir)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{card.version}.json"
    p.write_text(json.dumps(card.to_dict(), indent=2), encoding="utf-8")
    return p


def load_card(path: str | Path) -> VersionCard:
    return VersionCard(**json.loads(Path(path).read_text(encoding="utf-8")))


def promote(candidate: VersionCard, incumbent: VersionCard | None, tolerance_points: float = 2.0,
            categories: dict[str, str] | None = None) -> dict[str, Any]:
    """Compare on the intersection of regression items per task; return the decision with evidence.

    ``categories`` maps task name -> category label (defaults to the task name itself).
    """
    if incumbent is None:
        decision = {"promote": True, "reason": "no incumbent", "overall": None, "categories": {}}
    else:
        flags_c, flags_i, per_cat = [], [], {}
        cats = categories or {}
        for task, cand_items in candidate.regression_suite.items():
            inc_items = incumbent.regression_suite.get(task, {})
            ids = sorted(set(cand_items) & set(inc_items))
            if not ids:
                continue
            c = [bool(cand_items[i]) for i in ids]
            i_ = [bool(inc_items[i]) for i in ids]
            flags_c += c
            flags_i += i_
            cat = cats.get(task, task)
            bucket = per_cat.setdefault(cat, {"n": 0, "candidate": 0, "incumbent": 0})
            bucket["n"] += len(ids)
            bucket["candidate"] += sum(c)
            bucket["incumbent"] += sum(i_)
        if not flags_c:
            decision = {"promote": False, "reason": "no shared regression items", "overall": None, "categories": {}}
        else:
            overall = paired_bootstrap_diff(flags_i, flags_c)
            regressions = []
            for cat, b in per_cat.items():
                b["delta_points"] = 100 * (b["candidate"] - b["incumbent"]) / b["n"]
                if b["delta_points"] < -tolerance_points:
                    regressions.append(cat)
            better = overall["significant"] and overall["diff"] > 0
            decision = {"promote": better and not regressions,
                        "reason": ("better overall and no category regression" if better and not regressions else
                                   f"category regression beyond {tolerance_points} points: {regressions}" if regressions else
                                   "overall difference not significant" if not overall["significant"] else "worse overall"),
                        "overall": overall, "categories": per_cat}
    decision["decided_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    decision["incumbent"] = incumbent.version if incumbent else None
    candidate.promotion = decision
    candidate.status = "current" if decision["promote"] else "rejected"
    if decision["promote"] and incumbent is not None:
        incumbent.status = "archived"
    return decision
