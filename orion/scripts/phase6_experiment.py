"""Phase 6 — ORION-0.1: a real, small-scale training experiment on this laptop.

    1. generate verifier-checked procedural math (train / held-out test, disjoint by construction)
    2. run the data pipeline on the training set (provenance, filters, dedup, quality, stats)
    3. convert the kept records to SFT prompt/completion files (+ dataset version manifest)
    4. evaluate the base model on the held-out set (stored outputs, bootstrap CI)
    5. LoRA SFT (configs/train/laptop_lora_sft.yaml) with MLflow tracking and a run card
    6. evaluate the trained model on the same items; paired bootstrap before/after
    7. write docs/06_experiment_report.md from the stored results only

Usage (from orion/):
    .venv/Scripts/python.exe scripts/phase6_experiment.py --n-train 1200 --n-test 100 [--skip-train] [--only data|baseline|train|eval|report]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orion.data.contamination import EvalIndex  # noqa: E402
from orion.data.pipeline import run as run_pipeline  # noqa: E402
from orion.evals.metrics import paired_bootstrap_diff  # noqa: E402
from orion.evals.report import group_table, paired_group_table, scorecard  # noqa: E402
from orion.evals.runner import HFGenerator, run_task  # noqa: E402
from orion.evals.tasks import SynthMathTask  # noqa: E402
from orion.synth.math import INSTRUCTION, build_split, write_jsonl  # noqa: E402
from orion.train.common import load_config  # noqa: E402

RAW = ROOT / "data/raw/synth_math"
PROC = ROOT / "data/processed/synth_math_v1"
EVAL_DIR = ROOT / "runs/evals/orion-0.1"
TRAIN_CFG = ROOT / "configs/train/laptop_lora_sft.yaml"
REPORT = ROOT / "docs/06_experiment_report.md"


def step_data(n_train: int, n_test: int) -> dict:
    train, test, rep = build_split(n_train, n_test)
    write_jsonl(train, RAW / "train.jsonl")
    write_jsonl(test, RAW / "test.jsonl")
    # explicit disjointness check (the pipeline's n-gram contamination stage is off for templated data)
    train_problems = {t.problem for t in train}
    overlap = sum(1 for t in test if t.problem in train_problems)
    idx = EvalIndex()
    idx.add_many([t.problem for t in test], "synth-math-test")
    shared_13gram_docs = sum(1 for t in train if idx.hits(t.problem) > 0)
    gen_report = {"n_train": len(train), "n_test": len(test), **rep, "exact_problem_overlap": overlap,
                  "train_docs_sharing_a_13gram_with_test": shared_13gram_docs,
                  "families": sorted({t.family for t in train}),
                  "levels_train": {str(l): sum(1 for t in train if t.level == l) for l in (1, 2, 3)}}
    assert overlap == 0, "held-out problems must not appear in training data"
    manifest = run_pipeline(ROOT / "configs/data/synth_math_v1.yaml", ROOT)
    kept = [json.loads(l) for l in (PROC / "kept.jsonl").read_text(encoding="utf-8").splitlines()]
    files = {"train": open(PROC / "sft_train.jsonl", "w", encoding="utf-8"),
             "validation": open(PROC / "sft_validation.jsonl", "w", encoding="utf-8")}
    counts = {"train": 0, "validation": 0}
    for r in kept:
        m = r["meta"]
        row = {"id": r["id"], "family": m["family"], "level": m["level"],
               "prompt": [{"role": "user", "content": f"{m['problem']}\n{INSTRUCTION}"}],
               "completion": [{"role": "assistant", "content": m["solution"]}]}
        split = m["split_assigned"]
        files[split].write(json.dumps(row, ensure_ascii=False) + "\n")
        counts[split] += 1
    for f in files.values():
        f.close()
    gen_report.update(pipeline_manifest=manifest, sft_counts=counts)
    (PROC / "generation_report.json").write_text(json.dumps(gen_report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in gen_report.items() if k != "pipeline_manifest"}, indent=2))
    return gen_report


def step_eval(tag: str, adapter: Path | None, n_test: int | None, batch_size: int, max_new_tokens: int) -> dict:
    cfg = load_config(TRAIN_CFG)
    gen = HFGenerator(ROOT / cfg["model"], adapter, batch_size=batch_size, max_new_tokens=max_new_tokens)
    task = SynthMathTask(RAW / "test.jsonl", limit=n_test)
    summary = run_task(task, gen, EVAL_DIR / f"{tag}.jsonl")
    print(json.dumps({k: summary[k] for k in ("model", "n", "accuracy", "ci", "seconds", "no_answer_extracted")}, indent=2))
    return summary


def step_train() -> dict:
    from orion.train import sft

    return sft.main(str(TRAIN_CFG))


def step_report() -> None:
    gen = json.loads((PROC / "generation_report.json").read_text(encoding="utf-8"))
    before = json.loads((EVAL_DIR / "baseline.summary.json").read_text(encoding="utf-8"))
    after_path = EVAL_DIR / "trained.summary.json"
    after = json.loads(after_path.read_text(encoding="utf-8")) if after_path.exists() else None
    card_path = ROOT / load_config(TRAIN_CFG)["output_dir"] / "run_card.json"
    card = json.loads(card_path.read_text(encoding="utf-8")) if card_path.exists() else None

    lines = ["# ORION-0.1 — Phase 6 experiment report", "",
             "Generated by `scripts/phase6_experiment.py` from stored outputs; every number below can be traced to a",
             "file under `runs/evals/orion-0.1/` or the training run card. **The evaluation set is ORION's own",
             "procedurally generated, verifier-scored math set — not a standard benchmark — so these numbers measure",
             "in-distribution improvement on templated problems, nothing broader.**", "",
             "## Setup", "",
             f"- Base model: `{before['model'].split('+')[0]}` (Qwen/Qwen3.5-0.8B-Base, Apache-2.0), fp32 on CPU.",
             f"- Training data: {gen['sft_counts']['train']} SFT examples kept by the pipeline (validation {gen['sft_counts']['validation']}); "
             f"dataset version `{gen['pipeline_manifest']['dataset_version']}`; generator rejections {gen['rejected_train']}.",
             f"- Held-out test: {before['n']} problems, seeds disjoint from training, exact-problem overlap = {gen['exact_problem_overlap']} "
             f"(training docs sharing a template 13-gram with a test problem: {gen['train_docs_sharing_a_13gram_with_test']} — expected for templated data).",
             f"- Families: {', '.join(gen['families'])}.", ""]
    if card:
        hp = card["config"]["hyperparameters"]
        lines += ["## Training run", "",
                  f"- LoRA r={card['config']['lora']['r']} on `{card['config']['lora']['target_modules']}`: {card['trainable_params']:,} trainable of {card['model_params']:,} parameters.",
                  f"- {card['global_step']} optimizer steps, batch {hp['batch_size']}×{hp['grad_accum']}, lr {hp['learning_rate']}, max_length {hp['max_length']}.",
                  f"- Duration {card['duration_seconds'] / 60:.1f} min on {card['hardware']['cpu']}; final train loss {card['metrics'].get('final_train_loss')}, "
                  f"final eval loss {card['metrics'].get('final_eval_loss')}.", ""]
        losses = [(h["step"], h["loss"]) for h in card["log_history"] if "loss" in h]
        if losses:
            lines += ["Loss curve (step: loss): " + ", ".join(f"{s}: {l:.3f}" for s, l in losses), ""]
    lines += ["## Results", ""]
    summaries = [before] + ([after] if after else [])
    comparison = None
    if after:
        b_rows = {json.loads(l)["id"]: json.loads(l)["ok"] for l in (EVAL_DIR / "baseline.jsonl").read_text(encoding="utf-8").splitlines()}
        a_rows = {json.loads(l)["id"]: json.loads(l)["ok"] for l in (EVAL_DIR / "trained.jsonl").read_text(encoding="utf-8").splitlines()}
        ids = [i for i in b_rows if i in a_rows]
        comparison = paired_bootstrap_diff([b_rows[i] for i in ids], [a_rows[i] for i in ids])
    lines += [scorecard(summaries, comparison), ""]
    if after:
        lines += ["### By family", "", paired_group_table(before, after), "", "### By level", "", paired_group_table(before, after, "by_level", "level"), ""]
    else:
        lines += ["### Baseline by family", "", group_table(before), ""]
    lines += ["## Honest reading", "",
              "- This is a narrow, in-distribution test: the model was trained on the same "
              f"{len(gen['families'])} templates it is tested on, with different numbers.",
              "  It validates the pipeline end to end and shows whether training moved the needle; it says nothing about general math ability.",
              "- Standard benchmarks (GSM8K-Platinum, MATH-500, …) were not downloaded (not approved), so no claim is made about them.",
              "- The base model is a 0.8B pretrained checkpoint prompted with a chat template; a low baseline partly reflects format-following, not only math.",
              "- Confidence intervals are 95% bootstrap; the paired comparison is on identical items."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-train", type=int, default=1200)
    ap.add_argument("--n-test", type=int, default=100)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--max-new-tokens", type=int, default=200)
    ap.add_argument("--skip-train", action="store_true")
    ap.add_argument("--only", choices=["data", "baseline", "train", "eval", "report"])
    a = ap.parse_args()
    t0 = time.perf_counter()
    steps = [a.only] if a.only else ["data", "baseline", "train", "eval", "report"]
    if a.skip_train:
        steps = [s for s in steps if s not in ("train", "eval")]
    adapter = ROOT / load_config(TRAIN_CFG)["output_dir"] / "final"
    for s in steps:
        print(f"\n===== {s} ({(time.perf_counter() - t0) / 60:.1f} min elapsed) =====")
        if s == "data":
            step_data(a.n_train, a.n_test)
        elif s == "baseline":
            step_eval("baseline", None, a.n_test, a.batch_size, a.max_new_tokens)
        elif s == "train":
            step_train()
        elif s == "eval":
            step_eval("trained", adapter, a.n_test, a.batch_size, a.max_new_tokens)
        elif s == "report":
            step_report()
    print(f"\ndone in {(time.perf_counter() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
