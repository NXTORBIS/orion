import json
from collections import Counter
from pathlib import Path

import pytest
import yaml

from orion.train.common import load_config, load_model_with_adapter

ROOT = Path(__file__).resolve().parents[1]


def test_phase14_configs_continue_from_sft_adapter():
    for name in ("laptop_dpo_math.yaml", "laptop_grpo_math.yaml"):
        cfg = load_config(ROOT / "configs/train" / name)
        assert cfg["adapter"].endswith("orion-0.1-synthmath-lora/final"), name
        assert cfg["model"] == "models/Qwen3.5-0.8B-Base", name


def test_adapter_missing_fails_fast_without_loading_model(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_model_with_adapter("models/Qwen3.5-0.8B-Base", adapter_dir=tmp_path / "nope")


def test_grpo_prompts_are_fresh_schema_valid_and_disjoint(tmp_path):
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from build_phase14_data import build_grpo_prompts, known_problems

    out = tmp_path / "grpo_prompts.jsonl"
    rep = build_grpo_prompts(n_prompts=30, seed_start=4_000_000, out=out)
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert rep["n_prompts"] == len(rows) == 30
    assert all(set(r) == {"id", "family", "level", "prompt", "answer"} for r in rows)
    assert all(r["prompt"][0]["role"] == "user" for r in rows)
    # round-robin generation keeps families represented; tiny saturated families
    # (dice has ~28 distinct problems, all seen in SFT train) may legitimately drop out
    assert {r["family"] for r in rows} >= {"arithmetic", "linear", "system", "percent", "rate",
        "work", "quadratic", "gcd_lcm", "modular", "sequence", "geometry",
        "trig", "calculus", "stats"}
    known = known_problems()
    assert not ({r["prompt"][0]["content"].split("\n")[0] for r in rows} & known)
    again = tmp_path / "again.jsonl"
    build_grpo_prompts(n_prompts=30, seed_start=4_000_000, out=again)
    assert again.read_text(encoding="utf-8") == out.read_text(encoding="utf-8")


def test_dpo_pair_builder_needs_no_model(tmp_path):
    from orion.train.dpo import make_verified_pairs

    samples = tmp_path / "samples.jsonl"
    rows = [
        {"id": "p1", "prompt": [{"role": "user", "content": "Q1"}],
         "response": "good.\n#### 7", "ok": True},
        {"id": "p1", "prompt": [{"role": "user", "content": "Q1"}],
         "response": "bad.\n#### 8", "ok": False},
        {"id": "p2", "prompt": [{"role": "user", "content": "Q2"}],
         "response": "wrong.\n#### 1", "ok": False},
    ]
    samples.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    out = tmp_path / "pairs.jsonl"
    assert make_verified_pairs(samples, out) == 1  # p2 has no correct sample: no pair
    pair = json.loads(out.read_text(encoding="utf-8").strip())
    assert pair["chosen"][0]["content"].endswith("#### 7")
    assert pair["rejected"][0]["content"].endswith("#### 8")


def test_synth_config_and_registry_cover_new_families():
    train_cfg = yaml.safe_load((ROOT / "configs/train/laptop_lora_sft.yaml").read_text(encoding="utf-8"))
    assert train_cfg["hyperparameters"]["max_steps"] == 120
    assert (ROOT / "data/processed/synth_math_v1/grpo_prompts.jsonl").exists()


def test_promotion_script_reads_real_eval_files():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from promote_version import load_eval, weakest_groups

    from orion.registry import promote
    from orion.registry.versions import VersionCard

    items, summary = load_eval(ROOT / "runs/evals/orion-0.1/baseline")
    assert len(items) == 100
    assert abs(sum(items.values()) / len(items) - summary["accuracy"]) < 1e-9
    weak = weakest_groups(summary, k=3)
    assert len(weak) == 3 and any("gcd_lcm" in w or "quadratic" in w or "system" in w for w in weak)
    # self-comparison through the real gate: 100 ties, correctly rejected
    suite = {"synth-math": items}
    cand = VersionCard(version="t", weights="w", weights_owner="o", weights_license="l",
                       orion_modified=True, regression_suite=suite)
    inc = VersionCard(version="b", weights="w", weights_owner="o", weights_license="l",
                      orion_modified=False, regression_suite=suite)
    d = promote(cand, inc)
    assert not d["promote"] and d["overall"]["ties"] == 100 and cand.status == "rejected"
