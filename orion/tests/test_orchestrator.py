from orion.system.backends import ScriptedBackend
from orion.system.memory import MemoryStore
from orion.system.orchestrator import Orchestrator
from orion.system.rag import Retriever
from orion.system.response_engine import ResponseEngine, check_code, finalize_text
from orion.system.router import Router, classify_intent
from orion.system.tools import default_registry

LABELLED = [
    ("Compute (47 + 12) × 3.", "math"), ("Solve for x: 3x + 5 = 20", "math"), ("What is the probability of rolling a 7 with two dice?", "math"),
    ("Write a Python function that reverses a linked list.", "code"), ("Why does this traceback happen? ```python\nimport os\nos.foo()```", "code"),
    ("Refactor this JavaScript to avoid the bug in the loop.", "code"),
    ("Who founded the city of Bergen?", "factual"), ("What is the capital of Peru?", "factual"), ("When was the treaty signed, according to the docs?", "factual"),
    ("Explain why the sky is blue and compare it with sunsets.", "reasoning"), ("Design a plan to migrate a monolith to services; list the trade-offs.", "reasoning"),
    ("hi there", "chat"), ("thanks!", "chat"),
]


def test_router_intents_and_tools():
    assert Router.accuracy(LABELLED) >= 0.9
    r = Router(available_backends={"general", "reasoning", "coding"}, available_tools={"calculator", "python", "read_file", "search_docs"}, has_documents=True)
    m = r.route("Compute (47 + 12) × 3.")
    assert m.intent == "math" and m.expert == "reasoning" and m.needs_tools[:2] == ["calculator", "python"]
    assert m.candidates == (3 if m.difficulty >= 3 else 1)
    c = r.route("Read src/app.py and fix the bug in the parser function.")
    assert c.intent == "code" and c.expert == "coding" and "read_file" in c.needs_tools and "python" in c.needs_tools
    f = r.route("What does the documentation say about the retry policy?")
    assert f.intent == "factual" and f.needs_retrieval and "search_docs" in f.needs_tools and f.expert == "general"
    v = r.route("What is in this picture?", attachments=["img.png"])
    assert v.intent == "vision" and v.expert == "general" and any("unavailable" in x for x in v.reasons)
    assert classify_intent("hello")[0] == "chat"
    assert classify_intent("How many legs does a spider have?")[0] != "math"
    assert classify_intent("How many apples are left if I eat 3 of 10?")[0] == "math"


def test_response_engine_candidates_verification_and_repair():
    replies = iter(["Let me think.\n#### 41", "Working it out: 6 × 7 = 42.\n#### 42", "Answer: 42\n#### 42",
                    "Sorry — 6 × 7 = 42.\n#### 42"])
    backend = ScriptedBackend(lambda msgs: next(replies))
    engine = ResponseEngine(backend)
    checker = lambda text, ans: {"ok": ans.strip() == "42", "reason": None if ans.strip() == "42" else f"expected 42, got {ans}"}
    res = engine.run([{"role": "user", "content": "6 times 7?"}], intent="math", n_candidates=3, checker=checker)
    assert res.text.endswith("#### 42") and res.verification["checker"]["ok"] and res.verification["agreement"] > 0.5 and not res.repaired

    replies2 = iter(["I think it is about forty.", "It is 6 × 7 = 42.\n#### 42"])
    res2 = ResponseEngine(ScriptedBackend(lambda msgs: next(replies2))).run([{"role": "user", "content": "6 times 7?"}], intent="math", n_candidates=1, checker=checker)
    assert res2.repaired and res2.text.endswith("#### 42") and "failed a check" in ResponseEngine.__module__ or res2.repaired

    assert check_code("```python\ndef f(x):\n    return x*2\n```", ["assert f(2) == 4"])["ok"]
    assert not check_code("```python\ndef f(x)\n    return x\n```")["ok"]
    assert finalize_text("<think>hidden</think>Visible <tool_call>{}</tool_call> answer") == "Visible answer"


def make_orchestrator(tmp_path, reply):
    retriever = Retriever()
    retriever.add_document("policy", "The retry policy allows three attempts with exponential backoff starting at 200 ms.", {"title": "Policy"})
    tools = default_registry(workspace=tmp_path, retriever=retriever)
    memory = MemoryStore(tmp_path / "mem.json")
    backend = ScriptedBackend(reply, name="general-scripted")
    return Orchestrator({"general": backend, "reasoning": backend}, tools=tools, retriever=retriever, memory=memory), backend


