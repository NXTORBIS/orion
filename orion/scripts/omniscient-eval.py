#!/usr/bin/env python3
"""Comprehensive evaluation across ALL domains: Omniscient ORION assessment"""

import json
import logging
import sys
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def omniscient_eval(model_path: str, adapter_path: str, output_dir: str = "runs/omniscient-eval/", limit_per_task: int = 50):
    """Comprehensive evaluation: all 7 domains with detailed breakdown"""
    from orion.evals.tasks import TASK_REGISTRY
    from orion.evals.runner import HFGenerator, run_task
    import torch

    logger.info("=" * 70)
    logger.info("OMNISCIENT ORION EVALUATION - COMPREHENSIVE MULTI-DOMAIN ASSESSMENT")
    logger.info("=" * 70)
    logger.info(f"Model: {model_path}")
    logger.info(f"Adapter: {adapter_path}")

    # Load model
    dtype = torch.float32
    generator = HFGenerator(
        model_dir=model_path,
        adapter_dir=adapter_path,
        dtype=dtype,
        batch_size=8,
        max_new_tokens=256
    )

    # All 7 domains
    all_domains = {
        "math": ("data/raw/synth_math/test.jsonl", limit_per_task),
        "science": ("data/raw/synth_science/test.jsonl", limit_per_task),
        "sequences": ("data/raw/synth_sequences/test.jsonl", limit_per_task),
        "systems": ("data/raw/synth_systems/test.jsonl", limit_per_task),
        "coding": ("data/raw/synth_coding/test.jsonl", limit_per_task),
        "reasoning": ("data/raw/synth_reasoning/test.jsonl", limit_per_task),
        "knowledge": ("data/raw/synth_knowledge/test.jsonl", limit_per_task),
    }

    results = {}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print("DOMAIN EVALUATIONS")
    print("=" * 70)

    for domain_name, (task_path, limit) in all_domains.items():
        if not Path(task_path).exists():
            logger.warning(f"Dataset not found: {task_path}")
            continue

        logger.info(f"\n[{domain_name.upper()}] Evaluating...")
        try:
            task_registry_name = f"synth-{domain_name}"
            if task_registry_name not in TASK_REGISTRY:
                logger.warning(f"Task {task_registry_name} not in registry")
                continue

            TaskClass = TASK_REGISTRY[task_registry_name]
            task = TaskClass(task_path, limit=limit)

            summary = run_task(task, generator, output_dir / f"{domain_name}.jsonl", limit=limit)
            results[domain_name] = summary

            acc = summary.get("accuracy", 0)
            print(f"  {domain_name:12} | Accuracy: {acc:6.1%} | Correct: {summary.get('correct', 0):3d} / {summary.get('total', 0):3d}")

        except Exception as e:
            logger.error(f"Error evaluating {domain_name}: {e}")
            results[domain_name] = {"accuracy": 0.0, "error": str(e)}

    # Detailed Report
    print("\n" + "=" * 70)
    print("COMPREHENSIVE RESULTS")
    print("=" * 70)

    domain_scores = {}
    for domain, result in results.items():
        domain_scores[domain] = result.get("accuracy", 0)

    # Print individual domains
    print("\nBy Domain:")
    for domain in sorted(domain_scores.keys()):
        score = domain_scores[domain]
        status = "STRONG" if score >= 0.70 else "GOOD" if score >= 0.50 else "WEAK" if score >= 0.30 else "CRITICAL"
        print(f"  {domain:12} | {score:6.1%} [{status}]")

    # Category grouping
    print("\nBy Category:")
    categories = {
        "STEM": ["math", "science", "coding"],
        "Logic & Reasoning": ["reasoning", "sequences", "systems"],
        "Knowledge": ["knowledge"],
    }

    category_scores = {}
    for category, domains in categories.items():
        domain_list = [d for d in domains if d in domain_scores]
        if domain_list:
            avg = sum(domain_scores[d] for d in domain_list) / len(domain_list)
            category_scores[category] = avg
            print(f"  {category:20} | {avg:6.1%}")

    # Overall blended
    if domain_scores:
        blended = sum(domain_scores.values()) / len(domain_scores)
        print(f"\n  {'OVERALL BLENDED':20} | {blended:6.1%}")

        # Promotion decision
        print("\n" + "=" * 70)
        print("PROMOTION GATE ANALYSIS")
        print("=" * 70)

        weak_domains = [d for d, s in domain_scores.items() if s < 0.40]
        if weak_domains:
            print(f"WARNING: Weak domains (<40%): {', '.join(weak_domains)}")

        if blended >= 0.60:
            print(f"STATUS: PASS - Ready for promotion (blended {blended:.1%})")
            exit_code = 0
        else:
            print(f"STATUS: FAIL - Below 60% threshold ({blended:.1%})")
            exit_code = 1
    else:
        exit_code = 1

    # Save detailed results
    summary_file = output_dir / "summary.json"
    with open(summary_file, "w") as f:
        json.dump({
            "results": results,
            "domain_scores": domain_scores,
            "category_scores": category_scores,
            "blended_average": blended if domain_scores else 0,
        }, f, indent=2)

    logger.info(f"\nResults saved to {output_dir}")
    print("=" * 70)

    return exit_code


if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else "Qwen/Qwen3.5-0.8B-Base"
    adapter = sys.argv[2] if len(sys.argv) > 2 else "checkpoints/orion-0.2-omniscient/final"

    sys.exit(omniscient_eval(model, adapter))
