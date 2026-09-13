from collections import Counter
from pathlib import Path

import yaml

from orion.data.heuristics import HeuristicConfig, check
from orion.synth.math import TEMPLATES, build_split, generate, make_item
from orion.verify.math import equivalent, extract_final_answer, verify_math

ROOT = Path(__file__).resolve().parents[1]


def test_synth_profile_heuristics_keep_math_text():
    """Regression: web-text thresholds rejected 89% of math items (numbers are not 'words')."""
    thresholds = yaml.safe_load((ROOT / "configs/data/synth_math_v1.yaml").read_text(encoding="utf-8"))["stages"]["heuristics"]["thresholds"]
    cfg = HeuristicConfig(**thresholds)
    items, _ = generate(120, 9_000_000)
    reasons = [check(it.text, "und_Latn", cfg) for it in items]
    kept = sum(r is None for r in reasons)
    assert kept >= 0.95 * len(items), Counter(r for r in reasons if r)
    web_cfg = HeuristicConfig()
    assert sum(check(it.text, "und_Latn", web_cfg) is None for it in items) < kept  # the web profile is stricter, by design


def test_extraction_conventions():
    assert extract_final_answer("Step 1 ... so the total is 42.\n#### 42") == ("42", "hash")
    assert extract_final_answer("Therefore the answer is \\boxed{\\frac{3}{4}}.")[0] == "\\frac{3}{4}"
    assert extract_final_answer("Final answer: 17 apples")[0] == "17 apples"
    assert extract_final_answer("We get 3 then 5 and finally 8.") == ("8", "last-number")
    assert extract_final_answer("no digits here") == (None, "none")


def test_equivalence_methods():
    assert equivalent("1,000", "1000") == (True, "exact")
    assert equivalent("0.5", "1/2") == (True, "numeric")
    assert equivalent("$12.50", "12.5")[0] and equivalent("12.5", "12.500001")[0]
    assert not equivalent("12.5", "12.6")[0]
    assert equivalent("2*pi", "2π".replace("π", "*pi"))[0]
    assert equivalent("sqrt(8)", "2*sqrt(2)") == (True, "symbolic")
    assert equivalent("x^2 - 1", "(x-1)(x+1)")[0]
    assert not equivalent("sqrt(8)", "3")[0]
    assert equivalent("25%", "25")[0]


def test_verify_math_end_to_end():
    v = verify_math("Alice has 3, Bob has 4, together 7.\n#### 7", "7")
    assert v.ok and v.extraction == "hash" and v.comparison == "exact"
    assert not verify_math("I think it is 8.\n#### 8", "7").ok
    assert verify_math("The probability is 5/36.", "5/36").ok  # falls back to the last number


def test_every_template_verifies_across_seeds():
    for fam in TEMPLATES:
        items = [make_item(fam, s) for s in range(40)]
        bad = [i.verification for i in items if not i.verified]
        assert not bad, f"{fam}: {bad[:3]}"
        assert all(i.solution.endswith(f"#### {i.answer}") for i in items)
        assert all(verify_math(i.solution, i.answer).ok for i in items)


def test_generate_and_split_are_deterministic_and_disjoint():
    a, _ = generate(24, 0)
    b, _ = generate(24, 0)
    assert [i.problem for i in a] == [i.problem for i in b]
    full, rem = divmod(24, len(TEMPLATES))  # round-robin: first `rem` families get one extra
    assert Counter(i.family for i in a) == {f: full + (1 if k < rem else 0) for k, f in enumerate(TEMPLATES)}
    train, test, report = build_split(60, 24)
    assert len(train) == 60 and len(test) == 24
    assert not ({t.problem for t in train} & {t.problem for t in test})
    assert set(report) == {"rejected_train", "rejected_test", "test_overlap_removed"} and report["test_overlap_removed"] <= 12
    dice = [make_item("dice", s).problem for s in range(60)]
    assert len(set(dice)) >= 20  # four event types (28 distinct problems possible), not just nine sums
    sft = train[0].to_sft()
    assert sft["prompt"][0]["role"] == "user" and sft["completion"][0]["role"] == "assistant"
    assert sft["prompt"][0]["content"].endswith("#### <answer>'.") and sft["completion"][0]["content"].endswith(train[0].answer)
