# Orion Training Infrastructure Roadmap

## Executive Summary

The Orion project has a **production-grade, scientifically rigorous AI training pipeline** that already implements most principles in the AI development manifesto. This document maps current infrastructure against the manifesto and identifies the next phase of model development.

**Current State:**
- ✅ ORION-0.1 (current production) trained on synthetic math
- ✅ 64% accuracy on math (25 percentage point improvement over baseline)
- ✅ Rigorous promotion gate (95% bootstrap CI, regression testing)
- ✅ Version cards with complete provenance
- ✅ LoRA-based fine-tuning without catastrophic forgetting
- ⚠️ Currently only covers synthetic math domain

---

## Part 1: Existing Infrastructure (Already Implemented)

### 1.1 Training Pipeline (`src/orion/train/`)

**Implemented:**
- ✅ **SFT (Supervised Fine-Tuning)** via `trl.SFTTrainer` with LoRA or full weights
- ✅ **DPO (Direct Preference Optimization)** via `trl.DPOTrainer`
- ✅ **GRPO (RL with Verifiable Rewards)** via `trl.GRPOTrainer` + custom verifiers

**Run Card Recording:**
- Base model, tokenizer, training config, hyperparameters
- Hardware info, training duration, loss curves
- MLflow integration for experiment tracking
- Git commit hash for reproducibility

### 1.2 Evaluation Framework (`src/orion/evals/`)

**Implemented:**
- ✅ **Task definitions** with item generators and verifiers
- ✅ **Runner** (local HF models + optional LoRA adapters)
- ✅ **Metrics** — accuracy, bootstrap CIs, paired comparisons, group breakdowns
- ✅ **Report generation** — scorecards from measured data only
- ✅ **Blind evaluation** — human preference labeling
- ✅ **Red-team evaluation** — adversarial testing
- ✅ **Hard-example mining** — failure case curation

### 1.3 Verification Modules (`src/orion/verify/`)

**Implemented:**
- ✅ **Math verification** (`math.py`) — answer extraction and comparison
- ✅ **Code verification** (`code.py`) — execution and correctness
- ✅ **SQL verification** (`sql.py`) — query correctness
- ✅ **Tool-call verification** (`toolcall.py`) — API usage validation

### 1.4 Version Management (`src/orion/registry/versions.py`)

**Implemented:**
- ✅ **VersionCard** — complete model metadata
  - Weights source and license
  - Training run card reference
  - Dataset version
  - Evaluation results (by domain, by level)
  - Regression suite (per-item pass/fail)
  - Known weaknesses and improvements
  - Parent version tracking
  
- ✅ **Promotion Gate** — rigorous statistical validation
  - 95% paired-bootstrap confidence interval (zero excluded = significance)
  - Category-wise regression tolerance (default 2 points)
  - Automatic status assignment (candidate → current/archived/rejected)
  - Never downgrades production model

**Current Model Version ORION-0.1:**
- Weights: Qwen3.5-0.8B-Base (Alibaba, Apache-2.0 license)
- Adapter: 10.8M trainable LoRA params (r=16)
- Training: 120 steps on synth-math-v1, batch 2×4 accumulation
- Performance: 64% accuracy on math (up from 39% baseline)
- Status: **current** (promoted via statistical test)

---

## Part 2: Manifesto Alignment

### What's Already Aligned ✅

| Manifesto Item | Orion Status |
|---|---|
| Real training only (no fake improvements) | ✅ Actual weight updates via TRL trainers |
| Model version tracking | ✅ VersionCard with full provenance |
| Regression testing | ✅ Regression suite per-item validation |
| Evaluation suite | ✅ Task-based scoring + bootstrap CIs |
| Catastrophic forgetting prevention | ✅ LoRA adapters for incremental learning |
| Modular datasets/evaluations | ✅ `src/orion/data/` and `src/orion/evals/` separation |
| Hard-example mining | ✅ `evals/mining.py` identifies failures |
| User feedback pipeline | ✅ `data/pii.py`, `data/quality.py`, `evals/blind.py` |
| Multi-domain coverage | ⚠️ **Only math currently; science, coding, vision, etc. pending** |
| Reasoning + math + science + coding | ⚠️ **Infrastructure ready, datasets/tasks needed** |
| Continuous improvement loop | ✅ Failure → Analysis → Dataset → Training → Eval → Promote |

