import json

import pytest

from orion.system.backends import LlamaServerBackend, ScriptedBackend
from orion.system.memory import MemoryStore
from orion.system.rag import Retriever, chunk_text, reciprocal_rank_fusion
from orion.system.tools import ToolRegistry, default_registry


# ---------------- tools ----------------
def test_tool_registry_parse_validate_execute(tmp_path):
    (tmp_path / "notes.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    reg = default_registry(workspace=tmp_path)
    assert {"calculator", "python", "read_file"} <= set(reg.tools)
    text = 'Let me compute. <tool_call>{"name": "calculator", "arguments": {"expression": "(47 + 12) * 3"}}</tool_call>'
    calls = ToolRegistry.parse_calls(text)
    assert len(calls) == 1
    r = reg.execute(calls[0])
    assert r.ok and r.output == "177"
    assert reg.execute('{"name": "calculator", "arguments": {"expression": "sqrt(8)"}}').output.startswith("2*sqrt(2) = 2.828")
    bad = reg.execute('{"name": "calculator", "arguments": {"expression": "__import__(\'os\')"}}')
    assert not bad.ok and bad.errors
    py = reg.execute('{"name": "python", "arguments": {"code": "print(sum(range(10)))"}}')
    assert py.ok and "45" in py.output
    rf = reg.execute('{"name": "read_file", "arguments": {"path": "notes.txt", "start_line": 2, "max_lines": 1}}')
    assert rf.ok and rf.output == "2: beta"
    esc = reg.execute('{"name": "read_file", "arguments": {"path": "../../secret.txt"}}')
    assert not esc.ok and "outside the workspace" in esc.errors[0]
    unknown = reg.execute('{"name": "launch_missiles", "arguments": {}}')
    assert not unknown.ok and "unknown tool" in unknown.errors[0]
    assert "<tool_call>" in reg.prompt_block() and "calculator" in reg.prompt_block()


# ---------------- rag ----------------
DOCS = {
    "iceland": "Volcanic soils in Iceland are rich in minerals. Farmers rotate barley with grasses. Greenhouses heated by geothermal water grow most vegetables.",
    "bicycle": "A bicycle chain transfers power from the pedals to the rear wheel. A clean, oiled chain wastes little energy; rust and grit increase friction.",
    "tides": "Tide pools on the rocky coast hold anemones and small crabs. Rangers lead walks at low tide and explain how creatures survive the sun.",
}


def test_chunking_and_bm25_retrieval_with_citations():
    assert len(chunk_text(" ".join(["w"] * 500), max_words=200, overlap=40)) == 3
    r = Retriever()
    for k, v in DOCS.items():
        r.add_document(k, v, {"title": k.title(), "lang": "en"})
    hits = r.retrieve("how does geothermal heat help farmers grow vegetables", k=2)
    assert hits and hits[0].chunk.doc_id == "iceland"
    ev = r.format_evidence(hits)
    assert ev.startswith("[1] (source: iceland, Iceland)") and "geothermal" in ev
    assert r.citations(hits)[0] == {"n": 1, "doc_id": "iceland", "chunk": 0, "meta": {"title": "Iceland", "lang": "en"}}
    assert r.retrieve("chain friction", k=1, filters={"title": "Tides"}) == []
    assert r.describe()["mode"].startswith("keyword-only")


def test_hybrid_fusion_with_dense_index():
    vocab = ["volcanic", "chain", "tide", "geothermal", "friction", "crabs"]

    def embed(texts):  # toy embedding: term-presence vector — deterministic and dependency-free
        return [[float(w in t.lower()) for w in vocab] for t in texts]

    r = Retriever(embed=embed)
    for k, v in DOCS.items():
        r.add_document(k, v)
    hits = r.retrieve("crabs at low tide", k=3)
    assert hits[0].chunk.doc_id == "tides" and hits[0].source == "hybrid"
    assert r.describe()["dense"]
    fused = reciprocal_rank_fusion([r.bm25.search("chain", 3), r.dense.search("chain", 3)])
    assert fused[0].chunk.doc_id == "bicycle"


# ---------------- memory ----------------
def test_memory_controls_and_recall(tmp_path):
    m = MemoryStore(tmp_path / "memory.json", short_term_window=3)
    for i in range(5):
        m.add_turn("s1", "user", f"turn {i}")
    assert [t["content"] for t in m.context("s1")] == ["turn 2", "turn 3", "turn 4"]
    fact = m.propose("The user prefers metric units.")
    assert m.approved_facts() == [] and m.pending()[0]["id"] == fact["id"]
    assert m.approve(fact["id"], "The user prefers metric units (SI).")
    assert m.approved_facts() == ["The user prefers metric units (SI)."]
    eid = m.record_episode("s1", "How do I convert 5 miles to km?", "5 miles is about 8.05 km.")
    assert m.recall("miles to kilometres conversion")[0]["id"] == eid
    prompt = m.memory_prompt("convert miles", "s1")
    assert "metric units" in prompt and "8.05 km" in prompt
    reloaded = MemoryStore(tmp_path / "memory.json")
    assert reloaded.approved_facts() == m.approved_facts() and reloaded.recall("miles")[0]["id"] == eid
    assert reloaded.forget_episode(eid) and reloaded.recall("miles") == []
    assert reloaded.delete(fact["id"]) and reloaded.approved_facts() == []
    m.scratch("t1")["plan"] = ["a", "b"]
    m.end_task("t1")
    assert m.working == {}
    m.clear()
    assert m.export() == {"long_term": [], "episodes": [], "sessions": {}}


# ---------------- backends ----------------
def test_scripted_backend_and_llama_server_client_shape():
    b = ScriptedBackend(lambda msgs: f"echo:{msgs[-1]['content']}")
    assert b.chat([{"role": "user", "content": "hi"}]) == "echo:hi" and len(b.calls) == 1
    srv = LlamaServerBackend("http://127.0.0.1:1")  # nothing listening
    assert not srv.healthy()
    with pytest.raises(Exception):
        srv.chat([{"role": "user", "content": "hi"}])
