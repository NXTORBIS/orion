"""Evaluation infrastructure (project brief §19–20).

* ``tasks``   — benchmark task definitions (items + verifier-based scoring)
* ``runner``  — generators (local HF model with optional LoRA adapter; llama.cpp) and task runs
* ``metrics`` — accuracy, bootstrap confidence intervals, paired comparisons, group breakdowns
* ``report``  — scorecards and experiment reports written from measured results only
"""
