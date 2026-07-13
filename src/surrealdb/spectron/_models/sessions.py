from __future__ import annotations

from dataclasses import dataclass, field

from surrealdb.spectron._models.common import Model


@dataclass(slots=True)
class Session(Model):
    id: str
    created_at: str = ""
    scopes: list[list[str]] = field(default_factory=list)


@dataclass(slots=True)
class SessionContextResponse(Model):
    context: str = ""


@dataclass(slots=True)
class Turn(Model):
    id: str
    content: str = ""
    created_at: str = ""
    role: str = ""
    seq: int = 0
    session: str = ""


@dataclass(slots=True)
class TurnListResponse(Model):
    turns: list[Turn] = field(default_factory=list)
