# OMNISCIENT ORION - Comprehensive Multi-Domain Training

**Goal:** Train a single AI model that covers ALL knowledge domains simultaneously, achieving true "omniscient" capability across 7 major knowledge areas.

---

## The Challenge

ORION-0.2 focused on specific weaknesses (sequences, systems, science). Now we're scaling to **comprehensive knowledge coverage** — training on everything at once while preventing regression.

**Key Principle:** A truly capable AI doesn't specialize in just math or science. It needs:
- Math, Science, Coding, Reasoning, Knowledge, and domain-specific skills
- NO regression in existing strengths
- Simultaneous improvement across all domains

---

## 7 Knowledge Domains

### 1. **Mathematics** (2,000 examples)
- Algebra, geometry, arithmetic
- Problem-solving across domains
- Existing strength to maintain

### 2. **Science** (10,500 examples)
- Physics: kinematics, dynamics, thermodynamics
- Chemistry: stoichiometry, equilibrium
- Biology: genetics, evolution
- Weak area to strengthen (40% → 50%+)

### 3. **Sequences** (800 examples)
- Arithmetic sequences, geometric, Fibonacci, polynomial
- Pattern recognition and formula application
- Critical weakness (0% → 60%+)

### 4. **Systems of Equations** (600 examples)
- 2x2 and 3x3 systems
- Substitution and elimination methods
- Critical weakness (0% → 60%+)

### 5. **Coding** (800 examples)
- Array/string manipulation, algorithms, debugging
- Time complexity analysis
- Code comprehension and design

### 6. **Reasoning** (1,000 examples)
- Logic puzzles, analogies, common sense
- Cause-effect, multi-step thinking
- Foundation for general intelligence

### 7. **Knowledge** (1,000 examples)
- History, geography, culture, technology
- General factual knowledge
- Foundation for comprehensive understanding

---

## Total Training Data: 18,700 examples

**Why This Size?**
- Sufficient for 500-step training (36+ epochs effective)
- Covers breadth without overfitting
- Manageable within laptop constraints

---

## Training Configuration

**File:** `configs/train/orion-0.2-omniscient.yaml`

```yaml
Hyperparameters:
  max_steps:     500 (vs 300 aggressive, 100 fast-track)
  learning_rate: 0.0001
  batch_size:    8 effective (4 × 2 accumulation)
  epochs:        2 full passes
  duration:      ~4-8 hours
  
LoRA:
  r:     16 (balanced expressiveness)
  α:     32
  modules: q_proj, v_proj
  
Sequence:
  max_seq_length: 512 (vs 256 fast-track)
  packing: disabled (better for diverse domains)
```

**Why Omniscient Config?**
1. More steps (500 vs 300) for deeper learning
2. Larger sequences (512 vs 256) for complex reasoning
3. Longer training time (4-8h vs 2-4h) justified by 7 domains
4. Single LoRA adapter stacked on ORION-0.1 → preserves prior knowledge

---

## Evaluation Framework

**File:** `scripts/omniscient-eval.py`

### Comprehensive Assessment

```
Evaluates all 7 domains simultaneously:
  Math:      20 items per domain
  Science:   50 items
  Sequences: 50 items
  Systems:   50 items
  Coding:    50 items
  Reasoning: 50 items
  Knowledge: 50 items
  
Total: 350 evaluation items
Time: ~30 minutes
```

### Results Format

```
By Domain:
  math          | 70.0% [STRONG]
  science       | 50.0% [GOOD]
  sequences     | 60.0% [GOOD]
  systems       | 60.0% [GOOD]
  coding        | 45.0% [WEAK]
  reasoning     | 55.0% [GOOD]
  knowledge     | 50.0% [GOOD]

By Category:
  STEM                   | 55.0%
  Logic & Reasoning      | 58.3%
  Knowledge              | 50.0%

  OVERALL BLENDED        | 55.7%
```

### Promotion Criteria

✓ **PASS** if:
- Blended average ≥ 60%
- No domain drops below 30% (except reasoning/knowledge can go lower)
- Better than 95% of previous best

✗ **REJECT** if:
- Major regression in any core domain
- Blended < 60%

---

## Continuous Improvement Loop

**File:** `scripts/omniscient-loop.py`

### Cycle Structure

```
Iteration 1:
  [1] Train ORION-0.2 on all 7 domains (500 steps, 4-8h)
  [2] Evaluate comprehensively (30m)
  [3] Promote if blended ≥ 60%
      └─ ORION-0.2 becomes current
  [60s pause]

Iteration 2:
  [1] Train ORION-0.3 (builds on ORION-0.2)
  [2] Evaluate (if better than ORION-0.2, promote)
  [3] Continue indefinitely
```

### Key Features

1. **Stacked LoRA:** Each version builds on previous (ORION-0.1 → 0.2 → 0.3 → ...)
2. **Regression Prevention:** Previous best is baseline; must improve 95%
3. **All-Domain Training:** Every cycle improves or maintains all 7 domains
4. **Indefinite Cycles:** No stopping point — continuous improvement forever

---

## Expected Results

