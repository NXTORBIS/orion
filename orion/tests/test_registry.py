from orion.registry import VersionCard, load_card, promote, save_card


def card(version, ok_by_task):
    return VersionCard(version=version, weights="Qwen/Qwen3.5-0.8B-Base", weights_owner="Alibaba", weights_license="Apache-2.0",
                       orion_modified=version != "base", regression_suite=ok_by_task)


def test_promotion_gate_requires_significant_gain_and_no_regression(tmp_path):
    n = 200
    base = card("base", {"math": {str(i): i % 4 == 0 for i in range(n)}, "code": {str(i): i % 2 == 0 for i in range(n)}})
    better = card("cand-better", {"math": {str(i): i % 4 in (0, 1) for i in range(n)}, "code": {str(i): i % 2 == 0 for i in range(n)}})
    d = promote(better, base)
    assert d["promote"] and d["overall"]["significant"] and better.status == "current" and base.status == "archived"

    base2 = card("base2", base.regression_suite)
    regress = card("cand-regress", {"math": {str(i): i % 4 in (0, 1) for i in range(n)}, "code": {str(i): i % 4 == 0 for i in range(n)}})
    d2 = promote(regress, base2)
    assert not d2["promote"] and "regression" in d2["reason"] and regress.status == "rejected" and base2.status == "candidate"

    same = card("cand-same", base.regression_suite)
    d3 = promote(same, base2)
    assert not d3["promote"] and "not significant" in d3["reason"]

    first = card("first", base.regression_suite)
    assert promote(first, None)["promote"] and first.status == "current"

    p = save_card(better, tmp_path)
    loaded = load_card(p)
    assert loaded.version == "cand-better" and loaded.promotion["promote"] and loaded.status == "current"
