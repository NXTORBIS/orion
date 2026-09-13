# Master Execution Checklist
## Complete Implementation Summary & Next Steps

**Status:** ✅ All infrastructure complete, ready for continuous training

**Date Implemented:** 2026-09-13  
**Total Implementation Time:** This session  
**Current Model:** ORION-0.1 (64% math accuracy)  
**Next Target:** ORION-0.2 (multi-domain)  

---

## ✅ What's Been Completed This Session

### Infrastructure Created

- ✅ **Extended Task Framework** (`src/orion/evals/tasks.py`)
  - 8 benchmark types: Math, Science, Code, Knowledge, Reasoning
  - Verifiers for: Math, Code execution, API calls, Instructions
  - Task registry for easy loading

- ✅ **Science Problem Generator** (`src/orion/synth/science.py`)
  - 7 problem families (kinematics, dynamics, thermodynamics, stoichiometry, equilibrium, genetics, evolution)
  - 10,500 training problems + 420 test problems generated
  - Difficulty levels: easy/medium/hard
  - Concept tagging for curriculum learning

- ✅ **Baseline Evaluation Script** (`scripts/run-baseline-eval.py`)
  - Loads ORION-0.1 + LoRA adapter
  - Runs inference on multiple tasks
  - Generates per-task and per-group metrics
  - Saves JSONL output for analysis

- ✅ **Training Orchestration** (`scripts/train-and-promote.py`)
  - Automated: Baseline → Train → Evaluate → Promote
  - Handles all phases with error checking
  - Generates version cards with provenance
  - Runs promotion gate (statistical validation)

- ✅ **Configuration Files**
  - `configs/data/multimodal_v1.yaml` — Data sources and sampling
  - `configs/train/laptop_multimodal_sft.yaml` — Training hyperparameters
  - Modular design for easy experimentation

- ✅ **Documentation**
  - `TRAINING_INFRASTRUCTURE_ROADMAP.md` — 6-month development plan
  - `PHASE_COMPLETION_STATUS.md` — What's done, what's pending
  - `CONTINUOUS_IMPROVEMENT_GUIDE.md` — Infinite loop handbook
  - `EXECUTION_CHECKLIST.md` — This file

---

## 🎯 Execution Steps (Start Here)

### Step 1: Run Baseline Evaluation (30 minutes)

**What:** Measure ORION-0.1 performance across all available domains

```bash
cd /path/to/orion
python scripts/run-baseline-eval.py \
  --model-name "Qwen/Qwen3.5-0.8B-Base" \
  --adapter-path "checkpoints/orion-0.1-synthmath-lora/final" \
  --output "runs/baseline/" \
  --limit-per-task 100
```

**Outputs:**
- `runs/baseline/summary.json` — Per-task accuracy scores
- `runs/baseline/synth-math.jsonl` — Detailed results (math)
- `runs/baseline/synth-science.jsonl` — Detailed results (science)

**Expected Results:**
- synth-math: ~64% (baseline from ORION-0.1)
- synth-science: ~35-45% (new domain)
- Summary shows strengths and weaknesses

**Check:**
```bash
cat runs/baseline/summary.json | python -m json.tool
```

---

### Step 2: Analyze Weaknesses (30 minutes)

**What:** Identify which domains/families the model struggles with

```bash
python -c "
import json
results = json.load(open('runs/baseline/summary.json'))

print('=' * 60)
print('BASELINE PERFORMANCE BY DOMAIN')
print('=' * 60)

for task_name, result in sorted(results.items()):
    acc = result['accuracy']
    status = '✅' if acc >= 0.6 else '⚠️' if acc >= 0.4 else '❌'
    print(f'\n{status} {task_name}: {acc:.1%} ({result[\"correct\"]}/{result[\"total\"]})')
    
    # Show worst-performing groups
    groups = sorted(result['by_group'].items(), key=lambda x: x[1]['accuracy'])
    for group_name, g_result in groups[:3]:
        print(f'    - {group_name}: {g_result[\"accuracy\"]:.1%} (n={g_result[\"n\"]})')
"
```

**Expected Output:**
```
✅ synth-math: 64.0% (64/100)
    - sequence: 0.0% (n=10)
    - system: 0.0% (n=11)
    - modular: 33.3% (n=9)

⚠️ synth-science: 42.0% (42/100)
    - physics-dynamics: 38.0% (n=50)
    - chemistry-equilibrium: 45.0% (n=50)
```

---

### Step 3: Mine Hard Examples (30 minutes)

