"""Tool registry and structured tool calls.

A tool is a name, a description, a JSON schema for its arguments and a ``run`` function that
returns a string observation. Models request tools with a ``<tool_call>{json}</tool_call>``
block (the same convention Qwen models are trained with); calls are schema-validated by
``orion.verify.toolcall`` before anything runs, and every execution is bounded (timeouts,
workspace-restricted file access, expression-only calculator).
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from orion.verify.code import run_python
from orion.verify.toolcall import validate_tool_call

TOOL_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    run: Callable[[dict[str, Any]], str]

    def schema(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}


@dataclass
class ToolResult:
    name: str
    arguments: dict[str, Any] | None
    ok: bool
    output: str
    errors: list[str] = field(default_factory=list)


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None):
        self.tools: dict[str, Tool] = {t.name: t for t in (tools or [])}

    def add(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self.tools.values()]

    def prompt_block(self) -> str:
        return ("You can call tools. To call one, output exactly one block of the form\n"
                "<tool_call>{\"name\": \"<tool name>\", \"arguments\": {...}}</tool_call>\n"
                "and stop; you will receive the result in a tool message. Available tools:\n"
                + "\n".join(json.dumps(s, ensure_ascii=False) for s in self.schemas()))

    @staticmethod
    def parse_calls(text: str) -> list[str]:
        return TOOL_CALL.findall(text)

    def execute(self, call_json: str, max_output: int = 4000) -> ToolResult:
        v = validate_tool_call(call_json, self.schemas())
        if not v.ok:
            return ToolResult(v.name or "?", v.arguments, False, "", v.errors)
        try:
            out = self.tools[v.name].run(v.arguments or {})
            return ToolResult(v.name, v.arguments, True, str(out)[:max_output])
        except Exception as e:  # a tool failure is an observation, not a crash
            return ToolResult(v.name, v.arguments, False, "", [f"{type(e).__name__}: {e}"])


# ---------------- built-in tools ----------------
_SAFE_EXPR = re.compile(r"^[\d\s+\-*/().,%^eE]+$|^[\w\s+\-*/().,^]+$")


def calculator(args: dict[str, Any]) -> str:
    import sympy
    from sympy.parsing.sympy_parser import convert_xor, implicit_multiplication_application, parse_expr, standard_transformations

    expr = str(args["expression"]).replace("×", "*").replace("÷", "/")
    if len(expr) > 500 or not _SAFE_EXPR.match(expr):
        raise ValueError("expression contains unsupported characters")
    value = parse_expr(expr, transformations=standard_transformations + (implicit_multiplication_application, convert_xor))
    simplified = sympy.simplify(value)
    if simplified.is_Integer:
        return str(simplified)
    if simplified.is_Rational:
        return f"{simplified} = {float(simplified):.12g}"
    if simplified.is_number:
        return f"{simplified} = {sympy.N(simplified, 12)}"
    return str(simplified)  # symbolic result with free variables


def python_tool(args: dict[str, Any]) -> str:
    v = run_python(str(args["code"]), timeout=float(args.get("timeout", 10)))
    status = "ok" if v.ok else ("timed out" if v.timed_out else f"exit code {v.returncode}")
    return f"[{status}]\nstdout:\n{v.stdout}\nstderr:\n{v.stderr}".strip()


def make_read_file(workspace: str | Path):
    root = Path(workspace).resolve()

    def read_file(args: dict[str, Any]) -> str:
        target = (root / str(args["path"])).resolve()
        if root not in target.parents and target != root:
            raise PermissionError("path is outside the workspace")
        if not target.is_file():
            raise FileNotFoundError(str(args["path"]))
        text = target.read_text(encoding="utf-8", errors="replace")
        start, n = int(args.get("start_line", 1)), int(args.get("max_lines", 200))
        lines = text.splitlines()[start - 1 : start - 1 + n]
        return "\n".join(f"{start + i}: {l}" for i, l in enumerate(lines))

    return read_file


def make_sql_tool(db_path: str | Path):
    def sql(args: dict[str, Any]) -> str:
        conn = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
        try:
            cur = conn.execute(str(args["query"]))
            rows = cur.fetchmany(int(args.get("max_rows", 50)))
            cols = [d[0] for d in cur.description] if cur.description else []
            return json.dumps({"columns": cols, "rows": rows}, ensure_ascii=False, default=str)
        finally:
            conn.close()

    return sql


def make_search_tool(retriever):
    def search(args: dict[str, Any]) -> str:
        hits = retriever.retrieve(str(args["query"]), k=int(args.get("k", 5)))
        return retriever.format_evidence(hits)

    return search


def default_registry(workspace: str | Path | None = None, retriever=None, db_path: str | Path | None = None) -> ToolRegistry:
    reg = ToolRegistry([
        Tool("calculator", "Evaluate an arithmetic or algebraic expression exactly (SymPy).",
             {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}, calculator),
        Tool("python", "Run a short Python program in a fresh interpreter and return stdout/stderr.",
             {"type": "object", "properties": {"code": {"type": "string"}, "timeout": {"type": "number"}}, "required": ["code"]}, python_tool),
    ])
    if workspace is not None:
        reg.add(Tool("read_file", "Read lines from a text file inside the workspace.",
                     {"type": "object", "properties": {"path": {"type": "string"}, "start_line": {"type": "integer"}, "max_lines": {"type": "integer"}},
                      "required": ["path"]}, make_read_file(workspace)))
    if retriever is not None:
        reg.add(Tool("search_docs", "Search the indexed documents and return cited passages.",
                     {"type": "object", "properties": {"query": {"type": "string"}, "k": {"type": "integer"}}, "required": ["query"]},
                     make_search_tool(retriever)))
    if db_path is not None:
        reg.add(Tool("sql", "Run a read-only SQL query against the database.",
                     {"type": "object", "properties": {"query": {"type": "string"}, "max_rows": {"type": "integer"}}, "required": ["query"]},
                     make_sql_tool(db_path)))
    return reg
