from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from typing import Any, cast

from surrealdb.cbor import (
    CBORDecoder,
    CBOREncoder,
    CBORTag,
    shareable_encoder,
)
from surrealdb.data._decoder import Decoder
from surrealdb.data.types import constants
from surrealdb.data.types.datetime import Datetime, PreciseDatetime, parse_instant
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
from surrealdb.data.types.null import NullType
from surrealdb.data.types.range import BoundExcluded, BoundIncluded, Range
from surrealdb.data.types.record_id import RecordID, StringRecordId
from surrealdb.data.types.set import SurrealSet
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
from surrealdb.data.types.table import Table

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

    elif isinstance(obj, StringRecordId):
        tagged = CBORTag(constants.TAG_RECORD_ID, obj.value)

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
        # the *string* form ("1h30m"), which SurrealDB 4 refuses.
        _encode_duration(encoder, obj)
        return

    elif isinstance(obj, Datetime):
        tagged = CBORTag(
            constants.TAG_DATETIME_COMPACT, _seconds_and_nanos(parse_instant(obj.dt))
        )

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
    decoder: CBORDecoder | None, tag: CBORTag, shareable_index: int | None = None
) -> Any:
    """The SurrealDB value for a tag cbor2 has already decoded, read as plain cbor."""
    from surrealdb.cbor import dumps

    return decode(dumps(tag))


# SurrealDB stores integers as signed 64-bit. A Python int above the signed
# maximum still fits CBOR's unsigned range, so it encoded cleanly and the
# server reinterpreted the bits - 2**63 came back as -9223372036854775808 and
# 2**64-1 as -1, with no error anywhere.
_I64_MIN = -(2**63)
_I64_MAX = 2**63 - 1


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _seconds_and_nanos(value: datetime) -> list[int]:
    """The ``[seconds, nanoseconds]`` pair of tag 12, reading a naive value as UTC."""
    moment = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    delta = moment - _EPOCH
    nanosecond = value.nanosecond if isinstance(value, PreciseDatetime) else 0
    return [delta.days * 86400 + delta.seconds, delta.microseconds * 1000 + nanosecond]


_U64_MAX = 2**64 - 1
_NANOS = 1_000_000_000

_SIZED_TAGS: dict[type, int] = {
    I8: constants.TAG_I8,
    U8: constants.TAG_U8,
    I16: constants.TAG_I16,
    U16: constants.TAG_U16,
    I32: constants.TAG_I32,
    U32: constants.TAG_U32,
    U64: constants.TAG_U64,
    F16: constants.TAG_F16,
    F32: constants.TAG_F32,
}


def _encode_duration(encoder: CBOREncoder, value: Duration) -> None:
    """Tag 14 ``[seconds, nanoseconds]``, whose seconds run to u64, past an int's i64."""
    seconds, nanoseconds = divmod(value.elapsed, _NANOS)
    if not 0 <= seconds <= _U64_MAX:
        raise ValueError(
            f"{value!r} is outside the durations SurrealDB holds (0 to {_U64_MAX} "
            "seconds); a duration cannot be negative"
        )
    encoder.encode_length(6, constants.TAG_DURATION_COMPACT)
    encoder.encode_length(4, 2)
    encoder.encode_length(0, seconds)
    encoder.encode_length(0, nanoseconds)


def _encode_sized(encoder: CBOREncoder, value: SizedInt | SizedFloat) -> None:
    """A sized number: tagged over ``cbor.2``, widened as the server widens it otherwise."""
    if cast(_SurrealEncoder, encoder).v2:
        encoder.encode_length(6, _SIZED_TAGS[type(value)])
        if isinstance(value, SizedFloat):
            encoder.encode_float(float(value))
        elif value >= 0:
            encoder.encode_length(0, int(value))
        else:
            encoder.encode_length(1, -int(value) - 1)
    elif isinstance(value, SizedFloat):
        encoder.encode_float(float(value))
    elif value > _I64_MAX:
        encoder.encode(CBORTag(constants.TAG_DECIMAL_STRING, str(int(value))))
    else:
        encoder.encode_int(int(value))


def _encode_datetime(encoder: CBOREncoder, value: datetime) -> None:
    """Send a datetime as tag 12, which every SurrealDB 2.x, 3.x and 4.x server reads.

    cbor2 would write tag 0 (the datetime as text), which SurrealDB 4 refuses.
    """
    encoder.encode(CBORTag(constants.TAG_DATETIME_COMPACT, _seconds_and_nanos(value)))


class _SurrealEncoder(CBOREncoder):
    """CBOR encoder that routes Python sets through SurrealDB's set tag.

    The bundled cbor2 encoder natively serialises ``set``/``frozenset`` using
    CBOR tag 258, but SurrealDB expects its own set tag (56). Dropping the
    built-in set encoders lets sets fall through to :func:`default_encoder`,
    which emits ``constants.TAG_SET``.

    It also refuses an integer SurrealDB cannot represent, rather than letting
    it wrap silently on the server.
    """

    def __init__(self, *args: Any, v2: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.v2 = v2
        self._encoders.pop(set, None)
        self._encoders.pop(frozenset, None)

        # `SurrealSet` is a `list` subclass, and the generic lookup resolves a
        # subclass through `issubclass`, so it would find `list`'s encoder and
        # emit a plain array - which is exactly the bug this type exists to
        # stop. An exact-type registration is consulted first, so this wins.
        def _encode_surreal_set(encoder: CBOREncoder, value: SurrealSet) -> None:
            encoder.encode(CBORTag(constants.TAG_SET, list(value)))

        self._encoders[SurrealSet] = _encode_surreal_set

        # Registered for the subclass too, so the generic lookup never hands a
        # `PreciseDatetime` to an encoder that drops its nanoseconds.
        self._encoders[datetime] = _encode_datetime
        self._encoders[PreciseDatetime] = _encode_datetime

        self._encoders[Duration] = _encode_duration

        def _encode_plain_decimal(encoder: CBOREncoder, value: Decimal) -> None:
            # `str` writes exponent notation (`1E-28`), which SurrealDB refuses.
            if not value.is_finite():
                encoder.encode_decimal(value)
                return
            encoder.encode(CBORTag(constants.TAG_DECIMAL_STRING, format(value, "f")))

        self._encoders[Decimal] = _encode_plain_decimal
        for sized in _SIZED_TAGS:
            self._encoders[sized] = _encode_sized

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


def encode(obj: Any, *, v2: bool = False) -> bytes:
    """Encode *obj* for SurrealDB, as ``cbor.2`` when *v2* and as plain ``cbor`` otherwise.

    The two differ only in sized numbers (:mod:`surrealdb.data.types.sized`):
    ``cbor.2`` tags them, and plain ``cbor`` widens them as the server would.
    """
    with BytesIO() as fp:
        encoder = _SurrealEncoder(
            fp, default=default_encoder, timezone=timezone.utc, v2=v2
        )
        encoder.encode(obj)
        return fp.getvalue()


def decode(data: bytes, *, v2: bool = False) -> Any:
    """Decode a SurrealDB CBOR payload, as ``cbor.2`` when *v2* and as plain ``cbor`` otherwise.

    Plain CBOR null becomes :data:`Null`, not ``None``: on this wire a null is
    SurrealDB's NULL, which is a different value from its NONE. Decoding is as
    strict as a SurrealDB 4 server's, so input that does not hold a SurrealDB
    value raises :class:`~surrealdb.errors.UnexpectedResponseError`.
    """
    return Decoder(bytes(data), v2=v2).decode()
