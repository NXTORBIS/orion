# ORION — Phase 3: Hardware Report

**Inspected:** 2026-09-11 on the development machine.

- **Inventory** values were read from system queries: CIM `Win32_ComputerSystem`,
  `Win32_Processor`, `Win32_VideoController` and `Win32_PhysicalMemory`, plus
  `Get-PhysicalDisk`, `nvidia-smi`, `nvcc`, `wsl`, `docker`, `pip list` and `uv`.
- **Throughput** was measured with `scripts/measure_compute.py`. The raw result is in
  `docs/measurements/compute_probe_20260911_184253.json`.
- **Capacity limits** are calculations from those measurements, with the assumptions stated.

## Inventory (measured)

| Component | Value |
|---|---|
| Machine | Dell Latitude 5540 laptop, on AC power |
| CPU | Intel Core i7-1355U: 10 cores (2 P + 8 E), 12 threads, 15 W class. AVX2 + AVX-VNNI; no AVX-512 or AMX (per Intel specification). PyTorch uses 10 threads |
| RAM | 31.7 GB total; **2 × 16 GB DDR4-3200**, dual channel (~51 GB/s memory bandwidth). 14.7 GB was free at inspection |
| GPU | Intel Iris Xe (integrated, shares system RAM). `torch.xpu.is_available()` = **False** |
| NVIDIA / CUDA | **None.** `nvidia-smi` and `nvcc` not found; `CUDA_PATH` unset |
| Storage | 1 TB NVMe SSD (Kingston SNV2S); 320.8 GB free on `C:` |
| OS | Windows 11 Pro 10.0.26200 |
| Python | 3.12.14 in `orion/.venv` (uv 0.12.9), torch 2.14.0+cpu |
| Linux tooling | No WSL2, no Docker |
| Distributed | Single node, no accelerators, no NCCL or InfiniBand |

## Throughput (measured)

| Probe | Result |
|---|---|
| fp32 dense matmul, n = 2048 | **313 GFLOP/s** |
| bf16 dense matmul, n = 256 | **0.83 GFLOP/s**, about 377× slower. No native bf16 kernels on this CPU |
| fp32 training step: 4-layer pre-norm SwiGLU decoder (d = 1024, 54.5M params), seq 512, AdamW | 1.15 s/step, 444 tokens/s, **151 GFLOP/s effective** |
| bf16-autocast training step | skipped (bf16 kernels unusable) |

## Measured on the selected base model (Qwen3.5-0.8B-Base, fp32, CPU)

`scripts/probe_model.py`, result in `docs/measurements/model_probe_20260911_210628.json`.

| Probe | Result |
|---|---|
| Class loaded by transformers 5.17 | `Qwen3_5ForCausalLM` (text-only; the vision encoder is not loaded) |
| Parameters loaded | 752.4M (embeddings 254.3M, 24 layers 498.1M) |
| Load time | 4.8 s |
| Greedy generation, 32 new tokens | **6.7 tokens/s** |
| Forward + backward, 512 tokens, all parameters | 21.1 s → **24 tokens/s** |
| Peak process memory during that step | ~10 GB |
| Kernels | Gated DeltaNet and causal-conv1d run on the *reference PyTorch fallback* (`flash-linear-attention` / `causal_conv1d` are CUDA-only), which transformers flags as correct but much slower |

The fallback kernels make the measured rate about half the 43 tokens/s estimated from raw
GFLOP/s. Planning figures for this machine are therefore **~25 tokens/s for training
(~90k tokens/hour) and ~7 tokens/s for generation**. A 100-item evaluation with 150-token
answers takes about 40 minutes, so local evaluation sets are kept small and reported with
confidence intervals.

## What this means

- **This is not a training machine.** With no CUDA there is no FlashAttention, no GPU
  bitsandbytes, no vLLM, SGLang or DeepSpeed-GPU, and no NCCL. The production training and
  inference stack is Linux + NVIDIA and must run elsewhere.
- **fp32 only.** bf16 is unusable here, so every local run uses fp32, and memory estimates
  assume 4 bytes per parameter.
- **The Iris Xe GPU is unusable** for PyTorch (measured).
- **151 GFLOP/s is an optimistic upper figure.** It was measured on a small model that fits
  CPU caches well. Larger models are more memory-bound, and Qwen3.5's Gated DeltaNet layers
  run on pure-PyTorch fallback kernels (no Triton on Windows). Phase 6 measures the actual
  model.
- **Distributed code can still be tested for correctness**, using `torch.distributed` with the
  CPU `gloo` backend (2+ processes). This validates launch scripts and sharding logic, not
  performance.

## Memory ceiling (calculated)

Usable RAM for one training process is about 14 GB with the current background load, or about
24 GB with other applications closed.

Rules of thumb:
- **Full fine-tune** (AdamW, fp32): ~16 bytes/param (weights 4 + grads 4 + Adam moments 8),
  plus activations.
- **LoRA with a frozen fp32 base:** ~4 bytes/param + adapter state (<1% of params) +
  activations. Gradient checkpointing is on; a ~150k-vocab logits tensor alone is ~0.6 GB at
  1k tokens.
- **4-bit inference** (GGUF Q4-class): ~0.55–0.65 bytes/param + KV cache.

| Mode | ~14 GB usable | ~24 GB usable |
|---|---|---|
| Full fine-tune (AdamW, fp32) | ≤ ~0.6B params | ≤ ~1B params (batch 1) |
| LoRA, fp32 frozen base, seq ≤ 1–2k | ≤ ~1.5B params | ≤ ~3B params |
| 4-bit inference | ≤ ~14B dense | ≤ ~30B (e.g. a 30B-A3B MoE) |

