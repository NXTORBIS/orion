# Phase 2: Aggressive ORION-0.2 Training
## Targeting Identified Weaknesses

**Status:** TRAINING IN PROGRESS  
**Started:** 2026-09-13 ~21:00 UTC  
**Expected Duration:** 2-4 hours (300 steps, aggressive learning rate)  
**Log:** `training-orion-0.2.log`  

---

## Weaknesses Identified in Phase 1

From baseline evaluation, ORION-0.1 had critical failures:

```
SEQUENCES:     0% (0/1 correct)  ← Critical failure
SYSTEMS:       0% (0/1 correct)  ← Critical failure
SCIENCE:      40% (4/10 correct) ← Weak domain
```

**Goal of Phase 2:** Fix these three areas through targeted training.

---

## Phase 2 Training Data

### 1. Sequence Problems (800 training examples)
**Target Weakness:** Sequences (was 0%)

**Types Generated:**
- **Arithmetic Sequences** (200 examples)
  - Formula: a_n = a + (n-1)d
  - Examples: 2, 5, 10, 17, 26, ... (find 10th term)
  - Difficulty: Easy to Hard

- **Geometric Sequences** (200 examples)
  - Formula: a_n = a * r^(n-1)
  - Examples: 2, 6, 18, 54, ... (find nth term)
  - Difficulty: Medium to Hard

- **Fibonacci Variants** (200 examples)
  - Formula: a_n = a_(n-1) + a_(n-2)
  - Custom starting values
  - Difficulty: Medium

- **Polynomial Sequences** (200 examples)
  - Formula: a_n = an² + bn + c
  - Second-order patterns
  - Difficulty: Hard

**Expected Improvement:** 0% → 60%+

### 2. Systems of Equations (600 training examples)
**Target Weakness:** Systems (was 0%)

**Types Generated:**
- **2x2 Substitution** (200 examples)
  - Simple systems, designed for substitution method
  - Examples: 2x + 3y = 7, x + y = 3
  - Difficulty: Easy to Medium

- **2x2 Elimination** (200 examples)
  - Systems designed for elimination method
  - Aligned coefficients for easy elimination
  - Difficulty: Medium

- **3x3 Simple** (200 examples)
  - Diagonal-dominant systems
  - Triangular structure for easier solving
  - Difficulty: Hard

**Expected Improvement:** 0% → 60%+

### 3. Science Problems (10,500 training examples)
**Target Weakness:** Science (was 40%)

**Domains:**
- **Physics** (3500 examples)
  - Kinematics, Dynamics, Thermodynamics
  
- **Chemistry** (3500 examples)
  - Stoichiometry, Equilibrium
  
- **Biology** (3500 examples)
  - Genetics, Evolution

**Expected Improvement:** 40% → 50%+

### 4. Math Reinforcement (2000 training examples)
**Purpose:** Maintain existing strengths while adding new content

---

## ORION-0.2 Training Configuration

**File:** `configs/train/orion-0.2-aggressive-sft.yaml`

```yaml
Base Model:     Qwen3.5-0.8B-Base
Adapter:        LoRA r=16 on ORION-0.1 (stacked)
Method:         SFT (Supervised Fine-Tuning)

Hyperparameters:
  learning_rate:      0.0001  (lower than baseline)
  lr_scheduler:       cosine
  warmup_steps:       30
  num_epochs:         2
  max_steps:          300
  batch_size:         4 (per device)
  gradient_accum:     2 (effective batch = 8)
  
Training Duration:   ~2-4 hours on CPU
Model Size:         763M parameters
Trainable Params:   ~27M (LoRA stacked on LoRA)
```

**Why Aggressive?**
- Lower learning rate (0.0001 vs 0.0002) → More careful updates
- More steps (300 vs 200) → Longer training
- Larger batch size (4 vs 2) → Better gradient estimates
- Stacked LoRA → Can refine previous adaptations

---

## What Will Improve

### Immediate Targets

**Sequences (0% → 60% expected):**
```
Input:  "Arithmetic sequence: 2, 5, 10, 17, 26, ... What is the 10th term?"
Before: [FAILS - doesn't recognize pattern]
After:  [Should recognize a_n = a + (n-1)d pattern]
Result: Likely 10th term = 101 (CORRECT)
```

