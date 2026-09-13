"""Dataset statistics: counts, tokens, languages, domains, difficulty, quality, duplicates,
drop reasons per stage, and the validation-split distribution. Produced for every pipeline run
and stored next to the output as JSON + Markdown.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .schema import Record
from .text import words


class Stats:
    def __init__(self, tokenizer=None):
        self.tokenizer = tokenizer
        self.total = 0
        self.kept = 0
        self.tokens = 0
        self.words = 0
        self.drops: dict[str, Counter[str]] = defaultdict(Counter)
        self.languages: Counter[str] = Counter()
        self.domains: Counter[str] = Counter()
        self.reasoning: Counter[str] = Counter()
        self.difficulty: Counter[int] = Counter()
        self.quality_hist: Counter[str] = Counter()
        self.sources: Counter[str] = Counter()
        self.splits: Counter[str] = Counter()
        self.dup_exact = 0
        self.dup_near = 0
        self.pii_redactions: Counter[str] = Counter()

    def _reason_key(self, reason: str) -> str:
        # collapse numeric detail so reasons aggregate: "PII density 31.2 ..." -> "PII density"
        return " ".join(w for w in reason.split() if not any(c.isdigit() for c in w))[:60]

    def add(self, r: Record) -> None:
        self.total += 1
        self.sources[r.source] += 1
        for kind, n in (r.meta.get("pii") or {}).items():
            self.pii_redactions[kind] += n
        if not r.kept:
            self.drops[r.dropped_by][self._reason_key(r.drop_reason or "")] += 1
            if r.dropped_by == "exact_dedup":
                self.dup_exact += 1
            elif r.dropped_by == "near_dedup":
                self.dup_near += 1
            return
        self.kept += 1
        self.words += len(words(r.text))
        if self.tokenizer is not None:
            self.tokens += len(self.tokenizer(r.text, add_special_tokens=False)["input_ids"])
        self.languages[r.meta.get("lang", "unknown")] += 1
        self.domains[r.meta.get("domain", "unlabelled")] += 1
        for t in r.meta.get("reasoning", ["unlabelled"]):
            self.reasoning[t] += 1
        self.difficulty[int(r.meta.get("difficulty", 0))] += 1
        q = (r.meta.get("quality") or {}).get("score")
        if q is not None:
            self.quality_hist[f"{min(0.9, int(float(q) * 10) / 10):.1f}"] += 1
        self.splits[r.meta.get("split_assigned", "unassigned")] += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "examples_seen": self.total, "examples_kept": self.kept,
            "kept_fraction": round(self.kept / self.total, 4) if self.total else 0.0,
            "words_kept": self.words, "tokens_kept": self.tokens if self.tokenizer is not None else None,
            "sources": dict(self.sources), "drops_by_stage": {k: dict(v) for k, v in self.drops.items()},
            "duplicates": {"exact": self.dup_exact, "near": self.dup_near},
            "pii_redactions": dict(self.pii_redactions),
            "languages": dict(self.languages.most_common()), "domains": dict(self.domains.most_common()),
            "reasoning": dict(self.reasoning.most_common()), "difficulty": dict(sorted(self.difficulty.items())),
            "quality_histogram": dict(sorted(self.quality_hist.items())), "splits": dict(self.splits),
        }

    def write(self, path: str | Path) -> None:
        d = self.to_dict()
        p = Path(path)
        p.write_text(json.dumps(d, indent=2), encoding="utf-8")
        lines = [f"# Dataset statistics", "", f"- examples seen: {d['examples_seen']}", f"- examples kept: {d['examples_kept']} ({d['kept_fraction']:.1%})",
                 f"- words kept: {d['words_kept']}", f"- tokens kept: {d['tokens_kept']}", f"- duplicates: {d['duplicates']}",
                 f"- PII redactions: {d['pii_redactions']}", "", "## Drops by stage"]
        for stage, reasons in d["drops_by_stage"].items():
            lines.append(f"- **{stage}**: {sum(reasons.values())}")
            for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
                lines.append(f"  - {reason}: {n}")
        for title in ("languages", "domains", "reasoning", "difficulty", "quality_histogram", "splits", "sources"):
            lines += ["", f"## {title}"] + [f"- {k}: {v}" for k, v in d[title].items()]
        p.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
