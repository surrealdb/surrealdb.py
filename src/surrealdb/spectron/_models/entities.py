from __future__ import annotations

from dataclasses import dataclass, field

from surrealdb.spectron._models.common import Model


@dataclass(slots=True)
class EntityDetail(Model):
    id: str
    entity_type: str = ""
    name: str = ""
    created_at: str = ""
    updated_at: str = ""
    importance: float = 0.0
    memory_category: str = ""


@dataclass(slots=True)
class AttributeDetail(Model):
    id: str
    entity: str = ""
    key: str = ""
    value: str = ""
    created_at: str = ""
    importance: float = 0.0
    memory_category: str = ""
    superseded_by: str | None = None
    supersedes: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None


@dataclass(slots=True)
class RelationDetail(Model):
    id: str
    label: str = ""
    subject: str = ""
    object_: str = field(default="", metadata={"json": "object"})
    created_at: str = ""
    memory_category: str = ""
    valid_from: str | None = None
    valid_until: str | None = None


@dataclass(slots=True)
class EntityResponse(Model):
    entity: EntityDetail
    attributes: list[AttributeDetail] = field(default_factory=list)
    relations: list[RelationDetail] = field(default_factory=list)


@dataclass(slots=True)
class EntityListResponse(Model):
    entities: list[EntityDetail] = field(default_factory=list)


@dataclass(slots=True)
class EntityHistoryResponse(Model):
    history: list[AttributeDetail] = field(default_factory=list)
