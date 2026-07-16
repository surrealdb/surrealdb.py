import decimal
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any

from surrealdb.cbor import (
    CBORDecoder,
    CBOREncoder,
    CBORTag,
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
    if isinstance(obj, GeometryPoint):
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

    elif isinstance(obj, (set, frozenset)):
        # SurrealDB uses its own set tag (56); the bundled cbor2 encoder would
        # otherwise emit tag 258, which our decoder does not understand.
        tagged = CBORTag(constants.TAG_SET, list(obj))

    else:
        raise BufferError("no encoder for type ", type(obj))

    encoder.encode(tagged)


def tag_decoder(
    decoder: CBORDecoder, tag: CBORTag, shareable_index: int | None = None
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
            # seconds and nanoseconds
            return Duration.parse(tag.value[0], tag.value[1])

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
        # Convert [seconds, nanoseconds] into a datetime. Note that nanosecond
        # precision is truncated to microseconds (datetime's resolution).
        seconds = tag.value[0]
        nanoseconds = tag.value[1]
        microseconds = nanoseconds // 1000  # Convert nanoseconds to microseconds
        return datetime.fromtimestamp(seconds, timezone.utc) + timedelta(
            microseconds=microseconds
        )

    elif tag.tag == constants.TAG_UUID_STRING:
        # Defensive: the server encodes UUIDs with native tag 37, but decode a
        # string-tagged UUID (tag 9) too, in case one is ever received.
        return uuid.UUID(tag.value)

    elif tag.tag == constants.TAG_DECIMAL_STRING:
        return decimal.Decimal(tag.value)

    elif tag.tag == constants.TAG_SET:
        return set(tag.value) if isinstance(tag.value, list) else tag.value

    else:
        raise BufferError("no decoder for tag", tag.tag)


class _SurrealEncoder(CBOREncoder):
    """CBOR encoder that routes Python sets through SurrealDB's set tag.

    The bundled cbor2 encoder natively serialises ``set``/``frozenset`` using
    CBOR tag 258, but SurrealDB expects its own set tag (56). Dropping the
    built-in set encoders lets sets fall through to :func:`default_encoder`,
    which emits ``constants.TAG_SET``.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._encoders.pop(set, None)
        self._encoders.pop(frozenset, None)


def encode(obj: Any) -> bytes:
    with BytesIO() as fp:
        _SurrealEncoder(fp, default=default_encoder, timezone=timezone.utc).encode(obj)
        return fp.getvalue()


def decode(data: bytes) -> Any:
    return loads(data, tag_hook=tag_decoder)
