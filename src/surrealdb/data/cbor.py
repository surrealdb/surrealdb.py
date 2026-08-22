import decimal
import uuid
from datetime import timezone
from io import BytesIO
from typing import Any

from surrealdb.cbor import (
    CBORDecoder,
    CBOREncoder,
    CBORTag,
    shareable_encoder,
)
from surrealdb.data.types import constants
from surrealdb.data.types.datetime import Datetime, PreciseDatetime
from surrealdb.data.types.duration import Duration
from surrealdb.data.types.file import File
from surrealdb.data.types.geometry import (
    GeometryCollection,
    GeometryLine,
    GeometryMultiLine,
    GeometryMultiPoint,
    GeometryMultiPolygon,
    GeometryPoint,
    GeometryPolygon,
)
from surrealdb.data.types.null import Null, NullType
from surrealdb.data.types.range import BoundExcluded, BoundIncluded, Range
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.set import SurrealSet
from surrealdb.data.types.table import Table
from surrealdb.errors import UnexpectedResponseError

# Plain CBOR null: major type 7, subtype 22.
_CBOR_NULL_SUBTYPE = 22


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

    elif isinstance(obj, File):
        tagged = CBORTag(constants.TAG_FILE, [obj.bucket, obj.key])

    elif isinstance(obj, BoundIncluded):
        tagged = CBORTag(constants.TAG_BOUND_INCLUDED, obj.value)

    elif isinstance(obj, BoundExcluded):
        tagged = CBORTag(constants.TAG_BOUND_EXCLUDED, obj.value)

    elif isinstance(obj, Range):
        tagged = CBORTag(constants.TAG_RANGE, [obj.begin, obj.end])

    elif isinstance(obj, Duration):
        # Tag 14 (compact) is the `[seconds, nanoseconds]` form. Tag 13 carries
        # the *string* form ("1h30m"), so pairing it with the array payload
        # produced a frame the server rejects with HTTP 400 - a `Duration`
        # could be read back but never sent. The SDK's own decoder accepts
        # either shape, which is why this survived round-trip tests.
        tagged = CBORTag(constants.TAG_DURATION_COMPACT, obj.get_seconds_and_nano())

    elif isinstance(obj, Datetime):
        tagged = CBORTag(constants.TAG_DATETIME, obj.dt)

    elif isinstance(obj, (set, frozenset)):
        # SurrealDB uses its own set tag (56); the bundled cbor2 encoder would
        # otherwise emit tag 258, which our decoder does not understand.
        tagged = CBORTag(constants.TAG_SET, list(obj))

    elif isinstance(obj, NullType):
        # Plain CBOR null, which SurrealDB reads as NULL. `None` is handled by
        # the encoder's own `encode_none` and goes out as tag 6 (NONE) - see
        # `surrealdb.data.types.null` for why the two are kept apart.
        encoder.encode_length(7, _CBOR_NULL_SUBTYPE)
        return

    else:
        # `BufferError` means a buffer operation failed; this is "you handed me
        # a value I have no encoder for", which is a type problem. Raising the
        # semantically correct builtin also keeps it distinguishable from the
        # SurrealError tree, which covers operational failures rather than
        # unserialisable arguments.
        raise TypeError(
            f"cannot encode {type(obj).__name__} for SurrealDB; supported types "
            "are the JSON scalars, list, dict, set, bytes, and the surrealdb "
            "data types (RecordID, Table, Datetime, Duration, Range, Geometry, "
            "Decimal, UUID)"
        )

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
        # `_unchecked`, not the constructor: the constructor validates the id
        # type, and applying that to a value the *server* chose would turn a
        # future server's new id type into an unreadable record - and lose the
        # rest of the response with it, since this runs inside the decode of the
        # whole frame.
        return RecordID._unchecked(  # pyright: ignore[reportPrivateUsage]
            tag.value[0], tag.value[1]
        )

    elif tag.tag == constants.TAG_FILE:
        # `[bucket, key]`. Built unchecked: the server is the authority on what
        # a file reference is, and refusing to decode one the SDK dislikes would
        # lose the whole response rather than the one value.
        if not isinstance(tag.value, (list, tuple)) or len(tag.value) != 2:
            raise UnexpectedResponseError(
                f"expected a [bucket, key] pair for a file, got {tag.value!r}"
            )
        return File._unchecked(  # pyright: ignore[reportPrivateUsage]
            tag.value[0],
            tag.value[1],
        )

    elif tag.tag == constants.TAG_TABLE_NAME:
        return Table._unchecked(tag.value)  # pyright: ignore[reportPrivateUsage]

    elif tag.tag == constants.TAG_BOUND_INCLUDED:
        return BoundIncluded(tag.value)

    elif tag.tag == constants.TAG_BOUND_EXCLUDED:
        return BoundExcluded(tag.value)

    elif tag.tag == constants.TAG_RANGE:
        return Range(tag.value[0], tag.value[1])

    elif tag.tag == constants.TAG_DURATION_COMPACT:
        # The server omits trailing zero components, so a zero duration arrives
        # as an EMPTY array. Indexing [0] then raised IndexError and destroyed
        # the whole response, not just the field - and an ordinary expression
        # such as `time::now() - time::now()` produces one.
        if not tag.value:
            return Duration.parse(0, 0)
        if len(tag.value) == 1:
            return Duration.parse(tag.value[0], 0)  # seconds only
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
        # `[seconds, nanoseconds]`. `datetime` resolves to microseconds, so
        # this used to drop the last three digits - and writing the value back
        # then stored the truncated form, destroying precision in the database
        # on an ordinary read-modify-write. `PreciseDatetime` is a `datetime`
        # that keeps the remainder, so the value can be written back unchanged.
        seconds = tag.value[0] if tag.value else 0
        nanoseconds = tag.value[1] if len(tag.value) > 1 else 0
        return PreciseDatetime.from_seconds_and_nanos(seconds, nanoseconds)

    elif tag.tag == constants.TAG_UUID_STRING:
        # Defensive: the server encodes UUIDs with native tag 37, but decode a
        # string-tagged UUID (tag 9) too, in case one is ever received.
        return uuid.UUID(tag.value)

    elif tag.tag == constants.TAG_DECIMAL_STRING:
        return decimal.Decimal(tag.value)

    elif tag.tag == constants.TAG_SET:
        # `SurrealSet`, not a Python `set` and not a plain list. A Python set
        # cannot hold the objects and arrays a `set<object>` column contains, so
        # decoding into one raised `unhashable type: 'dict'` and lost the whole
        # response. A plain list can hold them but is a *different type* to the
        # server, so writing a record back either failed on a schemafull field
        # or silently turned a schemaless one into an array. `SurrealSet` reads
        # like the sequence it is and encodes back as a set - see
        # `surrealdb.data.types.set`.
        return SurrealSet(tag.value) if isinstance(tag.value, list) else tag.value

    else:
        # Unlike the encoder's unsupported-type case, this is not a caller
        # mistake: the server sent a tag this SDK does not know, which is an
        # operational failure and belongs in the SurrealError hierarchy so
        # `except SurrealError` covers it.
        raise UnexpectedResponseError(
            f"no decoder for CBOR tag {tag.tag}; the server sent a value this "
            "version of the SDK does not understand"
        )


