"""Phase 14 data builders: GRPO prompts and DPO self-play samples.

GRPO prompts are pure synthesis (no model compute) and can be built at any time::

    .venv/Scripts/python.exe scripts/build_phase14_data.py --only grpo-prompts --n-prompts 64

DPO sampling needs a trained policy (base model + ``final/`` adapter) and runs on CPU at
~7 tokens/s, so it is a separate, slower step::

    .venv/Scripts/python.exe scripts/build_phase14_data.py --only dpo-samples --n-prompts 64 --k 3
    .venv/Scripts/python.exe scripts/build_phase14_data.py --only dpo-pairs

Fresh seed ranges keep Phase-14 prompts disjoint from the SFT train/test split, and any
problem whose text already occurs in ``data/raw/synth_math`` is dropped.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orion.synth.math import INSTRUCTION, generate  # noqa: E402
from orion.verify.math import verify_math  # noqa: E402

RAW = ROOT / "data/raw/synth_math"
PROC = ROOT / "data/processed/synth_math_v1"
GRPO_PROMPTS = PROC / "grpo_prompts.jsonl"
DPO_SAMPLES = PROC / "dpo_samples.jsonl"
DPO_PAIRS = PROC / "dpo_pairs.jsonl"


def known_problems() -> set[str]:
    known: set[str] = set()
    for name in ("train.jsonl", "test.jsonl"):
        p = RAW / name
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        known.add(json.loads(line)["problem"])
                    except (KeyError, json.JSONDecodeError):
                        continue
    return known


def build_grpo_prompts(n_prompts: int = 64, seed_start: int = 2_000_000,
                       out: Path = GRPO_PROMPTS, append: bool = False) -> dict:
    seen = known_problems()
    existing: list[dict] = []
    if append and out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                existing.append(r)
                seen.add(r["prompt"][0]["content"].split("\n")[0])
        seed_start = 2_000_000 + len(existing) * 1000
    rows = list(existing)
    dropped, rejected_total, seed, attempts = 0, {}, seed_start, 0
    while len(rows) < n_prompts and attempts < 20:
        items, rejected = generate(n_prompts, seed)
        for k, v in rejected.items():
            rejected_total[k] = rejected_total.get(k, 0) + v
        for it in items:
            if it.problem in seen:
                dropped += 1
                continue
            rows.append({"id": it.id, "family": it.family, "level": it.level,
                         "prompt": [{"role": "user", "content": f"{it.problem}\n{INSTRUCTION}"}],
                         "answer": it.answer})
            if len(rows) >= n_prompts:
                break
        seed += 10_000_000
        attempts += 1
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    report = {"n_prompts": len(rows), "seed_start": seed_start, "overlap_dropped": dropped,
              "rejected_by_verifier": rejected_total, "families": dict(Counter(r["family"] for r in rows)),
              "out": str(out)}
    if len(rows) < n_prompts:
        report["warning"] = "problem space exhausted for some families (e.g. dice has ~28 distinct problems)"
    print(json.dumps(report, indent=2))
    return report


def sample_dpo_samples(model_dir: str | Path, adapter_dir: str | Path | None = None, n_prompts: int = 64,
                       k: int = 3, seed_start: int = 3_000_000, max_new_tokens: int = 128,
                       temperature: float = 0.8, batch_size: int = 1, max_new: int | None = None,
                       remix_unanimous: bool = False,
                       prompts_file: Path = GRPO_PROMPTS, out: Path = DPO_SAMPLES) -> dict:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not prompts_file.exists():
        build_grpo_prompts(max(n_prompts, 64))
    prompts = [json.loads(l) for l in prompts_file.read_text(encoding="utf-8").splitlines() if l.strip()][:n_prompts]
    # Crash-safe resume: rows are appended per prompt, so a killed run keeps its work.
    done_ids: set[str] = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    done_ids.add(json.loads(line)["id"])
                except (KeyError, json.JSONDecodeError):
                    continue
    todo = [p for p in prompts if p["id"] not in done_ids]
    if remix_unanimous and out.exists():  # resample all-wrong prompts (all-correct ones cannot form pairs)
        from collections import defaultdict
        verdicts: dict[str, set[bool]] = defaultdict(set)
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    r = json.loads(line)
                    verdicts[r["id"]].add(bool(r["ok"]))
                except (KeyError, json.JSONDecodeError):
                    continue
        hopeless = {i for i, v in verdicts.items() if v == {False}}
        if hopeless:
            print(f"remixing {len(hopeless)} all-wrong prompts at temperature {temperature}")
            todo = [p for p in prompts if p["id"] in hopeless]
            done_ids -= hopeless
    if max_new is not None:
        todo = todo[:max_new]
    est_tokens = len(todo) * k * max_new_tokens
    print(f"sampling {len(todo)} prompts x {k} = {len(todo) * k} completions "
          f"(~{est_tokens} tokens, roughly {est_tokens / 7 / 60:.0f} min on this laptop CPU; "
          f"resuming, {len(done_ids)} prompts already done)")

    tok = AutoTokenizer.from_pretrained(model_dir, padding_side="left")
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(model_dir, dtype=torch.float32)
    if adapter_dir:
        model = PeftModel.from_pretrained(model, str(adapter_dir))
    model = model.eval()
    stop = {tok.eos_token_id}
    for t in ("<|im_end|>", "<|endoftext|>"):
        tid = tok.convert_tokens_to_ids(t)
        if isinstance(tid, int) and tid >= 0:
            stop.add(tid)

    out.parent.mkdir(parents=True, exist_ok=True)
    n_ok = n_bad = n_err = 0
    t0 = time.perf_counter()
    for start in range(0, len(todo), batch_size):
        chunk = todo[start:start + batch_size]
        texts = [tok.apply_chat_template(p["prompt"], tokenize=False, add_generation_prompt=True) for p in chunk]
        enc = tok(texts, return_tensors="pt", padding=True)
        rows = []
        try:
            # One sequence per forward: keeps peak memory (logits over the 150k vocab in
            # fp32) small instead of batching k return-sequences at once (which OOM-killed
            # an earlier run with no traceback).
            with torch.no_grad():
                for j, p in enumerate(chunk):
                    for _ in range(k):
                        gen = model.generate(enc["input_ids"][j:j + 1], attention_mask=enc["attention_mask"][j:j + 1],
                                             max_new_tokens=max_new_tokens, do_sample=True,
                                             temperature=temperature, top_p=0.95,
                                             eos_token_id=sorted(stop), pad_token_id=tok.pad_token_id)
                        resp = tok.decode(gen[0, enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()
                        ok = verify_math(resp, p["answer"]).ok
                        rows.append({"id": p["id"], "prompt": p["prompt"], "response": resp,
                                     "gold": p["answer"], "ok": ok})
                        n_ok += ok
                        n_bad += (not ok)
        except Exception as e:  # a bad prompt must not kill a 70-minute run
            n_err += 1
            rows.append({"id": chunk[0]["id"], "prompt": chunk[0]["prompt"], "response": "",
                         "gold": chunk[0].get("answer", ""), "ok": False, "error": f"{type(e).__name__}: {e}"})
        with open(out, "a", encoding="utf-8") as f:  # append per batch: progress survives kills
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        done = len(done_ids) + min(start + batch_size, len(todo))
        print(f"  sampled {done}/{len(done_ids) + len(todo)} prompts "
              f"({(time.perf_counter() - t0) / 60:.1f} min, ok={n_ok}, bad={n_bad}, err={n_err})", flush=True)
    report = {"prompts": len(done_ids) + len(todo), "k": k, "ok": n_ok, "bad": n_bad, "errors": n_err,
              "minutes": round((time.perf_counter() - t0) / 60, 1), "out": str(out)}
    print(json.dumps(report, indent=2))
    return report


def build_dpo_pairs(samples: Path = DPO_SAMPLES, out: Path = DPO_PAIRS) -> dict:
    from orion.train.dpo import make_verified_pairs

    n = make_verified_pairs(samples, out)
    report = {"pairs": n, "out": str(out)}
    print(json.dumps(report, indent=2))
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["grpo-prompts", "dpo-samples", "dpo-pairs", "all"],
                    default="grpo-prompts")
    ap.add_argument("--n-prompts", type=int, default=64)
    ap.add_argument("--append", action="store_true", help="grow the prompts file instead of rewriting")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--remix-unanimous", action="store_true")
    ap.add_argument("--max-new", type=int, default=None,
                    help="cap NEW prompts this invocation (chunked foreground runs; resume-safe)")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--max-new-tokens", type=int, default=128)
    ap.add_argument("--model", default="models/Qwen3.5-0.8B-Base")
    ap.add_argument("--adapter", default="checkpoints/orion-0.1-synthmath-lora/final")
    a = ap.parse_args()
    steps = ["grpo-prompts", "dpo-samples", "dpo-pairs"] if a.only == "all" else [a.only]
    for s in steps:
        print(f"\n===== {s} =====")
        if s == "grpo-prompts":
            build_grpo_prompts(a.n_prompts, out=GRPO_PROMPTS, append=a.append)
        elif s == "dpo-samples":
            sample_dpo_samples(ROOT / a.model, ROOT / a.adapter if (ROOT / a.adapter).exists() else None,
                               a.n_prompts, a.k, max_new_tokens=a.max_new_tokens, max_new=a.max_new,
                               temperature=a.temperature, remix_unanimous=a.remix_unanimous)
        elif s == "dpo-pairs":
            build_dpo_pairs()


if __name__ == "__main__":
    main()