### What's Pending ⚠️

| Manifesto Item | Next Steps |
|---|---|
| **Multi-domain evaluation suite** | Load GSM8K-Platinum, MATH-500, MMLU-Pro, HumanEval+, MBPP+ |
| **Science domain** | Create synth-science tasks (physics, chemistry, biology) |
| **Reasoning domain** | Benchmark on reasoning-specific tasks (GSM8K → harder) |
| **Vision evaluation** | Integrate image-based tasks (if multimodal model added) |
| **Code-specific eval** | HumanEval+ or MBPP+ for code correctness |
| **Long-context eval** | Benchmarks on >4K token contexts |
| **Safety/red-team** | Expanded adversarial test suite (`redteam.py` framework ready) |
| **Factuality** | Baseline facts / retrieval-augmented QA tasks |
| **Instruction following** | IFEval or similar complexity task suite |

---

## Part 3: Next Phase Development

### Phase A: Multi-Domain Evaluation Baseline (1-2 weeks)

**Objective:** Create comprehensive regression suite across all major domains.

#### A.1 Load Standard Benchmarks

```bash
# Once files are available in datasets/:
- GSM8K-Platinum (math reasoning)
- MATH-500 (competition math)
- MMLU-Pro (factual knowledge, reasoning, science)
- HumanEval+ (coding)
- MBPP+ (coding)
- IFEval (instruction following)
```

**Action:**
1. Add loaders to `src/orion/evals/tasks.py` (pattern already exists: `JsonlMathTask`)
2. Test with ORION-0.1 to get baseline scores
3. Create initial regression suite (50-100 items per domain)
4. Document performance by domain and difficulty level

#### A.2 Create Domain-Specific Verifiers

Update `src/orion/verify/` with:
- Code execution + assertion checking (HumanEval+)
- Factuality checking (MMLU-Pro)
- Instruction compliance (IFEval)

### Phase B: Hard-Example Mining & Curation (2-3 weeks)

**Objective:** Identify and organize failure cases for targeted improvement.

#### B.1 Run Baseline Evaluation

```bash
python -m orion.evals.runner \
  --model Qwen3.5-0.8B-Base+checkpoints/orion-0.1-synthmath-lora/final \
  --tasks synth-math gsm8k-platinum humaneval-plus \
  --output runs/baseline-multimodal/
```

#### B.2 Mine Hard Examples

Using `src/orion/evals/mining.py`:
- Collect items with confidence < 0.5
- Group by failure mode (off-by-one, method confusion, timeout, syntax error)
- Sample for human review + curation
- Create hard-example dataset

#### B.3 Organize Failures

```
datasets/hard_examples/
├── math/
│   ├── arithmetic_edge_cases/
│   ├── multi_step_reasoning/
│   └── symbolic_manipulation/
├── code/
│   ├── off_by_one/
│   ├── edge_case_handling/
│   └── algorithm_choice/
├── reasoning/
│   ├── circular_dependency/
│   ├── contradictory_constraints/
│   └── many_step_inference/
└── science/
    ├── misconceptions/
    ├── unit_conversion/
    └── conceptual_understanding/
```

### Phase C: Science & Reasoning Dataset Creation (3-4 weeks)

**Objective:** Expand beyond math into science, reasoning, and mixed domains.

#### C.1 Procedural Science Generation

Extend `src/orion/synth/` with:
- **synth_physics.py** — mechanics, thermodynamics, electromagnetism problems
- **synth_chemistry.py** — stoichiometry, equilibrium, redox reactions
- **synth_biology.py** — genetics, ecology, cell biology
- **synth_reasoning.py** — logical inference, constraint satisfaction

