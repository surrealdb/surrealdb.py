"""Typed JSON (surrealdb-protocol spec/README.md) to and from this SDK's values.

The vectors and the conformance driver write SurrealDB values this way. Plain
JSON types mean what they say; anything else is a one-key object whose key
starts with ``$``.
"""

import datetime as dt
import json
import math
import uuid
from decimal import Decimal
from typing import Any

from surrealdb import (
    Datetime,
    Duration,
    File,
    GeometryCollection,
    GeometryLine,
    GeometryMultiLine,
    GeometryMultiPoint,
    GeometryMultiPolygon,
    GeometryPoint,
    GeometryPolygon,
    RecordID,
    SurrealSet,
    Table,
)
from surrealdb.data.types.geometry import Geometry
from surrealdb.data.types.null import Null, NullType
from surrealdb.data.types.range import Bound, BoundExcluded, BoundIncluded, Range
from surrealdb.data.types.record_id import StringRecordId
from surrealdb.data.types.sized import (
    F16,
    F32,
    I8,
    I16,
    I32,
    U8,
    U16,
    U32,
    U64,
    SizedFloat,
    SizedInt,
)

SIZED: dict[str, type[SizedInt] | type[SizedFloat]] = {
    "$i8": I8,
    "$u8": U8,
    "$i16": I16,
    "$u16": U16,
    "$i32": I32,
    "$u32": U32,
    "$u64": U64,
    "$f16": F16,
    "$f32": F32,
}
_SIZED_KEY = {kind: key for key, kind in SIZED.items()}

_TYPED = {
    "$none",
    "$int",
    "$float",
    "$decimal",
    "$string",
    "$bytes",
    "$uuid",
    "$datetime",
    "$duration",
    "$array",
    "$object",
    "$set",
    "$table",
    "$record",
    "$range",
    "$file",
    "$geometry",
    "$regex",
    *SIZED,
}

_GEOMETRY: dict[str, Any] = {
    "Point": GeometryPoint,
    "LineString": GeometryLine,
    "Polygon": GeometryPolygon,
    "MultiPoint": GeometryMultiPoint,
    "MultiLineString": GeometryMultiLine,
    "MultiPolygon": GeometryMultiPolygon,
}


def _float(raw: Any) -> float:
    if raw == "-0":
        return -0.0
    if isinstance(raw, str):
        return float(raw.replace("Infinity", "inf"))
    return float(raw)


def _geometry(geojson: dict[str, Any]) -> Any:
    if geojson["type"] == "GeometryCollection":
        return GeometryCollection(*(_geometry(g) for g in geojson["geometries"]))
    return _GEOMETRY[geojson["type"]].parse_coordinates(geojson["coordinates"])


def _bound(raw: dict[str, Any] | None) -> Bound | None:
    if raw is None:
        return None
    if "included" in raw:
        return BoundIncluded(to_native(raw["included"]))
    return BoundExcluded(to_native(raw["excluded"]))


def to_native(value: Any) -> Any:
    """The SDK value a typed JSON value stands for."""
    if value is None:
        return Null
    if isinstance(value, bool | str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, list):
        return [to_native(item) for item in value]
    assert isinstance(value, dict)
    if len(value) != 1 or next(iter(value)) not in _TYPED:
        return {key: to_native(item) for key, item in value.items()}
    ((key, raw),) = value.items()
    if key == "$none":
        return None
    if key == "$int":
        return int(raw)
    if key == "$float":
        return _float(raw)
    if key in SIZED:
        kind = SIZED[key]
        return kind(_float(raw)) if issubclass(kind, SizedFloat) else kind(int(raw))
    if key == "$decimal":
        return Decimal(raw)
    if key == "$string":
        return raw
    if key == "$bytes":
        return bytes.fromhex(raw)
    if key == "$uuid":
        return uuid.UUID(raw)
    if key == "$datetime":
        from surrealdb.data.types.datetime import parse_instant

        return parse_instant(raw)
    if key == "$duration":
        seconds, nanoseconds = raw
        return Duration(int(seconds) * 1_000_000_000 + int(nanoseconds))
    if key == "$array":
        return [to_native(item) for item in raw]
    if key == "$object":
        return {k: to_native(item) for k, item in raw.items()}
    if key == "$set":
        return SurrealSet([to_native(item) for item in raw])
    if key == "$table":
        return Table(raw)
    if key == "$record":
        return RecordID(raw["table"], to_native(raw["key"]))
    if key == "$range":
        return Range(_bound(raw["start"]), _bound(raw["end"]))
    if key == "$file":
        return File(raw["bucket"], raw["key"])
    if key == "$geometry":
        return _geometry(raw)
    raise NotImplementedError(f"typed JSON {key} has no value in this SDK")


