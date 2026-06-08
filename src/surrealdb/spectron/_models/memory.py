from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from surrealdb.spectron._models.common import Model


@dataclass(slots=True)
class ExtractionResult(Model):
    """Memory-extraction summary returned by /facts, /facts/batch and /chat.

    Nested summary lists (entities, attributes, ...) are intentionally kept as
    ``list[dict[str, Any]]`` rather than fully typed sub-models — the SurrealDB
    SDK exposes a slim public model surface and the upstream summary shapes
    are still evolving.
    """

    turn_id: str = ""
    entities: list[dict[str, Any]] = field(default_factory=list)
    attributes: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    instructions: list[dict[str, Any]] = field(default_factory=list)
    uncertainties: list[dict[str, Any]] = field(default_factory=list)
    corrections: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class RememberResponse(Model):
    mode: str
    session_id: str
    chunk_id: str | None = None
    extraction: ExtractionResult | None = None
    preview: bool | None = None
    turn_id: str | None = None


@dataclass(slots=True)
class RememberBatchResponse(Model):
    session_id: str
    turn_ids: list[str] = field(default_factory=list)
    extractions: list[ExtractionResult] = field(default_factory=list)


@dataclass(slots=True)
class RecallHit(Model):
    id: str
    score: float
    source: str
    text: str


@dataclass(slots=True)
class RecallResponse(Model):
    classification_kind: str = ""
    hits: list[RecallHit] = field(default_factory=list)
    query_ms: int = 0
    seed_entities: list[str] = field(default_factory=list)
    tier: str = ""
    trace: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatResponse(Model):
    reply: str
    session_id: str
    trace_id: str
    memory_updates: ExtractionResult | None = None


@dataclass(slots=True)
class ForgetResponse(Model):
    deleted: int = 0


@dataclass(slots=True)
class ConsolidateOutcome(Model):
    """One observation the consolidator created, updated, or superseded.

    `kind` is the wire string `create` / `update` / `supersede`; kept as a
    plain ``str`` to tolerate server-side additions.
    """

    entity_name: str = ""
    key: str = ""
    kind: str = ""
    proof_count: int = 0
    value: str = ""
    observation_id: str | None = None
    rationale: str | None = None


@dataclass(slots=True)
class ConsolidateResponse(Model):
    created: int = 0
    dry_run: bool = False
    outcomes: list[ConsolidateOutcome] = field(default_factory=list)
    superseded: int = 0
    trace_id: str = ""
    updated: int = 0


@dataclass(slots=True)
class ReflectResponse(Model):
    reflection: str = ""
    evidence: list[str] = field(default_factory=list)
    persisted_attributes: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str = ""


@dataclass(slots=True)
class ElaborateOutcome(Model):
    entity_name: str = ""
    entity_type: str = ""
    dry_run: bool = False
    relations_emitted: int = 0
    trace_id: str = ""
    proposed_relations: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class ElaborateResponse(Model):
    outcomes: list[ElaborateOutcome] = field(default_factory=list)
    relations_emitted: int = 0


@dataclass(slots=True)
class ContextQueryResponse(Model):
    context: str = ""
    query_ms: int = 0
    tier: str = ""


@dataclass(slots=True)
class StateResponse(Model):
    """Snapshot of the context's working memory.

    The per-category bundles (`context`/`identity`/`knowledge`) and the
    instruction / unknown summaries keep their nested rows as plain dicts,
    matching the slim-model convention used by ``ExtractionResult``.
    """

    context: dict[str, Any] = field(default_factory=dict)
    identity: dict[str, Any] = field(default_factory=dict)
    knowledge: dict[str, Any] = field(default_factory=dict)
    instructions: list[dict[str, Any]] = field(default_factory=list)
    unknowns: list[dict[str, Any]] = field(default_factory=list)
