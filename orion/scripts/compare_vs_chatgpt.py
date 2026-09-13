"""ORION vs ChatGPT on a fixed question set with checkable answers.

Scoring is automatic and blind: the scorer sees only a response and its gold answer, never which
system produced it. The questions come from ORION's own procedural sets, so results say nothing
about standard benchmarks, open-ended writing, coding, or instruction following.

    python scripts/compare_vs_chatgpt.py build
    python scripts/compare_vs_chatgpt.py orion                 # needs the ORION API on :8765
    python scripts/compare_vs_chatgpt.py chatgpt-api           # needs OPENAI_API_KEY with credits
    python scripts/compare_vs_chatgpt.py chatgpt-paste-prompt  # writes a prompt to paste into ChatGPT
    python scripts/compare_vs_chatgpt.py chatgpt-paste-import  # reads the pasted reply
    python scripts/compare_vs_chatgpt.py score
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orion.evals.metrics import bootstrap_ci, paired_bootstrap_diff  # noqa: E402
from fractions import Fraction  # noqa: E402

from orion.verify.math import normalize_answer, to_number, verify_math  # noqa: E402

OUT = ROOT / "runs" / "evals" / "vs-chatgpt"
ITEMS = OUT / "items.jsonl"
SETS = {"math": "synth_math", "sequences": "synth_sequences", "systems": "synth_systems",
        "knowledge": "synth_knowledge", "reasoning": "synth_reasoning"}
PER_SET = 10
# The knowledge/reasoning generators produced some wrong, ambiguous, or open-ended gold answers,
# so these two groups use hand-reviewed items (id -> gold, scorer) instead of a random sample.
CURATED = {
    "knowledge": {"know-cult-50200": ("Leonardo da Vinci|da Vinci", "text"), "know-hist-55100": ("1912", "text"),
                  "know-cult-15200": ("Piano", "text"), "know-tech-15200": ("Central Processing Unit", "text"),
                  "know-geo-100": ("Pacific", "text"), "know-tech-100": ("Tim Berners-Lee|Berners-Lee", "text"),
                  "know-sci-5100": ("Cell", "text"), "know-geo-20100": ("Paris", "text"),
                  "know-sci-100": ("206", "numeric"), "know-sci-20100": ("Au", "text")},
    "reasoning": {"reason-analogy-48300": ("end|ending", "text"), "reason-sense-12200": ("Yes", "text"),
                  "reason-logic-32100": ("No", "text"), "reason-analogy-40100": ("eat", "text"),
                  "reason-causal-52200": ("No", "text"), "reason-sense-16200": ("No", "text"),
                  "reason-multistep-12200": ("37.50", "numeric"), "reason-analogy-4100": ("sad", "text"),
                  "reason-analogy-100": ("dark|darkness", "text"), "reason-multistep-100": ("4", "numeric")},
}
SEED = 20260914
SUFFIX = "\n\nGive your final answer on the last line in the form: #### <answer>"
CHATGPT_MODEL = "chat-latest"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def build() -> None:
    rng = random.Random(SEED)
    items = []
    for group, name in SETS.items():
        rows = read_jsonl(ROOT / "data" / "raw" / name / "test.jsonl")
        if group in CURATED:
            by_id = {r["id"]: r for r in rows}
            for rid, (gold, scorer) in CURATED[group].items():
                r = by_id[rid]
                items.append({"id": rid, "group": group, "family": r.get("family"), "question": r["problem"].strip(),
                              "gold": gold, "scorer": scorer, "prompt": r["problem"].strip() + SUFFIX})
            continue
        if group == "math":
            rows = [r for r in rows if r.get("verified")]
        by_family = defaultdict(list)
        for r in rows:
            by_family[r.get("family", "all")].append(r)
        for fam in by_family.values():
            rng.shuffle(fam)
        picked, fams = [], sorted(by_family)
        while len(picked) < PER_SET and any(by_family[f] for f in fams):
            for f in fams:
                if by_family[f] and len(picked) < PER_SET:
                    picked.append(by_family[f].pop())
        for r in picked:
            items.append({"id": r["id"], "group": group, "family": r.get("family"), "question": r["problem"].strip(),
                          "gold": str(r["answer"]).strip(), "prompt": r["problem"].strip() + SUFFIX})
    OUT.mkdir(parents=True, exist_ok=True)
    ITEMS.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
    print(f"{len(items)} items -> {ITEMS}")
    for i in items:
        print(f"[{i['group']}/{i['family']}] {i['id']}\n  Q: {i['question']}\n  gold: {i['gold']}")


def post_json(url: str, body: dict, headers: dict | None = None, timeout: int = 1800) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **(headers or {})})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def run_system(system: str, ask) -> None:
    path = OUT / f"{system}.jsonl"
    done = {r["id"] for r in read_jsonl(path)}
    items = [i for i in read_jsonl(ITEMS) if i["id"] not in done]
    print(f"{system}: {len(done)} done, {len(items)} to go", flush=True)
    for n, it in enumerate(items, 1):
        t0 = time.time()
        try:
            text, meta = ask(it)
        except (urllib.error.URLError, TimeoutError, KeyError) as e:
            detail = e.read()[:300] if isinstance(e, urllib.error.HTTPError) else ""
            print(f"stopped at {it['id']}: {e} {detail}", flush=True)
            return
        append_jsonl(path, {"id": it["id"], "response": text, "seconds": round(time.time() - t0, 1), **meta})
        print(f"[{n}/{len(items)}] {it['id']} {round(time.time() - t0)}s", flush=True)


def ask_orion(it: dict) -> tuple[str, dict]:
    r = post_json("http://127.0.0.1:8765/v1/chat/completions",
                  {"messages": [{"role": "user", "content": it["prompt"]}], "session": f"vs-chatgpt-{it['id']}"})
    return r["choices"][0]["message"]["content"], {"model": r.get("model"), "expert": r.get("orion", {}).get("expert")}


def ask_chatgpt(it: dict) -> tuple[str, dict]:
    r = post_json("https://api.openai.com/v1/chat/completions",
                  {"model": CHATGPT_MODEL, "messages": [{"role": "user", "content": it["prompt"]}]},
                  {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]}, timeout=300)
    return r["choices"][0]["message"]["content"], {"model": r.get("model")}


def paste_prompt() -> None:
    items = read_jsonl(ITEMS)
    lines = ["Answer each of the following questions independently. For each one, reply on its own line in exactly "
             "this form, with no other text:", "Q<number> #### <answer>", ""]
    lines += [f"Q{n}. {it['question']}" for n, it in enumerate(items, 1)]
    path = OUT / "chatgpt_paste_prompt.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Paste the contents of {path} into ChatGPT, then save its full reply to {OUT / 'chatgpt_paste_reply.txt'}")


def paste_import() -> None:
    items = read_jsonl(ITEMS)
    reply = (OUT / "chatgpt_paste_reply.txt").read_text(encoding="utf-8")
    answers = {int(m.group(1)): m.group(2).strip() for m in re.finditer(r"^\s*\**Q(\d+)\**[.:)]?\s*#+\s*(.+?)\s*$", reply, re.M)}
    path = OUT / "chatgpt.jsonl"
    path.unlink(missing_ok=True)
    for n, it in enumerate(items, 1):
        append_jsonl(path, {"id": it["id"], "response": f"#### {answers[n]}" if n in answers else "", "model": "ChatGPT (pasted)"})
    print(f"imported {len(answers)}/{len(items)} answers -> {path}")


def final_line(text: str) -> str:
    m = re.findall(r"####\s*(.+)", text)
    return (m[-1] if m else text.strip().splitlines()[-1] if text.strip() else "").strip()


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9= ]", "", s.lower().replace("*", "")).strip()


def math_ok(response: str, gold: str) -> bool:
    text = response.replace("π", "pi")
    finals = re.findall(r"####\s*([^\n]+)", text)
    if finals:
        ans = re.sub(r"^\s*[a-z]\s*=\s*", "", finals[-1].strip(), flags=re.I)
        truncated = re.fullmatch(r"(-?\d+\.(\d+))\s*(?:\.\.\.|…)", ans)
        g = to_number(normalize_answer(gold))
        if truncated and g is not None:
            pred, step = Fraction(truncated.group(1)), Fraction(1, 10 ** len(truncated.group(2)))
            rounded = abs(pred - g) <= step / 2
            cut_off = 0 <= (g - pred if g >= 0 else pred - g) < step
            return rounded or cut_off
        text = f"#### {ans}"
    return verify_math(text, gold).ok


def score_item(it: dict, response: str) -> bool:
    if not response.strip():
        return False
    group, gold = it["group"], it["gold"]
    if group in ("math", "sequences") or it.get("scorer") == "numeric":
        return math_ok(response, gold)
    ans = final_line(response)
    if group == "systems":
        want = dict(re.findall(r"([xyz])\s*=\s*(-?\d+(?:\.\d+)?)", gold))
        got = dict(re.findall(r"([xyz])\s*=\s*(-?\d+(?:\.\d+)?)", ans))
        return bool(want) and all(k in got and float(got[k]) == float(v) for k, v in want.items())
    a = norm(ans)
    for g in map(norm, gold.split("|")):
        if g in ("yes", "no"):
            if a.split()[:1] == [g]:
                return True
        elif g and (g == a or re.search(rf"\b{re.escape(g)}\b", a)):
            return True
    return False


def score() -> None:
    items = read_jsonl(ITEMS)
    systems = {s: {r["id"]: r for r in read_jsonl(OUT / f"{s}.jsonl")} for s in ("orion", "chatgpt")}
    common = [it for it in items if all(it["id"] in systems[s] for s in systems)]
    if not common:
        sys.exit("no items answered by both systems yet")
    flags = {s: [score_item(it, systems[s][it["id"]]["response"]) for it in common] for s in systems}
    lines = [f"# ORION vs ChatGPT — {len(common)} items answered by both", "",
             "Questions are from ORION's own procedural test sets (not a standard benchmark). Scoring is automatic "
             "against gold answers and never sees which system answered.", "",
             "| Group | n | ORION | ChatGPT |", "|---|---|---|---|"]
    for group in list(SETS) + ["ALL"]:
        idx = [k for k, it in enumerate(common) if group == "ALL" or it["group"] == group]
        if not idx:
            continue
        cell = {}
        for s in systems:
            f = [flags[s][k] for k in idx]
            lo, hi = bootstrap_ci(f)
            cell[s] = f"{100 * sum(f) / len(f):.0f}% [{100 * lo:.0f}, {100 * hi:.0f}]"
        lines.append(f"| {group} | {len(idx)} | {cell['orion']} | {cell['chatgpt']} |")
    d = paired_bootstrap_diff(flags["orion"], flags["chatgpt"])
    lines += ["", f"ChatGPT − ORION: {100 * d['diff']:+.0f} points, 95% CI [{100 * d['ci'][0]:+.0f}, {100 * d['ci'][1]:+.0f}]; "
              f"ChatGPT-only correct {d['wins']}, ORION-only correct {d['losses']}, same {d['ties']}.", ""]
    for s in systems:
        secs = [systems[s][it["id"]].get("seconds") for it in common if systems[s][it["id"]].get("seconds") is not None]
        models = sorted({str(systems[s][it["id"]].get("model")) for it in common})
        if secs:
            lines.append(f"- {s}: median {sorted(secs)[len(secs) // 2]:.0f}s per answer; models: {', '.join(models)}")
        else:
            lines.append(f"- {s}: timing not recorded; models: {', '.join(models)}")
    rows = [{"id": it["id"], "group": it["group"], "gold": it["gold"],
             **{f"{s}_ok": flags[s][k] for s in systems}, **{f"{s}_answer": final_line(systems[s][it["id"]]["response"]) for s in systems}}
            for k, it in enumerate(common)]
    (OUT / "scored.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    actions = {"build": build, "orion": lambda: run_system("orion", ask_orion),
               "chatgpt-api": lambda: run_system("chatgpt", ask_chatgpt), "chatgpt-paste-prompt": paste_prompt,
               "chatgpt-paste-import": paste_import, "score": score}
    if cmd not in actions:
        sys.exit(__doc__)
    actions[cmd]()
