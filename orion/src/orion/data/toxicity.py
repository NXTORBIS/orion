"""Toxicity filtering.

* ``LexiconToxicity`` (v0): word-boundary matching of English profanity, sexual and threat
  terms, scored as hits per 1k words so a single quoted word does not drop a document.
  Coverage is stated honestly: it does not detect hate speech or non-English abuse.
* ``HAPClassifier``: a sequence-classification model such as IBM Granite Guardian HAP
  (Apache-2.0) when its weights are present. The positive-class index is read from the model
  config and checked at load time.
"""

from __future__ import annotations

import re
from pathlib import Path

from .schema import Record, RecordStage
from .text import words

_PROFANITY = [
    r"fuck\w*", r"shit\w*", r"bitch\w*", r"asshole\w*", r"cunt\w*", r"dick\w*", r"cock\w*", r"pussy",
    r"motherfucker\w*", r"bastard\w*", r"whore\w*", r"slut\w*", r"twat\w*", r"wank\w*", r"prick\w*",
]
_SEXUAL = [r"porn\w*", r"blowjob\w*", r"handjob\w*", r"cumshot\w*", r"gangbang\w*", r"hentai", r"xxx"]
_THREATS = [
    r"kill (you|him|her|them|yourself)", r"i will (murder|rape|shoot|stab)", r"(rape|raping) (you|her|him)",
    r"beat (you|him|her) to death", r"burn (you|them) alive", r"deserve[sd]? to die",
]
LEXICON = re.compile(r"\b(?:" + "|".join(_PROFANITY + _SEXUAL + _THREATS) + r")\b", re.I)
THREATS = re.compile(r"\b(?:" + "|".join(_THREATS) + r")\b", re.I)


class LexiconToxicity(RecordStage):
    name = "toxicity"

    def __init__(self, max_per_1k_words: float = 5.0, max_threats: int = 0):
        self.max_per_1k_words = max_per_1k_words
        self.max_threats = max_threats

    def apply(self, r: Record) -> None:
        hits = LEXICON.findall(r.text)
        threats = len(THREATS.findall(r.text))
        per_1k = 1000 * len(hits) / max(1, len(words(r.text)))
        r.meta["toxicity"] = {"method": "lexicon", "hits": len(hits), "per_1k_words": round(per_1k, 2), "threats": threats}
        if threats > self.max_threats:
            return r.drop(self.name, f"{threats} violent threat phrase(s)")
        if per_1k > self.max_per_1k_words:
            r.drop(self.name, f"profanity density {per_1k:.1f} per 1k words")


class HAPClassifier(RecordStage):
    name = "toxicity"

    def __init__(self, model_dir: str | Path, threshold: float = 0.5, batch_size: int = 16, max_chars: int = 2000):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        path = Path(model_dir)
        if not path.exists():
            raise FileNotFoundError(f"toxicity classifier not found: {path}")
        self.tok = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForSequenceClassification.from_pretrained(path).eval()
        id2label = {int(k): str(v).lower() for k, v in self.model.config.id2label.items()}
        positives = [i for i, l in id2label.items() if any(t in l for t in ("hap", "toxic", "label_1", "hate"))]
        if len(positives) != 1:
            raise ValueError(f"cannot identify the toxic class in id2label={id2label}")
        self.positive = positives[0]
        self.threshold, self.batch_size, self.max_chars, self.torch = threshold, batch_size, max_chars, torch

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
            probs = self.model(**enc).logits.softmax(-1)[:, self.positive].tolist()
        for r, p in zip(batch, probs):
            r.meta["toxicity"] = {"method": "classifier", "p_toxic": round(p, 4)}
            if p >= self.threshold:
                r.drop(self.name, f"classifier p_toxic={p:.2f}")
            yield r