Each generates:
```json
{
  "id": "physics-kinematics-1000000",
  "problem": "A ball is thrown...",
  "answer": "3.5",
  "family": "kinematics",
  "level": 1,
  "concepts": ["motion", "gravity"],
  "verifier": "numerical"
}
```

#### C.2 Create Evaluation Tasks

```python
# src/orion/evals/tasks.py
class SynthScienceTask(SynthMathTask):
    """Physics, chemistry, biology procedural problems."""
    name = "synth-science"
    
    def score(self, item, response):
        # Route to domain-specific verifier
        domain = item.group.split('-')[0]  # "physics", "chemistry", etc.
        verifier = DOMAIN_VERIFIERS[domain]
        return verifier(response, item.gold, item.meta)
```

#### C.3 Reasoning-Specific Benchmarks

Create multi-step reasoning tasks:
- Constraint satisfaction (0-1 optimal solution)
- Circular dependency resolution
- Fact integration from multiple sources
- Adversarial robustness (adversarial examples still solved correctly)

### Phase D: Training Run 1 — Multi-Domain SFT (2-3 weeks)

**Objective:** First multi-domain training, targeting math + reasoning + science.

#### D.1 Dataset Preparation

```yaml
# configs/data/multimodal_v1.yaml
name: "multimodal-v1"
version: "multimodal-v1-alpha"

sources:
  - task: synth-math
    path: data/raw/synth_math/train.jsonl
    count: 2000
    weight: 0.4
    
  - task: gsm8k-platinum
    path: datasets/gsm8k_platinum/train.jsonl
    count: 1000
    weight: 0.3
    
  - task: synth-reasoning
    path: data/raw/synth_reasoning/train.jsonl
    count: 500
    weight: 0.15
    
  - task: synth-science
    path: data/raw/synth_science/train.jsonl
    count: 500
    weight: 0.15

# Data quality & contamination checks
quality:
  - dedup_by_hash
  - remove_pii
  - check_contamination_vs_evals

total_samples: 4000
```

#### D.2 Training Configuration

```yaml
# configs/train/laptop_multimodal_sft.yaml
model_name_or_path: Qwen/Qwen3.5-0.8B-Base
adapter_name_or_path: checkpoints/orion-0.1-synthmath-lora/final

output_dir: checkpoints/orion-0.2-multimodal-sft

training_args:
  num_train_epochs: 1
  max_steps: 500  # ~0.125 epochs
  learning_rate: 0.0002
  lr_scheduler_type: cosine
  warmup_steps: 50
  per_device_train_batch_size: 2
  gradient_accumulation_steps: 4
  
  logging_steps: 10
  save_steps: 100
  eval_steps: 100
  
  # Hardware
  fp16: true
  dataloader_num_workers: 2
  optim: paged_adamw_8bit

lora_config:
  r: 16
  lora_alpha: 32
  target_modules: ["q_proj", "v_proj"]
  lora_dropout: 0.05
  bias: "none"
  task_type: CAUSAL_LM
```

#### D.3 Training Execution

```bash
cd src/orion
python train/sft.py configs/train/laptop_multimodal_sft.yaml
```

Outputs:
- Checkpoint with merged adapter weights
- `run_card.json` with metrics, duration, hardware info
- Training loss curve and validation metrics

### Phase E: Evaluation & Promotion (1 week)

**Objective:** Validate ORION-0.2 against full regression suite.

#### E.1 Run Comprehensive Eval

```bash
python -m orion.evals.runner \
  --model Qwen3.5-0.8B-Base+checkpoints/orion-0.2-multimodal-sft/final \
  --tasks synth-math synth-reasoning synth-science gsm8k-platinum humaneval-plus \
  --output runs/orion-0.2/ \
  --n-items 100  # Per-task sample
```

#### E.2 Create Version Card

