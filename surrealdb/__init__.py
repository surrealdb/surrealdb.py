from surrealdb.async_surrealdb import AsyncSurrealDB
from surrealdb.surrealdb import SurrealDB
from surrealdb.errors import (
    SurrealDbError,
    SurrealDbConnectionError,
    SurrealDbDecodeError,
    SurrealDbEncodeError,
)

from surrealdb.data.models import Patch, QueryResponse, GraphQLOptions
from surrealdb.data.types.duration import Duration
from surrealdb.data.types.future import Future
from surrealdb.data.types.geometry import (
    Geometry,
    GeometryPoint,
    GeometryLine,
    GeometryPolygon,
    GeometryMultiPoint,
    GeometryMultiLine,
    GeometryMultiPolygon,
    GeometryCollection,
)
from surrealdb.data.types.range import Bound, BoundIncluded, BoundExcluded, Range
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table

__all__ = (
    "SurrealDB",
    "AsyncSurrealDB",
    "SurrealDbError",
    "SurrealDbConnectionError",
    "SurrealDbDecodeError",
    "SurrealDbEncodeError",
    "Patch",
    "QueryResponse",
    "GraphQLOptions",
    "Duration",
    "Future",
    "Geometry",
    "GeometryPoint",
    "GeometryLine",
    "GeometryPolygon",
    "GeometryMultiPoint",
    "GeometryMultiLine",
    "GeometryMultiPolygon",
    "GeometryCollection",
    "Bound",
    "BoundIncluded",
    "BoundExcluded",
    "Range",
    "RecordID",
    "Table",
)
