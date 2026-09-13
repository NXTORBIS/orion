"""Promotion gate runner (brief §26): build a VersionCard from a training run card plus
stored eval outputs, compare it against the incumbent card on shared regression items,
and record the decision. No model compute; finishes in seconds.

First version (incumbent = unmodified base model on the same items)::

    .venv/Scripts/python.exe scripts/promote_version.py --version ORION-0.1 \\
        --run-card checkpoints/orion-0.1-synthmath-lora/run_card.json \\
        --adapter checkpoints/orion-0.1-synthmath-lora/final \\
        --task-evals synth-math=runs/evals/orion-0.1/trained \\
        --incumbent-from-eval synth-math=runs/evals/orion-0.1/baseline --incumbent-version ORION-0.0-base

Later versions pass ``--incumbent-card registry/versions/ORION-0.1.json`` instead.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orion.registry.versions import VersionCard, load_card, promote, save_card  # noqa: E402


def load_eval(prefix: str | Path) -> tuple[dict[str, bool], dict]:
    p = Path(prefix)
    rows = [json.loads(l) for l in (p.with_suffix(".jsonl") if p.suffix == "" else p).read_text(
        encoding="utf-8").splitlines() if l.strip()]
    summary = json.loads(p.with_suffix(".summary.json").read_text(encoding="utf-8"))
    return {str(r["id"]): bool(r["ok"]) for r in rows}, summary


def weakest_groups(summary: dict, k: int = 3) -> list[str]:
    groups = summary.get("by_group", {})
    ranked = sorted(groups.items(), key=lambda kv: kv[1].get("accuracy", 1.0))
    return [f"{name} ({info.get('accuracy', 0):.0%}, n={info.get('n', 0)})" for name, info in ranked[:k]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--run-card", required=True)
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--task-evals", nargs="+", default=[],
                    help="NAME=eval_prefix (prefix.jsonl rows carry id/ok; prefix.summary.json the summary)")
    ap.add_argument("--incumbent-card", default=None)
    ap.add_argument("--incumbent-from-eval", nargs="*", default=[])
    ap.add_argument("--incumbent-version", default="ORION-0.0-base")
    ap.add_argument("--weights", default="Qwen/Qwen3.5-0.8B-Base")
    ap.add_argument("--weights-owner", default="Alibaba (Qwen3.5-0.8B-Base)")
    ap.add_argument("--weights-license", default="Apache-2.0")
    ap.add_argument("--registry", default="registry/versions")
    a = ap.parse_args()

    run_card = json.loads(Path(a.run_card).read_text(encoding="utf-8"))
    evaluations, regression_suite = {}, {}
    for spec in a.task_evals:
        name, prefix = spec.split("=", 1)
        items, summary = load_eval(prefix)
        evaluations[name] = summary
        regression_suite[name] = items
    weak = [w for summaries in evaluations.values() for w in weakest_groups(summaries)]
    candidate = VersionCard(
        version=a.version, weights=a.weights, weights_owner=a.weights_owner,
        weights_license=a.weights_license, orion_modified=True, adapter=a.adapter,
        training_run_card=str(a.run_card), dataset_version=(run_card.get("dataset") or {}).get("dataset_version"),
        training_config={"config_path": run_card.get("config_path"),
                         "hyperparameters": (run_card.get("config") or {}).get("hyperparameters", {}),
                         "global_step": run_card.get("global_step"),
                         "metrics": run_card.get("metrics", {})},
        evaluations=evaluations, regression_suite=regression_suite,
        known_weaknesses=weak,
        improvements=[f"SFT LoRA r={(run_card.get('config') or {}).get('lora', {}).get('r')} "
                      f"({run_card.get('trainable_params', 0):,} trainable params) on synth-math v1"],
        parent_version=a.incumbent_version if (a.incumbent_card or a.incumbent_from_eval) else None)

    incumbent = None
    if a.incumbent_card:
        incumbent = load_card(a.incumbent_card)
    elif a.incumbent_from_eval:
        inc_evals, inc_suite = {}, {}
        for spec in a.incumbent_from_eval:
            name, prefix = spec.split("=", 1)
            items, summary = load_eval(prefix)
            inc_evals[name] = summary
            inc_suite[name] = items
        incumbent = VersionCard(version=a.incumbent_version, weights=a.weights,
                                weights_owner=a.weights_owner, weights_license=a.weights_license,
                                orion_modified=False, evaluations=inc_evals,
                                regression_suite=inc_suite, status="current")

    decision = promote(candidate, incumbent)
    reg = ROOT / a.registry
    save_card(candidate, reg)
    if incumbent is not None and incumbent.version == a.incumbent_version and a.incumbent_from_eval:
        save_card(incumbent, reg)
    print(json.dumps({"version": candidate.version, "status": candidate.status, **decision}, indent=2))
    print(f"card: {reg / (candidate.version + '.json')}")


if __name__ == "__main__":
    main()