```python
from orion.registry.versions import VersionCard, save_card, promote

card = VersionCard(
    version="ORION-0.2",
    weights="Qwen/Qwen3.5-0.8B-Base",
    weights_owner="Alibaba (Qwen3.5-0.8B-Base)",
    orion_modified=True,
    adapter="checkpoints/orion-0.2-multimodal-sft/final",
    training_run_card="checkpoints/orion-0.2-multimodal-sft/run_card.json",
    dataset_version="multimodal-v1-alpha",
    training_config={...},
    evaluations={...},  # Populated from eval runner
    regression_suite={...},  # Populated from eval runner
    known_weaknesses=[...],  # From mining
    improvements=["SFT on 4K multi-domain samples (math, reasoning, science)"],
    parent_version="ORION-0.1"
)

# Promotion gate
decision = promote(card, incumbent=load_card("registry/versions/ORION-0.1.json"))
print(decision)  # {"promote": True/False, "reason": "...", "overall": {...}}

save_card(card, "registry/versions/")
```

#### E.3 Promotion Decision

If promoted:
```json
{
  "promote": true,
  "reason": "better overall and no category regression",
  "overall": {
    "diff": 0.08,  // 8% absolute improvement
    "ci": [0.02, 0.14],  // 95% CI excludes zero
    "significant": true
  },
  "categories": {
    "synth-math": {"delta_points": 5},
    "gsm8k": {"delta_points": 12},
    "synth-reasoning": {"delta_points": 8}
  }
}
```

**Status transitions:**
- ORION-0.1: `current` → `archived`
- ORION-0.2: `candidate` → `current`

---

## Part 4: Six-Month Roadmap

### Month 1: Multi-Domain Baseline (Phases A–B)
- Load 5 standard benchmarks
- Mine hard examples from ORION-0.1
- Establish baseline regression suite
- **Milestone:** Version card for ORION-0.1 with full domain scores

### Month 2: Science & Reasoning (Phase C)
- Generate synth-science tasks (physics, chemistry, biology)
- Create synth-reasoning dataset
- Implement domain-specific verifiers
- **Milestone:** 3 new evaluation tasks, 1K items each

### Month 3: Multi-Domain Training (Phase D–E)
- Train ORION-0.2 on math + reasoning + science
- Full evaluation pipeline
- Promotion decision
- **Milestone:** ORION-0.2 released if significantly better

### Month 4: Feedback & Curation
- Collect user interactions from Orbis desktop app
- Red-team evaluation (`redteam.py`)
- Curate hard examples (failures + edge cases)
- Create reinforcement learning dataset
- **Milestone:** GRPO-ready dataset with 500+ labeled examples

### Month 5: Reasoning & Safety Focus
- Train ORION-0.3 with GRPO on reasoning + safety
- Extend to tool-use tasks
- Adversarial robustness evaluation
- **Milestone:** ORION-0.3 with improved reasoning and safety

### Month 6: Long-Context & Factuality
- Integrate long-context evaluation (8K, 16K token limits)
- Add factuality benchmarks
- Baseline vision tasks (if multimodal model adopted)
- **Milestone:** ORION-1.0 release candidate with all domains covered

---

## Part 5: Infrastructure Improvements Needed

### Immediate (Sprint 1)
- [ ] Add GSM8K, MATH, MMLU-Pro, HumanEval+, MBPP+ loaders to `tasks.py`
- [ ] Create `synth_science.py` generator with physics/chemistry/biology
- [ ] Implement domain-specific verifiers (code execution, numerical, symbolic)
- [ ] Add MLflow experiment tracking setup instructions
- [ ] Document run-card format and how to interpret results

### Short-term (Sprint 2–3)
- [ ] Hard-example mining framework (extend `mining.py`)
- [ ] Blind evaluation UI or script (`blind.py` integration)
- [ ] Feedback loop from Orbis → training dataset
- [ ] Regression suite auto-generation from eval results
- [ ] Model checkpointing + resumable training (if interrupted)

### Medium-term (Sprint 4–6)
- [ ] GRPO training pipeline (reward models for reasoning, safety, code)
- [ ] Long-context eval tasks (retrieval, summarization on 8K+ context)
- [ ] Tool-use benchmark (API calling, function composition)
- [ ] Multimodal eval (if vision model integrated)
- [ ] Automated nightly evaluation runs (CI-like system)

---

## Part 6: Success Metrics

