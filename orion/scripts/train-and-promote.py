#!/usr/bin/env python3
"""
Automated Training & Promotion Pipeline
Orchestrates: Baseline Eval → Training → Evaluation → Promotion Decision

This script:
1. Runs baseline eval with ORION-0.1 (if not cached)
2. Trains ORION-0.2 on multimodal data
3. Evaluates ORION-0.2 on all benchmarks
4. Creates version card with complete provenance
5. Runs promotion gate (statistical comparison)
6. Promotes ORION-0.2 if it beats ORION-0.1

Usage:
    python scripts/train-and-promote.py \
        --version-name orion-0.2 \
        --config configs/train/laptop_multimodal_sft.yaml \
        --skip-baseline-eval  # if already have baseline
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from orion.registry.versions import VersionCard, save_card, load_card, promote
from orion.evals.metrics import bootstrap_accuracy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_command(cmd: list[str], description: str, cwd: str | None = None) -> bool:
    """Run shell command and log output."""
    logger.info(f"[{description}] Starting...")
    logger.info(f"  Command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=False, text=True)
        if result.returncode == 0:
            logger.info(f"[{description}] ✅ Success")
            return True
        else:
            logger.error(f"[{description}] ❌ Failed with code {result.returncode}")
            return False
    except Exception as e:
        logger.error(f"[{description}] ❌ Error: {e}")
        return False


def run_baseline_eval(skip: bool = False, output_dir: str = "runs/baseline/") -> dict:
    """Run baseline evaluation with ORION-0.1 (if not cached)."""
    output_path = Path(output_dir) / "summary.json"

    if skip and output_path.exists():
        logger.info("Skipping baseline eval (cached)")
        with open(output_path) as f:
            return json.load(f)

    logger.info("=" * 60)
    logger.info("PHASE A: BASELINE EVALUATION (ORION-0.1)")
    logger.info("=" * 60)

    cmd = [
        "python", "scripts/run-baseline-eval.py",
        "--model-name", "Qwen/Qwen3.5-0.8B-Base",
        "--adapter-path", "checkpoints/orion-0.1-synthmath-lora/final",
        "--output", output_dir,
        "--limit-per-task", "100",
    ]

    if not run_command(cmd, "Baseline Eval"):
        return {}

    if output_path.exists():
        with open(output_path) as f:
            return json.load(f)
    return {}


def run_training(config_path: str, output_dir: str = "checkpoints/orion-0.2-multimodal-sft") -> bool:
    """Train ORION-0.2 with SFT."""
    logger.info("=" * 60)
    logger.info("PHASE D: MULTIMODAL TRAINING (ORION-0.2)")
    logger.info("=" * 60)

    cmd = [
        "python", "src/orion/train/sft.py",
        config_path,
    ]

    return run_command(cmd, "Training")


def run_training_eval(adapter_path: str, output_dir: str = "runs/orion-0.2/") -> dict:
    """Evaluate ORION-0.2 after training."""
    logger.info("=" * 60)
    logger.info("PHASE E: TRAINING EVALUATION (ORION-0.2)")
    logger.info("=" * 60)

    output_path = Path(output_dir) / "summary.json"

    cmd = [
        "python", "scripts/run-baseline-eval.py",
        "--model-name", "Qwen/Qwen3.5-0.8B-Base",
        "--adapter-path", adapter_path,
        "--output", output_dir,
        "--limit-per-task", "100",
    ]

    if not run_command(cmd, "Training Eval"):
        return {}

    if output_path.exists():
        with open(output_path) as f:
            return json.load(f)
    return {}


def create_version_card(version_name: str, adapter_path: str, training_config: dict,
                       eval_results: dict, run_card_path: str | None = None) -> VersionCard:
    """Create version card with complete provenance."""
    logger.info("Creating version card...")

    # Build evaluations dict from results
    evaluations = {}
    for task_name, result in eval_results.items():
        evaluations[task_name] = {
            "n": result["total"],
            "accuracy": result["accuracy"],
            "by_group": result["by_group"],
        }

    # Build regression suite (all items as pass/fail)
    regression_suite = {}
    for task_name in eval_results.keys():
        regression_suite[task_name] = {}  # Placeholder; in real pipeline would be populated

    card = VersionCard(
        version=version_name,
        weights="Qwen/Qwen3.5-0.8B-Base",
        weights_owner="Alibaba (Qwen3.5-0.8B-Base)",
        weights_license="Apache-2.0",
        orion_modified=True,
        adapter=adapter_path,
        training_run_card=run_card_path,
        dataset_version="multimodal-v1-alpha",
        training_config=training_config,
        evaluations=evaluations,
        regression_suite=regression_suite,
        known_weaknesses=[
            "Science domains may have lower performance (new domain)",
            "Reasoning accuracy varies by complexity level",
        ],
        improvements=[
            "SFT on multimodal data (math, reasoning, science)",
            "Merged synth-math, synth-science training sets",
        ],
        parent_version="ORION-0.1",
        status="candidate",
    )

    return card


def promotion_decision(candidate_card: VersionCard, incumbent_version: str = "ORION-0.1",
                      registry_dir: str = "registry/versions/") -> dict:
    """Run promotion gate and return decision."""
    logger.info("=" * 60)
    logger.info("PROMOTION GATE")
    logger.info("=" * 60)

    incumbent_path = Path(registry_dir) / f"{incumbent_version}.json"
    if not incumbent_path.exists():
        logger.warning(f"No incumbent found: {incumbent_version}")
        incumbent_card = None
    else:
        incumbent_card = load_card(incumbent_path)

    # Run promotion gate
    decision = promote(candidate_card, incumbent_card, tolerance_points=2.0)

    # Print decision
    print("\n" + "=" * 60)
    print("PROMOTION DECISION")
    print("=" * 60)
    print(f"Version: {candidate_card.version}")
    print(f"Status: {decision['promote']}")
    print(f"Reason: {decision['reason']}")

    if decision.get("overall"):
        overall = decision["overall"]
        print(f"Overall improvement: {overall['diff']:+.1%}")
        print(f"  95% CI: [{overall['ci'][0]:.1%}, {overall['ci'][1]:.1%}]")
        print(f"  Significant: {overall['significant']}")

    if decision.get("categories"):
        print("\nPer-category results:")
        for cat, results in decision["categories"].items():
            print(f"  {cat}: {results['delta_points']:+.1f}pp (n={results['n']})")

    if decision["promote"]:
        print(f"\n✅ PROMOTED: {candidate_card.version} is now the new current model")
        if incumbent_card:
            print(f"   Previous incumbent {incumbent_version} archived")
    else:
        print(f"\n❌ REJECTED: {candidate_card.version} does not meet promotion criteria")
        print(f"   Incumbent {incumbent_version} remains current")

    print("=" * 60 + "\n")

    return decision


def main():
    parser = argparse.ArgumentParser(description="Automated training and promotion pipeline")
    parser.add_argument("--version-name", default="ORION-0.2", help="Version name to train")
    parser.add_argument("--config", default="configs/train/laptop_multimodal_sft.yaml",
                       help="Training config path")
    parser.add_argument("--skip-baseline-eval", action="store_true", help="Skip baseline eval (use cached)")
    parser.add_argument("--skip-training", action="store_true", help="Skip training (use cached checkpoint)")
    parser.add_argument("--skip-eval", action="store_true", help="Skip evaluation")
    parser.add_argument("--registry-dir", default="registry/versions/", help="Version registry directory")
    parser.add_argument("--adapter-path", default="checkpoints/orion-0.2-multimodal-sft/final",
                       help="Path to trained adapter")
    args = parser.parse_args()

    logger.info(f"Starting training pipeline for {args.version_name}")
    logger.info(f"Config: {args.config}")

    # Phase A: Baseline evaluation
    baseline_results = run_baseline_eval(skip=args.skip_baseline_eval)
    if not baseline_results:
        logger.error("Baseline eval failed or returned empty results")
        sys.exit(1)

    logger.info(f"Baseline results: {json.dumps(baseline_results, indent=2)}")

    # Phase D: Training
    if not args.skip_training:
        if not run_training(args.config):
            logger.error("Training failed")
            sys.exit(1)

    # Phase E: Evaluation
    if not args.skip_eval:
        training_results = run_training_eval(args.adapter_path)
        if not training_results:
            logger.error("Training eval failed or returned empty results")
            sys.exit(1)
    else:
        # Use cached results if skip-eval
        try:
            with open(f"runs/{args.version_name.lower()}/summary.json") as f:
                training_results = json.load(f)
        except FileNotFoundError:
            logger.error("No cached eval results found")
            sys.exit(1)

    logger.info(f"Training results: {json.dumps(training_results, indent=2)}")

    # Create version card
    # Load training config for metadata
    import yaml
    with open(args.config) as f:
        train_config = yaml.safe_load(f)

    candidate_card = create_version_card(
        version_name=args.version_name,
        adapter_path=args.adapter_path,
        training_config=train_config.get("training_args", {}),
        eval_results=training_results,
    )

    # Promotion decision
    decision = promotion_decision(candidate_card, incumbent_version="ORION-0.1",
                                 registry_dir=args.registry_dir)

    # Update status based on decision
    if decision["promote"]:
        candidate_card.status = "current"
    else:
        candidate_card.status = "rejected"

    # Save version card
    card_path = save_card(candidate_card, args.registry_dir)
    logger.info(f"Version card saved: {card_path}")

    # If promoted, archive incumbent
    if decision["promote"]:
        incumbent_path = Path(args.registry_dir) / "ORION-0.1.json"
        if incumbent_path.exists():
            incumbent = load_card(incumbent_path)
            incumbent.status = "archived"
            save_card(incumbent, args.registry_dir)
            logger.info("Incumbent archived")

    logger.info("Pipeline complete!")
    sys.exit(0 if decision["promote"] else 1)


if __name__ == "__main__":
    main()
