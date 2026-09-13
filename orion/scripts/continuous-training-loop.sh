#!/bin/bash
# Continuous Training Loop for Orion
# Runs the full cycle: baseline → train → evaluate → promote
# Then loops indefinitely

set -e

cd "$(dirname "$0")/.."
source .venv/Scripts/activate

# Configuration
BASELINE_OUTPUT="runs/baseline-eval-$(date +%s)/"
VERSION_NUMBER=2
ITERATION=0

echo "========================================"
echo "ORION CONTINUOUS TRAINING LOOP"
echo "========================================"

while true; do
  ITERATION=$((ITERATION + 1))
  echo ""
  echo "========================================"
  echo "ITERATION $ITERATION"
  echo "========================================"

  # Step 1: Baseline Evaluation
  echo ""
  echo "[Step 1/5] Running Baseline Evaluation (ORION-0.$VERSION_NUMBER)"
  python scripts/run-baseline-eval.py \
    --model-name "Qwen/Qwen3.5-0.8B-Base" \
    --adapter-path "checkpoints/orion-0.$VERSION_NUMBER-multimodal-sft/final" \
    --output "$BASELINE_OUTPUT" \
    --limit-per-task 50

  # Step 2: Analyze Results
  echo ""
  echo "[Step 2/5] Analyzing Results..."
  python -c "
import json
results = json.load(open('$BASELINE_OUTPUT/summary.json'))
print('\nBaseline Performance:')
for task, result in results.items():
    print(f'  {task}: {result[\"accuracy\"]:.1%}')
"

  # Step 3: Train (if not first iteration or if improvement needed)
  echo ""
  echo "[Step 3/5] Training ORION-0.$((VERSION_NUMBER + 1))..."
  python src/orion/train/sft.py configs/train/laptop_multimodal_sft.yaml || {
    echo "Training failed, skipping to next iteration"
    ITERATION=$((ITERATION - 1))
    continue
  }

  # Step 4: Evaluate New Model
  echo ""
  echo "[Step 4/5] Evaluating Trained Model..."
  EVAL_OUTPUT="runs/orion-0.$((VERSION_NUMBER + 1))-eval-$(date +%s)/"
  python scripts/run-baseline-eval.py \
    --model-name "Qwen/Qwen3.5-0.8B-Base" \
    --adapter-path "checkpoints/orion-0.$((VERSION_NUMBER + 1))-multimodal-sft/final" \
    --output "$EVAL_OUTPUT" \
    --limit-per-task 50

  # Step 5: Promotion Gate
  echo ""
  echo "[Step 5/5] Running Promotion Gate..."
  python scripts/train-and-promote.py \
    --version-name "ORION-0.$((VERSION_NUMBER + 1))" \
    --config configs/train/laptop_multimodal_sft.yaml \
    --skip-baseline-eval \
    --skip-training

  # Update version if promoted
  PROMOTION_RESULT=$?
  if [ $PROMOTION_RESULT -eq 0 ]; then
    echo ""
    echo ">>> PROMOTED: ORION-0.$((VERSION_NUMBER + 1)) is now current"
    VERSION_NUMBER=$((VERSION_NUMBER + 1))
  else
    echo ""
    echo ">>> REJECTED: Keeping ORION-0.$VERSION_NUMBER"
  fi

  echo ""
  echo "Iteration $ITERATION complete. Looping back..."
  echo "(This is infinite loop. Press Ctrl+C to stop)"
  sleep 10

done
