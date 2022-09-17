from dataclasses import dataclass
from typing import Any

__all__ = ("SurrealResponse",)


@dataclass(frozen=True)
class SurrealResponse:
    time: str
    status: str
    result: list[dict[str, Any]]