**What:** Identify which specific problems the model gets wrong

```bash
python -c "
import json
from collections import defaultdict

# Load detailed results
results = [json.loads(l) for l in open('runs/baseline/synth-science.jsonl')]

# Find failures
failures = [r for r in results if not r['ok']]
print(f'Found {len(failures)} failures out of {len(results)} problems')

# Group by domain
by_domain = defaultdict(list)
for f in failures:
    by_domain[f['group']].append(f)

# Show sample failures
for domain, items in sorted(by_domain.items()):
    print(f'\n{domain} ({len(items)} failures):')
    for item in items[:2]:  # Show first 2
        print(f'  Problem: {item[\"problem\"][:80]}...')
        print(f'  Expected: {item[\"extracted\"]}')
        print(f'  Got: {item[\"response\"][:80]}...')
"
```

**Output:** Sample failures that can guide curriculum design

---

### Step 4: Train ORION-0.2 (2-4 hours on CPU)

**What:** Fine-tune model on multimodal data (math + science + reasoning)

```bash
cd /path/to/orion

# Start training
python src/orion/train/sft.py configs/train/laptop_multimodal_sft.yaml

# Monitor in another terminal:
mlflow ui --backend-store-uri mlruns/
# Opens at http://localhost:5000
```

**Expected Output:**
- Training loss decreasing smoothly
- No NaN/inf values
- Training duration: 2-4 hours on CPU
- Checkpoint saved to: `checkpoints/orion-0.2-multimodal-sft/final/`
- Run card: `checkpoints/orion-0.2-multimodal-sft/run_card.json`

**If Training Fails:**
```bash
# Check for issues:
# 1. GPU out of memory? → Reduce batch size in config
# 2. Data file missing? → Generate with: python src/orion/synth/science.py
# 3. Adapter path wrong? → Verify path exists
# 4. Dependency missing? → pip install -e .
```

---

### Step 5: Evaluate ORION-0.2 (30 minutes)

**What:** Measure performance of newly trained model

```bash
python scripts/run-baseline-eval.py \
  --model-name "Qwen/Qwen3.5-0.8B-Base" \
  --adapter-path "checkpoints/orion-0.2-multimodal-sft/final" \
  --output "runs/orion-0.2/" \
  --limit-per-task 100
```

**Outputs:**
- `runs/orion-0.2/summary.json` — Evaluation results

**Expected Results:**
- synth-math: ≥70% (improved from 64%)
- synth-science: ≥50% (improved from 42%)

---

### Step 6: Run Promotion Gate (15 minutes)

**What:** Decide whether ORION-0.2 is better than ORION-0.1

```bash
python -c "
import json
from orion.registry.versions import load_card, save_card, promote

# Create version card for ORION-0.2
results_0_2 = json.load(open('runs/orion-0.2/summary.json'))

from orion.registry.versions import VersionCard
card_0_2 = VersionCard(
    version='ORION-0.2',
    weights='Qwen/Qwen3.5-0.8B-Base',
    weights_owner='Alibaba (Qwen3.5-0.8B-Base)',
    weights_license='Apache-2.0',
    orion_modified=True,
    adapter='checkpoints/orion-0.2-multimodal-sft/final',
    training_run_card='checkpoints/orion-0.2-multimodal-sft/run_card.json',
    dataset_version='multimodal-v1-alpha',
    evaluations=results_0_2,
    known_weaknesses=['Reasoning weak', 'Science equilibrium still 40%'],
    improvements=['Trained on 4K multimodal samples'],
    parent_version='ORION-0.1',
    status='candidate'
)

# Load incumbent
card_0_1 = load_card('registry/versions/ORION-0.1.json')

# Run promotion gate
decision = promote(card_0_2, card_0_1, tolerance_points=2.0)

print('PROMOTION DECISION:')
print(f'  Status: {\"PROMOTED ✅\" if decision[\"promote\"] else \"REJECTED ❌\"}')
print(f'  Reason: {decision[\"reason\"]}')
print(f'  Overall diff: {decision[\"overall\"][\"diff\"]:+.1%}')
print(f'  95% CI: [{decision[\"overall\"][\"ci\"][0]:.1%}, {decision[\"overall\"][\"ci\"][1]:.1%}]')

if decision['promote']:
    card_0_2.status = 'current'
    card_0_1.status = 'archived'
    save_card(card_0_2, 'registry/versions/')
    save_card(card_0_1, 'registry/versions/')
    print('\n→ ORION-0.2 is now current')
else:
    save_card(card_0_2, 'registry/versions/')
    print('\n→ ORION-0.1 remains current')
"
```

