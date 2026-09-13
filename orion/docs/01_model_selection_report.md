# ORION — Phases 1–2: Open-Model Frontier and Model Selection

**Date:** 2026-09-11. **Status:** Phase 1–2 complete. All numbers are a dated snapshot and
must be re-pulled before any training spend or public comparison.

## How this was researched

- **Four parallel research passes:**
  1. Qwen / DeepSeek / Kimi
  2. GLM / MiniMax / other labs
  3. Meta / Mistral / Gemma / gpt-oss / Nemotron
  4. Independent leaderboards and the gap to ChatGPT

  A fifth pass (datasets, training frameworks) feeds Phases 4–5.
- **Specs and licenses** come from primary sources: Hugging Face model cards, `config.json`
  and `LICENSE` files, and vendor tech reports.
- **Capability claims** are cross-referenced across independent evaluators, never one
  ranking site:
  - Artificial Analysis Intelligence Index v4.3 (AA)
  - Epoch Capabilities Index (ECI) and FrontierMath
  - Arena (text / webdev / vision)
  - LiveBench (2026-06-25 question set)
  - Scale SEAL
  - OCRBench v2
- **Decision-critical facts were re-verified directly on 2026-09-11:**
  - Repo existence, license tag, parameter count and base-checkpoint availability for 24
    repos, via the Hugging Face API.
  - The DeepSeek-V4-Flash-Base `LICENSE` text.
  - The text of NSA/CISA/FBI advisory AA26-251A.

**Caveats.**
- Web pages were read through a summarizing fetch tool. Figures that drive decisions were
  re-verified as above; others are cited and should be spot-checked.
- AA rescaled its index on 2026-09-07, so only scores from the same snapshot are comparable.
- Vendor-reported numbers are never compared across vendors.
- This document is not legal advice.

---

## 1. Summary

