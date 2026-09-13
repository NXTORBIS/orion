"""Provenance gate — the first pipeline stage.

Enforces the "clean data" rule of docs/04_data_training_stack.md §1 using
registry/licenses/datasets.yaml. A record is dropped before any other processing if:
  * its source is not registered, is excluded, or is not registered for the requested use;
  * it comes from an evaluation split of a dataset (test/validation data is never trained on);
  * any of its generators is a model whose terms restrict training other models on its outputs;
  * its generators are unknown (every record must declare where its text came from).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .schema import Record, RecordStage

# Model families whose terms restrict using their outputs to train other models.
RESTRICTED_GENERATORS: dict[str, re.Pattern[str]] = {
    "OpenAI closed models": re.compile(r"\bgpt-?\d|chatgpt|\bo[1-4](-mini|-pro)?\b|davinci", re.I),
    "Anthropic Claude": re.compile(r"claude", re.I),
    "Google Gemini / Bard": re.compile(r"gemini|\bbard\b", re.I),
    "xAI Grok": re.compile(r"\bgrok", re.I),
    "Llama license (naming / use terms)": re.compile(r"\bllama(?!\.cpp)", re.I),
    "Gemma 1-3n terms (Model Derivatives)": re.compile(r"\bgemma[- ]?[123](n)?\b", re.I),
    "Qwen License 72B models": re.compile(r"qwen2(\.5)?(-math|-vl)?-72b", re.I),
    "Mistral research / non-production": re.compile(r"codestral|pixtral-large", re.I),
}

EVAL_SPLITS = {"test", "validation", "valid", "dev", "eval"}


def restricted_reason(generator: str) -> str | None:
    for reason, pattern in RESTRICTED_GENERATORS.items():
        if pattern.search(generator):
            return reason
    return None


def load_registry(path: str | Path) -> dict[str, dict[str, Any]]:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in doc["datasets"]}


class ProvenanceGate(RecordStage):
    name = "provenance"

    def __init__(self, registry: dict[str, dict[str, Any]], purpose: str = "train"):
        self.registry = registry
        self.purpose = purpose

    def apply(self, r: Record) -> None:
        entry = self.registry.get(r.source)
        if entry is None:
            return r.drop(self.name, f"unregistered source '{r.source}'")
        status = entry.get("status")
        if status == "excluded":
            return r.drop(self.name, f"excluded source: {entry.get('reason', 'see registry')}")
        if self.purpose == "train":
            if status == "eval-only" or "train" not in str(entry.get("use", "")):
                return r.drop(self.name, "source is not registered for training")
            if str(r.meta.get("split", "")).lower() in EVAL_SPLITS:
                return r.drop(self.name, f"evaluation split '{r.meta['split']}' cannot be used for training")
        if not r.generators or "unknown" in r.generators:
            return r.drop(self.name, "generator unknown")
        for g in r.generators:
            if reason := restricted_reason(g):
                return r.drop(self.name, f"restricted generator '{g}' ({reason})")
