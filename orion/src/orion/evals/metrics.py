"""Accuracy with uncertainty. Every reported score carries a bootstrap confidence interval,
and every before/after comparison is a *paired* bootstrap on the same items, so a difference
is only called an improvement when its interval excludes zero (project brief §26 promotion gate).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

import numpy as np


def accuracy(flags: Sequence[bool]) -> float:
    return float(np.mean(flags)) if len(flags) else 0.0


def bootstrap_ci(flags: Sequence[bool], n_boot: int = 2000, alpha: float = 0.05, seed: int = 0) -> tuple[float, float]:
    arr = np.asarray(flags, dtype=float)
    if arr.size == 0:
        return 0.0, 0.0
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, arr.size, size=(n_boot, arr.size))
    means = arr[idx].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def paired_bootstrap_diff(a: Sequence[bool], b: Sequence[bool], n_boot: int = 2000, alpha: float = 0.05, seed: int = 0) -> dict[str, Any]:
    """Difference b - a on the same items. ``significant`` is True when the CI excludes 0."""
    a_arr, b_arr = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    assert a_arr.shape == b_arr.shape, "paired comparison needs the same items in the same order"
    diff = b_arr - a_arr
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, diff.size, size=(n_boot, diff.size))
    means = diff[idx].mean(axis=1)
    lo, hi = float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))
    return {"diff": float(diff.mean()), "ci": (lo, hi), "significant": lo > 0 or hi < 0,
            "p_b_better": float(np.mean(means > 0)), "n": int(diff.size),
            "wins": int(np.sum(diff > 0)), "losses": int(np.sum(diff < 0)), "ties": int(np.sum(diff == 0))}


def by_group(groups: Sequence[str], flags: Sequence[bool]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[bool]] = defaultdict(list)
    for g, f in zip(groups, flags):
        buckets[str(g)].append(bool(f))
    return {g: {"n": len(v), "accuracy": accuracy(v), "ci": bootstrap_ci(v)} for g, v in sorted(buckets.items())}


def summarize(flags: Sequence[bool], groups: dict[str, Sequence[str]] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"n": len(flags), "accuracy": accuracy(flags), "ci": bootstrap_ci(flags)}
    for name, g in (groups or {}).items():
        out[f"by_{name}"] = by_group(g, flags)
    return out
