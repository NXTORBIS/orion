# ORION — Execution Roadmap (all 20 phases)

**Date:** 2026-09-12. **Machine:** Dell Latitude 5540, CPU-only (see `docs/03_hardware_report.md`).
**Rule:** a phase is DONE only with stored evidence; anything else is marked exactly as it is.

## Status

| Phase | State | Evidence |
|---|---|---|
| 1 Research open-model frontier | DONE | `docs/01_model_selection_report.md` |
| 2 Select foundations | DONE | Qwen3.5-0.8B-Base (laptop) / Qwen3.8-27B / GLM-5.3-Flash / DeepSeek V4-Flash-Base |
| 3 Hardware check | DONE | `docs/03_hardware_report.md` + `docs/measurements/` |
| 4 Dataset infrastructure | DONE | `src/orion/data/` (12 stages), `registry/licenses/datasets.yaml` |
| 5 Training pipeline | DONE | `src/orion/train/` (SFT/DPO/GRPO), tiered configs, `slurm_train.sbatch` |
| 6 Small real training experiment | RUNNING | SFT 120/120 (loss 0.0246); trained eval + `docs/06_experiment_report.md` pending |
| 7 Evaluation infrastructure | DONE | bootstrap CIs, paired diffs, blind comparison, red-team, mining, 53 tests green |
| 8 Large-scale continued pretraining | BLOCKED — needs 8–64× H100 (config ready, not executed) | — |
| 9–11 Reasoning / coding / agent training | QUEUED after Phase 6 | DPO pairs → `laptop_dpo_math.yaml` (30 steps) → GRPO wiring (4 steps) |
| 12 RAG + memory | BUILT, unmeasured | `src/orion/system/{rag,memory}.py`; measure vs trained policy |
| 13 Multimodal | BLOCKED — needs vision base + GPU (stub only, by design) | — |
| 14 Preference + RL (laptop scale) | QUEUED | `scripts/build_phase14_data.py`, 64 GRPO prompts built |
| 15–19 Benchmarks, mining, retrain loop | QUEUED | harness ready; iteration 1 starts from Phase-6 evals |
| 20 Deploy strongest verified model | QUEUED | only through the promotion gate (`registry/versions.py`) |

## Laptop execution queue (sequential — the CPU is the bottleneck)

1. Phase-6 trained eval (~22 min) → report → sync `trained.*`, `06_experiment_report.md`.
2. Promotion gate: paired bootstrap trained-vs-baseline (baseline 39% [30, 49]).
3. DPO sampling: 64 prompts × 3, ~160 tokens (~1.5–2 h) → `dpo_pairs.jsonl`.
4. DPO train, 30 steps (~45 min) → eval → gate.
5. GRPO wiring, 4 steps (~30 min) → proves verifier-reward RL loop.
6. Hard-example mining from stored evals → round-2 data (now 15 math families).
7. Red-team + blind re-runs behind the trained policy.

## Deliberately NOT claimed

- ChatGPT parity: the 0.8B laptop line cannot reach it; the GPU path (1×80GB → 8×H100)
  is specified in `docs/01_model_selection_report.md` §6–7 and stays unexecuted until hardware exists.
- Multimodal ability: stub only. No scores are reported for it.
- Standard benchmarks: not downloaded (not approved); all numbers are on ORION's own
  verifier-scored sets with CIs, labelled as such.
