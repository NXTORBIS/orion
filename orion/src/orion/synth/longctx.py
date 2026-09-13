"""Procedural long-context tasks with verifiable answers (project brief §12).

Each task builds a haystack of filler paragraphs to a target token/word length and plants
facts whose answer is checkable:
  * needle          — one fact; ask for it
  * multi-needle    — several facts about different entities; ask for one of them
  * counting        — count how many records match a condition across the document
  * contradiction   — two conflicting statements; ask which value appears later / flag the conflict
  * cross-document  — facts split across several documents; the answer combines them (sum)
The measurement is accuracy at each length, not the advertised context window.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

FILLER = ["The committee reviewed the proposal and agreed to revisit the budget in the spring.",
          "Volcanic soils are rich in minerals, and farmers rotate crops to keep them fertile.",
          "A bicycle chain transfers power from the pedals to the rear wheel through sprockets.",
          "The orchestra rehearses on Tuesday evenings in the old fire station near the river.",
          "Tide pools along the rocky coast hold anemones, small crabs and darting fish.",
          "The library extended its opening hours after residents asked for evening access.",
          "Engineers measured the bridge vibration and found it well within the design limits.",
          "The bakery sells tickets for the concert, and the proceeds pay for sheet music."]
NAMES = ["Ada", "Bao", "Chidi", "Dana", "Emil", "Farah", "Goran", "Hana", "Ines", "Jiro", "Kofi", "Lena"]
ITEMS = ["parcels", "invoices", "samples", "tickets", "reports", "batches"]


@dataclass
class LongCtxItem:
    id: str
    kind: str
    target_words: int
    documents: list[str]
    question: str
    answer: str
    words: int


def _haystack(rng: random.Random, words: int) -> list[str]:
    out, n = [], 0
    while n < words:
        s = rng.choice(FILLER)
        out.append(s)
        n += len(s.split())
    return out


def _plant(rng: random.Random, filler: list[str], sentences: list[str]) -> list[str]:
    doc = list(filler)
    for s in sentences:
        doc.insert(rng.randint(0, len(doc)), s)
    return doc


def make_item(kind: str, target_words: int, seed: int) -> LongCtxItem:
    rng = random.Random(f"{kind}:{target_words}:{seed}")
    filler = _haystack(rng, target_words)
    if kind == "needle":
        name, code = rng.choice(NAMES), rng.randint(1000, 9999)
        doc = _plant(rng, filler, [f"{name}'s locker code is {code}."])
        q, a, docs = f"What is {name}'s locker code?", str(code), [" ".join(doc)]
    elif kind == "multi-needle":
        people = rng.sample(NAMES, 4)
        codes = {p: rng.randint(1000, 9999) for p in people}
        doc = _plant(rng, filler, [f"{p}'s locker code is {c}." for p, c in codes.items()])
        target = rng.choice(people)
        q, a, docs = f"What is {target}'s locker code?", str(codes[target]), [" ".join(doc)]
    elif kind == "counting":
        item = rng.choice(ITEMS)
        k = rng.randint(3, 12)
        doc = _plant(rng, filler, [f"Record {rng.randint(100, 999)}: {rng.choice(NAMES)} shipped {rng.randint(1, 40)} {item}." for _ in range(k)])
        q, a, docs = f"How many records mention shipped {item}?", str(k), [" ".join(doc)]
    elif kind == "contradiction":
        name = rng.choice(NAMES)
        v1, v2 = rng.sample(range(10, 90), 2)
        first = f"{name}'s office is room {v1}."
        second = f"Correction: {name}'s office is room {v2}."
        doc = list(filler)
        i = rng.randint(0, len(doc) // 2)
        j = rng.randint(len(doc) // 2 + 1, len(doc))
        doc.insert(i, first)
        doc.insert(j, second)
        q, a, docs = f"Which room is {name}'s office in according to the most recent statement?", str(v2), [" ".join(doc)]
    elif kind == "cross-document":
        name, item = rng.choice(NAMES), rng.choice(ITEMS)
        parts = [rng.randint(1, 50) for _ in range(3)]
        docs = []
        for p in parts:
            d = _plant(rng, _haystack(rng, target_words // 3), [f"{name} shipped {p} {item} this week."])
            docs.append(" ".join(d))
        q, a = f"Across all documents, how many {item} did {name} ship in total?", str(sum(parts))
    else:
        raise ValueError(kind)
    return LongCtxItem(f"longctx-{kind}-{target_words}-{seed}", kind, target_words, docs, q, a, sum(len(d.split()) for d in docs))


KINDS = ["needle", "multi-needle", "counting", "contradiction", "cross-document"]


def generate(lengths: list[int], per_kind: int = 4, seed_start: int = 0) -> list[LongCtxItem]:
    return [make_item(k, L, s) for L in lengths for k in KINDS for s in range(seed_start, seed_start + per_kind)]


def prompt_for(item: LongCtxItem) -> str:
    docs = "\n\n".join(f"Document {i + 1}:\n{d}" for i, d in enumerate(item.documents))
    return f"{docs}\n\nQuestion: {item.question}\nAnswer with just the number on the last line as '#### <answer>'."
