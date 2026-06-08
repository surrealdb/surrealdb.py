from __future__ import annotations

from dataclasses import dataclass

from surrealdb.spectron._models.common import Model


@dataclass(slots=True)
class ScopeNode(Model):
    path: str
    created_at: str = ""
    tombstoned_at: str | None = None


@dataclass(slots=True)
class ForgetScopeResponse(Model):
    forgotten: int = 0