def _float_json(value: float) -> Any:
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    if value == 0 and math.copysign(1, value) < 0:
        return "-0"
    return value


def _int_json(value: int) -> Any:
    return value if abs(value) <= 2**53 else str(value)


def _datetime_json(value: dt.datetime) -> str:
    moment = (
        value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)
    )
    utc = moment.astimezone(dt.timezone.utc)
    nanos = utc.microsecond * 1000 + getattr(value, "nanosecond", 0)
    text = utc.strftime("%Y-%m-%dT%H:%M:%S")
    return f"{text}.{nanos:09d}Z" if nanos else f"{text}Z"


def _bound_json(bound: Any) -> Any:
    if isinstance(bound, BoundIncluded):
        return {"included": to_json(bound.value)}
    if isinstance(bound, BoundExcluded):
        return {"excluded": to_json(bound.value)}
    return None


def to_json(value: Any) -> Any:
    """The typed JSON for an SDK value."""
    if value is None:
        return {"$none": None}
    if isinstance(value, NullType):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, SizedInt):
        return {_SIZED_KEY[type(value)]: _int_json(int(value))}
    if isinstance(value, SizedFloat):
        return {_SIZED_KEY[type(value)]: _float_json(float(value))}
    if isinstance(value, int):
        return value if abs(value) <= 2**53 else {"$int": str(value)}
    if isinstance(value, float):
        return {"$float": _float_json(value)}
    if isinstance(value, Decimal):
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return {"$decimal": "0" if text in ("-0", "") else text}
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return {"$bytes": value.hex()}
    if isinstance(value, uuid.UUID):
        return {"$uuid": str(value)}
    if isinstance(value, dt.datetime):
        return {"$datetime": _datetime_json(value)}
    if isinstance(value, Datetime):
        from surrealdb.data.types.datetime import parse_instant

        return {"$datetime": _datetime_json(parse_instant(value.dt))}
    if isinstance(value, Duration):
        seconds, nanoseconds = divmod(value.elapsed, 1_000_000_000)
        return {"$duration": [_int_json(seconds), nanoseconds]}
    if isinstance(value, SurrealSet):
        return {"$set": sorted((to_json(item) for item in value), key=json.dumps)}
    if isinstance(value, list | tuple):
        return [to_json(item) for item in value]
    if isinstance(value, dict):
        out = {key: to_json(item) for key, item in value.items()}
        if len(out) == 1 and next(iter(out)) in _TYPED:
            return {"$object": out}
        return out
    if isinstance(value, Table):
        return {"$table": value.table_name}
    if isinstance(value, StringRecordId):
        table, _, key = value.value.partition(":")
        return {"$record": {"table": table, "key": key}}
    if isinstance(value, RecordID):
        return {"$record": {"table": value.table_name, "key": to_json(value.id)}}
    if isinstance(value, Range):
        return {
            "$range": {"start": _bound_json(value.begin), "end": _bound_json(value.end)}
        }
    if isinstance(value, File):
        return {"$file": {"bucket": value.bucket, "key": value.key}}
    if isinstance(value, GeometryCollection):
        return {
            "$geometry": {
                "type": "GeometryCollection",
                "geometries": [to_json(g)["$geometry"] for g in value.geometries],
            }
        }
    if isinstance(value, Geometry):
        name = next(n for n, kind in _GEOMETRY.items() if isinstance(value, kind))
        return {
            "$geometry": {
                "type": name,
                "coordinates": _coordinates(value.get_coordinates()),
            }
        }
    raise TypeError(f"no typed JSON for {type(value).__name__}")


def _coordinates(value: Any) -> Any:
    if isinstance(value, list | tuple):
        return [_coordinates(item) for item in value]
    return float(value)


def same(expected: Any, actual: Any) -> bool:
    """Whether two SDK values are the same value, kinds included.

    Numbers must be of the same type (an ``int`` is not a ``U8``), floats
    compare NaN equal to NaN and -0.0 unequal to 0.0, datetimes compare at
    nanosecond precision, and sets ignore order.
    """
    return bool(to_json(expected) == to_json(actual))
