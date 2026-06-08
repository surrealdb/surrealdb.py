from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from surrealdb.spectron._models.common import Model


@dataclass(slots=True)
class MintedKey(Model):
    """A freshly minted (or rotated) self-service key. ``key`` is the full
    bearer secret (`sp-{id}-{secret}`) and is only ever returned once.
    """

    id: str
    key: str
    valid_until: str | None = None


@dataclass(slots=True)
class KeyDetail(Model):
    id: str
    name: str = ""
    created_at: str = ""
    grants: dict[str, Any] | None = None
    last_used_at: str | None = None
    valid_until: str | None = None
