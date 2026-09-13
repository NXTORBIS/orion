"""Structured tool-call verification against JSON-schema tool definitions (OpenAI-style
``{"name": ..., "description": ..., "parameters": {json schema}}``)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import jsonschema


@dataclass
class ToolCallVerdict:
    ok: bool
    errors: list[str] = field(default_factory=list)
    name: str | None = None
    arguments: dict[str, Any] | None = None


def parse_tool_call(text_or_obj: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(text_or_obj, dict):
        return text_or_obj
    return json.loads(text_or_obj)


def validate_tool_call(call: str | dict[str, Any], tools: list[dict[str, Any]], allow_extra_args: bool = False) -> ToolCallVerdict:
    try:
        obj = parse_tool_call(call)
    except json.JSONDecodeError as e:
        return ToolCallVerdict(False, [f"not valid JSON: {e.msg}"])
    name = obj.get("name")
    args = obj.get("arguments", obj.get("parameters", {}))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return ToolCallVerdict(False, ["arguments is a string but not valid JSON"], name)
    tool = next((t for t in tools if t.get("name") == name), None)
    if tool is None:
        return ToolCallVerdict(False, [f"unknown tool '{name}'"], name, args)
    schema = dict(tool.get("parameters") or {"type": "object"})
    if not allow_extra_args and "additionalProperties" not in schema:
        schema["additionalProperties"] = False
    errors = [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
              for e in jsonschema.Draft202012Validator(schema).iter_errors(args)]
    return ToolCallVerdict(not errors, errors, name, args)


def expected_call_matches(call: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Exact match on name and arguments (used for tool-use evaluation with gold calls)."""
    return call.get("name") == expected.get("name") and call.get("arguments", {}) == expected.get("arguments", {})