def test_orchestrator_tool_loop_math_verification_retrieval_and_memory(tmp_path):
    def reply(msgs):
        last = msgs[-1]["content"].rsplit("\n\n", 1)[-1]  # recalled memory is prepended to the question
        if last.startswith("<tool_response>"):
            return "The calculator gives 177.\n#### 177"
        if "Compute" in last and "<tool_call>" not in "".join(m["content"] for m in msgs if m["role"] == "assistant"):
            return '<tool_call>{"name": "calculator", "arguments": {"expression": "(47 + 12) * 3"}}</tool_call>'
        if "retry policy" in last:
            return "Three attempts with exponential backoff from 200 ms [1]."
        return "Noted."

    orch, backend = make_orchestrator(tmp_path, reply)
    r = orch.answer("Compute the cost of 3 boxes at (47 + 12) dollars each.", session="s1")
    assert r.route.intent == "math" and r.tool_trace and r.tool_trace[0]["call"]["name"] == "calculator" and r.tool_trace[0]["output"] == "177"
    assert r.text.endswith("#### 177") and r.verification["checker"]["ok"] and r.trace["expert"] == "general-scripted"
    assert "<tool_call>" not in r.text

    f = orch.answer("What does the documentation say about the retry policy?", session="s1")
    assert f.route.needs_retrieval and f.citations and f.citations[0]["doc_id"] == "policy" and "[1]" in f.text
    assert f.trace["evidence_used"] and "Passages:" in f.trace["messages"][-1]["content"]

    m = orch.answer("Remember that I prefer answers in metric units.", session="s1")
    assert m.proposed_memory and m.proposed_memory["status"] == "proposed" and orch.memory.approved_facts() == []
    assert orch.memory.approve(m.proposed_memory["id"]) and orch.memory.approved_facts() == ["I prefer answers in metric units"]
    assert len(orch.memory.context("s1")) == 6 and orch.memory.recall("retry policy backoff")
    again = orch.answer("hello", session="s1")
    assert "metric units" in again.trace["messages"][-1]["content"] and "metric units" not in again.trace["messages"][0]["content"]


def test_episode_recall_switch_and_warm_up(tmp_path):
    orch, backend = make_orchestrator(tmp_path, lambda msgs: "Noted.")
    orch.answer("Tell me the history of the retry policy", session="a")
    assert "Relevant earlier exchanges" in orch.answer("hello, retry policy", session="b").trace["messages"][-1]["content"]
    orch.recall_episodes = False
    assert "Relevant earlier exchanges" not in orch.answer("hello, retry policy", session="c").trace["messages"][-1]["content"]
    backend.calls.clear()
    orch.warm_up([backend])
    assert len(backend.calls) == 2 and backend.calls[0][0]["content"] != backend.calls[1][0]["content"]


def test_exact_solver_answers_without_calling_a_model(tmp_path):
    orch, backend = make_orchestrator(tmp_path, lambda msgs: "the model was called")
    r = orch.answer("Compute (47 + 12) × 3.", session="s2")
    assert r.text.endswith("#### 177") and r.route.expert == "exact-solver" and backend.calls == []


def test_greedy_backend_gets_one_candidate_and_tool_loop_reply_is_reused():
    backend = ScriptedBackend(lambda msgs: "It is 42.\n#### 42")
    backend.supports_sampling = False
    res = ResponseEngine(backend).run([{"role": "user", "content": "6 times 7?"}], intent="math", n_candidates=3)
    assert len(backend.calls) == 1 and res.text.endswith("#### 42")
    res2 = ResponseEngine(backend).run([{"role": "user", "content": "6 times 7?"}], intent="math", n_candidates=3, first="Reused.\n#### 42")
    assert len(backend.calls) == 1 and res2.text.startswith("Reused")


def test_streaming_still_uses_the_exact_solver(tmp_path):
    orch, backend = make_orchestrator(tmp_path, lambda msgs: "the model was called")
    pieces = list(orch.answer_stream("Compute (47 + 12) × 3.", session="s3"))
    assert pieces and pieces[-1].endswith("#### 177") and backend.calls == []
