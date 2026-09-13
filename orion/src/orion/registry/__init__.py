"""Model version registry and promotion gate (project brief §26).

A *version card* records everything about an ORION version: which weights (and whose), the
training run card, the dataset version, evaluation summaries, known weaknesses and the
regression-suite results. ``promote`` decides whether a candidate may replace the current best,
and it can only say yes when the candidate is measurably better and nothing regressed.
"""

from .versions import VersionCard, load_card, promote, save_card  # noqa: F401
