"""Pick the chat model this machine runs fast enough, then write a server config for it.

Specs only narrow the candidates (the model has to fit in RAM or GPU memory). The choice comes from a short
llama-bench run, because fitting says nothing about speed: Qwen3-14B fits in 32 GB, but on an i7-1355U it
generated 2.96 tok/s while Qwen3-4B did 9.5.

    python -m orion.system.hardware              # detect, benchmark (cached), write configs/system/auto.yaml
    python -m orion.system.hardware --rebench    # ignore the cached measurements
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import psutil
import yaml

MAX_FIRST_WORD_S = 1.0
MIN_GEN_TPS = 8.0
NEW_PROMPT_TOKENS = 24  # a short question plus chat-template tokens; the fixed system prompt is served from cache


@dataclass
class Hardware:
    ram_gb: float
    logical_cpus: int
    physical_cpus: int
    gpus: list[dict]
    cpu_name: str


@dataclass(frozen=True)
class Candidate:
    name: str
    path: str
    file_gb: float


@dataclass
class Speed:
    prompt_tps: float
    gen_tps: float

    def first_word_s(self) -> float:
        return NEW_PROMPT_TOKENS / self.prompt_tps + 1 / self.gen_tps


CATALOG = [
    Candidate("qwen3-1.7b", "models/Qwen3-1.7B-GGUF/Qwen3-1.7B-Q8_0.gguf", 1.83),
    Candidate("qwen3-4b", "models/Qwen3-4B-GGUF/Qwen3-4B-Q4_K_M.gguf", 2.50),
    Candidate("qwen3-8b", "models/Qwen3-8B-GGUF/Qwen3-8B-Q4_K_M.gguf", 5.03),
    Candidate("qwen3-14b", "models/Qwen3-14B-GGUF/Qwen3-14B-Q4_K_M.gguf", 9.00),
]


def detect() -> Hardware:
    gpus: list[dict] = []
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=10).stdout
            for line in out.strip().splitlines():
                name, mib = (s.strip() for s in line.rsplit(",", 1))
                gpus.append({"name": name, "vram_gb": round(float(mib) / 1024, 1)})
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    return Hardware(ram_gb=round(psutil.virtual_memory().total / 1e9, 1), logical_cpus=psutil.cpu_count() or 1,
                    physical_cpus=psutil.cpu_count(logical=False) or 1, gpus=gpus, cpu_name=platform.processor())


def fits(c: Candidate, hw: Hardware) -> bool:
    return c.file_gb * 1.2 + 3 <= hw.ram_gb or any(g["vram_gb"] >= c.file_gb * 1.2 for g in hw.gpus)


def llama_bench(root: Path, c: Candidate, threads: int) -> Speed:
    exe = root / "tools/llama.cpp" / ("llama-bench.exe" if sys.platform == "win32" else "llama-bench")
    out = subprocess.run([str(exe), "-m", str(root / c.path), "-p", "64", "-n", "16", "-r", "1", "-t", str(threads), "-o", "json"],
                         capture_output=True, text=True, timeout=1800, check=True).stdout
    rows = json.loads(out)
    prompt = next(r["avg_ts"] for r in rows if r["n_prompt"] > 0 and r["n_gen"] == 0)
    gen = next(r["avg_ts"] for r in rows if r["n_gen"] > 0 and r["n_prompt"] == 0)
    return Speed(prompt, gen)


def choose(hw: Hardware, root: Path, bench: Callable[[Candidate], Speed]) -> tuple[Candidate | None, list[dict]]:
    """Largest installed model that fits and meets both speed targets; otherwise the smallest one that fits."""
    installed = [c for c in CATALOG if (root / c.path).exists()]
    fitting = [c for c in installed if fits(c, hw)]
    tried = []
    for c in sorted(fitting, key=lambda c: c.file_gb, reverse=True):
        s = bench(c)
        ok = s.first_word_s() <= MAX_FIRST_WORD_S and s.gen_tps >= MIN_GEN_TPS
        tried.append({"model": c.name, "prompt_tps": round(s.prompt_tps, 1), "gen_tps": round(s.gen_tps, 2),
                      "first_word_s": round(s.first_word_s(), 2), "meets_target": ok})
        if ok:
            return c, tried
    pool = fitting or installed
    return (min(pool, key=lambda c: c.file_gb) if pool else None), tried


def write_config(root: Path, c: Candidate, hw: Hardware, out: str = "configs/system/auto.yaml") -> Path:
    cfg = {"backends": {"general": {"kind": "llama-server", "model": c.path, "port": 8082, "threads": hw.physical_cpus,
                                    "ctx": 8192, "autostart": True, "thinking": False}},
           "tools": {"workspace": "workspace", "sqlite": None}, "documents": {"dir": "workspace/docs"},
           "memory": {"path": "runs/memory/laptop.json", "recall_episodes": False}, "server": {"host": "127.0.0.1", "port": 8765},
           "max_tool_steps": 6, "max_tokens": 768}
    path = root / out
    path.write_text(f"# Written by `python -m orion.system.hardware` for this machine ({c.name}).\n" + yaml.safe_dump(cfg, sort_keys=False),
                    encoding="utf-8")
    return path


def main(argv: list[str]) -> None:
    from orion.train.common import project_root

    root = project_root()
    hw = detect()
    print("hardware:", json.dumps(asdict(hw)))
    cache_path = root / "runs" / "hardware_choice.json"
    fingerprint = {"hardware": asdict(hw), "installed": [c.name for c in CATALOG if (root / c.path).exists()]}
    cached = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else None
    if cached and cached.get("fingerprint") == fingerprint and "--rebench" not in argv:
        pick = next((c for c in CATALOG if c.name == cached["choice"]), None)
        tried = cached["tried"]
    else:
        pick, tried = choose(hw, root, lambda c: llama_bench(root, c, hw.physical_cpus))
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"fingerprint": fingerprint, "choice": pick.name if pick else None, "tried": tried}, indent=2), encoding="utf-8")
    for t in tried:
        print(f"  {t['model']:11} prompt {t['prompt_tps']:6.1f} tok/s  gen {t['gen_tps']:5.2f} tok/s  first word ~{t['first_word_s']:.2f}s  "
              f"{'meets target' if t['meets_target'] else 'too slow'}")
    if pick is None:
        sys.exit("no chat model is installed; download one listed in orion.system.hardware.CATALOG")
    print(f"chosen: {pick.name} -> {write_config(root, pick, hw)}")
    print("start with: python -m orion.api.server configs/system/auto.yaml")


if __name__ == "__main__":
    main(sys.argv[1:])
