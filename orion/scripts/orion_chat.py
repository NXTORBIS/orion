"""Terminal chat with the ORION system (local backends only).

    .venv/Scripts/python.exe scripts/orion_chat.py [configs/system/laptop.yaml] [--dry-run] [--trace]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orion.api.app import build_system  # noqa: E402


def main(argv: list[str]) -> None:
    cfg = next((a for a in argv if a.endswith((".yaml", ".yml"))), "configs/system/laptop.yaml")
    system = build_system(cfg, dry_run="--dry-run" in argv)
    show_trace = "--trace" in argv
    print(f"ORION ready. backends={list(system.orchestrator.backends)}  (type /memory, /approve <id>, /quit)")
    try:
        while True:
            try:
                text = input("\nyou> ").strip()
            except EOFError:
                break
            if not text:
                continue
            if text in ("/quit", "/exit"):
                break
            mem = system.orchestrator.memory
            if text == "/memory":
                print(json.dumps({"approved": mem.approved_facts(), "proposed": mem.pending()}, indent=2, ensure_ascii=False))
                continue
            if text.startswith("/approve "):
                print("approved" if mem.approve(text.split(maxsplit=1)[1]) else "no such fact")
                continue
            r = system.orchestrator.answer(text, session="cli")
            print(f"\norion> {r.text}")
            bits = [f"intent={r.route.intent}", f"expert={r.route.expert}"]
            if r.tool_trace:
                bits.append("tools=" + ",".join(t["call"].get("name", "?") for t in r.tool_trace if isinstance(t["call"], dict)))
            if r.citations:
                bits.append("sources=" + ",".join(f"[{c['n']}]{c['doc_id']}" for c in r.citations))
            if r.verification:
                bits.append(f"verified={r.verification.get('ok')}")
            print("   (" + " ".join(bits) + ")")
            if show_trace:
                print(json.dumps(r.trace, indent=1, ensure_ascii=False, default=str)[:3000])
    finally:
        system.close()


if __name__ == "__main__":
    main(sys.argv[1:])
