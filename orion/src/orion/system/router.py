"""Query analysis and expert routing (project brief §22).

``Router.route`` turns a user message into a ``Route``: intent, which tools may help, whether
retrieval is needed, a difficulty estimate, how many candidate answers to generate, and which
expert backend to use. Rules are v0 and measured (``Router.accuracy`` on a labelled set); a
trained classifier can replace ``classify_intent`` without changing the interface. Routing
only earns its place if the routed system beats the best single backend on end-to-end evals —
that comparison is part of the evaluation suite, not assumed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from orion.data.classify import classify_reasoning, estimate_difficulty

CODE = re.compile(r"```|\bdef |\bclass \w+|\bimport \w+|#include|\b(function|script|program|regex|refactor|debug|bug|compile|"
                  r"stack ?trace|traceback|unit test|python|javascript|typescript|rust|golang|java|c\+\+|sql query|api endpoint)\b", re.I)
MATH = re.compile(r"\d\s*[+\-*/×÷^=]\s*\d|\b(solve|compute|calculate|evaluate|simplify|integral|derivative|equation|probability|"
                  r"how many|percent|%|sum of|product of|remainder|prime|factor|geometry|triangle|circle|area|perimeter|"
                  r"average speed|km/h|fraction)\b", re.I)
FACTUAL = re.compile(r"^\s*(who|what|when|where|which|how (old|tall|far|much|long)|is it true|did)\b|\b(according to|cite|source|"
                     r"documentation|docs|latest|news|population|capital of|born|founded|released)\b", re.I)
REASONING = re.compile(r"\b(why|explain|compare|contrast|analy[sz]e|plan|design|prove|logic|puzzle|strategy|trade-?off|"
                       r"pros and cons|step by step|argue|evaluate the claim)\b", re.I)
CHAT = re.compile(r"^\s*(hi|hello|hey|thanks|thank you|good (morning|evening)|how are you|bye)\b", re.I)
FILE = re.compile(r"\b[\w./\\-]+\.(py|txt|md|json|csv|yaml|yml|toml|log|html|js|ts)\b", re.I)
SQL = re.compile(r"\b(select|insert|update|delete)\b.*\b(from|into|table)\b|\bsql\b", re.I | re.S)
DATA_ANALYSIS = re.compile(r"\b(dataframe|csv|spreadsheet|plot|chart|statistics|mean|median|correlation)\b", re.I)


@dataclass
class Route:
    intent: str
    expert: str
    needs_tools: list[str] = field(default_factory=list)
    needs_retrieval: bool = False
    difficulty: int = 1
    candidates: int = 1
    reasons: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


def classify_intent(text: str, has_attachments: bool = False) -> tuple[str, list[str]]:
    reasons = []
    if has_attachments:
        return "vision", ["attachment present"]
    if CHAT.match(text) and len(text.split()) <= 8:
        return "chat", ["greeting/short conversational"]
    scores = {"code": len(CODE.findall(text)), "math": len(MATH.findall(text)), "factual": len(FACTUAL.findall(text)),
              "reasoning": len(REASONING.findall(text))}
    if "```" in text or re.search(r"\bdef |#include|traceback", text, re.I):
        scores["code"] += 3
        reasons.append("code block or code keyword")
    if re.search(r"\d\s*[+\-*/×÷^=]\s*\d", text):
        scores["math"] += 2
        reasons.append("arithmetic expression")
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return ("reasoning" if len(text.split()) > 40 else "chat"), ["no signal; length fallback"]
    reasons.append(f"scores={scores}")
    return best, reasons


class Router:
    def __init__(self, experts: dict[str, str] | None = None, available_backends: set[str] | None = None,
                 available_tools: set[str] | None = None, has_documents: bool = False):
        # intent -> backend name; anything missing falls back to "general"
        self.experts = {"math": "reasoning", "reasoning": "reasoning", "code": "coding", "vision": "vision",
                        "factual": "general", "chat": "general", **(experts or {})}
        self.backends = available_backends or {"general"}
        self.tools = available_tools or set()
        self.has_documents = has_documents

    def route(self, text: str, attachments: list[Any] | None = None) -> Route:
        intent, reasons = classify_intent(text, bool(attachments))
        tools: list[str] = []
        if intent == "math" and "calculator" in self.tools:
            tools.append("calculator")
        if intent in ("math", "code") and "python" in self.tools:
            tools.append("python")
        if FILE.search(text) and "read_file" in self.tools:
            tools.append("read_file")
        if SQL.search(text) and "sql" in self.tools:
            tools.append("sql")
        if DATA_ANALYSIS.search(text) and "python" in self.tools and "python" not in tools:
            tools.append("python")
        needs_retrieval = self.has_documents and ("search_docs" in self.tools or True) and intent in ("factual", "reasoning")
        if needs_retrieval and "search_docs" in self.tools:
            tools.append("search_docs")
        reasoning = classify_reasoning(text)
        difficulty = max(estimate_difficulty(text, reasoning), 2 if intent in ("math", "code", "reasoning") else 1)
        candidates = 3 if (intent in ("math", "code") and difficulty >= 3) else (2 if intent == "math" else 1)
        expert = self.experts.get(intent, "general")
        if expert not in self.backends:
            reasons.append(f"expert '{expert}' unavailable -> general")
            expert = "general"
        return Route(intent=intent, expert=expert, needs_tools=tools, needs_retrieval=needs_retrieval, difficulty=difficulty,
                     candidates=candidates, reasons=reasons)

    @staticmethod
    def accuracy(labelled: list[tuple[str, str]]) -> float:
        return sum(classify_intent(t)[0] == y for t, y in labelled) / max(1, len(labelled))
