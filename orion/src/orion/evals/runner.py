"""Generators and task runs.

``HFGenerator`` runs a local transformers model (optionally with a LoRA adapter) with batched
greedy decoding, left padding, and early stop on end-of-turn. ``run_task`` writes one JSONL
line per item (prompt, raw response, extracted answer, gold, verdict) so every number in a
report can be traced back to a stored model output.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch

from .metrics import summarize


class HFGenerator:
    def __init__(self, model_dir: str | Path, adapter_dir: str | Path | None = None, dtype: torch.dtype = torch.float32,
                 batch_size: int = 8, max_new_tokens: int = 256):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.tok = AutoTokenizer.from_pretrained(model_dir, padding_side="left")
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        model = AutoModelForCausalLM.from_pretrained(model_dir, dtype=dtype)
        if adapter_dir:
            from peft import PeftModel

            model = PeftModel.from_pretrained(model, adapter_dir)
        self.model = model.eval()
        self.batch_size, self.max_new_tokens = batch_size, max_new_tokens
        self.name = f"{Path(model_dir).name}" + (f"+{Path(adapter_dir).name}" if adapter_dir else "")
        stop = {self.tok.eos_token_id}
        for t in ("<|im_end|>", "<|endoftext|>"):
            tid = self.tok.convert_tokens_to_ids(t)
            if isinstance(tid, int) and tid >= 0:
                stop.add(tid)
        self.stop_ids = sorted(stop)

    def render(self, messages: list[dict[str, str]]) -> str:
        return self.tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    @torch.no_grad()
    def generate(self, prompts: list[list[dict[str, str]]]) -> list[str]:
        texts = [self.render(m) for m in prompts]
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))  # length-sorted batches waste less padding
        outputs: list[str] = [""] * len(texts)
        for start in range(0, len(order), self.batch_size):
            idx = order[start : start + self.batch_size]
            enc = self.tok([texts[i] for i in idx], return_tensors="pt", padding=True)
            gen = self.model.generate(**enc, max_new_tokens=self.max_new_tokens, do_sample=False,
                                      eos_token_id=self.stop_ids, pad_token_id=self.tok.pad_token_id)
            new = gen[:, enc["input_ids"].shape[1]:]
            for i, row in zip(idx, new):
                outputs[i] = self.tok.decode(row, skip_special_tokens=True).strip()
        return outputs


def run_task(task, generator, out_path: str | Path, limit: int | None = None) -> dict[str, Any]:
    items = task.items()[:limit] if limit else task.items()
    t0 = time.perf_counter()
    responses = generator.generate([it.messages for it in items])
    seconds = time.perf_counter() - t0
    flags, rows = [], []
    for it, resp in zip(items, responses):
        s = task.score(it, resp)
        flags.append(s.ok)
        rows.append({"id": it.id, "group": it.group, "level": it.level, "prompt": it.messages, "response": resp,
                     "extracted": s.extracted, "gold": it.gold, "ok": s.ok, **s.details})
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = summarize(flags, {"group": [it.group for it in items], "level": [str(it.level) for it in items]})
    summary.update(task=task.name, standard_benchmark=getattr(task, "standard_benchmark", False), model=generator.name,
                   seconds=round(seconds, 1), items_per_minute=round(60 * len(items) / max(seconds, 1e-9), 2),
                   outputs=str(out), timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   no_answer_extracted=sum(1 for r in rows if r["extracted"] is None))
    out.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