# SurrealDB stores integers as signed 64-bit. A Python int above the signed
# maximum still fits CBOR's unsigned range, so it encoded cleanly and the
# server reinterpreted the bits - 2**63 came back as -9223372036854775808 and
# 2**64-1 as -1, with no error anywhere.
_I64_MIN = -(2**63)
_I64_MAX = 2**63 - 1


def _encode_precise_datetime(encoder: CBOREncoder, value: PreciseDatetime) -> None:
    """Send all nine fractional digits, which SurrealDB stores faithfully."""
    encoder.encode(CBORTag(constants.TAG_DATETIME, value.isoformat_with_nanoseconds()))


class _SurrealEncoder(CBOREncoder):
    """CBOR encoder that routes Python sets through SurrealDB's set tag.

    The bundled cbor2 encoder natively serialises ``set``/``frozenset`` using
    CBOR tag 258, but SurrealDB expects its own set tag (56). Dropping the
    built-in set encoders lets sets fall through to :func:`default_encoder`,
    which emits ``constants.TAG_SET``.

    It also refuses an integer SurrealDB cannot represent, rather than letting
    it wrap silently on the server.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._encoders.pop(set, None)
        self._encoders.pop(frozenset, None)

        # `SurrealSet` is a `list` subclass, and the generic lookup resolves a
        # subclass through `issubclass`, so it would find `list`'s encoder and
        # emit a plain array - which is exactly the bug this type exists to
        # stop. An exact-type registration is consulted first, so this wins.
        def _encode_surreal_set(encoder: CBOREncoder, value: SurrealSet) -> None:
            encoder.encode(CBORTag(constants.TAG_SET, list(value)))

        self._encoders[SurrealSet] = _encode_surreal_set

        # Registered for the exact subclass only, so a plain `datetime` keeps
        # cbor2's native encoding untouched. Without this the native encoder
        # claims the subclass through the MRO and silently drops the
        # nanoseconds again - the `default=` hook never sees it.
        self._encoders[PreciseDatetime] = _encode_precise_datetime

        encode_int = self._encoders[int]

        def _encode_checked_int(encoder: CBOREncoder, value: int) -> None:
            if not _I64_MIN <= value <= _I64_MAX:
                raise ValueError(
                    f"integer {value} is outside SurrealDB's signed 64-bit "
                    f"range ({_I64_MIN} to {_I64_MAX}); it would be stored as a "
                    "different number. Send it as a string or a Decimal instead."
                )
            encode_int(encoder, value)

        self._encoders[int] = _encode_checked_int


def encode(obj: Any) -> bytes:
    with BytesIO() as fp:
        _SurrealEncoder(fp, default=default_encoder, timezone=timezone.utc).encode(obj)
        return fp.getvalue()


def decode(data: bytes) -> Any:
    """Decode a SurrealDB CBOR payload.

    Plain CBOR null becomes :data:`Null`, not ``None``: on this wire a null is
    SurrealDB's NULL, which is a different value from its NONE. The public
    ``surrealdb.cbor`` package is a general-purpose CBOR implementation and is
    left alone - ``loads(b"\\xf6")`` there still returns ``None``.
    """
    with BytesIO(data) as fp:
        decoder = CBORDecoder(fp, tag_hook=tag_decoder)
        decoder.null_value = Null
        return decoder.decode()
