from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def drop_none(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Drop keys whose value is ``None`` from a request payload."""
    return {k: v for k, v in payload.items() if v is not None}


__all__ = ["drop_none"]
