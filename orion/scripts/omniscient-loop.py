#!/usr/bin/env python3
"""Omniscient ORION: Continuous multi-domain training loop
Trains on ALL knowledge domains simultaneously with regression prevention.
Cycle: Omniscient Training (500 steps, 4-8h) → Comprehensive Eval (30m) → Promote → Repeat
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

def run_cmd(cmd: list, desc: str) -> bool:
    """Run command and return success"""
    print(f"\n{'='*70}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {desc}")
    print(f"{'='*70}")
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0

def omniscient_loop():
    """Continuous multi-domain training with comprehensive evaluation"""
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║  OMNISCIENT ORION - MULTI-DOMAIN CONTINUOUS IMPROVEMENT LOOP       ║
    ║  All Knowledge: Math, Science, Coding, Reasoning, Knowledge        ║
    ║  Cycle: Train (4-8h) → Comprehensive Eval (30m) → Promote → Repeat ║
    ╚════════════════════════════════════════════════════════════════════╝
    """)

    iteration = 0
    current_model = "ORION-0.1"
    best_model = current_model
    best_score = 0.55  # Baseline from initial eval

    while True:
        iteration += 1
        print(f"\n{'#'*70}")
        print(f"# OMNISCIENT ITERATION {iteration} - {datetime.now().isoformat()}")
        print(f"# Current Model: {current_model} (Best: {best_model} @ {best_score:.1%})")
        print(f"{'#'*70}")

        # Step 1: Omniscient Training (500 steps, 4-8 hours)
        print(f"\n[STEP 1/3] OMNISCIENT TRAINING (500 steps, ~4-8 hours)")
        next_version = f"ORION-{float(current_model.split('-')[1]) + 0.1:.1f}"

        if not run_cmd(
            [sys.executable, "src/orion/train/sft.py",
             "configs/train/orion-0.2-omniscient.yaml"],
            f"Training {next_version} on ALL 7 domains (18,700 examples)"
        ):
            print("Training failed!")
            sys.exit(1)

        # Step 2: Comprehensive Evaluation (~30 minutes)
        print(f"\n[STEP 2/3] COMPREHENSIVE OMNISCIENT EVALUATION")
        print("Evaluating across all 7 domains (Math, Science, Sequences, Systems, Coding, Reasoning, Knowledge)...")

        eval_result = run_cmd(
            [sys.executable, "scripts/omniscient-eval.py",
             "Qwen/Qwen3.5-0.8B-Base",
             f"checkpoints/{next_version.lower()}-omniscient/final"],
            f"Comprehensive eval of {next_version}"
        )

        # Step 3: Promotion Decision
        print(f"\n[STEP 3/3] PROMOTION GATE - OMNISCIENT ASSESSMENT")
        eval_path = Path("runs/omniscient-eval/summary.json")

        promoted = False
        if eval_path.exists():
            try:
                results = json.load(open(eval_path))
                blended = results.get("blended_average", 0)
                domain_scores = results.get("domain_scores", {})

                print(f"\nDomain Results:")
                for domain in sorted(domain_scores.keys()):
                    score = domain_scores[domain]
                    print(f"  {domain:12} | {score:6.1%}")

                print(f"\nBlended Average: {blended:.1%}")
                print(f"Previous Best:   {best_score:.1%}")

                # Check for regressions
                major_regressions = []
                if domain_scores:
                    for domain, score in domain_scores.items():
                        if score < 0.30 and domain not in ["reasoning", "knowledge"]:
                            major_regressions.append(f"{domain}({score:.0%})")

                if major_regressions:
                    print(f"\nREJECTED: Critical regressions - {', '.join(major_regressions)}")
                elif blended >= best_score * 0.95:  # At least 95% of previous
                    print(f"\n{'='*70}")
                    print(f"PROMOTED: {next_version} is now current")
                    print(f"Improvement: {blended - best_score:+.1%}")
                    print(f"{'='*70}")

                    promoted = True
                    current_model = next_version
                    if blended > best_score:
                        best_model = next_version
                        best_score = blended
                else:
                    print(f"\nREJECTED: Only {blended:.1%} (need {best_score*0.95:.1%})")

            except Exception as e:
                print(f"Error reading eval: {e}")

        # Summary
        print(f"\n{'='*70}")
        print(f"Iteration {iteration} Summary:")
        print(f"  Current:  {current_model}")
        print(f"  Best:     {best_model} @ {best_score:.1%}")
        print(f"  Promoted: {'YES' if promoted else 'NO'}")
        print(f"  Next cycle in 60 seconds...")
        print(f"{'='*70}")

        time.sleep(60)

if __name__ == "__main__":
    try:
        omniscient_loop()
    except KeyboardInterrupt:
        print("\n\nOmniscient loop stopped by user")
        sys.exit(0)
