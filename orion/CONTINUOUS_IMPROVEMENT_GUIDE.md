# Orion Continuous Improvement Guide
## Never-Stop Training & Development Loop

**Purpose:** Automated processes for continuous AI model improvement without manual intervention.

---

## The Loop (Infinite Cycle)

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   ┌──────────────────────────────────────────────┐     │
│   │ 1. IDENTIFY WEAKNESSES                       │     │
│   │    - Run comprehensive evaluation            │     │
│   │    - Analyze failures by domain/difficulty   │     │
│   │    - Mine hard examples                      │     │
│   │    - Identify patterns in errors             │     │
│   └──────────────────────────────────────────────┘     │
│                         ↓                               │
│   ┌──────────────────────────────────────────────┐     │
│   │ 2. CURATE TARGETED DATASETS                  │     │
│   │    - Create synthetic hard examples          │     │
│   │    - Collect from real failures              │     │
│   │    - Generate adversarial examples           │     │
│   │    - Organize by domain/difficulty           │     │
│   └──────────────────────────────────────────────┘     │
│                         ↓                               │
│   ┌──────────────────────────────────────────────┐     │
│   │ 3. TRAIN / FINE-TUNE                         │     │
│   │    - SFT on curated hard dataset             │     │
│   │    - DPO on preference pairs                 │     │
│   │    - GRPO with reward models                 │     │
│   │    - Merge LoRA adapters                     │     │
│   └──────────────────────────────────────────────┘     │
│                         ↓                               │
│   ┌──────────────────────────────────────────────┐     │
│   │ 4. EVALUATE & COMPARE                        │     │
│   │    - Baseline eval on all benchmarks         │     │
│   │    - Bootstrap CIs for statistical validity  │     │
│   │    - Check for regressions                   │     │
│   │    - Generate version card                   │     │
│   └──────────────────────────────────────────────┘     │
│                         ↓                               │
│   ┌──────────────────────────────────────────────┐     │
│   │ 5. PROMOTION GATE                            │     │
│   │    - Better overall AND no category regressions? │  │
│   │    - YES → Promote to current                │     │
│   │    - NO  → Archive, keep current             │     │
│   └──────────────────────────────────────────────┘     │
│                         ↓                               │
│   ┌──────────────────────────────────────────────┐     │
│   │ 6. RELEASE & MONITOR                         │     │
│   │    - Tag version in git                      │     │
│   │    - Deploy to Orbis desktop app             │     │
│   │    - Monitor user feedback                   │     │
│   │    - Collect real-world failures             │     │
│   └──────────────────────────────────────────────┘     │
│                         ↓                               │
│  ┌────────────────────────────────────────────────┐    │
│  │ Loop back to STEP 1: IDENTIFY NEW WEAKNESSES   │    │
│  └────────────────────────────────────────────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Step 1: Identify Weaknesses

**Goal:** Discover what's broken, hard, or missing in the current model.

### 1.1: Comprehensive Evaluation
```bash
# Run baseline eval with current model on ALL benchmarks
python scripts/run-baseline-eval.py \
  --model-name "Qwen/Qwen3.5-0.8B-Base" \
  --adapter-path "registry/versions/CURRENT.json" \
  --output "runs/latest-eval/" \
  --limit-per-task 200  # Larger sample for better coverage
```

**Output:** `runs/latest-eval/summary.json`
- Per-task accuracy scores
- Per-group/per-level breakdowns
- Distribution of errors by domain

### 1.2: Hard Example Mining
```bash
# Identify items where model confidence < 0.5
python src/orion/evals/mining.py \
  --input "runs/latest-eval/" \
  --output "datasets/hard_examples/" \
  --confidence-threshold 0.5 \
  --sample-size 500
```

**Output:** `datasets/hard_examples/{domain}/`
```
synth-math/
├── arithmetic_edge_cases/
├── multi_step_reasoning/
└── symbolic_manipulation/

synth-science/
├── misconceptions/
├── unit_conversion/
└── extreme_values/

code/
├── off_by_one_errors/
├── timeout_cases/
└── complex_algorithms/
```

### 1.3: Failure Pattern Analysis
```bash
# Analyze error patterns in each domain
python -c "
import json
from pathlib import Path
from collections import defaultdict

results = json.load(open('runs/latest-eval/synth-math.jsonl'))
errors_by_family = defaultdict(int)

for r in results:
    if not r['ok']:
        errors_by_family[r['group']] += 1

for family, count in sorted(errors_by_family.items(), key=lambda x: -x[1]):
    print(f'{family}: {count} errors')
"
```

