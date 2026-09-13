"""RL with verifiable rewards via TRL ``GRPOTrainer``.

The reward is a verifier, never a model's opinion: for math, ``verify_math`` on the completion
against the dataset's ``answer`` column (1.0 correct / 0.0 wrong), plus a small format reward for
ending with the ``#### <answer>`` line so the policy learns the answer convention. Dataset rows:
``{"prompt": [{"role": "user", ...}], "answer": "..."}``.

On this laptop rollouts run through ``transformers.generate`` (no vLLM on Windows); it is slow
but real. On Linux GPUs set ``use_vllm: true`` in the config.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from trl import GRPOConfig, GRPOTrainer

from orion.verify.math import extract_final_answer, verify_math

from .common import RunCard, dataset_manifest, load_config, load_model_with_adapter, load_tokenizer, lora_config, project_root, setup_mlflow


def _text(completion) -> str:
    if isinstance(completion, list):  # conversational: [{"role": "assistant", "content": ...}]
        return "".join(m.get("content", "") for m in completion)
    return str(completion)


def reward_correct(completions, answer, **kwargs) -> list[float]:
    return [1.0 if verify_math(_text(c), a).ok else 0.0 for c, a in zip(completions, answer)]


def reward_format(completions, **kwargs) -> list[float]:
    return [0.1 if extract_final_answer(_text(c))[1] == "hash" else 0.0 for c in completions]


def make_grpo_config(cfg: dict[str, Any], output_dir: Path) -> GRPOConfig:
    hp = cfg.get("hyperparameters", {})
    kwargs = dict(
        output_dir=str(output_dir), run_name=cfg.get("run_name"), seed=cfg.get("seed", 0),
        learning_rate=float(hp.get("learning_rate", 1e-6)), lr_scheduler_type=hp.get("lr_scheduler", "constant"),
        per_device_train_batch_size=hp.get("batch_size", 4), gradient_accumulation_steps=hp.get("grad_accum", 1),
        num_generations=hp.get("num_generations", 4), max_completion_length=hp.get("max_completion_length", 256),
        temperature=hp.get("temperature", 1.0),
        beta=hp.get("beta", 0.0), loss_type=hp.get("loss_type", "dapo"), max_steps=hp.get("max_steps", -1),
        num_train_epochs=hp.get("epochs", 1), logging_steps=hp.get("logging_steps", 1), save_steps=hp.get("save_steps", 10),
        save_strategy="steps", save_total_limit=2, use_vllm=cfg.get("use_vllm", False),
        bf16=cfg.get("dtype") in ("bf16", "bfloat16"), use_cpu=cfg.get("device", "auto") == "cpu",
        gradient_checkpointing=cfg.get("gradient_checkpointing", False), report_to=cfg.get("report_to", ["mlflow"]),
        log_completions=True, num_completions_to_print=2,
    )
    # Optional/cosmetic fields differ across TRL releases; keep only those this version defines.
    known = GRPOConfig.__dataclass_fields__
    dropped = sorted(k for k in kwargs if k not in known)
    if dropped:
        print(f"[grpo] ignoring config fields unknown to this TRL version: {dropped}")
    return GRPOConfig(**{k: v for k, v in kwargs.items() if k in known})


def main(config_path: str, resume_from: str | None = None) -> dict[str, Any]:
    from datasets import load_dataset

    cfg = load_config(config_path)
    root = project_root()
    model_dir = root / cfg["model"]
    tok = load_tokenizer(model_dir)
    model = load_model_with_adapter(model_dir, cfg.get("dtype"), cfg.get("gradient_checkpointing", False), cfg.get("adapter"))
    ds = load_dataset("json", data_files={"train": str(root / cfg["train_file"])})["train"]
    if cfg.get("max_train_examples"):
        ds = ds.select(range(min(cfg["max_train_examples"], len(ds))))
    output_dir = root / cfg["output_dir"]
    trainer = GRPOTrainer(model=model, reward_funcs=[reward_correct, reward_format], args=make_grpo_config(cfg, output_dir),
                          train_dataset=ds, processing_class=tok, peft_config=lora_config(cfg["lora"]) if cfg.get("lora") else None)
    # Auto-resume from the latest checkpoint when no final/ exists (see sft.main).
    resumed_from = resume_from
    if resumed_from is None and not (output_dir / "final").exists():
        ckpts = sorted(output_dir.glob("checkpoint-*"),
                       key=lambda p: int(p.name.split("-")[-1]) if p.name.split("-")[-1].isdigit() else -1)
        valid = [c for c in ckpts if (c / "trainer_state.json").exists()]
        if valid:
            resumed_from = str(valid[-1])
            print(f"resuming from {resumed_from}")
    card = RunCard(cfg, "grpo", output_dir)
    card.add(model=cfg["model"], adapter=cfg.get("adapter"), train_examples=len(ds), dataset=dataset_manifest(root / cfg["train_file"]),
             trainable_params=sum(p.numel() for p in trainer.model.parameters() if p.requires_grad),
             rewards=["verify_math correctness (1/0)", "format: ends with '#### <answer>' (+0.1)"])
    run = setup_mlflow(cfg, cfg.get("run_name", output_dir.name))
    result = trainer.train(resume_from_checkpoint=resumed_from)
    history = [h for h in trainer.state.log_history if "reward" in h or "loss" in h]
    trainer.save_model(str(output_dir / "final"))
    tok.save_pretrained(str(output_dir / "final"))
    card.finish(metrics=result.metrics, log_history=history, checkpoint=str(output_dir / "final"), global_step=trainer.state.global_step)
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