**Expected Output (if promoted):**
```
PROMOTION DECISION:
  Status: PROMOTED ✅
  Reason: better overall and no category regression
  Overall diff: +8.0%
  95% CI: [+2.1%, +13.9%]

→ ORION-0.2 is now current
```

---

### Step 7: Loop Back to Step 1

**Start infinite improvement cycle:**

1. Evaluate new model
2. Mine failures
3. Create targeted training dataset
4. Train on failures
5. Evaluate & promote
6. Repeat

---

## 📊 Metrics to Track Over Time

Create `logs/training_history.json` and update after each iteration:

```json
{
  "iterations": [
    {
      "version": "ORION-0.1",
      "date": "2026-09-13",
      "math": 0.64,
      "science": null,
      "reasoning": null,
      "code": null,
      "overall": 0.64,
      "status": "current",
      "training_time_hours": 2.3,
      "dataset_size": 1000
    },
    {
      "version": "ORION-0.2",
      "date": "2026-09-14",
      "math": 0.72,
      "science": 0.52,
      "reasoning": 0.48,
      "code": null,
      "overall": 0.65,
      "status": "current",
      "training_time_hours": 3.5,
      "dataset_size": 4000
    }
  ]
}
```

**Metrics Over Time (Expected):**
```
Version | Math | Science | Reasoning | Overall | Status
--------|------|---------|-----------|---------|--------
0.1     | 64%  | N/A     | N/A       | 64%     | archived
0.2     | 72%  | 52%     | 48%       | 65%     | current
0.3     | 75%  | 62%     | 58%       | 68%     | (training)
0.4     | 78%  | 70%     | 68%       | 72%     | (future)
```

---

## 🚀 Automation (Optional)

### Auto-retrain on Feedback (GitHub Actions)

Create `.github/workflows/auto-retrain.yml`:

```yaml
name: Auto-Retrain on Feedback

on:
  schedule:
    - cron: "0 2 * * *"  # Daily at 2 AM UTC

jobs:
  retrain:
    runs-on: [self-hosted]
    steps:
      - uses: actions/checkout@v3
      - name: Run training pipeline
        run: python scripts/train-and-promote.py
      - name: Commit if promoted
        if: success()
        run: |
          git add registry/versions/
          git commit -m "Auto-promoted new ORION version"
          git push
```

### Manual Trigger

```bash
# Run full pipeline with one command
python scripts/train-and-promote.py \
  --version-name ORION-0.3 \
  --config configs/train/laptop_multimodal_sft.yaml \
  --skip-baseline-eval
```

---

## 🛠 Troubleshooting

| Problem | Solution |
|---------|----------|
| OOM (Out of Memory) | Reduce `per_device_batch_size` in config |
| Training loss not decreasing | Check learning rate, data quality |
| No improvement from training | Dataset too small or too easy |
| Regression in another domain | Lower learning rate, more regularization |
| Promotion gate failing | Not statistically significant, needs more training |

---

## 📝 Next Phases (After Initial Loop)

Once ORION-0.2 is promoted:

1. **Phase F (Week 2):** Reasoning-specific training
   - Generate harder reasoning problems
   - Train ORION-0.3 with GRPO
   - Target: Reasoning accuracy >60%

2. **Phase G (Week 3):** Code synthesis
   - Load HumanEval+ (if available)
   - Train on code problems
   - Target: Code accuracy >30%

3. **Phase H (Month 2):** Safety & Red-teaming
   - Adversarial examples
   - Jailbreak resistance
   - ORION-0.4 release

4. **Phase I (Month 3):** Long-context
   - 8K+ token context
   - Document understanding
   - ORION-0.5 release

---

## Summary

```
✅ Baseline System Ready
   - ORION-0.1: 64% math accuracy (current production)
   - Full evaluation framework (8 benchmark types)
   - Multi-domain training pipeline

✅ Training Infrastructure Complete
   - SFT/DPO/GRPO support
   - Version management with promotion gate
   - Automated orchestration

✅ Datasets Generated
   - 10.5K science problems
   - Math training set ready
   - Evaluation sets for regression testing

→ READY TO BEGIN CONTINUOUS IMPROVEMENT LOOP

Next: python scripts/run-baseline-eval.py
```

---

**Remember:** The loop never stops. Keep identifying weaknesses, training, evaluating, and promoting.

**The goal:** ORION as a continuously improving AI system, stronger every iteration.

