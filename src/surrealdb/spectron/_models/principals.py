from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from surrealdb.spectron._models.common import Model


@dataclass(slots=True)
class Principal(Model):
    """A principal and its grants. ``grants`` is a per-verb scope-pattern map
    (`{"memory:read": ["org/acme/*"], ...}`) kept loose per the slim convention.
    """

    id: str
    display_name: str = ""
    kind: str = ""
    grants: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EffectiveGrants(Model):
    path: str
    verbs: list[str] = field(default_factory=list)
    as_of: str | None = None


@dataclass(slots=True)
class WhoamiResponse(Model):
    principal_id: str = ""
    display_name: str = ""
    kind: str = ""
    enforce: bool = False
    grants: dict[str, Any] = field(default_factory=dict)
    effective_grants: dict[str, Any] = field(default_factory=dict)
    delegated_principal_id: str | None = None
    token_grants: dict[str, Any] | None = None


@dataclass(slots=True)
class ProfileEntry(Model):
    key: str
    value: str


@dataclass(slots=True)
class ProfileResponse(Model):
    dynamic: list[ProfileEntry] = field(default_factory=list)
    preferences: list[ProfileEntry] = field(default_factory=list)
    static: list[ProfileEntry] = field(default_factory=list)
    instructions: list[dict[str, Any]] = field(default_factory=list)
