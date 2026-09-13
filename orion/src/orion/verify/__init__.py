"""Automated verifiers (project brief §16).

Each verifier turns a model response plus a reference into a ``Verdict`` with a stated method,
so training data and evaluation scores are never based on unverified text.
"""

from .math import MathVerdict, equivalent, extract_final_answer, verify_math  # noqa: F401