**Key Questions to Answer:**
- Which domains/families perform worst?
- What's the error distribution (wrong answer, timeout, syntax, logic)?
- Are there patterns (e.g., multi-step problems always fail)?
- What's the gap to production-level performance?

---

## Step 2: Curate Targeted Datasets

**Goal:** Create focused training data that addresses identified weaknesses.

### 2.1: Generate Synthetic Hard Examples
```bash
# For any domain (math, science, code, reasoning):
python src/orion/synth/{domain}.py \
  --n-samples 1000 \
  --difficulty hard \
  --seed-offset 10000 \
  --output datasets/train/hard_{domain}_v2.jsonl
```

**Example: Hard Physics Problems**
```bash
python src/orion/synth/science.py \
  --families physics \
  --n-per-family 1000 \
  --min-level 2 \
  --output datasets/train/hard_physics_v1.jsonl
```

### 2.2: Collect Real Failures
```bash
# From mining output, create dataset of actual failures
python -c "
import json
from pathlib import Path

# Load mined hard examples
hard_items = [json.loads(l) for l in open('datasets/hard_examples/synth-math/sequences.jsonl')]

# Create training pairs (input, correct_answer)
with open('datasets/train/failures_math_sequences.jsonl', 'w') as f:
    for item in hard_items:
        # Include problem + solution approach
        f.write(json.dumps({
            'messages': [{'role': 'user', 'content': item['problem']}],
            'answer': item['gold'],
            'family': 'sequences',
            'source': 'failure_mining'
        }) + '\n')
"
```

### 2.3: Organize by Curriculum
```yaml
# configs/data/hard_examples_curriculum_v1.yaml
sources:
  # Level 1: Fix critical failures (0% accuracy currently)
  - task: synth-math-sequences
    path: datasets/train/hard_math_sequences.jsonl
    count: 200
    weight: 0.3
    difficulty: hard
    min_level: 3

  # Level 2: Improve weak domains (30-50% accuracy)
  - task: synth-science-thermodynamics
    path: datasets/train/hard_science_thermodynamics.jsonl
    count: 300
    weight: 0.4
    difficulty: hard

  # Level 3: Adversarial robustness (edge cases)
  - task: adversarial-math
    path: datasets/train/adversarial_math.jsonl
    count: 200
    weight: 0.3
    difficulty: extreme
```

---

## Step 3: Train / Fine-Tune

**Goal:** Update model weights to fix identified weaknesses.

### 3.1: Choose Training Method

**For Quick Improvements (1-2 hours):**
```bash
# LoRA SFT on hard examples
python src/orion/train/sft.py configs/train/hard_examples_sft.yaml
```

Config:
```yaml
model_name_or_path: Qwen/Qwen3.5-0.8B-Base
adapter_name_or_path: checkpoints/orion-0.1-synthmath-lora/final

output_dir: checkpoints/orion-0.2-hard-examples-sft

training_args:
  max_steps: 200  # Quick training
  learning_rate: 0.0001  # Lower to avoid catastrophic forgetting
  per_device_batch_size: 4
```

**For Larger Improvements (4-8 hours):**
```bash
# DPO on preference pairs (harder, longer)
python src/orion/train/dpo.py configs/train/hard_examples_dpo.yaml
```

**For RL-Based Training (8-24 hours):**
```bash
# GRPO with reward models
python src/orion/train/grpo.py configs/train/hard_examples_grpo.yaml
```

### 3.2: Monitor Training
```bash
# Real-time MLflow dashboard
mlflow ui --backend-store-uri mlruns/
# Opens at http://localhost:5000
```

**Watch for:**
- Loss curve smoothness (not diverging)
- Eval loss tracking training loss
- No NaN/inf values

### 3.3: Merge LoRA Adapter (Optional)
```bash
# Merge trained LoRA into base model weights
python -c "
from peft import PeftModel
from transformers import AutoModelForCausalLM

base = AutoModelForCausalLM.from_pretrained('Qwen/Qwen3.5-0.8B-Base')
model = PeftModel.from_pretrained(base, 'checkpoints/orion-0.2-hard-examples-sft/final')
merged = model.merge_and_unload()
merged.save_pretrained('checkpoints/orion-0.2-hard-examples-merged/')
"
```

---

## Step 4: Evaluate & Compare

**Goal:** Measure whether training improved the model.

### 4.1: Run Full Evaluation
```bash
python scripts/run-baseline-eval.py \
  --adapter-path "checkpoints/orion-0.2-hard-examples-sft/final" \
  --output "runs/orion-0.2-hard-examples/" \
  --limit-per-task 200
```