### ORION-0.1 Baseline (before omniscient)
```
Math:      70% (STRONG)
Science:   40% (WEAK)
Sequences: 0%  (CRITICAL)
Systems:   0%  (CRITICAL)
Coding:    25% (BASELINE)
Reasoning: 40% (BASELINE)
Knowledge: 35% (BASELINE)
─────────────────────────
BLENDED:   33% (limited)
```

### ORION-0.2 Omniscient (after training on all 7 domains)

**Conservative Targets:**
```
Math:      72% (maintain)
Science:   50% (improve)
Sequences: 60% (fix critical)
Systems:   60% (fix critical)
Coding:    40% (improve)
Reasoning: 55% (improve)
Knowledge: 50% (improve)
─────────────────────────
BLENDED:   56% (60%+ target)
```

**Aggressive Targets:**
```
Math:      75% (improve)
Science:   55% (improve)
Sequences: 70% (exceed target)
Systems:   70% (exceed target)
Coding:    50% (improve)
Reasoning: 65% (improve)
Knowledge: 60% (improve)
─────────────────────────
BLENDED:   62% (comfortable pass)
```

---

## Avoiding Catastrophic Forgetting

**Problem:** Training on new domains can cause regression in old ones.

**Solution:** Multi-domain stacked training
1. All 18,700 examples trained in single 500-step pass
2. Each domain present in every epoch (18,700 ÷ 500 steps ≈ 37 examples/step on average)
3. Continuous exposure to all domains prevents forgetting
4. Regression prevention gate catches failures early

---

## Integration with Orbis

The trained ORION-0.2 model will power the Orbis desktop application:
- Users get improved model automatically (checkpoint reload)
- All 7 domains available in chat interface
- Continuous improvement loop keeps Orbis cutting-edge

**Timeline:**
1. Start omniscient training loop now
2. First promotion expected: 4-8 hours (initial iteration)
3. Subsequent cycles: Every 4-8 hours if promoted
4. Within 48 hours: Multiple generations possible

---

## Files Structure

```
orion/
├── configs/train/
│   └── orion-0.2-omniscient.yaml          # Master training config
├── scripts/
│   ├── omniscient-eval.py                 # Comprehensive evaluation
│   └── omniscient-loop.py                 # Continuous improvement loop
├── src/orion/synth/
│   ├── coding.py          (NEW)           # Generate coding problems
│   ├── reasoning.py       (NEW)           # Generate reasoning problems
│   ├── knowledge.py       (NEW)           # Generate knowledge problems
│   ├── sequences.py       (EXISTING)      # Generate sequence problems
│   ├── systems.py         (EXISTING)      # Generate systems problems
│   ├── science.py         (EXISTING)      # Generate science problems
│   └── math.py            (EXISTING)      # Generate math problems
├── data/raw/
│   ├── synth_math/                        # 2K train + 500 test
│   ├── synth_science/                     # 10.5K train + 420 test
│   ├── synth_sequences/                   # 800 train + 200 test
│   ├── synth_systems/                     # 600 train + 150 test
│   ├── synth_coding/        (NEW)         # 800 train + 200 test
│   ├── synth_reasoning/     (NEW)         # 1K train + 250 test
│   └── synth_knowledge/     (NEW)         # 1K train + 250 test
└── runs/
    └── omniscient-eval/                   # Comprehensive eval results
```

---

## Running the Pipeline

### Option 1: Single Training + Evaluation
```bash
# Train on all 7 domains
python src/orion/train/sft.py configs/train/orion-0.2-omniscient.yaml

# Comprehensive evaluation
python scripts/omniscient-eval.py \
  Qwen/Qwen3.5-0.8B-Base \
  checkpoints/orion-0.2-omniscient/final
```

### Option 2: Continuous Improvement Loop
```bash
# Run indefinite omniscient cycles
python scripts/omniscient-loop.py
```

**Expected Runtime per Cycle:**
- Training: 4-8 hours
- Evaluation: 30 minutes
- Total: 4.5-8.5 hours
- Pause: 60 seconds before next cycle

---

## Philosophy

> **"All knowledge, continuously improving, no forgetting, all at once."**

Instead of training domain-by-domain or version-by-version in isolation, the omniscient approach recognizes that:

1. **Knowledge isn't siloed** — math helps reasoning, coding helps problem-solving, etc.
2. **Breadth matters** — a model weak in 3 domains isn't ready for production
3. **Continuous matters** — the goal isn't "done" but "always better"
4. **Regression is poison** — one mistake can undo weeks of work

This pipeline delivers all four.

---

## Next Steps

1. Generate all 7 domain datasets ✓ (18,700 examples ready)
2. Add new task types to registry ✓ (CodingTask, ReasoningTask, KnowledgeTask)
3. Create unified training config ✓ (omniscient.yaml)
4. Build comprehensive evaluation ✓ (omniscient-eval.py)
5. Launch continuous loop ✓ (omniscient-loop.py)
6. **START TRAINING NOW**
7. Monitor iterations and promotion decisions
8. Iterate until ORION becomes truly omniscient

---

**Status:** Ready to launch omniscient training loop  
**Target:** 60%+ blended average across all 7 domains  
**Ultimate Goal:** Create an AI model that genuinely understands all domains