## Training speed on this laptop (from the measured 151 GFLOP/s)

Cost per token is about **6N** FLOPs for full fine-tuning and about **4N** for LoRA (no
weight gradients for the frozen base). Attention's sequence-length term is ignored.

| Run | FLOPs / token | tokens / s | tokens / hour |
|---|---|---|---|
| Full fine-tune, 135M model | 8.1e8 | ~186 | ~0.67M |
| LoRA, Qwen3.5-0.8B-Base (0.87B) | 3.5e9 | ~43 | ~155k |
| LoRA, 1.5B model | 6.0e9 | ~25 | ~90k |
| LoRA, Qwen3.5-2B-Base (2.27B) | 9.1e9 | ~17 | ~60k |
| From-scratch pretraining, 20M model | 1.2e8 | ~1,260 | ~4.5M |

A compute-optimal (~20 tokens/param) 20M-parameter pretraining run needs about 400M tokens,
which is roughly 88 hours here. From-scratch pretraining on this machine is useful only to
validate the code path.

## Local inference speed limit (calculated, then measured)

When generating, each new token has to read the weights from RAM, so memory bandwidth sets the
ceiling. At 51.2 GB/s:

| Model | Weights read per token | Theoretical maximum |
|---|---|---|
| 4-bit dense 14B (~9 GB) | all weights | ≤ ~5.7 tokens/s |
| 4-bit dense 27B (~14–16 GB) | all weights | ≤ ~3.2–3.6 tokens/s |
| 4-bit 3B-active MoE (~2 GB active) | active experts only | ≤ ~25 tokens/s |

**Measured** with llama.cpp b10909 (`llama-bench`, CPU backend `alderlake`, 10 threads) on the
downloaded `Qwen/Qwen3-14B-GGUF` Q4_K_M (8.38 GiB, 14.77B params):

| Test | Result |
|---|---|
| Prompt processing, 128 tokens (pp128) | **8.58 ± 0.20 tokens/s** |
| Generation, 32 tokens (tg32) | **3.19 ± 0.01 tokens/s** |

So a 14B model is usable here for batch evaluation and orchestration experiments (a 300-token
answer takes ~100 s) but not for interactive use; a 27B model would be roughly half that.

## What this laptop can realistically do

- LoRA SFT / DPO on an open model of up to about 1.5B parameters, with roughly 0.1–0.5M
  training tokens per run.
- A few-dozen-step GRPO run with a verifiable reward (math answer check or unit tests) on a
  ≤ 0.9B model. It will be slow, because RL time is dominated by generation.
- Tiny from-scratch pretraining (10–30M params) to validate the pretraining pipeline.
- Running a 4-bit 27B model for evaluation and orchestration experiments, at a few tokens/s.
- Testing the distributed launch configuration with multiple CPU processes over `gloo`.

## What it cannot do

- Continued pretraining of any frontier-class model.
- Full fine-tuning above about 1B parameters.
- Serving large MoE teacher models fast enough for synthetic-data generation.
- Long-context training (above about 32k tokens), or vision-model training beyond toy scale.

## Hardware required for the real phases (estimates)

**Assumptions:**
- H100-80GB-class GPUs, BF16.
- About 3e14 effective FLOP/s per GPU (≈ 35–40% MFU on dense models; MoE is usually lower).
- Figures cover a single successful run. Real projects need 2–3× that for data generation,
  evaluation, ablations and failed runs.
- Recompute with exact parameter counts before spending money. See `01_model_selection_report.md`.

| Stage | Model class | Compute / memory | Minimum practical hardware |
|---|---|---|---|
| Dev LoRA / QLoRA SFT, DPO, small GRPO | 7–27B dense, or 30B-A3B MoE at 4-bit | — | 1× 24–80 GB GPU |
| Full SFT | 30B-A3B MoE | ~480 GB optimizer state + activations | 8× H100 (FSDP / ZeRO-3), Linux |
| Continued pretraining, 100B tokens | 30B-A3B MoE | 6 × 3e9 × 1e11 = 1.8e21 FLOPs ≈ 1,700 GPU-h | 8× H100 ≈ 9 days, or 16× ≈ 4.5 days |
| Continued pretraining, 100B tokens | DeepSeek V4-Flash-Base (292B / 13B) | 6 × 1.3e10 × 1e11 = 7.8e21 FLOPs ≈ 7,200 GPU-h | 64× H100/H200 ≈ 5 days, plus expert parallelism |
| LoRA post-training + serving | GLM-5.3-Flash (321B / 18B) | ~330 GB BF16 weights (162–210 GB at 4-bit) | 8× H100/H200 |
| Full post-training | ~1T-class MoE | ~16 TB optimizer state | ≥ 256 H100/H200-class GPUs, or LoRA only |
| RL with verifiable rewards at useful scale | 30B-A3B MoE | dominated by rollout generation | 8× H100 (vLLM/SGLang rollouts + FSDP trainer) |
| Serving | 27B dense, FP8 / INT4 | ~28 GB / ~16 GB | 1× 48 GB GPU, or 1× 24 GB at INT4 |

## Plan under these constraints (project brief §28)

1. Build the complete pipeline: data → verification → training → evaluation → registry.
2. Run a real small-scale training experiment on this machine and record the measured numbers.
3. Validate the whole loop end to end, including the "keep only if better" promotion rule.
4. Ship distributed configurations (FSDP2 / DeepSpeed / expert-parallel, Linux cluster). They
   are syntax- and dry-run-checked here, but not executed at scale.
5. State the hardware required (this document).