### 4.2: Create Version Card
```bash
python -c "
import json
from orion.registry.versions import VersionCard, save_card

# Load eval results
results = json.load(open('runs/orion-0.2-hard-examples/summary.json'))

card = VersionCard(
    version='ORION-0.2-hard-examples',
    weights='Qwen/Qwen3.5-0.8B-Base',
    weights_owner='Alibaba (Qwen3.5-0.8B-Base)',
    weights_license='Apache-2.0',
    orion_modified=True,
    adapter='checkpoints/orion-0.2-hard-examples-sft/final',
    training_run_card='checkpoints/orion-0.2-hard-examples-sft/run_card.json',
    dataset_version='hard-examples-v1',
    training_config={},  # Load from config file
    evaluations=results,
    regression_suite={},  # Populate from results
    known_weaknesses=['Multi-step reasoning still weak'],
    improvements=['Trained on 1000 hard math examples'],
    parent_version='ORION-0.1',
    status='candidate'
)

save_card(card, 'registry/versions/')
"
```

### 4.3: Compare Against Incumbent
```bash
python -c "
from orion.registry.versions import load_card, promote

candidate = load_card('registry/versions/ORION-0.2-hard-examples.json')
incumbent = load_card('registry/versions/ORION-0.1.json')

decision = promote(candidate, incumbent, tolerance_points=2.0)
print('Decision:', decision)
"
```

---

## Step 5: Promotion Gate

**Criteria:**
- Candidate accuracy > Incumbent accuracy (95% CI excludes zero)
- No category drops more than 2 percentage points
- At least one significant improvement visible

**If YES → Promote:**
```bash
python -c "
from orion.registry.versions import load_card, save_card

candidate = load_card('registry/versions/ORION-0.2-hard-examples.json')
incumbent = load_card('registry/versions/ORION-0.1.json')

# Update statuses
candidate.status = 'current'
incumbent.status = 'archived'

# Save
save_card(candidate, 'registry/versions/')
save_card(incumbent, 'registry/versions/')

print('PROMOTED!')
"
```

**If NO → Analyze & Retry:**
```bash
# Why didn't it promote? Check:
# 1. Overall accuracy worse? Fix: Need more/better training data
# 2. Category regression? Fix: Fine-tune on regressed domain
# 3. Only marginal improvement? Fix: Longer training or better hyperparams
```

---

## Step 6: Release & Monitor

### 6.1: Tag Version in Git
```bash
git tag -a v0.2.0-hard-examples -m "ORION-0.2 with hard-example training"
git push origin v0.2.0-hard-examples
```

### 6.2: Deploy to Orbis
```bash
# Build new Orbis installer with ORION-0.2
cd "../Orbis AI desktop app"
npm run dist:complete
# Creates dist/Orbis-Installer-1.0.1.exe with ORION-0.2

# Release on GitHub
gh release create v1.0.1 \
  --title "Orbis 1.0.1 - ORION-0.2" \
  --notes "Improved math reasoning, science knowledge" \
  dist/Orbis-Installer-1.0.1.exe
```

### 6.3: Monitor User Feedback
```bash
# Collect failures from Orbis usage
# Create feedback dataset:
# - User queries where model fails
# - Corrections from user
# - Thumbs-down ratings

# Store in: datasets/feedback/
```

### 6.4: Real-World Failure Loop
```bash
# Process user feedback into next training cycle
python -c "
import json
from pathlib import Path

# Collect feedback from Orbis data directory
feedback_files = list(Path('datasets/feedback/').glob('*.jsonl'))

# Create curated dataset from feedback
with open('datasets/train/feedback_curated_v1.jsonl', 'w') as out:
    for fb_file in feedback_files:
        for line in fb_file.open():
            item = json.loads(line)
            # Only use high-quality feedback (verified by user)
            if item.get('verified', False):
                out.write(json.dumps({
                    'messages': [{'role': 'user', 'content': item['query']}],
                    'answer': item['correction'],
                    'source': 'user_feedback',
                    'domain': item.get('domain', 'general')
                }) + '\n')
"
```

---

## Automation: Make It Run Continuously

### Nightly Training Run
**File:** `.github/workflows/train-nightly.yml`

```yaml
name: Nightly Training

on:
  schedule:
    # Every night at 2 AM UTC
    - cron: "0 2 * * *"

jobs:
  train:
    runs-on: [self-hosted, gpu]  # Use GPU if available
    steps:
      - uses: actions/checkout@v3

      - name: Evaluate Current Model
        run: python scripts/run-baseline-eval.py --limit-per-task 100

      - name: Mine Hard Examples
        run: python src/orion/evals/mining.py --output datasets/hard_examples/

      - name: Train on Hard Examples
        run: python src/orion/train/sft.py configs/train/hard_examples_sft.yaml

      - name: Evaluate Trained Model
        run: python scripts/run-baseline-eval.py --adapter-path checkpoints/orion-{version}/final

      - name: Promotion Gate
        run: python scripts/train-and-promote.py --skip-training --version-name ORION-{version}

      - name: Release if Promoted
        if: success()
        run: |
          git tag ORION-{version}
          gh release create ORION-{version}
```