1. **"ChatGPT" is three different targets.**

   | ChatGPT tier | Model | AA v4.3 |
   |---|---|---|
   | Free / Go | GPT-5.6 Luna | 38 |
   | Plus | GPT-5.6 Sol | 47 |
   | Pro / Business / Enterprise | GPT-6 Astra | 53 (#1 overall, tied with Claude Fable 5.1) |

   The tier mapping comes from press reports, because openai.com blocked automated
   access. Every ORION comparison must name the tier.
2. **Strongest open-weight models on AA v4.3:**

   | Model | AA v4.3 |
   |---|---|
   | GLM-5.3 | 45 |
   | Kimi K3 | 44 |
   | GLM-5.3-Flash | 42 |
   | Qwen3.8-2.4T | 40 |
   | DeepSeek V4.1-Flash | 40 |
   | DeepSeek V4-Pro | 36 |
   | DeepSeek V4-Flash | 35 |
   | Qwen3.8-27B | 34 |
3. **Where the best open models stand on independent evals:**
   - **vs ChatGPT Free (Luna):** ahead on most composites (AA +7, LiveBench +7.5, GDPval +180 Elo). Behind on hard math (FrontierMath tiers 1–3: −9.9).
   - **vs ChatGPT Plus (Sol):** roughly at parity on Arena Text, LiveBench, long-context and real-work evals. Behind on factual accuracy (SimpleQA Verified −19) and hard math (FrontierMath −17).
   - **vs ChatGPT Pro (Astra):** clearly behind (AA −8, ECI −9, Terminal-Bench −17).
4. **None of the top five open models released a base checkpoint.** They are strong
   assistants but poor starting points for continued pretraining. The frontier-class
   base checkpoints that do exist:
   - DeepSeek V4-Flash-Base (292B, MIT)
   - DeepSeek V4-Pro-Base (1.6T, MIT)
   - MiMo-V2.5-Pro-Base (1.02T, MIT)
   - Nemotron 3 Ultra Base (550B, OpenMDW-1.1, largely open data)
   - K2 Horizon 375B (Apache-2.0, open data)
5. **This laptop can run a 27B model but cannot train one.**
   - The strongest model that fits in 32 GB of RAM is Qwen3.8-27B (Apache-2.0, AA 34) at
     4-bit. That is below ChatGPT Free on the AA composite.
   - Real training here is limited to ≤ ~1–2B-parameter models (see
     `03_hardware_report.md`).
   - **Consequence:** a laptop-only ORION cannot honestly be expected to beat ChatGPT
     across the board. The system layer (tools, retrieval, verification) can beat it on
     specific verifiable task types, and that must be measured, not assumed.
6. **Decision:**
   - Approach **A + B**, wrapped in a model-agnostic system layer.
   - Approach **C** only as system-level routing, plus merging adapters of the same base.
   - No weight merging across model families: architectures and tokenizers are
     incompatible.

---

## 2. Candidate models

✔ = license tag, parameter count and base availability verified on the Hugging Face API
(2026-09-11). Everything else is from cited vendor pages.

### A. Frontier-class open weights (AA v4.3 ≥ 30)

| Model | Org | Released | Total / active params, attention | Context | Input | Base ckpt | License | AA |
|---|---|---|---|---|---|---|---|---|
| GLM-5.3 | Z.ai | Aug 2026 | 753B / 40B MoE; DSA sparse | 1M | text | no ✔ | GLM-5.3 License (custom) ✔ | 45 |
| Kimi K3 | Moonshot AI | Jul 2026 | 2.78T / 104B MoE; KDA linear + gated MLA | 1M | text, image | no ✔ (MXFP4 only, 1.56 TB) | Kimi K3 License (custom) ✔ | 44 |
| GLM-5.3-Flash | Z.ai | Aug 2026 | 321B / 18B MoE; linear + DSA | 1M | text, image | no ✔ | MIT ✔ | 42 |
| Qwen3.8-2.4T-A95B | Alibaba | Aug 2026 | 2.4T / 95B MoE; Gated DeltaNet hybrid | 262K / 1M | text | no | Qwen3.8-Max License | 40 |
| DeepSeek V4.1-Flash | DeepSeek | 2026-09-10 | 763B incl. 196B Engram memory / 8–16B active | 1M | text, image | no ✔ | MIT ✔ | 40 |
| DeepSeek V4-Pro-0813 | DeepSeek | Aug 2026 | 1.6T / 49B MoE; CSA + HCA | 1M | text | **yes** | MIT | 36 |
| DeepSeek V4-Flash-0731 | DeepSeek | Jul 2026 | 292B / 13B MoE; CSA + HCA | 1M | text | **yes** ✔ (FP8) | MIT ✔ (LICENSE text read) | 35 |
| Qwen3.8-27B | Alibaba | Aug 2026 | 27.8B dense; Gated DeltaNet hybrid | 262K / 1M | text, image, video | no ✔ | Apache-2.0 ✔ | 34 |
| K2 Horizon 375B-A23B | IFM | Sep 2026 | 375B / 23B MoE | 524K | text | intermediate ckpts | Apache-2.0; data released (some pending) | 31 |
| MiniMax-M3 | MiniMax | Jun 2026 | ~428B / ~23B MoE; sparse | 1M | text, image, video | no | MiniMax Community License | 30 |

### B. Below the frontier, but valuable for size, license or data openness

| Model | Org | Total / active | Base ckpt | License | AA | Why it matters |
|---|---|---|---|---|---|---|
| MiMo-V2.5-Pro | Xiaomi | 1.02T / 42B | yes ✔ | MIT ✔ | 26 | Largest MIT base checkpoint |
| Inkling | Thinking Machines | 975B / 41B | yes (vendor) | Apache-2.0 | 26 | Text + image + audio |
| Nemotron 3 Ultra | NVIDIA | 550B / 55B hybrid Mamba-2 MoE | yes | OpenMDW-1.1 | 23 | Base + major pretraining/post-training data released |
| Qwen3.6-35B-A3B | Alibaba | 36B / 3B | no (3.5 base ✔) | Apache-2.0 ✔ | 19 | Fast CPU/GPU inference (3B active) |
| Muse Glimmer 30B | Meta | 29.8B dense | no | Apache-2.0 ✔ (card adds use terms; legal check) | 18 | Not from a lab named in AA26-251A |
| Gemma 4 31B | Google | 32.7B dense | yes ✔ | Apache-2.0 ✔ | 15 | Apache Gemma; base released |
| Qwen3.5-9B | Alibaba | 9.65B dense | yes ✔ | Apache-2.0 ✔ | 14 | Best single-24GB-GPU base |
| Nemotron 3 Super | NVIDIA | 120B / 12B | yes | Nemotron Open Model License | 14 | Open post-training data |
| gpt-oss-120b | OpenAI | 117B / 5.1B | no | Apache-2.0 (✔ for 20b) | 12 | Fast; MXFP4 |
| Mistral Small 4 | Mistral | 119B / 6.5B | no | Apache-2.0 | 11 | — |
| Llama 4 Maverick | Meta | 400B / 17B | yes | Llama 4 Community License | 9 | Excluded (see §4) |
| Olmo 3 32B | Ai2 | 32.2B dense | yes ✔ | Apache-2.0 ✔ | — | Fully open data; decontamination reference |

### C. Small models (this laptop, or one consumer GPU), all verified on HF

| Model | Params | BF16 weights | License | Loads in transformers 5.17 |
|---|---|---|---|---|
| Qwen/Qwen3.5-0.8B-Base | 0.87B | 1.75 GB | Apache-2.0 | yes, native (`qwen3_5`) |
| Qwen/Qwen3.5-2B-Base | 2.27B | 4.55 GB | Apache-2.0 | yes, native |
| Qwen/Qwen3.5-4B-Base | 4.66B | 9.32 GB | Apache-2.0 | yes, native |
| Qwen/Qwen3.5-9B-Base | 9.65B | 19.31 GB | Apache-2.0 | yes, native |
| IFM/K2-Horizon-0.9B | 1.08B | 2.16 GB | card says `apache-2.0` but also `license_name: internal-only` (inconsistent) | no — needs `trust_remote_code` |
| google/gemma-4-E2B | 5.12B total (2.3B "effective") | 10.25 GB | Apache-2.0 | yes, native (`gemma4`) — too large for CPU LoRA |

---

## 3. Capability comparison: independent evaluators only

"Gap" = best open score minus the ChatGPT model's score (positive = open is ahead).
Dates are snapshot dates.

| Capability | Eval (date) | Best open models | Best closed | Gap vs Luna / Sol / Astra |
|---|---|---|---|---|
| Composite | AA Intelligence Index v4.3 (09-11) | GLM-5.3 45, Kimi K3 44, GLM-5.3-Flash 42 | Astra, Fable 5.1: 53 | +7 / −2 / −8 |
| Composite | Epoch ECI | Kimi K3 158, GLM-5.3 155 | Astra 167 | +2 / −4 / −9 |
| Composite, contamination-resistant | LiveBench global (06-25 set) | V4.1-Flash 81.1, K3 79.2, V4-Pro 77.4 | Fable 5.1 83.4 | +7.5 / 0 / −1.1 |
| Chat preference | Arena Text (09-02) | K3 1489, GLM-5.3 1482, GLM-5.3-Flash 1474 | Fable 5: 1507 | — / +6 (within CI) / not listed |
| Knowledge + reasoning | HLE (AA) | K3 47, GLM-5.3 42 | Fable 5.1 59.1 | — / −2 / — |
| Hard math | FrontierMath tiers 1–3 (Epoch) | K3 72.2, GLM-5.3 68.8 | Astra 93.7 | −9.9 / −16.9 / −21.5 |
| Frontier math | FrontierMath tier 4 (Epoch) | K3 39.0, GLM-5.3 29.3 | Astra 97.6 (Epoch-run unverified) | −22 / −43.9 / −58.6 |
| Math | LiveBench Math | V4-Pro 95.1, V4.1-Flash 93.3 | Fable 5.1 97.0 | — / −1.1 / — (near saturation) |
| Coding | LiveBench Coding | K3 81.4, V4.1-Flash 80.0, GLM-5.2 79.7 | Fable 5.1 86.4 | −1.5 / −2.5 / — |
| Agentic coding | AA Terminal-Bench v4.0 (09-09) | GLM-5.3 42, K3 13 | Astra 59 | — / +2 / −17 |
| Agentic coding | LiveBench Agentic Coding | V4.1-Flash 77.3 (#1 overall), V4-Flash-Vision 65.1 | Fable 5.1 66.1 | — / +21 / — (outlier; needs replication) |
| Web development | Arena WebDev (09-08) | K3 1674, Qwen3.8-Flash-Next 1631 | Astra 1796 | — / +57 / −122 |
| Agents + tools | AA Agentic Index (mirror, 09-10) | GLM-5.3 53.4, K3 50.6, V4-Pro 49.6 | Fable 5.1 58.0 | — / +2.9 / +1.9 |
| Real-world work | GDPval-AA v2 (Elo) | GLM-5.3-Flash 1669, GLM-5.3 1667 | Fable 5.1 1764 | +180 / +45 / +89 |
| Long context | AA-LCR v1.1 | K3 88.7 (#1 overall), GLM-5.3 80 | Fable 5.1 85.3 | — / +4.7 / unverified |
| Instruction following | LiveBench IF | Qwen3.8-Flash-Next 77.1, Nemotron 3 Ultra 73.4, Qwen3.8-27B 72.7 | Gemini 3.8 Flash 81.4 | +17 / +5.3 / +1.5 |
| Vision | Arena Vision (08-27) | GLM-5.3-Flash 1273, Kimi K2.6 1263, Gemma 4 31B 1261 | Fable 5: 1313 | — / −9 (±17) / — |
| Documents / OCR | OCRBench v2 English (2026-06) | Nemotron 3 Nano Omni 65.8, Qwen3.6-35B-A3B 65.5 | Yaochi-DTS 73.4 | GPT-5.6 not listed |
| Factual accuracy | SimpleQA Verified (Epoch) | K3 50.6, GLM-5.3 41.0 | Astra 75.6 | +9.6 / −19.1 / −25 |
| Hallucination rate (lower is better) | AA-Omniscience (mirror, 09-10) | MiniMax-M3 18.4%, GLM-5.3 29.6%, Qwen3.8-27B 30.3% | — | Luna 92.6%, Sol 92.2%, Astra 51.3% |
| Knowledge net of hallucination | AA-Omniscience Index | K3 20, GLM-5.3 14 | Astra (high) 44 | — / −2 / −24 |
| Multilingual | MMLU-ProX (mostly vendor-reported) | Qwen3.5-397B 84.7, GLM-5 83.1 | Qwen3.7 Max 87 | GPT-5.6 not listed — **unverified** |
| Tool calling | BFCL, τ²-bench | stale (no 2026-H2 entries); τ²-Telecom saturated (99.1%) | — | **unverified** |
| Output speed | AA tokens/s | V4.1-Flash 199, gpt-oss-120b 181, Nemotron 3 Ultra 157 | — | Luna 109, Sol 60, Astra ~50 |

**How to read this honestly:**
- **Hallucination:** open models "win" on hallucination *rate* mostly by abstaining. On
  *accuracy* (SimpleQA Verified, Omniscience Index) they lose to Sol and Astra by 19–25 points.
- **Saturated evals don't discriminate between top models:** GPQA-Diamond (90.9–95.8), AIME,
  τ²-Telecom, LiveBench Math.
- **SWE-bench Verified is frozen and contaminated:** no entries since Feb 2026, and OpenAI
  stopped reporting it. ORION will use private, refreshed task sets instead.
- **Vendor vs independent runs differ a lot:** e.g. Kimi K3 claims Terminal-Bench 2.1 88.3;
  AA's Terminal-Bench v4.0 harness measures 13%.

---

## 4. Licensing and provenance

The machine-readable record is `registry/licenses/models.yaml`.
"Open-weight" ≠ "open-source": only K2 Horizon, Olmo 3 and (largely) Nemotron 3 also
release training data.

**Green — permissive, no restriction on using outputs for training:**
- **Apache-2.0:**
  - Alibaba: Qwen3.5, Qwen3.6, Qwen3.8-27B ✔
  - Google: Gemma 4 ✔
  - OpenAI: gpt-oss ✔
  - Meta: Muse Glimmer ✔ (card adds use terms; legal check)
  - Mistral: Small 4, Large 3, Ministral 3
  - Other labs: K2 Horizon, Inkling, Step-3.7-Flash, Hy4-preview, Command A+, Olmo 3 ✔
- **MIT:**
  - DeepSeek V4 / V4.1 ✔ (V4-Flash-Base LICENSE read verbatim). DeepSeek's API terms also
    explicitly allow distillation.
  - GLM-5.3-Flash ✔, GLM-5.2
  - MiMo-V2.5 ✔, LongCat-2.0, Ring-2.6
- **OpenMDW-1.1:** Nemotron 3 Ultra.

**Yellow — permissive, with commercial thresholds or attribution:**
- **GLM-5.3:** Model-as-a-Service providers with more than $10B group revenue need a
  security review.
- **Kimi K3:** MaaS businesses above $20M revenue need a separate agreement. Display the
  name above 100M MAU or $20M monthly revenue. Kimi K2.6 uses a modified MIT license with
  the same display clause.
- **Qwen3.8-2.4T** (Qwen3.8-Max License): MaaS or "AI Work Assistant" businesses above
  $50M revenue need a separate license.
- **MiniMax-M3:** show "Built with MiniMax M3"; one-time notice below $20M revenue, written
  authorization above.
- **NVIDIA Nemotron Open Model License** (Nemotron 3 Super / Nano): attribution notice.

**Red — excluded for ORION:**
- **Qwen3.8-Flash-Next** (Qwen Community License): *any* MaaS or AI-assistant business
  needs a separate license, and ORION is exactly that.
- **Llama 4:** any model built with Llama materials *or outputs* must be named "Llama…",
  plus the AUP, the 700M-MAU cap and the EU multimodal carve-out.
- **Gemma 3 / 3n:** students distilled from them become "Model Derivatives" bound by
  Google's terms. Gemma 4 is fine.
- **Mistral Medium 3.5 / Devstral 2:** no rights above $20M monthly revenue, including for
  derivatives.
- **Mistral Research License, Mistral Non-Production License and CC-BY-NC models:**
  non-commercial; research-licensed outputs are also restricted.
- **MiniMax-M2.7:** commercial use needs written authorization.

**Firewall rules (enforced in the data pipeline):**
1. **Closed models are evaluation comparators only.** ChatGPT, Claude, Gemini and similar
   outputs never enter training data: their providers' terms prohibit using outputs to
   build competing models (re-check the current terms before each release). The pipeline
   tags every example's source and rejects closed-model sources.
2. **Teachers are self-hosted from weights by default.** Hosted APIs have their own terms:
   the Kimi API forbids building competing models, while the DeepSeek API allows
   distillation. An API may only be used as a teacher after its terms are recorded in the
   registry.
3. **Community quantizations and fine-tunes are not trusted by default.** "Abliterated",
   "uncensored" and merged variants are excluded. Quantizations are accepted only from the
   vendor or an established quantizer, with the license re-checked.

**Provenance risk: advisory AA26-251A** (read on 2026-09-08 publication; retrieved 2026-09-11).
- **Title and issuers:** "China-Based Artificial Intelligence Companies Conducting
  Industrial-Scale Distillation Campaigns Against U.S. AI Companies" — NSA, CISA and FBI.
- **Named companies:** DeepSeek, Moonshot AI, Alibaba, MiniMax, StepFun, Z.AI.
- **Status:** informational. It recommends detection and mitigation by AI providers and does
  **not** restrict use of open-weight models.

**Implications for ORION:** a legal and reputational risk to review before any commercial
release, not a technical or legal block. Mitigations:
1. Record the teacher and license on every training example.
2. Keep the pipeline teacher-swappable.
3. Also build an **alternative data profile** using only teachers from labs not named in the
   advisory (NVIDIA Nemotron 3, IFM K2 Horizon, Google Gemma 4, OpenAI gpt-oss, Thinking
   Machines Inkling, Xiaomi MiMo, Meta Muse Glimmer) plus public or human data. Measure
   what the two profiles cost in quality.

---

## 5. Approach A / B / C

### A — Strongest foundation + continued pretraining + post-training
- **Blocker:** the five strongest open models have no base checkpoint. Continued pretraining
  on post-trained weights erodes the vendor's post-training, which was built with far more
  data and compute than we will have.
- **Viable bases:**
  - DeepSeek V4-Flash-Base (292B / 13B, MIT). Its post-trained sibling scores AA 35.
  - V4-Pro-Base (1.6T / 49B).
  - K2 Horizon 375B (Apache-2.0, open data, intermediate checkpoints).
  - Nemotron 3 Ultra Base (open data).
  - MiMo-V2.5-Pro-Base.
- **Cost:** ≥ 64 H100-class GPUs and custom engineering. V4 weights are FP8-only, and the
  CSA/HCA attention and mHC residuals are not supported by LLaMA-Factory or verl.
- **Verdict:** use continued pretraining only for targeted domains or languages, not generic
  knowledge. Most measurable gains will come from post-training on verified data and from
  the system layer.

### B — Teacher ensemble → distillation
- **Verdict:** viable and license-clean, provided teachers are self-hosted and every output
  is verified (Phase 16) before it becomes training data.
- **Candidate teachers by capability** (self-hosted weights):

  | Capability | Primary teachers | Evidence |
  |---|---|---|
  | General reasoning, agents, real-world work | GLM-5.3-Flash (MIT) and GLM-5.3 | AA 42 / 45; Agentic Index 53.4; GDPval 1669. The Flash model is the cheapest frontier-class teacher to serve. |
  | Math, competitive coding | DeepSeek V4.1-Flash (MIT) | LiveBench Coding 80.0, LiveBench Agentic Coding 77.3. For the hardest math, Kimi K3 (FrontierMath tiers 1–3: 72.2). |
  | Long context | Kimi K3 | AA-LCR 88.7, #1 overall. Internal-use license; 1.56 TB of MXFP4 weights makes it expensive to host. |
  | Vision and documents | GLM-5.3-Flash; Qwen3.6-35B-A3B and Nemotron 3 Nano Omni for OCR | Arena Vision; OCRBench v2 |
  | Multilingual | Qwen family | Low confidence: evidence is mostly vendor-reported |
  | Labs not named in AA26-251A | K2 Horizon 375B, Nemotron 3 Ultra, Gemma 4 31B, gpt-oss-120b, Inkling | — |

- **Known ceiling:** students rarely beat their teachers on broad tasks. They can beat them
  on verifiable domains through RL with verifiable rewards and verifier-filtered data.

### C — Mixture, specialists, merging
- **Cross-family weight merging is impossible.** Qwen's Gated DeltaNet, DeepSeek's CSA/HCA
  and GLM's DSA differ in architecture and tokenizer.
- **Merging works only among fine-tunes of one base.** Examples: TIES/DARE merges of several
  Qwen3.8-27B fine-tunes, or LoRA adapter composition. Each merge is accepted only if it
  beats its parents on the regression suite.
- **Sparse upcycling** (dense → MoE) needs pretraining-scale compute. Deferred until GPUs
  are available.
- **System-level routing** among separately served models works across architectures, and
  ORION will do it. It must beat the strongest single model on end-to-end evals, not just
  score high on router accuracy. A single frontier model often beats routing among weaker
  specialists.

### Decision
Build a **model-agnostic system layer** (orchestrator, router, verifier, RAG, memory, tools,
response engine) now. Swap foundations underneath it as hardware allows. Use B (verified
teacher data) for post-training at every stage. Use A only once a cluster is available.

---

## 6. Selected models

### For this laptop (ORION-0.x)

| Role | Model | Why | Size |
|---|---|---|---|
| **Training base, Phase 6 experiment** | `Qwen/Qwen3.5-0.8B-Base` | Apache-2.0. A true base checkpoint. Natively supported in transformers, so no remote code. Same `qwen3_5` architecture as Qwen3.8-27B, so recipes and tokenizer transfer. Fits CPU LoRA and full fine-tuning. | 1.75 GB |
| Stretch training base | `Qwen/Qwen3.5-2B-Base` | Same family; LoRA fits in ~14 GB | 4.55 GB |
| **Local inference model** (orchestrator, candidate judge) | Qwen3.8-27B 4-bit GGUF (`unsloth/Qwen3.8-27B-GGUF`: UD-IQ4_XS 14.25 GB or UD-Q4_K_M 16.46 GB), run with llama.cpp | Strongest Apache-2.0 model that fits in RAM (AA 34) | 14.3–16.5 GB |
| Fast local fallback | Qwen3.6-35B-A3B, 4-bit | 3B active parameters, so several times faster decoding; AA 19 | ~20 GB (est.) |

**Risks, to be measured rather than assumed:**
- Qwen3.5's Gated DeltaNet layers fall back to pure-PyTorch kernels on CPU (no Triton on
  Windows).
- llama.cpp support for this architecture on Windows CPU is implied by the GGUF releases but
  not yet tested.
- A dense 27B decoder on a 15 W laptop CPU will likely manage only a few tokens/s. The real
  number will be recorded.

### For GPU phases (ORION-1.x / 2.x)

| Hardware | Foundation | Purpose |
|---|---|---|
| 1× 80 GB GPU | Qwen3.8-27B (LoRA / QLoRA SFT + GRPO), or `Qwen3.5-35B-A3B-Base` | Post-training on verified teacher data |
| 8× H100/H200 | **GLM-5.3-Flash** (MIT; 321B weights, 162–210 GB at 4-bit) + post-training + system layer | Fastest measurable route past ChatGPT Free, since it already scores AA 42 vs Luna's 38. Must still be proven in ORION's own blind eval. |
| 64+ GPU cluster | **DeepSeek V4-Flash-Base** (MIT), or K2 Horizon 375B for open-data provenance | Continued pretraining + full post-training |

---

## 7. Version plan and promotion gates

Every version card names the underlying weights, their license, and whether ORION modified
them. An unmodified third-party model is never presented as ORION's own model.

| Version | Runs on | Weights | Proves |
|---|---|---|---|
| ORION-0.1 | this laptop | Qwen3.5-0.8B-Base + ORION LoRA | Pipeline works end to end; real before/after numbers on held-out, decontaminated evals |
| ORION-0.5 | this laptop | Qwen3.8-27B (unmodified, Alibaba, Apache-2.0) + ORION system layer | Gain of the system layer over the same model alone; first small blind comparison against ChatGPT Free |
| ORION-1.0 | 1× 80 GB GPU | Qwen3.8-27B + ORION post-training | Post-training gains; target: beat ChatGPT Free on verifiable categories |
| ORION-1.5 | 8× H100/H200 | GLM-5.3-Flash + ORION post-training | Target: beat ChatGPT Free in a broad blind evaluation |
| ORION-2.0 | 64+ GPUs | DeepSeek V4-Flash-Base + continued pretraining + full post-training | Target: at least match ChatGPT Plus |

**Promotion gate:** a candidate replaces the current best only if both hold:
1. Its overall score beats the current best with a 95% bootstrap confidence interval that
   excludes zero.
2. No category regresses beyond its tolerance on the frozen regression suite.

Otherwise it is archived with its results. A better model is never replaced by a worse one.

---

## 8. Re-verify before spending on GPUs
- Test llama.cpp with Qwen3.8-27B on this machine (tokens/s, memory).
- Confirm the training path for FP8-only DeepSeek V4 base weights in a supported framework.
- **Legal review:**
  - Kimi K3, GLM-5.3 and Qwen3.8-Max revenue clauses
  - MiniMax attribution terms
  - Implications of AA26-251A
  - Muse Glimmer model-card terms
  - Share-alike (CC-BY-SA) datasets
- Re-pull AA, Epoch, LiveBench and Arena snapshots immediately before any public claim.

## Sources (primary)
- **Model cards:**
  - Qwen: [Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) · [Qwen3.8-2.4T](https://huggingface.co/Qwen/Qwen3.8-2.4T-A95B) · [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)
  - DeepSeek: [V4.1-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash) · [V4-Pro](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro) · [V4-Flash-Base LICENSE](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-Base/raw/main/LICENSE)
  - Kimi / GLM / MiniMax: [Kimi K3](https://huggingface.co/moonshotai/Kimi-K3) · [GLM-5.3](https://huggingface.co/zai-org/GLM-5.3) · [GLM-5.3-Flash](https://huggingface.co/zai-org/GLM-5.3-Flash) · [MiniMax-M3](https://huggingface.co/MiniMaxAI/MiniMax-M3)
  - Other labs: [K2 Horizon 375B](https://huggingface.co/IFM/K2-Horizon-375B-A23B) · [MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) · [Nemotron 3 Ultra](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16)
  - Western labs: [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4) · [gpt-oss model card](https://arxiv.org/html/2508.10925) · [Muse Glimmer](https://huggingface.co/meta-models/Muse-Glimmer-30B)
- **Licenses and terms:**
  - Model terms: [Gemma Terms](https://ai.google.dev/gemma/terms) · [Llama 4 License](https://developer.meta.com/ai/llama4/license/) · [Mistral Research License](https://mistral.ai/licenses/MRL-0.1.md) · [OpenMDW-1.1](https://openmdw.ai/license/1-1/) · [NVIDIA Nemotron Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/)
  - API terms: [DeepSeek API ToS](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html) · [Kimi API ToS](https://platform.kimi.ai/docs/agreement/modeluse)
- **Independent evaluations:**
  - AA and Arena: [AA open-weights](https://artificialanalysis.ai/models/open-source) · [AA leaderboard](https://artificialanalysis.ai/leaderboards/models) · [AA GPT-6 Astra benchmarks](https://artificialanalysis.ai/articles/benchmarking-gpt-6-astra) · [Arena Text](https://arena.ai/leaderboard/text) · [Arena WebDev](https://arena.ai/leaderboard/code/webdev) · [Arena Vision](https://arena.ai/leaderboard/vision)
  - Epoch and others: [Epoch GPT-6 Astra](https://epoch.ai/models/gpt-6-astra) · [Epoch open/closed gap](https://epoch.ai/data-insights/open-closed-eci-gap) · [LiveBench CSV](https://livebench.ai/table_2026_06_25.csv) · [Scale HLE](https://labs.scale.com/leaderboard/humanitys_last_exam) · [OCRBench v2](https://99franklin.github.io/ocrbench_v2/)
- **Advisory:** [NSA/CISA/FBI AA26-251A](https://www.cisa.gov/news-events/cybersecurity-advisories/aa26-251a)
