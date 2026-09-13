#!/usr/bin/env python3
"""
Continuous Training Loop for Orion
Runs the full improvement cycle indefinitely: baseline → train → evaluate → promote → repeat
"""

import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def run_command(cmd: list[str], description: str) -> bool:
    """Execute command and return success status."""
    logger.info(f"[{description}]")
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        if result.returncode == 0:
            logger.info(f"[{description}] SUCCESS")
            return True
        else:
            logger.error(f"[{description}] FAILED (code {result.returncode})")
            return False
    except Exception as e:
        logger.error(f"[{description}] ERROR: {e}")
        return False


def continuous_loop(max_iterations: int = None):
    """Main continuous training loop."""
    iteration = 0
    current_version = "ORION-0.1"
    next_version = "ORION-0.2"

    logger.info("=" * 70)
    logger.info("ORION CONTINUOUS TRAINING LOOP (Windows)")
    logger.info("=" * 70)

    while True:
        iteration += 1
        logger.info("")
        logger.info("=" * 70)
        logger.info(f"ITERATION {iteration}")
        logger.info(f"Current: {current_version} → Next: {next_version}")
        logger.info("=" * 70)

        if max_iterations and iteration > max_iterations:
            logger.info(f"Reached max iterations ({max_iterations})")
            break

        # Step 1: Baseline Evaluation
        timestamp = datetime.now().strftime("%s")
        baseline_output = f"runs/baseline-eval-{next_version}-{timestamp}/"

        logger.info("")
        logger.info(f"STEP 1: Baseline Evaluation ({next_version})")
        cmd = [
            sys.executable, "scripts/run-baseline-eval.py",
            "--model-name", "Qwen/Qwen3.5-0.8B-Base",
            "--adapter-path", "checkpoints/orion-0.2-multimodal-sft/final",
            "--output", baseline_output,
            "--limit-per-task", "20",
        ]
        if not run_command(cmd, "Baseline Eval"):
            logger.warning("Baseline eval failed, continuing anyway...")

        # Step 2: Analyze Results
        summary_file = Path(baseline_output) / "summary.json"
        if summary_file.exists():
            logger.info("")
            logger.info("STEP 2: Baseline Results")
            try:
                results = json.load(open(summary_file))
                for task, result in results.items():
                    acc = result.get("accuracy", 0)
                    print(f"  {task}: {acc:.1%}")
            except Exception as e:
                logger.error(f"Could not read results: {e}")

        # Step 3: Train
        logger.info("")
        logger.info("STEP 3: Training (ORION-0.2)")
        cmd = [sys.executable, "src/orion/train/sft.py", "configs/train/laptop_multimodal_sft.yaml"]
        if not run_command(cmd, "Training"):
            logger.warning("Training failed, skipping to evaluation")
            # Continue anyway to test what we have

        # Step 4: Evaluate Trained Model
        logger.info("")
        logger.info("STEP 4: Evaluation (ORION-0.2)")
        eval_output = f"runs/orion-0.2-eval-{timestamp}/"
        cmd = [
            sys.executable, "scripts/run-baseline-eval.py",
            "--model-name", "Qwen/Qwen3.5-0.8B-Base",
            "--adapter-path", "checkpoints/orion-0.2-multimodal-sft/final",
            "--output", eval_output,
            "--limit-per-task", "20",
        ]
        if not run_command(cmd, "Training Eval"):
            logger.warning("Eval failed")

        # Step 5: Promotion Gate
        logger.info("")
        logger.info("STEP 5: Promotion Gate")
        cmd = [
            sys.executable, "scripts/train-and-promote.py",
            "--version-name", "ORION-0.2",
            "--skip-baseline-eval",
            "--skip-training",
        ]
        promotion_success = run_command(cmd, "Promotion Gate")

        # Update versions if promoted
        if promotion_success:
            logger.info("")
            logger.info(">>> PROMOTED: ORION-0.2 is now current")
            current_version = "ORION-0.2"
            next_version = "ORION-0.3"
        else:
            logger.info("")
            logger.info(f">>> REJECTED: Keeping {current_version}")

        # Prepare for next iteration
        logger.info("")
        logger.info(f"Iteration {iteration} complete. Looping...")
        logger.info("(Press Ctrl+C to stop)")
        time.sleep(5)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Continuous Orion training loop")
    parser.add_argument("--max-iterations", type=int, default=None,
                       help="Max iterations (default: infinite)")
    parser.add_argument("--skip-first-baseline", action="store_true",
                       help="Skip baseline on first iteration")
    args = parser.parse_args()

    try:
        continuous_loop(max_iterations=args.max_iterations)
    except KeyboardInterrupt:
        logger.info("\nTraining loop interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