### For ORION-0.2 Release
```
Target: All domains at >55% accuracy (from <40% baseline where applicable)

✅ Math (synth-math): >70%  (currently 64%)
✅ Math (GSM8K): >60%       (baseline unknown, ~15-20% likely)
✅ Reasoning (synth-reasoning): >55%
✅ Science (synth-science): >50%
✅ Code (HumanEval+): >30%   (very hard, 8B model)
✅ Regression: No domain drops >2 percentage points from ORION-0.1
```

### For ORION-1.0 Release
```
✅ Math reasoning competitive with Claude-3.5 Sonnet (≥80%)
✅ Science: >70% across domains
✅ Coding: >50% on HumanEval+
✅ Long-context: Maintains performance on 8K tokens
✅ Safety: Red-team resistance to jailbreaks
✅ Factuality: >85% on MMLU-Pro factual subsets
```

---

## Part 7: Usage Instructions

### Running Existing Training

```bash
# Install dependencies
pip install -e .

# View available configs
ls configs/train/
ls configs/data/

# Run SFT training
python src/orion/train/sft.py configs/train/laptop_multimodal_sft.yaml

# Run evaluation
python -m orion.evals.runner \
  --model Qwen3.5-0.8B-Base+checkpoints/orion-0.2/final \
  --tasks synth-math gsm8k-platinum \
  --output runs/eval-orion-0.2/

# Check MLflow results
mlflow ui --backend-store-uri mlruns/
```

### Creating New Training Runs

1. Create data config in `configs/data/` (YAML)
2. Create train config in `configs/train/` (YAML)
3. Run: `python src/orion/train/sft.py configs/train/your_config.yaml`
4. Eval results saved to `runs/evals/` with auto-generated version card
5. Review results, then promote if appropriate

---

## Part 8: Key Principles

1. **No fake training** — every model change comes from actual weight updates via TRL
2. **Measure everything** — version cards record complete provenance
3. **Regression is forbidden** — promotion gate ensures no downgrades
4. **Hard examples drive improvement** — mine failures, curate datasets, retrain
5. **Modular domains** — can improve math without breaking code
6. **Real evaluation** — bootstrap CIs, paired comparisons, human review
7. **Continuous loop** — Orbis usage → feedback → dataset → training → eval → release

---

## Appendix: Current File Locations

**Training:**
- `src/orion/train/sft.py` — Supervised fine-tuning
- `src/orion/train/dpo.py` — Preference optimization
- `src/orion/train/grpo.py` — RL with verifiable rewards
- `src/orion/train/common.py` — Shared utilities

**Evaluation:**
- `src/orion/evals/tasks.py` — Benchmark definitions
- `src/orion/evals/runner.py` — Eval executor
- `src/orion/evals/metrics.py` — Scoring (bootstrap CI, paired comparisons)
- `src/orion/evals/mining.py` — Hard-example identification
- `src/orion/evals/blind.py` — Human preference labeling
- `src/orion/evals/redteam.py` — Adversarial evaluation

**Data:**
- `src/orion/data/pipeline.py` — Data loading and processing
- `src/orion/data/quality.py` — Quality filtering
- `src/orion/data/dedup.py` — Deduplication
- `src/orion/data/contamination.py` — Benchmark contamination check
- `src/orion/data/pii.py` — Personally identifiable info handling

**Synthesis:**
- `src/orion/synth/math.py` — Procedural math generation
- `src/orion/synth/longctx.py` — Long-context task generation

**Verification:**
- `src/orion/verify/math.py` — Math answer verification
- `src/orion/verify/code.py` — Code execution + correctness
- `src/orion/verify/sql.py` — SQL query verification
- `src/orion/verify/toolcall.py` — API/function call validation

**Registry:**
- `registry/versions/ORION-0.0-base.json` — Baseline version card
- `registry/versions/ORION-0.1.json` — Current production model
- `src/orion/registry/versions.py` — Version card and promotion gate

---

**Last updated:** 2026-09-13 | **Status:** Ready for Phase A (Multi-Domain Baseline)

