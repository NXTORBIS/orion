"""Preference optimisation via TRL ``DPOTrainer`` (``loss_type`` selects DPO / IPO / hinge …;
ORPO lives in ``trl.experimental`` and is pinned separately).

Preference pairs come from *verifier-filtered self-play*: for one prompt, a correct sampled
answer is ``chosen`` and an incorrect one is ``rejected`` (see ``make_verified_pairs``). No
judge model and no closed-model outputs are involved, so the data stays license-clean.
Rows: ``{"prompt": [...messages], "chosen": [{"role": "assistant", ...}], "rejected": [...]}``.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from trl import DPOConfig, DPOTrainer

from .common import RunCard, dataset_manifest, load_config, load_model_with_adapter, load_tokenizer, lora_config, project_root, setup_mlflow


def make_verified_pairs(samples_jsonl: str | Path, out_path: str | Path, max_pairs_per_prompt: int = 1) -> int:
    """samples_jsonl rows: {"id", "prompt": [...], "response", "ok"} (several rows per id)."""
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in Path(samples_jsonl).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            by_id[r["id"]].append(r)
    n = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for rid, rows in by_id.items():
            good = [r for r in rows if r["ok"]]
            bad = [r for r in rows if not r["ok"]]
            for g, b in list(zip(good, bad))[:max_pairs_per_prompt]:
                f.write(json.dumps({"id": rid, "prompt": g["prompt"], "chosen": [{"role": "assistant", "content": g["response"]}],
                                    "rejected": [{"role": "assistant", "content": b["response"]}]}, ensure_ascii=False) + "\n")
                n += 1
    return n


def make_dpo_config(cfg: dict[str, Any], output_dir: Path) -> DPOConfig:
    hp = cfg.get("hyperparameters", {})
    return DPOConfig(
        output_dir=str(output_dir), run_name=cfg.get("run_name"), seed=cfg.get("seed", 0),
        beta=hp.get("beta", 0.1), loss_type=hp.get("loss_type", "sigmoid"), max_length=hp.get("max_length", 1024),
        learning_rate=float(hp.get("learning_rate", 5e-6)), lr_scheduler_type=hp.get("lr_scheduler", "cosine"),
        warmup_steps=hp.get("warmup_steps", 0), per_device_train_batch_size=hp.get("batch_size", 1),
        gradient_accumulation_steps=hp.get("grad_accum", 1), num_train_epochs=hp.get("epochs", 1), max_steps=hp.get("max_steps", -1),
        logging_steps=hp.get("logging_steps", 5), save_strategy="steps", save_steps=hp.get("save_steps", 50), save_total_limit=2,
        bf16=cfg.get("dtype") in ("bf16", "bfloat16"), use_cpu=cfg.get("device", "auto") == "cpu",
        gradient_checkpointing=cfg.get("gradient_checkpointing", False), report_to=cfg.get("report_to", ["mlflow"]),
    )


def main(config_path: str, resume_from: str | None = None) -> dict[str, Any]:
    from datasets import load_dataset

    cfg = load_config(config_path)
    root = project_root()
    model_dir = root / cfg["model"]
    tok = load_tokenizer(model_dir)
    model = load_model_with_adapter(model_dir, cfg.get("dtype"), cfg.get("gradient_checkpointing", False), cfg.get("adapter"))
    ds = load_dataset("json", data_files={"train": str(root / cfg["train_file"])})["train"]
    output_dir = root / cfg["output_dir"]
    trainer = DPOTrainer(model=model, args=make_dpo_config(cfg, output_dir), train_dataset=ds, processing_class=tok,
                         peft_config=lora_config(cfg["lora"]) if cfg.get("lora") else None)
    # Auto-resume from the latest checkpoint when no final/ exists (see sft.main).
    resumed_from = resume_from
    if resumed_from is None and not (output_dir / "final").exists():
        ckpts = sorted(output_dir.glob("checkpoint-*"),
                       key=lambda p: int(p.name.split("-")[-1]) if p.name.split("-")[-1].isdigit() else -1)
        valid = [c for c in ckpts if (c / "trainer_state.json").exists()]
        if valid:
            resumed_from = str(valid[-1])
            print(f"resuming from {resumed_from}")
    card = RunCard(cfg, "dpo", output_dir)
    card.add(model=cfg["model"], adapter=cfg.get("adapter"), train_pairs=len(ds), dataset=dataset_manifest(root / cfg["train_file"]),
             trainable_params=sum(p.numel() for p in trainer.model.parameters() if p.requires_grad))
    run = setup_mlflow(cfg, cfg.get("run_name", output_dir.name))
    result = trainer.train(resume_from_checkpoint=resumed_from)
    trainer.save_model(str(output_dir / "final"))
    tok.save_pretrained(str(output_dir / "final"))
    card.finish(metrics=result.metrics, log_history=[h for h in trainer.state.log_history if "loss" in h],
                checkpoint=str(output_dir / "final"), global_step=trainer.state.global_step)
    if run is not None:
        import mlflow

        mlflow.log_dict(card.card, "run_card.json")
        mlflow.end_run()
    print(json.dumps(result.metrics, indent=2))
    return card.card


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--resume-from", default=None)
    a = ap.parse_args()
    main(a.config, a.resume_from)
