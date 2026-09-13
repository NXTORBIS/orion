"""Configurable, streaming data pipeline.

    RAW DATA -> provenance -> language -> PII -> toxicity -> heuristics (spam/boilerplate)
    -> exact dedup -> near dedup -> quality -> classify (domain / reasoning / difficulty)
    -> contamination -> split assignment -> FINAL DATASET (+ dropped log + stats + manifest)

The run is described by a YAML config (see configs/data/*.yaml). Stages that need model
weights are only instantiated when configured; the manifest of every run lists exactly which
stages ran and with which method, so a heuristic run is never mistaken for a classifier run.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .classify import ClassifyStage
from .contamination import ContaminationFilter, EvalIndex
from .dedup import ExactDedup, NearDedup
from .heuristics import HeuristicConfig, HeuristicFilter
from .language import GlotLIDDetector, LanguageStage, ScriptDetector
from .pii import PIIFilter
from .provenance import ProvenanceGate, load_registry
from .quality import EduClassifier, HeuristicQuality
from .readers import read_records
from .stats import Stats
from .toxicity import HAPClassifier, LexiconToxicity


def assign_split(record_id: str, validation_fraction: float) -> str:
    """Deterministic split by id hash so re-runs and mixtures agree."""
    h = int(hashlib.sha256(record_id.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "validation" if h < validation_fraction else "train"


def build_stages(cfg: dict[str, Any], registry: dict[str, dict[str, Any]], root: Path) -> list:
    s = cfg.get("stages", {})
    stages: list = [ProvenanceGate(registry, purpose=cfg.get("purpose", "train"))]

    lang = s.get("language", {})
    if lang.get("enabled", True):
        det = GlotLIDDetector(root / lang["glotlid_model"]) if lang.get("glotlid_model") else ScriptDetector()
        allowed = set(lang["allowed"]) if lang.get("allowed") else None
        stages.append(LanguageStage(det, allowed=allowed))

    if s.get("pii", {}).get("enabled", True):
        stages.append(PIIFilter(max_per_1k_words=s.get("pii", {}).get("max_per_1k_words", 20.0)))

    tox = s.get("toxicity", {})
    if tox.get("enabled", True):
        if tox.get("classifier_model"):
            stages.append(HAPClassifier(root / tox["classifier_model"], threshold=tox.get("threshold", 0.5)))
        else:
            stages.append(LexiconToxicity(max_per_1k_words=tox.get("max_per_1k_words", 5.0)))

    if s.get("heuristics", {}).get("enabled", True):
        stages.append(HeuristicFilter(HeuristicConfig(**s.get("heuristics", {}).get("thresholds", {}))))

    if s.get("dedup", {}).get("enabled", True):
        stages.append(ExactDedup())
        stages.append(NearDedup(threshold=s.get("dedup", {}).get("near_threshold", 0.8)))

    q = s.get("quality", {})
    if q.get("enabled", True):
        if q.get("edu_classifier_model"):
            stages.append(EduClassifier(root / q["edu_classifier_model"], min_score=q.get("min_edu_score", 2.0)))
        else:
            stages.append(HeuristicQuality(min_score=q.get("min_heuristic_score", 0.4)))

    if s.get("classify", {}).get("enabled", True):
        stages.append(ClassifyStage())

    cont = s.get("contamination", {})
    if cont.get("enabled", True):
        index_path = root / cont["index"] if cont.get("index") else None
        index = EvalIndex.load(index_path) if index_path and index_path.exists() else EvalIndex()
        if not index.grams:
            for eval_file in cont.get("eval_files", []):
                for r in read_records(root / eval_file["path"], eval_file["source"], registry,
                                      text_field=eval_file.get("text_field", "text")):
                    index.add(r.text, eval_file["source"])
                    for extra in eval_file.get("extra_fields", []):
                        if isinstance(r.meta.get(extra), str):
                            index.add(r.meta[extra], eval_file["source"])
            if index_path and index.grams:
                index_path.parent.mkdir(parents=True, exist_ok=True)
                index.save(index_path)
        stages.append(ContaminationFilter(index, max_hits=cont.get("max_hits", 0)))
    return stages


def run(config_path: str | Path, root: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(config_path)
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    root = Path(root) if root else cfg_path.resolve().parents[2]
    registry = load_registry(root / cfg.get("registry", "registry/licenses/datasets.yaml"))
    out_dir = root / cfg["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    stages = build_stages(cfg, registry, root)

    tokenizer = None
    if cfg.get("tokenizer"):
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(root / cfg["tokenizer"])
    stats = Stats(tokenizer)
    val_frac = float(cfg.get("validation_fraction", 0.02))

    def source_stream():
        for src in cfg["sources"]:
            yield from read_records(root / src["path"], src["source"], registry, text_field=src.get("text_field", "text"),
                                    id_field=src.get("id_field"), split=src.get("split"), limit=src.get("limit"),
                                    generators=src.get("generators"))

    stream = source_stream()
    for stage in stages:
        stream = stage.process(stream)

    t0 = time.perf_counter()
    kept_path, dropped_path = out_dir / "kept.jsonl", out_dir / "dropped.jsonl"
    sha = hashlib.sha256()
    with open(kept_path, "w", encoding="utf-8") as kept_f, open(dropped_path, "w", encoding="utf-8") as drop_f:
        for r in stream:
            if r.kept:
                r.meta["split_assigned"] = assign_split(r.id, val_frac)
                line = json.dumps(r.to_dict(), ensure_ascii=False)
                kept_f.write(line + "\n")
                sha.update(line.encode("utf-8"))
            else:
                drop_f.write(json.dumps({"id": r.id, "source": r.source, "stage": r.dropped_by, "reason": r.drop_reason},
                                        ensure_ascii=False) + "\n")
            stats.add(r)
    stats.write(out_dir / "stats.json")
    summary = stats.to_dict()
    manifest = {
        "config": str(cfg_path), "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_version": sha.hexdigest()[:16], "seconds": round(time.perf_counter() - t0, 1),
        "stages": [{"name": st.name, "class": type(st).__name__,
                    "method": getattr(getattr(st, "detector", None), "method", None)} for st in stages],
        "output": {"kept": str(kept_path), "dropped": str(dropped_path)},
        "summary": {k: summary[k] for k in ("examples_seen", "examples_kept", "kept_fraction", "words_kept", "tokens_kept")},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    import sys

    print(json.dumps(run(sys.argv[1]), indent=2))
