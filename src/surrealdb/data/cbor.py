from datetime import datetime, timedelta, timezone

from surrealdb.cbor2 import shareable_encoder, CBORTag, dumps, loads

from surrealdb.data.types import constants
from surrealdb.data.types.datetime import IsoDateTimeWrapper
from surrealdb.data.types.duration import Duration
from surrealdb.data.types.future import Future
from surrealdb.data.types.geometry import (
    GeometryPoint,
    GeometryLine,
    GeometryPolygon,
    GeometryMultiLine,
    GeometryMultiPoint,
    GeometryMultiPolygon,
    GeometryCollection,
)
from surrealdb.data.types.range import BoundIncluded, BoundExcluded, Range
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


@shareable_encoder
def default_encoder(encoder, obj):
    if isinstance(obj, GeometryPoint):
        tagged = CBORTag(constants.TAG_GEOMETRY_POINT, obj.get_coordinates())

    if obj is None:
        tagged = CBORTag(constants.TAG_NONE, None)

    elif isinstance(obj, GeometryLine):
        tagged = CBORTag(constants.TAG_GEOMETRY_LINE, obj.get_coordinates())

    elif isinstance(obj, GeometryPolygon):
        tagged = CBORTag(constants.TAG_GEOMETRY_POLYGON, obj.get_coordinates())

    elif isinstance(obj, GeometryMultiLine):
        tagged = CBORTag(constants.TAG_GEOMETRY_MULTI_LINE, obj.get_coordinates())

    elif isinstance(obj, GeometryMultiPoint):
        tagged = CBORTag(constants.TAG_GEOMETRY_MULTI_POINT, obj.get_coordinates())

    elif isinstance(obj, GeometryMultiPolygon):
        tagged = CBORTag(constants.TAG_GEOMETRY_MULTI_POLYGON, obj.get_coordinates())

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
        tagged = CBORTag(constants.TAG_BOUND_EXCLUDED, [obj.begin, obj.end])

    elif isinstance(obj, Future):
        tagged = CBORTag(constants.TAG_BOUND_EXCLUDED, obj.value)

    elif isinstance(obj, Duration):
        tagged = CBORTag(constants.TAG_DURATION, obj.get_seconds_and_nano())

    elif isinstance(obj, IsoDateTimeWrapper):
        tagged = CBORTag(constants.TAG_DATETIME, obj.dt)
    else:
        raise BufferError("no encoder for type ", type(obj))

    encoder.encode(tagged)


def tag_decoder(decoder, tag, shareable_index=None):
    if tag.tag == constants.TAG_GEOMETRY_POINT:
        return GeometryPoint.parse_coordinates(tag.value)

    elif tag.tag == constants.TAG_GEOMETRY_LINE:
        return GeometryLine.parse_coordinates(tag.value)

    elif tag.tag == constants.TAG_GEOMETRY_POLYGON:
        return GeometryPolygon.parse_coordinates(tag.value)

    elif tag.tag == constants.TAG_GEOMETRY_MULTI_POINT:
        return GeometryMultiPoint.parse_coordinates(tag.value)

    elif tag.tag == constants.TAG_GEOMETRY_MULTI_LINE:
        return GeometryMultiLine.parse_coordinates(tag.value)

    elif tag.tag == constants.TAG_GEOMETRY_MULTI_POLYGON:
        return GeometryMultiPolygon.parse_coordinates(tag.value)

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
        return Duration.parse(tag.value[0], tag.value[1])  # Two numbers (s, ns)

    elif tag.tag == constants.TAG_DURATION:
        return Duration.parse(tag.value)  # String (e.g., "1d3m5ms")

    elif tag.tag == constants.TAG_DATETIME_COMPACT:
        # TODO => convert [seconds, nanoseconds] => return datetime
        seconds = tag.value[0]
        nanoseconds = tag.value[1]
        microseconds = nanoseconds // 1000  # Convert nanoseconds to microseconds
        return datetime.fromtimestamp(seconds) + timedelta(microseconds=microseconds)

    else:
        raise BufferError("no decoder for tag", tag.tag)


def encode(obj):
    return dumps(obj, default=default_encoder, timezone=timezone.utc)


def decode(data):
    return loads(data, tag_hook=tag_decoder)
