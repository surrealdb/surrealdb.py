"""
Type definitions for SurrealDB values.

This module defines the Value type, which represents all possible values
that can be returned from SurrealDB queries, including standard JSON types,
bytes, and SurrealDB-specific types. It also defines Tokens for signin/signup
responses (access and refresh tokens).
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Union
from uuid import UUID

from surrealdb.data.types.datetime import Datetime
from surrealdb.data.types.duration import Duration
from surrealdb.data.types.geometry import (
    GeometryCollection,
    GeometryLine,
    GeometryMultiLine,
    GeometryMultiPoint,
    GeometryMultiPolygon,
    GeometryPoint,
    GeometryPolygon,
)
from surrealdb.data.types.range import Range
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table

# Define recursive Value type that represents all possible SurrealDB values
Value = Union[
    # Primitives
    str,
    int,
    float,
    bool,
    None,
    bytes,
    # Standard library types
    UUID,
    Decimal,
    # SurrealDB types
    Table,
    Range,
    RecordID,
    Duration,
    Datetime,
    GeometryPoint,
    GeometryLine,
    GeometryPolygon,
    GeometryMultiPoint,
    GeometryMultiLine,
    GeometryMultiPolygon,
    GeometryCollection,
    # Recursive containers (using forward references for recursion)
    dict[str, "Value"],
    list["Value"],
]


@dataclass(frozen=True)
class Tokens:
    """
    Authentication tokens returned by signin and signup.

    The server may return a string (JWT) or an object with optional
    ``access`` (JWT) and ``refresh`` (refresh token). This type normalizes
    the response so callers always receive an object with both properties
    optional.
    """

    access: str | None = None
    refresh: str | None = None


def parse_auth_result(result: Any) -> Tokens:
    """
    Normalize signin/signup result to Tokens.

    The server may return a string (JWT), a dict with ``access`` and/or
    ``refresh``, or (legacy) a string that is the refresh token only.
    """
    if isinstance(result, str):
        return Tokens(access=result, refresh=None)
    if isinstance(result, dict):
        access = result.get("access")
        refresh = result.get("refresh")
        if access is not None and not isinstance(access, str):
            access = str(access)
        if refresh is not None and not isinstance(refresh, str):
            refresh = str(refresh)
        return Tokens(access=access, refresh=refresh)
    return Tokens(access=None, refresh=None)


__all__ = ["Value", "Tokens", "parse_auth_result"]
