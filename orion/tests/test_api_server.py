import json
import threading
import urllib.request

import yaml

from orion.api.app import build_system
from orion.api.server import serve
from orion.system.backends import ScriptedBackend


def _call(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if body else "GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode()) if r.headers.get("Content-Type", "").startswith("application/json") else r.read().decode()


def test_api_gateway_end_to_end(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/policy.md").write_text("The retry policy allows three attempts with exponential backoff starting at 200 ms.", encoding="utf-8")
    cfg = {"backends": {"general": {"kind": "hf", "model": "unused"}}, "tools": {"workspace": str(tmp_path)},
           "documents": {"dir": str(tmp_path / "docs")}, "memory": {"path": str(tmp_path / "mem.json")}}
    cfg_path = tmp_path / "system.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    def reply(msgs):
        last = msgs[-1]["content"]
        if "retry policy" in last:
            return "Three attempts with exponential backoff [1]."
        return "Hello!"

    system = build_system(cfg_path, backends={"general": ScriptedBackend(reply, name="scripted")})
    httpd = serve(system, "127.0.0.1", 0)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    try:
        assert _call(base + "/health")[1]["status"] == "ok"
        assert _call(base + "/v1/models")[1]["data"][0]["id"] == "general"
        html = _call(base + "/")[1]
        assert "<title>ORION</title>" in html
        status, out = _call(base + "/v1/chat/completions", {"messages": [{"role": "user", "content": "What does the documentation say about the retry policy?"}], "session": "t"})
        assert status == 200 and out["choices"][0]["message"]["content"].endswith("[1].")
        assert out["orion"]["citations"][0]["doc_id"] == "policy.md" and out["orion"]["intent"] == "factual"
        trace = _call(base + "/v1/trace/" + out["orion"]["trace_id"])[1]
        assert trace["route"]["needs_retrieval"] and trace["trace"]["evidence_used"]
        _, out2 = _call(base + "/v1/chat/completions", {"messages": [{"role": "user", "content": "Remember that my name is Sam."}], "session": "t"})
        fid = out2["orion"]["proposed_memory"]["id"]
        mem = _call(base + "/v1/memory")[1]
        assert mem["proposed"][0]["id"] == fid and mem["approved"] == []
        assert _call(base + "/v1/memory/approve", {"id": fid})[1]["ok"]
        assert _call(base + "/v1/memory")[1]["approved"][0]["text"] == "my name is Sam"
        assert _call(base + "/v1/memory/delete", {"clear": "all"})[1]["ok"]
        assert _call(base + "/v1/memory")[1] == {"approved": [], "proposed": [], "episodes": []}
    finally:
        httpd.shutdown()
