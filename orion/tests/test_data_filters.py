from orion.data.dedup import ExactDedup, NearDedup
from orion.data.heuristics import HeuristicFilter, check, dup_ngram_char_frac
from orion.data.pii import PIIFilter, find_pii, iban_ok, luhn_ok
from orion.data.provenance import ProvenanceGate, restricted_reason
from orion.data.schema import Record

GOOD_TEXT = (
    "The committee reviewed the proposal and agreed that the new library should open in the spring. "
    "Members noted that the building has been renovated with better lighting, and that funding for "
    "children's programs will continue through the next three years. Several residents asked whether "
    "the parking lot would be expanded, and the chair explained that a traffic study is under way."
)


def rec(text=GOOD_TEXT, source="openr1-math-220k", generators=("DeepSeek-R1",), split="train", id="r1", lang=""):
    meta = {"split": split}
    if lang:
        meta["lang"] = lang
    return Record(id=id, text=text, source=source, license="Apache-2.0", generators=list(generators), meta=meta)


def run(stage, *records):
    return list(stage.process(records))


# ---------------- provenance ----------------
REGISTRY = {
    "gsm8k": {"status": "selected", "use": "train split -> small math SFT; test split -> decontamination index only"},
    "gsm8k-platinum": {"status": "selected", "use": "eval"},
    "tulu-3-sft-mixture": {"status": "excluded", "reason": "GPT-4o / Claude outputs"},
    "openr1-math-220k": {"status": "candidate", "use": "train"},
}


def test_restricted_generators():
    for g in ["gpt-4o", "GPT-5.6 Sol", "claude-3.7-sonnet", "Gemini 2.5 Pro", "Llama-3.3-70B-Instruct",
              "gemma-3-27b-it", "gemma-3n-E4B", "Qwen2.5-72B-Instruct", "o3-mini", "grok-4"]:
        assert restricted_reason(g), g
    for g in ["gpt-oss-120b", "DeepSeek-R1", "Qwen3-235B-A22B", "Qwen2.5-32B", "gemma-4-31b", "QwQ-32B",
              "Kimi-K2", "Olmo-3-32B", "human", "web", "llama.cpp"]:
        assert restricted_reason(g) is None, g


def test_provenance_gate():
    gate = ProvenanceGate(REGISTRY)
    assert run(gate, rec())[0].kept
    assert "unregistered" in run(gate, rec(source="mystery"))[0].drop_reason
    assert "excluded" in run(gate, rec(source="tulu-3-sft-mixture"))[0].drop_reason
    assert "not registered for training" in run(gate, rec(source="gsm8k-platinum", generators=["human"]))[0].drop_reason
    assert "evaluation split" in run(gate, rec(source="gsm8k", generators=["human"], split="test"))[0].drop_reason
    assert run(gate, rec(source="gsm8k", generators=["human"], split="train"))[0].kept
    assert "restricted generator" in run(gate, rec(generators=["DeepSeek-R1", "gpt-4o"]))[0].drop_reason
    assert "generator unknown" in run(gate, rec(generators=["unknown"]))[0].drop_reason
    eval_gate = ProvenanceGate(REGISTRY, purpose="eval")
    assert run(eval_gate, rec(source="gsm8k-platinum", generators=["human"], split="test"))[0].kept


def test_dropped_records_pass_through_untouched():
    r = rec()
    r.drop("earlier", "reason")
    out = run(ProvenanceGate({}), r)[0]
    assert (out.dropped_by, out.drop_reason) == ("earlier", "reason")


# ---------------- PII ----------------
def kinds(text):
    return sorted(k for _, _, k in find_pii(text))


def test_checksums():
    assert luhn_ok("4111111111111111") and not luhn_ok("4111111111111112")
    assert iban_ok("GB82 WEST 1234 5698 7654 32") and not iban_ok("GB82 WEST 1234 5698 7654 33")


def test_detects_structured_pii():
    text = ("Mail jane.doe@example.com or call +1 415-555-0132. Card 4111 1111 1111 1111, "
            "IBAN GB82 WEST 1234 5698 7654 32, SSN 123-45-6789, server 192.168.10.24.")
    assert kinds(text) == sorted(["EMAIL", "PHONE", "CARD_NUMBER", "IBAN", "US_SSN", "IP_ADDRESS"])


def test_no_pii_in_ordinary_numbers():
    text = "On 2024-01-15 the population was 10 000 000; ISBN 978-3-16-148410-0; Python 3.12.14; pi is 3.14159."
    assert kinds(text) == []


def test_pii_filter_redacts_and_drops_dumps():
    out = run(PIIFilter(), rec(text="Contact jane.doe@example.com about the results. " + GOOD_TEXT))[0]
    assert out.kept and "<EMAIL>" in out.text and "example.com" not in out.text
    dump = rec(text=" ".join(f"user{i}@mail.com" for i in range(30)))
    assert "PII density" in run(PIIFilter(), dump)[0].drop_reason


# ---------------- heuristics ----------------
def test_good_text_passes():
    assert check(GOOD_TEXT, "eng_Latn") is None


def test_heuristic_rules_fire():
    assert "too short" in check("Buy the thing now.", "eng_Latn")
    assert "spam terms" in check(GOOD_TEXT + " casino casino buy now click here viagra", "eng_Latn")
    assert "URLs per 100 words" in check(GOOD_TEXT + " " + " ".join(f"https://x.example/{i}" for i in range(10)), "eng_Latn")
    repeated = "\n".join(["Great deals on shoes today"] * 10 + [GOOD_TEXT])
    assert "duplicate-line" in check(repeated, "eng_Latn")
    assert "English stop words" in check(" ".join(["alpha beta gamma delta epsilon"] * 12), "eng_Latn")
    assert dup_ngram_char_frac("a b c d e a b c d e".split(), 5) == 1.0


def test_heuristic_filter_removes_boilerplate_lines_and_skips_word_rules_for_cjk():
    r = run(HeuristicFilter(), rec(text=GOOD_TEXT + "\nThis site uses cookies to improve your experience.", lang="eng_Latn"))[0]
    assert r.kept and "cookies" not in r.text and r.meta["boilerplate_lines_removed"] == 1
    assert run(HeuristicFilter(), rec(text="委员会审查了该提案，并同意新图书馆应在春季开放。", lang="cmn_Hani"))[0].kept


# ---------------- dedup ----------------
def test_exact_and_near_dedup():
    a = rec(id="a")
    b = rec(id="b", text=GOOD_TEXT.upper().replace(" ", "  "))  # same after normalization
    c = rec(id="c", text=GOOD_TEXT.replace("spring", "summer"))  # near duplicate
    d = rec(id="d", text="An entirely different paragraph about volcanic soil chemistry and crop rotation in Iceland.")
    exact = run(ExactDedup(), a, b, c, d)
    assert [r.kept for r in exact] == [True, False, True, True]
    assert exact[1].drop_reason == "exact duplicate of a"
    near = run(NearDedup(), *exact)
    assert [r.kept for r in near] == [True, False, False, True]
    assert near[2].drop_reason == "near duplicate of a"
