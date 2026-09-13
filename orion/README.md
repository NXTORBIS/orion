# ORION

An AI research system built on open-weight models and run on our own infrastructure: data
pipeline → verifiers → training → evaluation → orchestration/product. The target is
ChatGPT-level performance proven by independent, blind evaluation. **That target has not been
reached**; every report in `docs/` states exactly what was measured and on what.

## Where things are

| Path | What |
|---|---|
| `docs/01_model_selection_report.md` | Phase 1–2: open-model frontier survey (Sept 2026), licenses, gap to ChatGPT, selected models |
| `docs/03_hardware_report.md` | Phase 3: measured hardware limits of this laptop and the hardware real training needs |
| `docs/04_data_training_stack.md` | Phase 4–5 inputs: dataset provenance rules, approved/excluded sources, tool stack |
| `docs/06_experiment_report.md` | Phase 6: the real small-scale training experiment (generated from stored outputs) |
| `registry/licenses/{models,datasets}.yaml` | Every model, dataset and tool: source, license, restrictions, provenance flags |
| `src/orion/data/` | Streaming pipeline: provenance → language → PII → toxicity → heuristics → dedup → quality → classify → contamination → stats |
| `src/orion/verify/` | Verifiers: math (SymPy), code (process sandbox), SQL (SQLite), tool calls (JSON schema) |
| `src/orion/synth/` | Procedural, verifier-checked data: math (12 families), long-context tasks |
| `src/orion/train/` | TRL entry points: SFT (LoRA/full), DPO, GRPO with verifier rewards; run cards; MLflow |
| `src/orion/evals/` | Tasks, batched runner, bootstrap metrics, scorecards, blind comparison, red-team, hard-example mining |
| `src/orion/registry/` | Version cards and the promotion gate (better with CI excluding 0, no category regression) |
| `src/orion/system/` | Backends, tools, hybrid RAG with citations, user-controlled memory, router, response engine, orchestrator |
| `src/orion/api/` | HTTP gateway (OpenAI-style chat, memory and trace endpoints) and the chat page |
| `configs/` | Data profiles, training configs (laptop, single GPU, FSDP2 8-GPU, DeepSpeed ZeRO-3), system profile |
| `scripts/` | `measure_compute.py`, `probe_model.py`, `phase6_experiment.py`, `orion_chat.py`, `slurm_train.sbatch` |
| `tests/` | 48 tests; system logic is tested with scripted backends so tests cost no model compute |

Not in git: `models/` (weights), `data/`, `checkpoints/`, `runs/`, `tools/` (llama.cpp build).

## Running

```bash
.venv/Scripts/python.exe -m pytest -q                                   # tests
.venv/Scripts/python.exe -m orion.data.pipeline configs/data/laptop_v0.yaml
.venv/Scripts/python.exe scripts/phase6_experiment.py --n-train 1200 --n-test 100
.venv/Scripts/python.exe -m orion.train.sft configs/train/laptop_lora_sft.yaml
.venv/Scripts/python.exe -m orion.api.server configs/system/laptop.yaml    # then open http://127.0.0.1:8765
.venv/Scripts/python.exe scripts/orion_chat.py configs/system/laptop.yaml
```

## Rules the code enforces

- **No hosted models.** Backends are local weights (transformers or llama.cpp). Closed models
  are evaluation comparators only and are hard-blocked from training data.
- **Provenance first.** A training record must name its source, license and generator; outputs
  of models whose terms forbid training other models are rejected before any other stage.
- **Verified, not trusted.** Synthetic items are emitted only when generator and independent
  verifier agree; training rewards and eval scores come from verifiers or stored judgements.
- **Numbers carry uncertainty.** Every score has a bootstrap CI; before/after comparisons are
  paired; a candidate replaces the incumbent only through the promotion gate.
- **Honest labels.** Heuristic stages report `method: heuristic`; procedural evals are marked
  "not a standard benchmark"; unmodified third-party weights are never presented as ORION's.

## Status (2026-09-11)

Phases 1–7 built and tested on a laptop with no GPU (see the hardware report). Standard
benchmark files were not downloaded (not approved), so measured results are on ORION's own
verifier-scored sets. GPU/cluster configs are prepared and syntax-checked, not executed.
