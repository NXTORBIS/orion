"""Shared training utilities: config loading, model/tokenizer loading, run cards, MLflow."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cfg["_config_path"] = str(path)
    return cfg


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project_root(), text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def pick_dtype(name: str | None) -> torch.dtype:
    """fp32 is the only fast dtype on this laptop's CPU (measured); bf16 on GPUs."""
    if name in (None, "auto"):
        return torch.bfloat16 if torch.cuda.is_available() else torch.float32
    return {"fp32": torch.float32, "float32": torch.float32, "bf16": torch.bfloat16, "bfloat16": torch.bfloat16,
            "fp16": torch.float16, "float16": torch.float16}[name]


def hardware_summary() -> dict[str, Any]:
    info: dict[str, Any] = {"platform": platform.platform(), "cpu": platform.processor(), "torch": torch.__version__,
                            "cpu_threads": torch.get_num_threads(), "cuda": torch.cuda.is_available()}
    if torch.cuda.is_available():
        info["gpus"] = [{"name": torch.cuda.get_device_name(i), "vram_gb": round(torch.cuda.get_device_properties(i).total_memory / 1e9, 1)}
                        for i in range(torch.cuda.device_count())]
    return info


def load_tokenizer(model_dir: str | Path):
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_dir)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    return tok


def load_model(model_dir: str | Path, dtype: str | None = None, gradient_checkpointing: bool = False):
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(model_dir, dtype=pick_dtype(dtype))
    if gradient_checkpointing:
        model.gradient_checkpointing_enable()
        model.config.use_cache = False
    return model


def load_model_with_adapter(model_dir: str | Path, dtype: str | None = None, gradient_checkpointing: bool = False,
                            adapter_dir: str | Path | None = None):
    """Load the base model and, if ``adapter_dir`` is set, merge a previously trained LoRA
    adapter into it (``merge_and_unload``) so the next stage (DPO/GRPO) continues from the
    current policy instead of restarting from the base checkpoint. Raises FileNotFoundError
    when the adapter path does not contain an adapter."""
    if adapter_dir:  # fail fast: validate before loading gigabytes of weights
        ap = Path(adapter_dir)
        if not (ap / "adapter_config.json").exists():
            raise FileNotFoundError(f"LoRA adapter not found: {ap}")
    model = load_model(model_dir, dtype, gradient_checkpointing)
    if adapter_dir:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, str(adapter_dir))
        model = model.merge_and_unload()
    return model


def lora_config(cfg: dict[str, Any]):
    from peft import LoraConfig

    return LoraConfig(r=cfg.get("r", 16), lora_alpha=cfg.get("alpha", 32), lora_dropout=cfg.get("dropout", 0.05),
                      target_modules=cfg.get("target_modules", "all-linear"), task_type="CAUSAL_LM",
                      modules_to_save=cfg.get("modules_to_save"))


def dataset_manifest(path: str | Path) -> dict[str, Any] | None:
    """Return the data-pipeline manifest (dataset version hash) that produced a training file, if any."""
    for parent in Path(path).resolve().parents:
        m = parent / "manifest.json"
        if m.exists():
            try:
                d = json.loads(m.read_text(encoding="utf-8"))
                return {"dataset_version": d.get("dataset_version"), "manifest": str(m), "summary": d.get("summary")}
            except json.JSONDecodeError:
                return None
    return None


def setup_mlflow(cfg: dict[str, Any], run_name: str):
    """SQLite-backed MLflow at runs/mlflow.db unless MLFLOW_TRACKING_URI is set. Returns the active run or None."""
    try:
        import mlflow
    except ImportError:
        return None
    runs_dir = project_root() / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    uri = os.environ.get("MLFLOW_TRACKING_URI") or "sqlite:///" + (runs_dir / "mlflow.db").as_posix()
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(cfg.get("experiment", "orion"))
    os.environ.setdefault("MLFLOW_EXPERIMENT_NAME", cfg.get("experiment", "orion"))
    os.environ.setdefault("MLFLOW_TRACKING_URI", uri)
    return mlflow.start_run(run_name=run_name)


class RunCard:
    """Collects everything a version card needs; written as JSON next to the checkpoint."""

    def __init__(self, cfg: dict[str, Any], kind: str, output_dir: Path):
        self.card: dict[str, Any] = {
            "kind": kind, "run_name": cfg.get("run_name"), "config_path": cfg.get("_config_path"), "config": {k: v for k, v in cfg.items() if not k.startswith("_")},
            "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_commit": git_commit(),
            "hardware": hardware_summary(), "output_dir": str(output_dir),
        }
        self.t0 = time.perf_counter()
        self.output_dir = output_dir

    def add(self, **fields: Any) -> None:
        self.card.update(fields)

    def finish(self, **fields: Any) -> dict[str, Any]:
        self.card.update(fields)
        self.card["duration_seconds"] = round(time.perf_counter() - self.t0, 1)
        self.card["finished_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "run_card.json").write_text(json.dumps(self.card, indent=2, default=str), encoding="utf-8")
        return self.card
