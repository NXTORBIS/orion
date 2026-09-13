"""SQL verification: execute a predicted query and a reference query against the same SQLite
test database and compare result sets (order-insensitive unless the reference query orders)."""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from dataclasses import dataclass


@dataclass
class SQLVerdict:
    ok: bool
    error: str | None
    rows_pred: int
    rows_ref: int


def _run(conn: sqlite3.Connection, query: str) -> list[tuple]:
    cur = conn.execute(query)
    return [tuple(r) for r in cur.fetchall()]


def verify_sql(schema_and_data: str, predicted: str, reference: str, timeout_s: float = 5.0) -> SQLVerdict:
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(schema_and_data)
        deadline = {"n": 0}

        def guard():  # progress handler: abort runaway queries
            deadline["n"] += 1
            return 1 if deadline["n"] > int(timeout_s * 20000) else 0

        conn.set_progress_handler(guard, 1000)
        ref = _run(conn, reference)
        try:
            pred = _run(conn, predicted)
        except sqlite3.Error as e:
            return SQLVerdict(False, f"predicted query failed: {e}", 0, len(ref))
        ordered = re.search(r"\border\s+by\b", reference, re.I) is not None
        ok = pred == ref if ordered else Counter(pred) == Counter(ref)
        return SQLVerdict(ok, None, len(pred), len(ref))
    except sqlite3.Error as e:
        return SQLVerdict(False, f"setup/reference failed: {e}", 0, 0)
    finally:
        conn.close()
