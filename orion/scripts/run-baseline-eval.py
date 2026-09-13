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
from orion.evals.runner import ModelRunner
from orion.evals.metrics import bootstrap_accuracy, paired_bootstrap_diff
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
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch

    logger.info(f"Loading model: {model_name}")

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
        load_in_8bit=True if torch.cuda.is_available() else False,
    )
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    if adapter_path:
        logger.info(f"Loading LoRA adapter: {adapter_path}")
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter_path, is_trainable=False)

    return ModelRunner(model, tokenizer)


def run_task_eval(runner, task_name: str, task_path: str, limit: int | None = None, output_dir: Path | None = None):
    """Run evaluation on a single task."""
    logger.info(f"Evaluating task: {task_name}")

    if not Path(task_path).exists():
        logger.warning(f"Task file not found: {task_path}, skipping {task_name}")
        return None

    try:
        # Load task
        TaskClass = TASK_REGISTRY[task_name]
        task = TaskClass(task_path, limit=limit)

        # Get items
        items = task.items()
        logger.info(f"  Loaded {len(items)} items")

        # Run inference
        results = []
        correct = 0
        by_group = {}

        for i, item in enumerate(items):
            if i % 10 == 0:
                logger.info(f"  Processing item {i}/{len(items)}")

            # Get response from model
            response = runner.run(item.messages)

            # Score response
            score = task.score(item, response)

            results.append({
                "id": item.id,
                "group": item.group,
                "response": response[:500],  # Truncate for storage
                "ok": score.ok,
                "extracted": score.extracted,
                "details": score.details,
            })

            if score.ok:
                correct += 1

            # Track by group
            if item.group not in by_group:
                by_group[item.group] = {"n": 0, "correct": 0}
            by_group[item.group]["n"] += 1
            by_group[item.group]["correct"] += score.ok

        accuracy = correct / len(items) if items else 0
        logger.info(f"  Accuracy: {accuracy:.1%} ({correct}/{len(items)})")

        # Save results
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{task_name}.jsonl"
            with open(output_file, "w") as f:
                for r in results:
                    f.write(json.dumps(r) + "\n")
            logger.info(f"  Saved results to {output_file}")
        else:
            output_file = None

        # Compute bootstrap CI
        ci = bootstrap_accuracy([r["ok"] for r in results])

        return EvalResult(
            task_name=task_name,
            total=len(items),
            correct=correct,
            accuracy=accuracy,
            by_group={g: {"n": s["n"], "accuracy": s["correct"] / s["n"]} for g, s in by_group.items()},
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
    runner = load_model(args.model_name, args.adapter_path)

    # Define tasks (with file paths)
    tasks_to_eval = {
        "synth-math": "data/raw/synth_math/test.jsonl",
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

        result = run_task_eval(runner, task_name, task_path, limit=args.limit_per_task, output_dir=output_dir)
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
