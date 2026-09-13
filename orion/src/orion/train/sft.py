"""Supervised fine-tuning (LoRA or full) with TRL ``SFTTrainer``.

Input: a JSONL file of prompt/completion conversations
    {"prompt": [{"role": "user", "content": ...}], "completion": [{"role": "assistant", "content": ...}]}
TRL applies the tokenizer's chat template and, for prompt/completion data, trains on the
completion tokens only. Every run writes ``run_card.json`` (model revision, dataset version,
hyper-parameters, hardware, loss curve, duration) and logs to MLflow.

    .venv/Scripts/python.exe -m orion.train.sft configs/train/laptop_lora_sft.yaml
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from trl import SFTConfig, SFTTrainer

from .common import RunCard, dataset_manifest, load_config, load_model, load_tokenizer, lora_config, project_root, setup_mlflow


def make_sft_config(cfg: dict[str, Any], output_dir: Path, has_eval: bool) -> SFTConfig:
    hp = cfg.get("hyperparameters", {})
    return SFTConfig(
        output_dir=str(output_dir), run_name=cfg.get("run_name"), seed=cfg.get("seed", 0),
        max_length=hp.get("max_length", 1024), packing=hp.get("packing", False),
        learning_rate=float(hp.get("learning_rate", 1e-4)), lr_scheduler_type=hp.get("lr_scheduler", "cosine"),
        warmup_steps=hp.get("warmup_steps", 0), weight_decay=hp.get("weight_decay", 0.0), max_grad_norm=hp.get("max_grad_norm", 1.0),
        per_device_train_batch_size=hp.get("batch_size", 1), gradient_accumulation_steps=hp.get("grad_accum", 1),
        num_train_epochs=hp.get("epochs", 1), max_steps=hp.get("max_steps", -1),
        logging_steps=hp.get("logging_steps", 5), save_strategy="steps", save_steps=hp.get("save_steps", 50), save_total_limit=2,
        eval_strategy="steps" if has_eval else "no", eval_steps=hp.get("eval_steps", 50),
        per_device_eval_batch_size=hp.get("batch_size", 1),
        bf16=cfg.get("dtype") in ("bf16", "bfloat16"), use_cpu=cfg.get("device", "auto") == "cpu",
        gradient_checkpointing=cfg.get("gradient_checkpointing", False), report_to=cfg.get("report_to", ["mlflow"]),
        dataloader_num_workers=0, disable_tqdm=False,
    )


def build_trainer(cfg: dict[str, Any], root: Path):
    from datasets import load_dataset

    model_dir = root / cfg["model"]
    tok = load_tokenizer(model_dir)
    model = load_model(model_dir, cfg.get("dtype"), cfg.get("gradient_checkpointing", False))
    data_files = {"train": str(root / cfg["train_file"])}
    if cfg.get("eval_file"):
        data_files["validation"] = str(root / cfg["eval_file"])
    ds = load_dataset("json", data_files=data_files)
    if cfg.get("max_train_examples"):
        ds["train"] = ds["train"].select(range(min(cfg["max_train_examples"], len(ds["train"]))))
    output_dir = root / cfg["output_dir"]
    args = make_sft_config(cfg, output_dir, "validation" in ds)
    peft_cfg = lora_config(cfg["lora"]) if cfg.get("lora") else None
    trainer = SFTTrainer(model=model, args=args, train_dataset=ds["train"], eval_dataset=ds.get("validation"),
                         processing_class=tok, peft_config=peft_cfg)
    return trainer, tok, ds, output_dir


def main(config_path: str, resume_from: str | None = None) -> dict[str, Any]:
    cfg = load_config(config_path)
    root = project_root()
    trainer, tok, ds, output_dir = build_trainer(cfg, root)
    # Auto-resume: if the run was interrupted (checkpoints exist but no final/),
    # continue from the latest checkpoint so `phase6_experiment.py` can be re-run.
    resumed_from = resume_from
    if resumed_from is None and not (output_dir / "final").exists():
        ckpts = sorted(output_dir.glob("checkpoint-*"),
                       key=lambda p: int(p.name.split("-")[-1]) if p.name.split("-")[-1].isdigit() else -1)
        valid = [c for c in ckpts if (c / "trainer_state.json").exists()]
        if valid:
            resumed_from = str(valid[-1])
            print(f"resuming from {resumed_from}")
    card = RunCard(cfg, "sft", output_dir)
    trainable = sum(p.numel() for p in trainer.model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in trainer.model.parameters())
    rev_file = root / cfg["model"] / "orion_download.json"
    card.add(model=cfg["model"], model_params=total, trainable_params=trainable,
             model_revision=json.loads(rev_file.read_text())["revision"] if rev_file.exists() else None,
             train_examples=len(ds["train"]), eval_examples=len(ds["validation"]) if "validation" in ds else 0,
             dataset=dataset_manifest(root / cfg["train_file"]),
             resumed_from=resumed_from)
    print(f"trainable params: {trainable:,} / {total:,} ({100 * trainable / total:.2f}%)")

    run = setup_mlflow(cfg, cfg.get("run_name", output_dir.name))
    result = trainer.train(resume_from_checkpoint=resumed_from)
    history = [h for h in trainer.state.log_history if "loss" in h or "eval_loss" in h]
    trainer.save_model(str(output_dir / "final"))
    tok.save_pretrained(str(output_dir / "final"))
    metrics = {**result.metrics, "final_train_loss": next((h["loss"] for h in reversed(history) if "loss" in h), None),
               "final_eval_loss": next((h["eval_loss"] for h in reversed(history) if "eval_loss" in h), None)}
    card.finish(metrics=metrics, log_history=history, checkpoint=str(output_dir / "final"), global_step=trainer.state.global_step)
    if run is not None:
        import mlflow

        mlflow.log_dict(card.card, "run_card.json")
        mlflow.end_run()
    print(json.dumps(metrics, indent=2))
    return card.card


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--resume-from", default=None)
    a = ap.parse_args()
    main(a.config, a.resume_from)
