import json
import threading
import urllib.request

import yaml

from orion.api.app import build_system
from orion.api.server import serve
from orion.system.backends import ScriptedBackend


class StreamingBackend(ScriptedBackend):
    def chat_stream(self, messages, max_tokens=512, temperature=0.0):
        self.calls.append(messages)
        yield from ["Hel", "lo ", "there!"]


def _start(tmp_path, backend):
    cfg = {"backends": {"general": {"kind": "hf", "model": "unused"}}, "tools": {"workspace": str(tmp_path)},
           "memory": {"path": str(tmp_path / "mem.json")}}
    cfg_path = tmp_path / "system.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    httpd = serve(build_system(cfg_path, backends={"general": backend}), "127.0.0.1", 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def _stream(url, text, session="s"):
    body = {"messages": [{"role": "user", "content": text}], "session": session, "stream": True}
    req = urllib.request.Request(url + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.headers["Content-Type"].startswith("text/event-stream")
        return [line[6:] for line in r.read().decode("utf-8").splitlines() if line.startswith("data: ")]


def test_plain_chat_streams_pieces_then_metadata(tmp_path):
    backend = StreamingBackend(lambda msgs: "unused", name="streamer")
    httpd, base = _start(tmp_path, backend)
    try:
        events = _stream(base, "hello")
        assert events[-1] == "[DONE]"
        chunks = [json.loads(e) for e in events[:-1]]
        assert [c["choices"][0]["delta"].get("content") for c in chunks[:-1]] == ["Hel", "lo ", "there!"]
        final = chunks[-1]
        assert final["choices"][0]["finish_reason"] == "stop" and final["orion"]["intent"] == "chat"
        with urllib.request.urlopen(base + "/v1/memory", timeout=10) as r:
            assert len(json.loads(r.read())["episodes"]) == 1
        assert backend.calls[0][-1]["content"] == "hello"
    finally:
        httpd.shutdown()


def test_routes_that_need_verification_send_the_full_answer_once(tmp_path):
    backend = ScriptedBackend(lambda msgs: "6 × 7 = 42\n#### 42", name="scripted")
    httpd, base = _start(tmp_path, backend)
    try:
        events = _stream(base, "Compute the cost of 6 boxes at 7 dollars each.")  # plain "6 * 7" is answered by the exact solver
        chunks = [json.loads(e) for e in events[:-1]]
        assert [c["choices"][0]["delta"].get("content") for c in chunks[:-1]] == ["6 × 7 = 42\n#### 42"]
        assert chunks[-1]["orion"]["intent"] == "math"
    finally:
        httpd.shutdown()
