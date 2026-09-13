#!/usr/bin/env python3
"""Quick evaluation for fast-track training - 5 minutes vs 30 minutes"""

import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def quick_eval(model_path: str, adapter_path: str, output_dir: str = "runs/quick-eval/", limit_per_task: int = 20):
    """Fast evaluation: 20 items per task, key domains only"""
    from orion.evals.tasks import TASK_REGISTRY
    from orion.evals.runner import HFGenerator, run_task
    import torch

    logger.info("Quick Evaluation (Fast Track)")
    logger.info(f"Model: {model_path}")
    logger.info(f"Adapter: {adapter_path}")

    # Load model
    dtype = torch.float32
    generator = HFGenerator(
        model_dir=model_path,
        adapter_dir=adapter_path,
        dtype=dtype,
        batch_size=8,
        max_new_tokens=128
    )

    # Fast-track tasks: only key domains
    fast_tasks = {
        "synth-math": ("data/raw/synth_math/test.jsonl", limit_per_task),
        "synth-sequences": ("data/raw/synth_sequences/test.jsonl", limit_per_task),
        "synth-systems": ("data/raw/synth_systems/test.jsonl", limit_per_task),
        "synth-science": ("data/raw/synth_science/test.jsonl", limit_per_task),
    }

    results = {}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for task_name, (task_path, limit) in fast_tasks.items():
        if not Path(task_path).exists():
            logger.warning(f"Task file not found: {task_path}, skipping")
            continue

        logger.info(f"Evaluating {task_name}...")
        try:
            TaskClass = TASK_REGISTRY[task_name]
            task = TaskClass(task_path, limit=limit)

            summary = run_task(task, generator, output_dir / f"{task_name}.jsonl", limit=limit)
            results[task_name] = summary
            logger.info(f"  {task_name}: {summary.get('accuracy', 0):.1%}")
        except Exception as e:
            logger.error(f"Error on {task_name}: {e}")

    # Save summary
    summary_file = output_dir / "summary.json"
    with open(summary_file, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"\nQuick Eval Summary:")
    for task, result in results.items():
        acc = result.get("accuracy", 0)
        print(f"  {task}: {acc:.1%}")

    # Compute blended average
    if results:
        avg = sum(r.get("accuracy", 0) for r in results.values()) / len(results)
        print(f"\nBlended Average: {avg:.1%}")
        print(f"Target: 60%+ for fast promotion")

        if avg >= 0.60:
            print("Status: PASS - Ready for promotion")
            return 0
        else:
            print("Status: FAIL - Below target")
            return 1

    return 1


if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else "Qwen/Qwen3.5-0.8B-Base"
    adapter = sys.argv[2] if len(sys.argv) > 2 else "checkpoints/orion-0.2-fast-track/final"

    sys.exit(quick_eval(model, adapter))