**Systems (0% → 60% expected):**
```
Input:  "Solve: 2x + 3y = 7, x + y = 3"
Before: [FAILS - doesn't manipulate equations]
After:  [Should recognize substitution/elimination methods]
Result: Likely x = 2, y = 1 (CORRECT)
```

**Science (40% → 50% expected):**
```
Input:  "Object falls 100m. How long does it take? (g=9.8)"
Before: 40% chance correct (random domain knowledge)
After:  50%+ chance correct (domain-specific training)
```

### Maintained Strengths

**Math Arithmetic:** 100% → 100%+ (should stay high)
**Math Algebra:** 100% → 100%+ (should stay high)
**Math Percents:** 100% → 100%+ (should stay high)

---

## Success Metrics

### Phase 2 Success Criteria

| Domain | Baseline | Target | Status |
|--------|----------|--------|--------|
| Sequences | 0% | 60%+ | Training |
| Systems | 0% | 60%+ | Training |
| Science | 40% | 50%+ | Training |
| Math (overall) | 70% | 72%+ | Training |
| **Blended** | **55%** | **65%+** | **Training** |

**Promotion Threshold:** 65%+ blended average with no regression >5pp

---

## After Training Complete

### Step 1: Evaluation (1-2 hours after training)
```bash
python scripts/run-baseline-eval.py \
  --adapter-path checkpoints/orion-0.2-aggressive-sft/final \
  --output runs/orion-0.2-eval-aggressive/ \
  --limit-per-task 50
```

**Expected Results:**
```
Sequences: 60-70%  (was 0%)
Systems:   60-70%  (was 0%)
Science:   50-60%  (was 40%)
Math:      72-75%  (was 70%)
Overall:   65-70%  (was 55%)
```

### Step 2: Promotion Gate
```bash
python scripts/train-and-promote.py \
  --version-name ORION-0.2 \
  --skip-baseline-eval \
  --skip-training
```

**Decision Logic:**
- If overall > 60% AND no category regresses >5pp: **PROMOTE**
- Otherwise: Keep ORION-0.1, analyze, iterate

### Step 3: If Promoted
- ORION-0.2 becomes current production model
- ORION-0.1 archived
- Begin Phase 3: ORION-0.3 training with new weaknesses

---

## Monitoring

### Check Training Progress
```bash
# Real-time log
tail -f training-orion-0.2.log

# MLflow metrics
mlflow ui --backend-store-uri mlruns/
# Open http://localhost:5000

# Check checkpoint size
watch -n 10 "du -sh checkpoints/orion-0.2-aggressive-sft/"
```

### Expected Log Output
```
Loading model: Qwen/Qwen3.5-0.8B-Base
Loading adapter: checkpoints/orion-0.1-synthmath-lora/final
Loading training data: 14000 samples
  - Sequences: 800 samples
  - Systems: 600 samples
  - Science: 10500 samples
  - Math: 2000 samples
Starting training...
  Step 10: loss = 0.45
  Step 20: loss = 0.38
  Step 50: loss = 0.25
  ...
  Step 300: loss = 0.08
Training complete!
Merged checkpoint saved to: checkpoints/orion-0.2-aggressive-sft/final
```

---

## Parallel Continuous Loop

While ORION-0.2 trains, the system is ready for:

1. **Prepare ORION-0.3 training data** (if needed)
2. **Monitor Phase 1 baseline** (already complete)
3. **Build evaluation infrastructure** for Phase 2
4. **Plan Phase 3** based on Phase 2 results

---

## Timeline

| Time | Activity | Status |
|------|----------|--------|
| 21:00 | Phase 2 training starts | RUNNING |
| 22:00 | 100 steps completed | ETA |
| 23:00 | 200 steps completed | ETA |
| 00:00 | 300 steps completed | ETA |
| 00:30 | Training complete | ETA |
| 01:00 | Full evaluation complete | ETA |
| 01:30 | Promotion decision | ETA |
| 02:00 | If promoted: ORION-0.2 current | ETA |

---

## Key Difference from Phase 1

**Phase 1 (Baseline):** Evaluated existing ORION-0.1 model
**Phase 2 (Aggressive):** Train on targeted data for identified weaknesses

**Result Expected:** Significant improvement in sequences and systems (0% → 60%+)

