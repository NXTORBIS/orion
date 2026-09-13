"""Execute code against tests in a separate process with a timeout.

Isolation level, stated plainly: a fresh interpreter (``python -I -B``) in a temporary working
directory with a minimal environment and a wall-clock timeout. That is process isolation, not a
security sandbox — on this Windows laptop there is no seccomp, namespace or container layer.
Production data generation and evaluation must run this in containers (Docker / gVisor / k8s),
which ``run_python`` supports through the ``python`` argument (e.g. a wrapper script).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CodeVerdict:
    ok: bool
    returncode: int | None
    stdout: str
    stderr: str
    seconds: float
    timed_out: bool


def run_python(program: str, timeout: float = 10.0, python: str | None = None, max_output: int = 4000) -> CodeVerdict:
    """Run ``program`` as a script; ok == exit code 0 within the timeout."""
    with tempfile.TemporaryDirectory(prefix="orion-sandbox-") as d:
        path = Path(d) / "program.py"
        path.write_text(program, encoding="utf-8")
        env = {"PATH": os.environ.get("PATH", ""), "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
               "PYTHONIOENCODING": "utf-8", "PYTHONHASHSEED": "0", "OMP_NUM_THREADS": "1"}
        t0 = time.perf_counter()
        try:
            proc = subprocess.run([python or sys.executable, "-I", "-B", str(path)], cwd=d, env=env, capture_output=True,
                                  text=True, timeout=timeout, encoding="utf-8", errors="replace")
            return CodeVerdict(proc.returncode == 0, proc.returncode, proc.stdout[-max_output:], proc.stderr[-max_output:],
                               round(time.perf_counter() - t0, 3), False)
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or b"") if isinstance(e.stdout, (bytes, bytearray)) else (e.stdout or "")
            err = (e.stderr or b"") if isinstance(e.stderr, (bytes, bytearray)) else (e.stderr or "")
            return CodeVerdict(False, None, str(out)[-max_output:], str(err)[-max_output:], round(time.perf_counter() - t0, 3), True)


def humaneval_program(prompt: str, completion: str, test: str, entry_point: str) -> str:
    """Assemble a HumanEval-style check: prompt + completion define the function, ``test``
    defines ``check(candidate)``; exit code 0 means every assertion passed."""
    return f"{prompt}{completion}\n\n{test}\n\ncheck({entry_point})\n"


def assert_program(solution: str, asserts: list[str]) -> str:
    """Solution code followed by plain assert statements (MBPP style)."""
    return solution + "\n\n" + "\n".join(asserts) + "\n"


def verify_code(solution: str, tests: str | list[str], timeout: float = 10.0) -> CodeVerdict:
    program = assert_program(solution, tests) if isinstance(tests, list) else f"{solution}\n\n{tests}\n"
    return run_python(program, timeout=timeout)
