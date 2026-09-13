"""Assemble the ORION system from a config file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from orion.system.backends import HFBackend, LlamaServerBackend, ScriptedBackend, start_llama_server
from orion.system.memory import MemoryStore
from orion.system.orchestrator import Orchestrator
from orion.system.rag import Retriever
from orion.system.tools import default_registry
from orion.train.common import project_root


class System:
    def __init__(self, orchestrator: Orchestrator, config: dict[str, Any], processes: list | None = None):
        self.orchestrator, self.config, self.processes = orchestrator, config, processes or []
        self.traces: dict[str, dict[str, Any]] = {}

    def close(self) -> None:
        for p in self.processes:
            try:
                p.terminate()
            except Exception:
                pass


def load_documents(retriever: Retriever, folder: Path) -> int:
    n = 0
    if folder.is_dir():
        for p in sorted(folder.rglob("*")):
            if p.suffix.lower() in (".txt", ".md") and p.is_file():
                retriever.add_document(str(p.relative_to(folder)).replace("\\", "/"), p.read_text(encoding="utf-8", errors="replace"), {"title": p.stem})
                n += 1
    return n


def build_backends(cfg: dict[str, Any], root: Path, dry_run: bool = False) -> tuple[dict[str, Any], list]:
    backends: dict[str, Any] = {}
    processes: list = []
    for name, spec in cfg.get("backends", {}).items():
        kind = spec.get("kind")
        if dry_run:
            backends[name] = ScriptedBackend(lambda msgs, n=name: f"[{n} dry-run] no model loaded", name=f"{name}-dry-run")
            continue
        if kind == "hf":
            adapter = root / spec["adapter"] if spec.get("adapter") and (root / spec["adapter"]).exists() else None
            backends[name] = HFBackend(root / spec["model"], adapter, max_new_tokens=spec.get("max_new_tokens", 512))
        elif kind == "llama-server":
            url = f"http://127.0.0.1:{spec.get('port', 8080)}"
            backend = LlamaServerBackend(url, name=f"{name}:{Path(spec['model']).name}")
            if not backend.healthy() and spec.get("autostart", True):
                proc, backend = start_llama_server(root / spec["model"], spec.get("port", 8080), spec.get("threads", 8), spec.get("ctx", 8192),
                                                   exe=root / "tools/llama.cpp/llama-server.exe")
                backend.name = f"{name}:{Path(spec['model']).name}"
                processes.append(proc)
            backends[name] = backend
        else:
            raise ValueError(f"unknown backend kind {kind!r} for {name}")
    return backends, processes


def build_system(config_path: str | Path, dry_run: bool = False, backends: dict[str, Any] | None = None) -> System:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    root = project_root()
    if backends is None:
        backends, processes = build_backends(cfg, root, dry_run)
    else:
        processes = []
    retriever = Retriever()
    docs_dir = root / cfg.get("documents", {}).get("dir", "workspace/docs")
    load_documents(retriever, docs_dir)
    workspace = root / cfg.get("tools", {}).get("workspace", "workspace")
    workspace.mkdir(parents=True, exist_ok=True)
    sqlite = cfg.get("tools", {}).get("sqlite")
    tools = default_registry(workspace=workspace, retriever=retriever, db_path=root / sqlite if sqlite else None)
    memory = MemoryStore(root / cfg.get("memory", {}).get("path", "runs/memory/default.json"))
    orch = Orchestrator(backends, tools=tools, retriever=retriever, memory=memory,
                        max_tool_steps=cfg.get("max_tool_steps", 6), max_tokens=cfg.get("max_tokens", 768))
    return System(orch, cfg, processes)
