#!/usr/bin/env python3
"""Fast continuous training loop: Full cycle in 30-60 minutes"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

def run_cmd(cmd: list, desc: str) -> bool:
    """Run command and return success"""
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {desc}")
    print(f"{'='*60}")

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0

def fast_loop():
    """30-60 minute continuous training loop"""
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║   ORION FAST-TRACK CONTINUOUS LOOP (30-60 min cycles)     ║
    ║   Baseline → Train → Quick-Eval → Promote → Repeat        ║
    ╚════════════════════════════════════════════════════════════╝
    """)

    iteration = 0
    current_model = "ORION-0.1"

    while True:
        iteration += 1
        print(f"\n{'#'*60}")
        print(f"# ITERATION {iteration} - {datetime.now().isoformat()}")
        print(f"{'#'*60}")

        # Step 1: Quick Baseline (5 min)
        print(f"\n[STEP 1/4] Quick Baseline ({current_model})")
        if not run_cmd(
            [sys.executable, "scripts/quick-eval.py",
             "Qwen/Qwen3.5-0.8B-Base",
             f"checkpoints/{current_model.lower()}-fast-track/final"],
            f"Quick eval {current_model}"
        ):
            print("Baseline failed, skipping")

        # Step 2: Fast Training (10-15 min)
        print(f"\n[STEP 2/4] Fast Training")
        next_version = f"ORION-{float(current_model.split('-')[1]) + 0.1:.1f}"

        if not run_cmd(
            [sys.executable, "src/orion/train/sft.py",
             "configs/train/orion-0.2-fast-track.yaml"],
            f"Training {next_version} (100 steps, 10-15 min)"
        ):
            print("Training failed!")
            sys.exit(1)

        # Step 3: Quick Evaluation (5 min)
        print(f"\n[STEP 3/4] Quick Evaluation ({next_version})")
        eval_result = run_cmd(
            [sys.executable, "scripts/quick-eval.py",
             "Qwen/Qwen3.5-0.8B-Base",
             f"checkpoints/{next_version.lower()}-fast-track/final"],
            f"Quick eval {next_version}"
        )

        # Step 4: Promotion Decision (1 min)
        print(f"\n[STEP 4/4] Promotion Gate")
        eval_path = Path("runs/quick-eval/summary.json")

        promoted = False
        if eval_path.exists():
            try:
                results = json.load(open(eval_path))
                avg = sum(r.get("accuracy", 0) for r in results.values()) / len(results)

                print(f"\nResults:")
                for task, result in results.items():
                    print(f"  {task}: {result.get('accuracy', 0):.1%}")
                print(f"\nBlended: {avg:.1%}")

                if avg >= 0.60:
                    print(f"\n✓ PROMOTED: {next_version} is now current")
                    promoted = True
                    current_model = next_version
                else:
                    print(f"\n✗ REJECTED: Below 60% threshold, keeping {current_model}")
            except Exception as e:
                print(f"Error reading eval: {e}")

        # Summary
        print(f"\n{'='*60}")
        elapsed = datetime.now()
        print(f"Iteration {iteration} complete")
        print(f"Current model: {current_model}")
        print(f"Next cycle in 60 seconds...")
        print(f"{'='*60}")

        time.sleep(60)

if __name__ == "__main__":
    try:
        fast_loop()
    except KeyboardInterrupt:
        print("\n\nFast loop stopped by user")
        sys.exit(0)
