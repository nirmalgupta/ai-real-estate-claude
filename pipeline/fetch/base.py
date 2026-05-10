"""Base contract every fetcher follows.

A fetcher takes an Address, hits one source, returns a normalized dict
of facts plus provenance. Extract is decoupled — the fetcher does the
HTTP and minimal parsing; the wiki layer reasons about conflicts.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pipeline.common.address import Address


@dataclass
class Fact:
    """One field of data with its provenance."""
    value: Any
    source: str
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_ref: str | None = None       # url, file path, or other source pointer
    confidence: str = "high"         # high | medium | low | unknown
    note: str | None = None


@dataclass
class FetchResult:
    """What a Source.fetch() returns."""
    source_name: str
    address: Address
    facts: dict[str, Fact]
    raw: dict[str, Any] = field(default_factory=dict)   # original API response, for debugging
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class Source(ABC):
    """Base class for a fetcher.

    Subclasses must set `name` and implement `fetch`.
    """
    name: str = "unnamed"

    @abstractmethod
    def fetch(self, address: Address) -> FetchResult:
        ...
