import json
from pathlib import Path

import numpy as np
import torch
import yaml

from orion.evals.metrics import bootstrap_ci, by_group, paired_bootstrap_diff, summarize
from orion.evals.report import scorecard
from orion.evals.tasks import SynthMathTask
from orion.synth.math import INSTRUCTION, generate, write_jsonl
from orion.train.common import load_config, lora_config, pick_dtype
from orion.train.sft import make_sft_config

ROOT = Path(__file__).resolve().parents[1]


def test_metrics_and_paired_comparison():
    rng = np.random.default_rng(1)
    before = list(rng.random(200) < 0.3)
    after = [b or (rng.random() < 0.4) for b in before]
    lo, hi = bootstrap_ci(before)
    assert lo < 0.3 < hi and hi - lo < 0.2
    cmp = paired_bootstrap_diff(before, after)
    assert cmp["diff"] > 0 and cmp["significant"] and cmp["losses"] == 0 and cmp["n"] == 200
    same = paired_bootstrap_diff(before, before)
    assert same["diff"] == 0 and not same["significant"]
    groups = by_group(["a"] * 100 + ["b"] * 100, before)
    assert set(groups) == {"a", "b"} and groups["a"]["n"] == 100
    s = summarize(before, {"family": ["x"] * 200})
    assert s["n"] == 200 and "by_family" in s


def test_scorecard_renders_from_summaries():
    s = {"model": "m", "task": "synth-math", "standard_benchmark": False, "n": 10, "accuracy": 0.5, "ci": (0.2, 0.8),
         "no_answer_extracted": 1, "items_per_minute": 3.0}
    md = scorecard([s], {"diff": 0.2, "ci": (0.05, 0.35), "significant": True, "wins": 3, "losses": 1, "ties": 6, "n": 10})
    assert "not a standard benchmark" in md and "improvement" in md and "+20.0 points" in md


def test_synth_math_task_scores_with_verifier(tmp_path):
    items, _ = generate(6, 5_000_000)
    write_jsonl(items, tmp_path / "test.jsonl")
    task = SynthMathTask(tmp_path / "test.jsonl")
    evs = task.items()
    assert len(evs) == 6 and evs[0].messages[0]["content"].endswith(INSTRUCTION)
    assert task.score(evs[0], items[0].solution).ok
    assert not task.score(evs[0], "I do not know.\n#### 123456789").ok


def test_train_configs_parse_and_build_args(tmp_path):
    from orion.train.dpo import make_dpo_config
    from orion.train.grpo import make_grpo_config

    acc = yaml.safe_load((ROOT / "configs/train/accelerate_fsdp2_8gpu.yaml").read_text(encoding="utf-8"))
    assert acc["distributed_type"] == "FSDP" and acc["fsdp_config"]["fsdp_version"] == 2
    seen = 0
    for cfg_path in sorted((ROOT / "configs/train").glob("*.yaml")):
        if cfg_path.name.startswith("accelerate"):
            continue
        cfg = load_config(cfg_path)
        assert lora_config(cfg["lora"]).r == cfg["lora"]["r"]
        if cfg.get("dtype") in ("bf16", "bfloat16") and not torch.cuda.is_available():
            continue  # GPU-only config: TrainingArguments validates bf16 against the real hardware
        out = tmp_path / cfg_path.stem
        if cfg_path.name.endswith("_sft.yaml"):
            args = make_sft_config(cfg, out, has_eval=bool(cfg.get("eval_file")))
            assert args.max_length == cfg["hyperparameters"]["max_length"]
        elif "grpo" in cfg_path.name:
            args = make_grpo_config(cfg, out)
            assert args.num_generations == cfg["hyperparameters"]["num_generations"]
        elif "dpo" in cfg_path.name:
            args = make_dpo_config(cfg, out)
            assert args.beta == cfg["hyperparameters"]["beta"]
        else:
            raise AssertionError(f"unrecognised training config {cfg_path.name}")
        assert args.use_cpu == (cfg.get("device") == "cpu")
        seen += 1
    assert seen >= 4
    ds = json.loads((ROOT / "configs/train/deepspeed_zero3.json").read_text(encoding="utf-8"))
    assert ds["zero_optimization"]["stage"] == 3
    assert pick_dtype("fp32").is_floating_point and str(pick_dtype("bf16")) == "torch.bfloat16"
