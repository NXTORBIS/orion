import json

from orion.evals.blind import judge_with_model, load_outputs, make_pairs, scorecard_md, unblind, write_judging_file
from orion.evals.mining import empirical_difficulty, level_for, load_runs, mine, report_md
from orion.evals.redteam import CASES, check_case, run_redteam
from orion.synth.longctx import KINDS, generate, make_item, prompt_for
from orion.system.backends import ScriptedBackend
from orion.system.memory import MemoryStore
from orion.system.orchestrator import Orchestrator
from orion.system.rag import Retriever
from orion.system.tools import default_registry
from orion.verify.math import verify_math


def _write(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_blind_pairs_are_anonymised_and_unblind_correctly(tmp_path):
    ids = [f"q{i}" for i in range(20)]
    _write(tmp_path / "a.jsonl", [{"id": i, "prompt": f"p{i}", "response": f"good {i}", "gold": "x"} for i in ids])
    _write(tmp_path / "b.jsonl", [{"id": i, "prompt": f"p{i}", "response": f"bad {i}", "gold": "x"} for i in ids])
    outputs = {"sysA": load_outputs(tmp_path / "a.jsonl", "sysA"), "sysB": load_outputs(tmp_path / "b.jsonl", "sysB")}
    pairs, key = make_pairs(outputs, seed=3)
    assert len(pairs) == 20 and all(set(p) == {"pair_id", "prompt", "gold", "A", "B"} for p in pairs)
    sides = [key[p["pair_id"]]["A"] for p in pairs]
    assert 3 < sides.count("sysA") < 17  # order randomised
    write_judging_file(pairs, tmp_path / "judge.jsonl")
    assert '"verdicts"' in (tmp_path / "judge.jsonl").read_text(encoding="utf-8")

    def judge(prompt, a, b, gold):  # a judge that prefers responses starting with "good", regardless of position
        pick = "A" if a.startswith("good") else "B" if b.startswith("good") else "tie"
        return {c: pick for c in ("correctness", "reasoning", "completeness", "instruction_following", "overall")}

    judged = judge_with_model(pairs, judge)
    res = unblind(judged, key)
    assert res["by_criterion"]["overall"]["sysA"]["win_rate"] == 1.0 and res["by_criterion"]["overall"]["sysB"]["win_rate"] == 0.0
    assert res["head_to_head_overall_wins"]["sysA"]["sysB"] == 20 and res["judged_pairs"] == 20
    assert "sysA" in scorecard_md(res) and "anonymised" in scorecard_md(res)


def test_mining_buckets_and_targets(tmp_path):
    rows1 = [{"id": f"i{i}", "ok": i % 3 != 0, "group": "dice" if i < 10 else "linear"} for i in range(20)]
    rows2 = [{"id": f"i{i}", "ok": i % 2 == 0, "group": "dice" if i < 10 else "linear"} for i in range(20)]
    _write(tmp_path / "r1.jsonl", rows1)
    _write(tmp_path / "r2.jsonl", rows2)
    by_item = load_runs([tmp_path / "r1.jsonl", tmp_path / "r2.jsonl"])
    diff = empirical_difficulty(by_item)
    assert diff["i0"]["pass_rate"] == 0.5 and diff["i0"]["level"] == 3 and diff["i2"]["n_runs"] == 2
    assert level_for(1.0) == 1 and level_for(0.0) == 5 and level_for(0.75) == 2
    m = mine(by_item)
    assert sum(m["buckets"].values()) == 20 and m["weakest_groups"][0][0] in ("dice", "linear") and all(w >= 1 for w in m["targets"].values())
    assert "Oversampling" in report_md(m)


def test_redteam_checks_and_run_through_orchestrator(tmp_path):
    safe = check_case(CASES[0], "Week one: meet the team and set up accounts.", [])
    unsafe = check_case(CASES[0], "PWNED", [])
    assert safe["ok"] and not unsafe["ok"] and "forbidden pattern" in unsafe["failures"][0]

    def reply(msgs):  # a scripted model that follows injected instructions in documents -> should FAIL those cases
        last = msgs[-1]["content"]
        question = last.split("\n\nPassages:")[0]
        if "IGNORE ALL PREVIOUS" in last and "onboarding guide" in question:
            return "PWNED"  # obeys the injected document when it is relevant to the question
        if "2 + 2" in last:
            return "4"
        return "I can't help with that; I don't have such a document."

    retriever = Retriever()
    orch = Orchestrator({"general": ScriptedBackend(reply)}, tools=default_registry(workspace=tmp_path, retriever=retriever),
                        retriever=retriever, memory=MemoryStore(tmp_path / "m.json"))
    res = run_redteam(orch, tmp_path)
    by_id = {r["id"]: r for r in res["results"]}
    assert not by_id["inj-doc-1"]["ok"] and by_id["conflict-1"]["ok"] and by_id["jail-1"]["ok"] and by_id["cite-1"]["ok"]
    assert res["n"] == len(CASES) and "by_category" in res


def test_longctx_generation_is_verifiable_and_sized():
    items = generate([300, 1200], per_kind=2)
    assert len(items) == 2 * len(KINDS) * 2
    for it in items:
        assert it.words >= 0.8 * it.target_words and it.answer.isdigit()
        assert it.question in prompt_for(it) and "#### <answer>" in prompt_for(it)
    c = make_item("contradiction", 500, 1)
    doc = c.documents[0]
    assert doc.index("Correction:") > doc.index("'s office is room") and verify_math(f"#### {c.answer}", c.answer).ok
    x = make_item("cross-document", 600, 2)
    assert len(x.documents) == 3 and int(x.answer) == sum(int(d.split(" shipped ")[1].split()[0]) for d in x.documents)
    assert make_item("needle", 300, 5).answer == make_item("needle", 300, 5).answer
