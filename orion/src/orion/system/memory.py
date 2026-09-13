"""Memory with user control (project brief §14).

* short-term  — the current session's turns (bounded window)
* long-term   — facts about the user; stored only after the user approves them
* semantic    — searchable record of past interactions (BM25) the user can inspect and delete
* working     — scratch state for the task in progress; cleared when the task ends

Nothing is written to long-term memory automatically: the system may *propose* a fact, the user
approves, edits or rejects it. ``export`` and ``clear`` give complete control over stored data.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .rag import BM25Index, Chunk


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MemoryStore:
    def __init__(self, path: str | Path | None = None, short_term_window: int = 20):
        self.path = Path(path) if path else None
        self.window = short_term_window
        self.short_term: dict[str, list[dict[str, str]]] = {}
        self.long_term: list[dict[str, Any]] = []      # {id, text, status: proposed|approved, created, source}
        self.episodes: list[dict[str, Any]] = []       # {id, session, user, assistant, created}
        self.working: dict[str, dict[str, Any]] = {}
        self._index = BM25Index()
        if self.path and self.path.exists():
            self._load()

    # ---------------- persistence ----------------
    def _load(self) -> None:
        d = json.loads(self.path.read_text(encoding="utf-8"))
        self.long_term, self.episodes = d.get("long_term", []), d.get("episodes", [])
        for e in self.episodes:
            self._index.add(Chunk(e["id"], 0, f"{e['user']}\n{e['assistant']}", {"session": e["session"]}))

    def save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"long_term": self.long_term, "episodes": self.episodes}, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---------------- short-term ----------------
    def add_turn(self, session: str, role: str, content: str) -> None:
        turns = self.short_term.setdefault(session, [])
        turns.append({"role": role, "content": content})
        del turns[: max(0, len(turns) - self.window)]

    def context(self, session: str) -> list[dict[str, str]]:
        return list(self.short_term.get(session, []))

    # ---------------- long-term (user-approved) ----------------
    def propose(self, text: str, source: str = "assistant") -> dict[str, Any]:
        fact = {"id": uuid.uuid4().hex[:8], "text": text, "status": "proposed", "created": _now(), "source": source}
        self.long_term.append(fact)
        self.save()
        return fact

    def approve(self, fact_id: str, edited_text: str | None = None) -> bool:
        for f in self.long_term:
            if f["id"] == fact_id:
                f["status"] = "approved"
                if edited_text:
                    f["text"] = edited_text
                f["approved"] = _now()
                self.save()
                return True
        return False

    def delete(self, fact_id: str) -> bool:
        before = len(self.long_term)
        self.long_term = [f for f in self.long_term if f["id"] != fact_id]
        self.save()
        return len(self.long_term) < before

    def approved_facts(self) -> list[str]:
        return [f["text"] for f in self.long_term if f["status"] == "approved"]

    def pending(self) -> list[dict[str, Any]]:
        return [f for f in self.long_term if f["status"] == "proposed"]

    # ---------------- semantic (episodes) ----------------
    def record_episode(self, session: str, user: str, assistant: str) -> str:
        eid = uuid.uuid4().hex[:8]
        self.episodes.append({"id": eid, "session": session, "user": user, "assistant": assistant, "created": _now()})
        self._index.add(Chunk(eid, 0, f"{user}\n{assistant}", {"session": session}))
        self.save()
        return eid

    def recall(self, query: str, k: int = 3) -> list[dict[str, Any]]:
        hits = self._index.search(query, k)
        by_id = {e["id"]: e for e in self.episodes}
        return [dict(by_id[h.chunk.doc_id], score=round(h.score, 3)) for h in hits if h.chunk.doc_id in by_id]

    def forget_episode(self, episode_id: str) -> bool:
        before = len(self.episodes)
        self.episodes = [e for e in self.episodes if e["id"] != episode_id]
        self._index = BM25Index()
        for e in self.episodes:
            self._index.add(Chunk(e["id"], 0, f"{e['user']}\n{e['assistant']}", {"session": e["session"]}))
        self.save()
        return len(self.episodes) < before

    # ---------------- working ----------------
    def scratch(self, task_id: str) -> dict[str, Any]:
        return self.working.setdefault(task_id, {})

    def end_task(self, task_id: str) -> None:
        self.working.pop(task_id, None)

    # ---------------- user controls ----------------
    def export(self) -> dict[str, Any]:
        return {"long_term": list(self.long_term), "episodes": list(self.episodes), "sessions": {k: list(v) for k, v in self.short_term.items()}}

    def clear(self, what: str = "all") -> None:
        if what in ("all", "long_term"):
            self.long_term = []
        if what in ("all", "episodes"):
            self.episodes, self._index = [], BM25Index()
        if what in ("all", "short_term"):
            self.short_term = {}
        if what in ("all", "working"):
            self.working = {}
        self.save()

    def memory_prompt(self, query: str, session: str, recall: bool = True) -> str:
        parts = []
        if facts := self.approved_facts():
            parts.append("Known about the user (approved by them):\n- " + "\n- ".join(facts))
        if recall and (past := self.recall(query, k=2)):
            parts.append("Relevant earlier exchanges:\n" + "\n".join(f"- User: {p['user'][:200]} / Assistant: {p['assistant'][:200]}" for p in past))
        return "\n\n".join(parts)
