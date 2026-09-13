"""Readers that turn raw files into provenance-tagged ``Record`` streams.

Supported: ``.jsonl``, ``.jsonl.gz``, ``.json`` (list), ``.parquet``, ``.txt`` (one document per
file). The dataset registry supplies ``license`` and ``generators`` for the source; a reader
never invents provenance — a source missing from the registry yields records with
``generators=["unknown"]``, which the provenance gate then drops.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .schema import Record


def _rows_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _rows_parquet(path: Path) -> Iterator[dict[str, Any]]:
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=1024):
        yield from batch.to_pylist()


def iter_rows(path: str | Path) -> Iterator[dict[str, Any]]:
    p = Path(path)
    name = p.name.lower()
    if name.endswith((".jsonl", ".jsonl.gz", ".ndjson")):
        yield from _rows_jsonl(p)
    elif name.endswith((".json", ".json.gz")):
        opener = gzip.open if name.endswith(".gz") else open
        with opener(p, "rt", encoding="utf-8") as f:
            data = json.load(f)
        yield from (data if isinstance(data, list) else data.get("data", []))
    elif name.endswith(".parquet"):
        yield from _rows_parquet(p)
    elif name.endswith(".txt"):
        yield {"text": p.read_text(encoding="utf-8", errors="replace")}
    else:
        raise ValueError(f"unsupported file type: {p}")


def read_records(path: str | Path, source: str, registry: dict[str, dict[str, Any]],
                 text_field: str = "text", id_field: str | None = None,
                 split: str | None = None, limit: int | None = None,
                 generators: list[str] | None = None) -> Iterator[Record]:
    entry = registry.get(source, {})
    license_ = str(entry.get("license", "unknown"))
    gens = generators or list(entry.get("generators") or ["unknown"])
    p = Path(path)
    for i, row in enumerate(iter_rows(p)):
        if limit is not None and i >= limit:
            break
        text = row.get(text_field)
        if not isinstance(text, str):
            continue
        rid = str(row[id_field]) if id_field and id_field in row else f"{source}:{p.name}:{i}"
        meta = {k: v for k, v in row.items() if k != text_field and isinstance(v, (str, int, float, bool))}
        if split:
            meta["split"] = split
        yield Record(id=rid, text=text, source=source, license=license_, generators=list(gens), meta=meta)
