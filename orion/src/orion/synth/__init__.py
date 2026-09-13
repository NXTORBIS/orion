"""Procedural, verifier-checked synthetic data generators (project brief §6).

Every generated item carries the template family, difficulty level, seed, and the result of
an independent verification (SymPy re-derivation or exhaustive enumeration). Items whose
verification fails are never emitted, and the failure is counted so generator bugs surface.
"""
