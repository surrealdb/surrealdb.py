"""
Type definitions for SurrealDB values.

This module defines the Value type, which represents all possible values
that can be returned from SurrealDB queries, including standard JSON types,
bytes, and SurrealDB-specific types.
"""

from decimal import Decimal
from typing import Union
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

__all__ = ["Value"]
