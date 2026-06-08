from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from surrealdb.spectron._models.common import Model


@dataclass(slots=True)
class TraceRecord(Model):
    id: str
    cached: bool = False
    created_at: str = ""
    latency_ms: int = 0
    query_text: str = ""
    resolution_tier: str = ""
    tier_reason: str = ""


@dataclass(slots=True)
class TraceListResponse(Model):
    traces: list[TraceRecord] = field(default_factory=list)


@dataclass(slots=True)
class TraceStatsResponse(Model):
    """Aggregated trace statistics. The nested operational-signal bundles
    (contradiction / retrieval / supersession / tier_counts) stay loose dicts
    per the slim-model convention.
    """

    total_queries: int = 0
    avg_latency_ms: float = 0.0
    cache_hit_rate: float = 0.0
    cache_hits: int = 0
    response_traces_cached: int = 0
    response_traces_total: int = 0
    window_hours: int = 0
    contradiction: dict[str, Any] = field(default_factory=dict)
    retrieval: dict[str, Any] = field(default_factory=dict)
    supersession: dict[str, Any] = field(default_factory=dict)
    tier_counts: dict[str, Any] = field(default_factory=dict)
    source_kind_distribution: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class AuditRow(Model):
    """One row of the access/cost audit log. ``kind`` is the wire string
    `decision` / `retrieval` / `response`, kept as a plain ``str``.
    """

    trace_id: str = ""
    created_at: str = ""
    kind: str = ""
    cost: float = 0.0
    latency_ms: int = 0
    rows_touched: int = 0
    model: str | None = None
    principal: str | None = None


@dataclass(slots=True)
class AuditResponse(Model):
    rows: list[AuditRow] = field(default_factory=list)
