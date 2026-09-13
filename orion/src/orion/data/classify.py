"""Knowledge-domain, reasoning-type and difficulty annotation (v0, rule-based).

These labels feed dataset statistics and mixture balancing. They are heuristics and are
stored as ``classify_method="rules-v0"``. The real difficulty signal ORION trains on is
*empirical* difficulty — the measured pass rate of the current model on an item (see
``orion.evals.mining``) — which replaces these estimates as soon as evaluation data exists.
"""

from __future__ import annotations

import re
from collections import Counter

from .schema import Record, RecordStage
from .text import words

DOMAIN_TERMS: dict[str, set[str]] = {
    "math": {"theorem", "lemma", "proof", "integral", "derivative", "equation", "polynomial", "matrix", "prime",
             "integer", "probability", "geometry", "algebra", "calculus", "vector", "fraction", "solve", "sum"},
    "code": {"function", "variable", "compile", "runtime", "python", "javascript", "java", "class", "method",
             "array", "string", "loop", "api", "bug", "commit", "repository", "sql", "database", "server", "algorithm"},
    "physics": {"velocity", "quantum", "photon", "electron", "momentum", "relativity", "thermodynamics", "entropy",
                "voltage", "magnetic", "particle", "gravity", "wavelength", "newton"},
    "chemistry": {"molecule", "reaction", "acid", "compound", "ion", "catalyst", "polymer", "oxidation", "solvent",
                  "mole", "enzyme", "chemical", "bond", "electrolyte"},
    "biology": {"cell", "protein", "gene", "dna", "species", "organism", "evolution", "bacteria", "virus",
                "membrane", "neuron", "tissue", "genome", "ecosystem"},
    "medicine": {"patient", "diagnosis", "symptom", "treatment", "clinical", "dose", "therapy", "disease",
                 "surgery", "infection", "chronic", "prescribed", "hospital"},
    "law": {"court", "statute", "plaintiff", "defendant", "contract", "liability", "jurisdiction", "appeal",
            "regulation", "clause", "tribunal", "legislation", "attorney"},
    "finance": {"revenue", "equity", "investment", "interest", "stock", "market", "asset", "dividend", "inflation",
                "loan", "portfolio", "fiscal", "tax", "profit"},
    "history": {"century", "empire", "war", "treaty", "dynasty", "revolution", "medieval", "ancient", "kingdom",
                "colonial", "reign", "battle"},
    "literature": {"novel", "poem", "poetry", "narrator", "protagonist", "metaphor", "author", "chapter",
                   "fiction", "verse", "prose", "literary"},
    "technology": {"software", "hardware", "network", "device", "internet", "cloud", "processor", "chip",
                   "startup", "platform", "app", "cybersecurity"},
}

STEP_MARKERS = re.compile(r"\b(step \d|first(ly)?|second(ly)?|then|therefore|hence|thus|so that|because|implies|it follows)\b", re.I)
EQUATION = re.compile(r"[=<>≤≥≠]|\\frac|\\int|\\sum|\^|\d+\s*[+\-*/×÷]\s*\d+")
CODE_BLOCK = re.compile(r"```|^\s{4,}\S|\bdef |\bclass |\breturn\b|\bimport |#include|;\s*$|\{\s*$", re.M)
PROOF = re.compile(r"\b(prove|proof|lemma|theorem|q\.e\.d|contradiction|induction|suppose|assume|wlog)\b", re.I)
LOGIC = re.compile(r"\b(if and only if|iff|for all|there exists|implies|contrapositive|premise|conclusion|valid|invalid)\b", re.I)
ADVANCED_MATH = re.compile(r"\b(integral|derivative|eigen\w*|manifold|topolog\w*|homomorphism|isomorphism|tensor|"
                           r"limit|converge\w*|differential|stochastic|combinatori\w*|modulo|bijection)\b", re.I)
BASIC_MATH = re.compile(r"\b(add|subtract|multiply|divide|plus|minus|times|total|how many|percent|fraction)\b", re.I)


def classify_domain(text: str) -> tuple[str, dict[str, float]]:
    ws = words(text)
    n = max(1, len(ws))
    counts = Counter(ws)
    scores = {d: round(1000 * sum(counts[t] for t in terms) / n, 2) for d, terms in DOMAIN_TERMS.items()}
    if CODE_BLOCK.search(text):
        scores["code"] += 5.0
    if EQUATION.search(text):
        scores["math"] += 2.0
    best, val = max(scores.items(), key=lambda kv: kv[1])
    return (best if val >= 3.0 else "general"), scores


def classify_reasoning(text: str) -> list[str]:
    tags = []
    if PROOF.search(text):
        tags.append("proof")
    if LOGIC.search(text):
        tags.append("logical")
    if len(EQUATION.findall(text)) >= 2:
        tags.append("mathematical")
    if CODE_BLOCK.search(text):
        tags.append("code")
    if len(STEP_MARKERS.findall(text)) >= 3:
        tags.append("multi-step")
    return tags or ["none"]


def estimate_difficulty(text: str, reasoning: list[str]) -> int:
    """1 (basic) … 5 (frontier) from structure only; replaced by empirical pass rates later."""
    ws = words(text)
    level = 1
    if "multi-step" in reasoning or "mathematical" in reasoning or "code" in reasoning:
        level = 2
    if len(STEP_MARKERS.findall(text)) >= 6 or len(ws) > 400:
        level = max(level, 3)
    if ADVANCED_MATH.search(text) or "proof" in reasoning:
        level = max(level, 4)
    if "proof" in reasoning and ADVANCED_MATH.search(text) and len(ws) > 300:
        level = 5
    if BASIC_MATH.search(text) and level <= 2 and not ADVANCED_MATH.search(text):
        level = 1 if len(ws) < 120 else 2
    return level


class ClassifyStage(RecordStage):
    name = "classify"

    def apply(self, r: Record) -> None:
        domain, scores = classify_domain(r.text)
        reasoning = classify_reasoning(r.text)
        r.meta.update(domain=domain, domain_scores=scores, reasoning=reasoning,
                      difficulty=estimate_difficulty(r.text, reasoning), classify_method="rules-v0")
