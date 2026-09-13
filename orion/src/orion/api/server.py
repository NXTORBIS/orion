"""HTTP API gateway (standard library only).

    POST /v1/chat/completions   OpenAI-style {messages, session?} -> answer (+ orion.trace_id, citations)
    GET  /v1/models             backends currently configured
    GET  /v1/memory             approved facts, proposed facts, episodes
    POST /v1/memory/approve     {id, text?}
    POST /v1/memory/delete      {id} | {episode_id} | {clear: "all"|"long_term"|"episodes"}
    GET  /v1/trace/<id>         full internal trace of one answer (audit; not shown in the chat UI)
    GET  /health
    GET  /                      the chat page

    .venv/Scripts/python.exe -m orion.api.server configs/system/laptop.yaml [--dry-run]
"""

from __future__ import annotations

import json
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .app import System, build_system

STATIC = Path(__file__).parent / "static"


def make_handler(system: System):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "ORION/0.1"

        def _send(self, status: int, body: Any, content_type: str = "application/json") -> None:
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type + ("; charset=utf-8" if "text" in content_type or "json" in content_type else ""))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self) -> dict[str, Any]:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

        def log_message(self, fmt, *args):  # quieter default logging
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def do_GET(self) -> None:
            path = self.path.split("?")[0]
            if path == "/health":
                return self._send(200, {"status": "ok", "backends": list(system.orchestrator.backends)})
            if path == "/v1/models":
                return self._send(200, {"data": [{"id": n, "backend": getattr(b, "name", n)} for n, b in system.orchestrator.backends.items()]})
            if path == "/v1/memory":
                mem = system.orchestrator.memory
                return self._send(200, {"approved": [f for f in mem.long_term if f["status"] == "approved"], "proposed": mem.pending(),
                                        "episodes": mem.episodes[-50:]})
            if path.startswith("/v1/trace/"):
                t = system.traces.get(path.rsplit("/", 1)[-1])
                return self._send(200, t) if t else self._send(404, {"error": "unknown trace"})
            if path in ("/", "/index.html"):
                return self._send(200, (STATIC / "index.html").read_bytes(), "text/html")
            return self._send(404, {"error": "not found"})

        def do_POST(self) -> None:
            path = self.path.split("?")[0]
            try:
                body = self._body()
            except json.JSONDecodeError:
                return self._send(400, {"error": "invalid JSON"})
            mem = system.orchestrator.memory
            if path == "/v1/chat/completions":
                messages = body.get("messages") or []
                user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), None)
                if not user:
                    return self._send(400, {"error": "no user message"})
                session = body.get("session") or body.get("user") or "default"
                with lock:  # one generation at a time on this machine
                    r = system.orchestrator.answer(user, session=session)
                tid = uuid.uuid4().hex[:12]
                system.traces[tid] = {"id": tid, "route": r.route.__dict__, "tool_trace": r.tool_trace, "verification": r.verification, "trace": r.trace}
                return self._send(200, {"id": f"chatcmpl-{tid}", "object": "chat.completion", "model": r.trace["expert"],
                                        "choices": [{"index": 0, "message": {"role": "assistant", "content": r.text}, "finish_reason": "stop"}],
                                        "orion": {"trace_id": tid, "intent": r.route.intent, "expert": r.route.expert, "tools_used": [t["call"].get("name") for t in r.tool_trace if isinstance(t["call"], dict)],
                                                  "citations": r.citations, "verified": r.verification.get("ok"), "proposed_memory": r.proposed_memory}})
            if path == "/v1/memory/approve":
                return self._send(200, {"ok": mem.approve(body.get("id", ""), body.get("text"))})
            if path == "/v1/memory/delete":
                if body.get("clear"):
                    mem.clear(body["clear"])
                    return self._send(200, {"ok": True})
                if body.get("episode_id"):
                    return self._send(200, {"ok": mem.forget_episode(body["episode_id"])})
                return self._send(200, {"ok": mem.delete(body.get("id", ""))})
            return self._send(404, {"error": "not found"})

    return Handler


def serve(system: System, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), make_handler(system))
    return httpd


def main(argv: list[str]) -> None:
    config = argv[0] if argv else "configs/system/laptop.yaml"
    system = build_system(config, dry_run="--dry-run" in argv)
    host, port = system.config.get("server", {}).get("host", "127.0.0.1"), int(system.config.get("server", {}).get("port", 8765))
    httpd = serve(system, host, port)
    print(f"ORION API on http://{host}:{port}  (backends: {list(system.orchestrator.backends)})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        system.close()


if __name__ == "__main__":
    main(sys.argv[1:])
