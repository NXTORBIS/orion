"""Quality scoring.

* ``heuristic_quality`` (v0): a 0–1 score from surface features of well-formed prose — lines
  that end in terminal punctuation, plausible sentence length, lexical diversity, paragraph
  structure, and low URL/symbol/capital noise. It is a heuristic and is reported as one.
* ``EduClassifier``: the FineWeb-Edu classifier (Apache-2.0; a regression head giving 0–5
  "educational value") when its weights are present. Its training labels were produced by
  Llama-3-70B; that is a label-only dependency and is recorded in the dataset registry.
"""

from __future__ import annotations

import re
from pathlib import Path

from .schema import Record, RecordStage
from .text import words

SENT_END = re.compile(r"[.!?。！？](?:\s|$)")
TERMINAL = (".", "!", "?", '"', "'", ")", ":", ";", "。", "！", "？", "」", "”")
URL = re.compile(r"https?://\S+|www\.\S+")


def heuristic_quality(text: str) -> dict[str, float]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    ws = words(text)
    n = len(ws)
    if not lines or n == 0:
        return {"score": 0.0}
    punct_end = sum(1 for line in lines if line.endswith(TERMINAL)) / len(lines)
    sentences = max(1, len(SENT_END.findall(text)))
    spl = n / sentences
    sent_len = 1.0 if 8 <= spl <= 40 else max(0.0, 1 - abs(spl - 24) / 40)
    sample = ws[:300]
    ttr = len(set(sample)) / len(sample)
    diversity = min(1.0, ttr / 0.45)
    paragraphs = text.count("\n\n") + 1
    structure = min(1.0, (paragraphs - 1) / 3 + sentences / 10)
    letters = [ch for ch in text if ch.isalpha()]
    caps = sum(ch.isupper() for ch in letters) / max(1, len(letters))
    urls = len(URL.findall(text)) * 100 / n
    noise = max(0.0, 1 - caps / 0.3) * max(0.0, 1 - urls / 5)
    parts = {"punct_end": punct_end, "sent_len": sent_len, "diversity": diversity, "structure": structure, "noise": noise}
    parts["score"] = sum(parts.values()) / len(parts)
    return {k: round(v, 3) for k, v in parts.items()}


class HeuristicQuality(RecordStage):
    name = "quality"

    def __init__(self, min_score: float = 0.4):
        self.min_score = min_score

    def apply(self, r: Record) -> None:
        q = heuristic_quality(r.text)
        r.meta["quality"] = {"method": "heuristic", **q}
        if q["score"] < self.min_score:
            r.drop(self.name, f"heuristic quality {q['score']:.2f} < {self.min_score}")


class EduClassifier(RecordStage):
    name = "quality"

    def __init__(self, model_dir: str | Path, min_score: float = 2.0, batch_size: int = 16, max_chars: int = 3000):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        path = Path(model_dir)
        if not path.exists():
            raise FileNotFoundError(f"quality classifier not found: {path}")
        self.tok = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForSequenceClassification.from_pretrained(path).eval()
        if self.model.config.num_labels != 1:
            raise ValueError("expected a single-output regression head (FineWeb-Edu classifier)")
        self.min_score, self.batch_size, self.max_chars, self.torch = min_score, batch_size, max_chars, torch

    def process(self, records):
        batch: list[Record] = []
        for r in records:
            if not r.kept:
                yield r
                continue
            batch.append(r)
            if len(batch) == self.batch_size:
                yield from self._score(batch)
                batch = []
        if batch:
            yield from self._score(batch)

    def _score(self, batch: list[Record]):
        enc = self.tok([r.text[: self.max_chars] for r in batch], padding=True, truncation=True, max_length=512, return_tensors="pt")
        with self.torch.no_grad():
            scores = self.model(**enc).logits.squeeze(-1).tolist()
        for r, s in zip(batch, scores):
            r.meta["quality"] = {"method": "fineweb-edu", "score": round(float(s), 3), "int_score": int(round(max(0, min(5, s))))}
            if s < self.min_score:
                r.drop(self.name, f"edu score {s:.2f} < {self.min_score}")
            yield r