### Continuous Feedback Loop
**File:** `src/orion/data/feedback_loop.py`

```python
"""Collect feedback from Orbis, create training dataset, trigger retraining."""

class FeedbackCollector:
    def collect_from_orbis(self, feedback_dir: Path):
        """Load thumbs-down ratings from Orbis data."""
        items = []
        for f in feedback_dir.glob('*.jsonl'):
            for line in f.open():
                item = json.loads(line)
                if item.get('rating') == 'down':  # Thumbs down = failure
                    items.append(item)
        return items

    def curate_training_dataset(self, items: list[dict], min_agreement: float = 0.8) -> list[dict]:
        """Filter high-quality feedback for training."""
        # Only include items with high agreement (multiple users confirmed failure)
        curated = [i for i in items if i.get('agreement', 0) >= min_agreement]
        return curated

    def trigger_training_if_threshold_reached(self, feedback_count: int, threshold: int = 100):
        """Retrain if enough new failures collected."""
        if feedback_count >= threshold:
            subprocess.run(['python', 'scripts/train-and-promote.py'])
```

---

## The Infinite Loop in Practice

### Iteration Example: ORION-0.1 → 0.2 → 0.3 → 0.4 ...

**ORION-0.1 (Baseline):**
- 64% on math

**ORION-0.2 (Hard Math Examples):**
- Run baseline → identify sequences/systems at 0%
- Generate hard sequence problems
- Train SFT on 500 sequence problems + other hard math
- Evaluate → 72% overall, sequences improved to 30%
- Promote ✅

**ORION-0.3 (Multi-Domain):**
- Evaluate 0.2 → Science weak (45%), Reasoning (38%)
- Generate 1000 hard science problems + 500 reasoning
- Train DPO on failures
- Evaluate → 75% overall, science 55%, reasoning 50%
- Promote ✅

**ORION-0.4 (Safety & Edge Cases):**
- Red-team evaluation finds adversarial examples
- Collect adversarial dataset (500 examples)
- Train GRPO with reward model
- Evaluate → safety metrics improved
- Promote ✅

**ORION-0.5 (Multimodal Integration):**
- Add vision tasks
- Add code synthesis tasks
- Evaluate on vision + code + text
- Multi-task training
- Promote ✅

---

## Success Metrics Over Time

```
Iteration | Version  | Math | Science | Reasoning | Code | Overall
----------|----------|------|---------|-----------|------|----------
0         | 0.0-base | 39%  | N/A     | N/A       | N/A  | 39%
1         | 0.1      | 64%  | N/A     | N/A       | N/A  | 64%
2         | 0.2      | 72%  | 45%     | 38%       | N/A  | 55%
3         | 0.3      | 75%  | 55%     | 50%       | 20%  | 60%
4         | 0.4      | 78%  | 60%     | 62%       | 35%  | 65%
5         | 0.5      | 82%  | 68%     | 72%       | 52%  | 72%
6         | 0.6      | 85%  | 75%     | 80%       | 68%  | 78%
...       | ...      | ...  | ...     | ...       | ...  | ...
N         | 1.0      | 88%  | 82%     | 85%       | 75%  | 82%
```

---

## Critical Rules

### ✅ DO:
- Train frequently (daily/weekly if feedback available)
- Track every version card with complete provenance
- Mine hard examples continuously
- Run regression tests before promotion
- Archive old versions (never delete)
- Collect real-world failures

### ❌ DON'T:
- Claim improvement without measurement
- Promote without statistical significance test
- Train on evaluation set (contamination)
- Forget to check regression on other domains
- Use fake data or synthetic-only training forever
- Stop iterating (the loop never ends)

---

## Start the Loop Now

```bash
# 1. Run baseline eval
python scripts/run-baseline-eval.py --limit-per-task 50

# 2. Review results to find weaknesses
cat runs/baseline/summary.json | python -m json.tool

# 3. Mine hard examples
python src/orion/evals/mining.py --output datasets/hard_examples/

# 4. Create training config for hard examples
# (adapt configs/train/laptop_multimodal_sft.yaml)

# 5. Train
python src/orion/train/sft.py configs/train/hard_examples_sft.yaml

# 6. Evaluate & Promote
python scripts/train-and-promote.py --skip-baseline-eval

# 7. Loop back to step 1
```

**Total time:** 8-24 hours per iteration (depending on dataset size)

**The system never stops improving.**

