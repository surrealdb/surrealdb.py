from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from surrealdb.spectron._models.common import Model


@dataclass(slots=True)
class LifecycleResponse(Model):
    """Result of a lifecycle maintenance op (decay / expire). ``affected`` is
    the number of rows the pass touched.
    """

    affected: int = 0


@dataclass(slots=True)
class FsckReport(Model):
    """Integrity-check findings. Each finding list keeps its rows loose per the
    slim-model convention; ``total`` is the combined finding count.
    """

    total: int = 0
    contradictions: list[dict[str, Any]] = field(default_factory=list)
    duplicates: list[dict[str, Any]] = field(default_factory=list)
    injection: list[dict[str, Any]] = field(default_factory=list)
