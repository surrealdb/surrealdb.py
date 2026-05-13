from __future__ import annotations

from surrealdb.spectron._transport import quote_path


def enduser_base(context_id: str) -> str:
    return f"/api/v1/{quote_path(context_id)}"


def management_base() -> str:
    return "/api/v1/contexts"
