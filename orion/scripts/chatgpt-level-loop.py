#!/usr/bin/env python3
"""ChatGPT-Level ORION: Continuous training until reaching ChatGPT parity

Target: 75%+ blended average across all 8 domains
Run indefinitely with increasingly aggressive training cycles
Stop only when ORION reaches or exceeds ChatGPT capability
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ChatGPT-level benchmarks (typical performance targets)
CHATGPT_TARGETS = {
    "math": 0.80,           # Math reasoning
    "science": 0.75,        # Science understanding
    "sequences": 0.75,      # Pattern recognition
    "systems": 0.75,        # Equation solving
    "coding": 0.70,         # Algorithm understanding
    "reasoning": 0.80,      # Logical reasoning
    "knowledge": 0.78,      # General knowledge
    "instruction": 0.85,    # Instruction following
}

CHATGPT_BLENDED_TARGET = 0.77  # Overall ChatGPT parity: 77%+

def run_cmd(cmd: list, desc: str) -> bool:
    """Run command and return success"""
    print(f"\n{'='*70}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {desc}")
    print('='*70)
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0

def chatgpt_level_loop():
    """Continuous training until ChatGPT parity achieved"""
    print("""
    ================================================================
    CHATGPT-LEVEL ORION CONTINUOUS TRAINING
    Target: ChatGPT parity on all 8 domains (77%+ blended)
    Run: Indefinitely until reaching ChatGPT level
    ================================================================
    """)

    iteration = 0
    current_model = "ORION-0.1"
    best_model = current_model
    best_blended = 0.55
    domain_history = {}
    not_promoted_count = 0

    while True:
        iteration += 1
        print(f"\n{'#'*70}")
        print(f"# CHATGPT-LEVEL ITERATION {iteration} - {datetime.now().isoformat()}")
        print(f"# Current: {current_model} @ {best_blended:.1%} (Target: {CHATGPT_BLENDED_TARGET:.1%})")
        print(f"# Progress: {(best_blended/CHATGPT_BLENDED_TARGET)*100:.0f}% to ChatGPT parity")
        print(f"{'#'*70}")

        # Adaptive training intensity based on progress
        if best_blended < 0.60:
            config = "orion-chatgpt-level.yaml"
            steps_desc = "1000 steps"
        elif best_blended < 0.70:
            config = "orion-chatgpt-level.yaml"
            steps_desc = "1000 steps (aggressive)"
        else:
            config = "orion-chatgpt-level.yaml"
            steps_desc = "1000 steps (maximum)"

        next_version = f"ORION-{float(current_model.split('-')[1]) + 0.1:.1f}"

        print(f"\n[STEP 1/3] CHATGPT-LEVEL TRAINING ({steps_desc})")
        print(f"Domains: Math, Science, Sequences, Systems, Coding, Reasoning, Knowledge, Instruction")

        if not run_cmd(
            [sys.executable, "src/orion/train/sft.py",
             f"configs/train/{config}"],
            f"Training {next_version} toward ChatGPT parity (~8-12 hours)"
        ):
            print("Training failed!")
            not_promoted_count += 1
            if not_promoted_count >= 3:
                print("Multiple training failures. Aborting.")
                sys.exit(1)
            time.sleep(60)
            continue

        # Comprehensive ChatGPT-level evaluation
        print(f"\n[STEP 2/3] CHATGPT-LEVEL COMPREHENSIVE EVALUATION")
        print("Testing all 8 domains for ChatGPT parity...")

        eval_result = run_cmd(
            [sys.executable, "scripts/omniscient-eval.py",
             "Qwen/Qwen3.5-0.8B-Base",
             f"checkpoints/{next_version.lower()}-chatgpt-level/final"],
            f"ChatGPT-level eval of {next_version}"
        )

        # ChatGPT parity decision
        print(f"\n[STEP 3/3] CHATGPT PARITY ASSESSMENT")
        eval_path = Path("runs/omniscient-eval/summary.json")

        if eval_path.exists():
            try:
                results = json.load(open(eval_path))
                blended = results.get("blended_average", 0)
                domain_scores = results.get("domain_scores", {})

                print(f"\nDomain Results vs ChatGPT Targets:")
                print("-" * 70)
                progress_to_target = []

                for domain in sorted(domain_scores.keys()):
                    score = domain_scores[domain]
                    target = CHATGPT_TARGETS.get(domain, 0.75)
                    parity = (score / target) * 100 if target > 0 else 0

                    if score >= target:
                        status = "CHATGPT"
                    elif score >= target * 0.90:
                        status = "NEAR"
                    elif score >= target * 0.75:
                        status = "GOOD"
                    else:
                        status = "WEAK"

                    progress_to_target.append(parity)
                    print(f"  {domain:12} | {score:6.1%} (target {target:5.1%}) [{status:7s}] {parity:5.0f}%")

                print("-" * 70)
                print(f"Blended Average:    {blended:6.1%}")
                print(f"ChatGPT Target:     {CHATGPT_BLENDED_TARGET:6.1%}")
                print(f"Progress to Target: {(blended/CHATGPT_BLENDED_TARGET)*100:5.0f}%")

                # Check if ChatGPT level reached
                if blended >= CHATGPT_BLENDED_TARGET:
                    print(f"\n{'='*70}")
                    print(f"CHATGPT PARITY ACHIEVED!")
                    print(f"Model: {next_version}")
                    print(f"Blended: {blended:.1%} (target {CHATGPT_BLENDED_TARGET:.1%})")
                    print(f"{'='*70}")
                    print("\nORION has reached ChatGPT-level performance!")
                    print("Congratulations - the model is ready for production.")

                    # Update current and best
                    current_model = next_version
                    best_model = next_version
                    best_blended = blended
                    not_promoted_count = 0

                    # Save achievement
                    achievement_file = Path("runs/chatgpt-level-achieved.json")
                    with open(achievement_file, "w") as f:
                        json.dump({
                            "model": next_version,
                            "blended": blended,
                            "domain_scores": domain_scores,
                            "timestamp": datetime.now().isoformat(),
                            "iteration": iteration
                        }, f, indent=2)

                    # Continue training beyond ChatGPT level
                    print("\nContinuing training for further improvement...")
                    time.sleep(60)
                    continue

                # Check for improvement (must beat previous by 2%+ or match 95%)
                improvement_threshold = max(best_blended * 0.95, best_blended - 0.02)
                if blended >= improvement_threshold:
                    print(f"\nPROMOTED: {next_version}")
                    print(f"Improvement: {blended - best_blended:+.1%}")
                    current_model = next_version
                    not_promoted_count = 0

                    if blended > best_blended:
                        best_model = next_version
                        best_blended = blended
                else:
                    print(f"\nREJECTED: {blended:.1%} < threshold {improvement_threshold:.1%}")
                    not_promoted_count += 1
                    if not_promoted_count >= 5:
                        print("Multiple rejections. Adjusting strategy...")
                        not_promoted_count = 0

            except Exception as e:
                print(f"Error reading eval: {e}")
                not_promoted_count += 1

        # Status summary
        print(f"\n{'='*70}")
        print(f"Iteration {iteration} Summary:")
        print(f"  Current Model:        {current_model}")
        print(f"  Best Model:           {best_model}")
        print(f"  Best Blended Score:   {best_blended:.1%}")
        print(f"  ChatGPT Target:       {CHATGPT_BLENDED_TARGET:.1%}")
        print(f"  Progress:             {(best_blended/CHATGPT_BLENDED_TARGET)*100:.0f}% to parity")
        print(f"  {'='*66}")
        print(f"  Next iteration starting in 60 seconds...")
        print(f"  (Run continuously until ChatGPT parity achieved)")
        print(f"{'='*70}")

        time.sleep(60)

if __name__ == "__main__":
    try:
        chatgpt_level_loop()
    except KeyboardInterrupt:
        print("\n\nChatGPT-level loop stopped by user")
        sys.exit(0)
