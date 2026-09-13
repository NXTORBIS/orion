"""Records that flow through the ORION data pipeline.

Every record carries provenance (source, license, generators) from the moment it is read, so
license and contamination rules can be enforced before any other processing. Dropped records
keep flowing (marked, not deleted) so every stage's rejections can be counted and audited.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass
class Record:
    id: str
    text: str
    source: str  # dataset id in registry/licenses/datasets.yaml
    license: str
    generators: list[str] = field(default_factory=lambda: ["unknown"])  # "human", "web", or model names
    meta: dict[str, Any] = field(default_factory=dict)  # per-stage annotations: lang, quality, domain, ...
    dropped_by: str | None = None
    drop_reason: str | None = None

    @property
    def kept(self) -> bool:
        return self.dropped_by is None

    def drop(self, stage: str, reason: str) -> None:
        if self.kept:
            self.dropped_by, self.drop_reason = stage, reason

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Record:
        return cls(**d)


class Stage(Protocol):
    """A pipeline stage. Implementations must pass dropped records through untouched."""

    name: str

    def process(self, records: Iterable[Record]) -> Iterator[Record]: ...


class RecordStage:
    """Base class for stages that look at one kept record at a time."""

    name = "stage"

    def process(self, records: Iterable[Record]) -> Iterator[Record]:
        for r in records:
            if r.kept:
                self.apply(r)
            yield r

    def apply(self, record: Record) -> None:
        raise NotImplementedError
