from orion.verify.code import humaneval_program, run_python, verify_code
from orion.verify.sql import verify_sql
from orion.verify.toolcall import expected_call_matches, validate_tool_call


def test_run_python_pass_fail_timeout():
    assert run_python("print('hi')").ok
    bad = run_python("assert 1 == 2")
    assert not bad.ok and "AssertionError" in bad.stderr
    slow = run_python("while True: pass", timeout=1.0)
    assert slow.timed_out and not slow.ok


def test_verify_code_humaneval_and_assert_styles():
    prompt = "def add(a, b):\n    \"\"\"Return a + b.\"\"\"\n"
    good = "    return a + b\n"
    test = "def check(candidate):\n    assert candidate(2, 3) == 5\n    assert candidate(-1, 1) == 0\n"
    assert run_python(humaneval_program(prompt, good, test, "add")).ok
    assert not run_python(humaneval_program(prompt, "    return a - b\n", test, "add")).ok
    assert verify_code("def sq(x):\n    return x * x", ["assert sq(3) == 9", "assert sq(0) == 0"]).ok
    assert not verify_code("def sq(x):\n    return x + x", ["assert sq(3) == 9"]).ok


SCHEMA = """
CREATE TABLE orders(id INTEGER, customer TEXT, amount REAL);
INSERT INTO orders VALUES (1, 'ann', 10.0), (2, 'bob', 25.5), (3, 'ann', 4.5);
"""


def test_verify_sql():
    ref = "SELECT customer, SUM(amount) FROM orders GROUP BY customer"
    assert verify_sql(SCHEMA, "SELECT customer, SUM(amount) AS total FROM orders GROUP BY customer ORDER BY customer DESC", ref).ok
    assert not verify_sql(SCHEMA, "SELECT customer, COUNT(*) FROM orders GROUP BY customer", ref).ok
    v = verify_sql(SCHEMA, "SELECT nope FROM orders", ref)
    assert not v.ok and "predicted query failed" in v.error
    ordered_ref = "SELECT customer FROM orders ORDER BY amount"
    assert not verify_sql(SCHEMA, "SELECT customer FROM orders ORDER BY amount DESC", ordered_ref).ok


TOOLS = [{"name": "get_weather", "description": "weather", "parameters": {
    "type": "object", "properties": {"city": {"type": "string"}, "unit": {"type": "string", "enum": ["c", "f"]}},
    "required": ["city"]}}]


def test_validate_tool_call():
    assert validate_tool_call({"name": "get_weather", "arguments": {"city": "Oslo", "unit": "c"}}, TOOLS).ok
    assert validate_tool_call('{"name": "get_weather", "arguments": "{\\"city\\": \\"Oslo\\"}"}', TOOLS).ok
    v = validate_tool_call({"name": "get_weather", "arguments": {"unit": "k"}}, TOOLS)
    assert not v.ok and any("city" in e for e in v.errors) and any("k" in e for e in v.errors)
    assert not validate_tool_call({"name": "get_weather", "arguments": {"city": "Oslo", "zip": 1}}, TOOLS).ok
    assert not validate_tool_call({"name": "launch", "arguments": {}}, TOOLS).ok
    assert not validate_tool_call("{not json", TOOLS).ok
    assert expected_call_matches({"name": "get_weather", "arguments": {"city": "Oslo"}}, {"name": "get_weather", "arguments": {"city": "Oslo"}})
