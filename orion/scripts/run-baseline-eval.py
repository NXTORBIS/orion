#!/usr/bin/env python3
"""Phase A: Run baseline evaluation of ORION-0.1 across all available tasks.

This script:
1. Loads ORION-0.1 (Qwen3.5-0.8B-Base + LoRA adapter)
2. Runs inference on each task (math, reasoning, code, instruction-following)
3. Scores responses using task-specific verifiers
4. Generates baseline version card for regression tracking
5. Identifies hard examples for future training

Usage:
    python scripts/run-baseline-eval.py --model-name orion-0.1 --output runs/baseline/
"""

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from orion.evals.tasks import TASK_REGISTRY
from orion.evals.runner import HFGenerator, run_task
from orion.evals.metrics import bootstrap_ci, paired_bootstrap_diff
from orion.registry.versions import VersionCard

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    task_name: str
    total: int
    correct: int
    accuracy: float
    by_group: dict
    outputs_path: str


def load_model(model_name: str, adapter_path: str | None = None):
    """Load model + optional LoRA adapter."""
    import torch

    logger.info(f"Loading model: {model_name}")

    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    generator = HFGenerator(
        model_dir=model_name,
        adapter_dir=adapter_path,
        dtype=dtype,
        batch_size=4,
        max_new_tokens=256
    )

    return generator


def run_task_eval(generator, task_name: str, task_path: str, limit: int | None = None, output_dir: Path | None = None):
    """Run evaluation on a single task."""
    logger.info(f"Evaluating task: {task_name}")

    if not Path(task_path).exists():
        logger.warning(f"Task file not found: {task_path}, skipping {task_name}")
        return None

    try:
        # Load task
        TaskClass = TASK_REGISTRY[task_name]
        task = TaskClass(task_path, limit=limit)

        # Run task
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{task_name}.jsonl"
        else:
            output_file = output_dir / f"{task_name}.jsonl"

        summary = run_task(task, generator, output_file, limit=limit)

        # Extract results
        accuracy = summary.get("accuracy", 0)
        total = len(task.items()[:limit]) if limit else len(task.items())
        correct = int(accuracy * total)

        by_group = {}
        if "by_group" in summary:
            for group, stats in summary["by_group"].items():
                by_group[group] = {
                    "n": stats.get("n", 0),
                    "accuracy": stats.get("accuracy", 0)
                }

        logger.info(f"  Accuracy: {accuracy:.1%} ({correct}/{total})")

        return EvalResult(
            task_name=task_name,
            total=total,
            correct=correct,
            accuracy=accuracy,
            by_group=by_group,
            outputs_path=str(output_file) if output_file else "none",
        )

    except Exception as e:
        logger.error(f"Error evaluating {task_name}: {e}", exc_info=True)
        return None


def main():
    parser = argparse.ArgumentParser(description="Run baseline evaluation of ORION-0.1")
    parser.add_argument("--model-name", default="Qwen/Qwen3.5-0.8B-Base", help="Base model name or path")
    parser.add_argument("--adapter-path", default="checkpoints/orion-0.1-synthmath-lora/final", help="LoRA adapter path")
    parser.add_argument("--output", default="runs/baseline/", help="Output directory")
    parser.add_argument("--limit-per-task", type=int, default=100, help="Limit items per task (for quick eval)")
    parser.add_argument("--skip-tasks", nargs="+", default=[], help="Skip these tasks")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load model
    generator = load_model(args.model_name, args.adapter_path)

    # Define tasks (with file paths)
    tasks_to_eval = {
        "synth-math": "data/raw/synth_math/test.jsonl",
        "synth-science": "data/raw/synth_science/test.jsonl",
        # These require external files; add them as they become available:
        # "gsm8k-platinum": "datasets/gsm8k_platinum/test.jsonl",
        # "math-500": "datasets/math_500/test.jsonl",
        # "mmlu-pro": "datasets/mmlu_pro/test.jsonl",
        # "humaneval-plus": "datasets/humaneval_plus/test.jsonl",
        # "mbpp-plus": "datasets/mbpp_plus/test.jsonl",
        # "ifeval": "datasets/ifeval/test.jsonl",
    }

    # Run evaluations
    logger.info(f"Starting baseline evaluation (limit={args.limit_per_task} items/task)")
    results = {}

    for task_name, task_path in tasks_to_eval.items():
        if task_name in args.skip_tasks:
            logger.info(f"Skipping {task_name}")
            continue

        result = run_task_eval(generator, task_name, task_path, limit=args.limit_per_task, output_dir=output_dir)
        if result:
            results[task_name] = asdict(result)

    # Save results summary
    summary_file = output_dir / "summary.json"
    with open(summary_file, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Saved summary to {summary_file}")

    # Print summary
    print("\n" + "=" * 60)
    print("BASELINE EVALUATION SUMMARY (ORION-0.1)")
    print("=" * 60)
    for task_name, result in results.items():
        print(f"\n{task_name}:")
        print(f"  Accuracy: {result['accuracy']:.1%} ({result['correct']}/{result['total']})")
        if result["by_group"]:
            for group, g_result in result["by_group"].items():
                print(f"    {group}: {g_result['accuracy']:.1%} (n={g_result['n']})")


if __name__ == "__main__":
    main()
