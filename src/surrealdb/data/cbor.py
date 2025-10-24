import decimal
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from surrealdb.cbor import (
    CBORDecoder,
    CBOREncoder,
    CBORTag,
    dumps,
    loads,
    shareable_encoder,
)
from surrealdb.data.types import constants
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
from surrealdb.data.types.range import BoundExcluded, BoundIncluded, Range
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@shareable_encoder
def default_encoder(encoder: CBOREncoder, obj: Any) -> None:
    if obj is None:
        tagged = CBORTag(constants.TAG_NONE, None)

    elif isinstance(obj, GeometryPoint):
        tagged = CBORTag(constants.TAG_GEOMETRY_POINT, obj.get_coordinates())

    elif isinstance(obj, GeometryLine):
        tagged = CBORTag(constants.TAG_GEOMETRY_LINE, obj.geometry_points)

    elif isinstance(obj, GeometryPolygon):
        tagged = CBORTag(constants.TAG_GEOMETRY_POLYGON, obj.geometry_lines)

    elif isinstance(obj, GeometryMultiLine):
        tagged = CBORTag(constants.TAG_GEOMETRY_MULTI_LINE, obj.geometry_lines)

    elif isinstance(obj, GeometryMultiPoint):
        tagged = CBORTag(constants.TAG_GEOMETRY_MULTI_POINT, obj.geometry_points)

    elif isinstance(obj, GeometryMultiPolygon):
        tagged = CBORTag(constants.TAG_GEOMETRY_MULTI_POLYGON, obj.geometry_polygons)

    elif isinstance(obj, GeometryCollection):
        tagged = CBORTag(constants.TAG_GEOMETRY_COLLECTION, obj.geometries)

    elif isinstance(obj, RecordID):
        tagged = CBORTag(constants.TAG_RECORD_ID, [obj.table_name, obj.id])

    elif isinstance(obj, Table):
        tagged = CBORTag(constants.TAG_TABLE_NAME, obj.table_name)

    elif isinstance(obj, BoundIncluded):
        tagged = CBORTag(constants.TAG_BOUND_INCLUDED, obj.value)

    elif isinstance(obj, BoundExcluded):
        tagged = CBORTag(constants.TAG_BOUND_EXCLUDED, obj.value)

    elif isinstance(obj, Range):
        tagged = CBORTag(constants.TAG_RANGE, [obj.begin, obj.end])

    elif isinstance(obj, Duration):
        tagged = CBORTag(constants.TAG_DURATION, obj.get_seconds_and_nano())

    elif isinstance(obj, Datetime):
        tagged = CBORTag(constants.TAG_DATETIME, obj.dt)

    elif isinstance(obj, decimal.Decimal):
        tagged = CBORTag(constants.TAG_DECIMAL_STRING, str(obj))

    else:
        raise BufferError("no encoder for type ", type(obj))

    encoder.encode(tagged)


def tag_decoder(
    decoder: CBORDecoder, tag: CBORTag, shareable_index: Optional[int] = None
) -> Any:
    if tag.tag == constants.TAG_GEOMETRY_POINT:
        return GeometryPoint.parse_coordinates(tag.value)

    elif tag.tag == constants.TAG_GEOMETRY_LINE:
        return GeometryLine(*tag.value)

    elif tag.tag == constants.TAG_GEOMETRY_POLYGON:
        return GeometryPolygon(*tag.value)

    elif tag.tag == constants.TAG_GEOMETRY_MULTI_POINT:
        return GeometryMultiPoint(*tag.value)

    elif tag.tag == constants.TAG_GEOMETRY_MULTI_LINE:
        return GeometryMultiLine(*tag.value)

    elif tag.tag == constants.TAG_GEOMETRY_MULTI_POLYGON:
        return GeometryMultiPolygon(*tag.value)

    elif tag.tag == constants.TAG_GEOMETRY_COLLECTION:
        return GeometryCollection(*tag.value)

    elif tag.tag == constants.TAG_NONE:
        return None

    elif tag.tag == constants.TAG_RECORD_ID:
        return RecordID(tag.value[0], tag.value[1])

    elif tag.tag == constants.TAG_TABLE_NAME:
        return Table(tag.value)

    elif tag.tag == constants.TAG_BOUND_INCLUDED:
        return BoundIncluded(tag.value)

    elif tag.tag == constants.TAG_BOUND_EXCLUDED:
        return BoundExcluded(tag.value)

    elif tag.tag == constants.TAG_RANGE:
        return Range(tag.value[0], tag.value[1])

    elif tag.tag == constants.TAG_DURATION_COMPACT:
        if len(tag.value) == 1:
            return Duration.parse(tag.value[0], 0)  # seconds only
        else:
            return Duration.parse(tag.value[0], tag.value[1])  # seconds and nanoseconds

    elif tag.tag == constants.TAG_DURATION:
        # TAG_DURATION is encoded as [seconds, nanoseconds] tuple
        if isinstance(tag.value, (list, tuple)) and len(tag.value) == 2:
            return Duration.parse(tag.value[0], tag.value[1])
        # Fallback for string format (if server sends it)
        elif isinstance(tag.value, str):
            return Duration.parse(tag.value)
        else:
            raise ValueError(f"Unexpected TAG_DURATION value format: {tag.value}")

    elif tag.tag == constants.TAG_DATETIME_COMPACT:
        # TODO => convert [seconds, nanoseconds] => return datetime
        seconds = tag.value[0]
        nanoseconds = tag.value[1]
        microseconds = nanoseconds // 1000  # Convert nanoseconds to microseconds
        return datetime.fromtimestamp(seconds, timezone.utc) + timedelta(
            microseconds=microseconds
        )

    elif tag.tag == constants.TAG_DECIMAL_STRING:
        return decimal.Decimal(tag.value)

    else:
        raise BufferError("no decoder for tag", tag.tag)


def encode(obj: Any) -> bytes:
    return dumps(obj, default=default_encoder, timezone=timezone.utc)


def decode(data: bytes) -> Any:
    return loads(data, tag_hook=tag_decoder)
