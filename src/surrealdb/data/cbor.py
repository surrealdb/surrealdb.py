import re
from datetime import date, datetime, time, timezone
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
from surrealdb.data.types.big_decimal import BigDecimal
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
from surrealdb.data.types.regex import Regex
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
from surrealdb.data.types.temporal import Interval, PlainDate, PlainTime, Timestamp

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

    elif isinstance(obj, re.Pattern):
        raise TypeError(
            f"cannot encode the compiled pattern {obj.pattern!r}: SurrealQL regexes "
            "use the syntax of Rust's regex crate, not Python's re. Wrap the "
            "pattern's text in Regex(...) to send it as a SurrealQL regex"
        )

    else:
        # `BufferError` means a buffer operation failed; this is "you handed me
        # a value I have no encoder for", which is a type problem. Raising the
        # semantically correct builtin also keeps it distinguishable from the
        # SurrealError tree, which covers operational failures rather than
        # unserialisable arguments.
        raise TypeError(
            f"cannot encode {type(obj).__name__} for SurrealDB; supported types "
            "are the JSON scalars, list, dict, set, bytes, date, time, and the "
            "surrealdb data types (RecordID, Table, Datetime, Duration, Range, "
            "Geometry, Decimal, UUID, the sized numbers, PlainDate, PlainTime, "
            "Timestamp, Interval, BigDecimal, Regex)"
        )

    encoder.encode(tagged)


def tag_decoder(
    decoder: CBORDecoder | None, tag: CBORTag, shareable_index: int | None = None
) -> Any:
    """The SurrealDB value for a tag cbor2 has already decoded, read as plain cbor.

    As a ``tag_hook``, the tags inside *tag* reach it already turned into the
    SDK's types - the points of a line, the bounds of a range - so it is
    written back out with :func:`encode`, which knows them, before it is read.
    """
    return decode(encode(tag))


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

# SurrealDB's decimal holds at most 28 digits after the point.
_DECIMAL_SCALE_MAX = 28


def _within_decimal_scale(value: Decimal) -> Decimal:
    """*value* without the trailing zeros that take it past SurrealDB's scale.

    Decimal arithmetic leaves them behind - ``Decimal("0E-30")`` is an
    ordinary result - and they change nothing about the number, but written
    out they are 30 digits after the point, which no SurrealDB decimal holds.
    Digits that are not zeros are left alone: dropping them would send a
    different number.
    """
    sign, digits, written = value.as_tuple()
    if not isinstance(written, int) or written >= -_DECIMAL_SCALE_MAX:
        return value
    exponent: int = written
    kept = list(digits)
    while exponent < -_DECIMAL_SCALE_MAX and len(kept) > 1 and kept[-1] == 0:
        kept.pop()
        exponent += 1
    if kept == [0]:
        exponent = max(exponent, -_DECIMAL_SCALE_MAX)
    return Decimal((sign, tuple(kept), exponent))


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


_SECONDS_PER_DAY = 86_400
_DECIMAL_MANTISSA_MAX = 2**96 - 1
_DECIMAL_DIGITS_MAX = len(str(_DECIMAL_MANTISSA_MAX))


def _speaks_v2(encoder: CBOREncoder) -> bool:
    return cast(_SurrealEncoder, encoder).v2


def _encode_plain_date(encoder: CBOREncoder, value: PlainDate) -> None:
    """Tag 100 over ``cbor.2``, and midnight UTC of the date, as tag 12, otherwise."""
    if _speaks_v2(encoder):
        encoder.encode_length(6, constants.TAG_DATE)
        encoder.encode_int(value.days)
        return
    seconds = value.days * _SECONDS_PER_DAY
    encoder.encode(CBORTag(constants.TAG_DATETIME_COMPACT, [seconds, 0]))


def _encode_date(encoder: CBOREncoder, value: date) -> None:
    """A ``datetime.date`` as a SurrealDB date, where cbor2 wrote tag 1004, which no server reads.

    Registered over cbor2's own ``date`` encoder, so it keeps that one's place
    after ``datetime`` in the encoder lookup, and a ``datetime`` subclass still
    finds the ``datetime`` encoder first.
    """
    _encode_plain_date(encoder, PlainDate.from_date(value))


def _encode_plain_time(encoder: CBOREncoder, value: PlainTime) -> None:
    """Tag 189 over ``cbor.2``, and the duration since midnight, as tag 14, otherwise."""
    if _speaks_v2(encoder):
        encoder.encode_length(6, constants.TAG_TIME)
        encoder.encode_length(0, value.nanoseconds)
        return
    _encode_duration(encoder, Duration(value.nanoseconds))


def _encode_time(encoder: CBOREncoder, value: time) -> None:
    """A naive ``datetime.time`` as a SurrealDB time, which has no zone."""
    _encode_plain_time(encoder, PlainTime.from_time(value))


def _encode_timestamp(encoder: CBOREncoder, value: Timestamp) -> None:
    """Tag 190 over ``cbor.2``, and the wall-clock time read as UTC, as tag 12, otherwise."""
    tag = (
        constants.TAG_TIMESTAMP
        if _speaks_v2(encoder)
        else constants.TAG_DATETIME_COMPACT
    )
    encoder.encode(CBORTag(tag, list(value.seconds_and_nanos)))


def _encode_interval(encoder: CBOREncoder, value: Interval) -> None:
    """Tag 191 over ``cbor.2``, and the ISO 8601 text otherwise, as the server widens one."""
    if _speaks_v2(encoder):
        parts = [value.months, value.days, value.microseconds]
        encoder.encode(CBORTag(constants.TAG_INTERVAL, parts))
        return
    encoder.encode_string(str(value))


def _as_decimal(value: Decimal) -> Decimal | None:
    """*value* as SurrealDB's ``decimal`` holds it, or ``None`` if it does not fit one."""
    sign, digits, exponent = value.as_tuple()
    if not isinstance(exponent, int):
        return None
    kept = list(digits)
    while exponent < 0 and len(kept) > 1 and kept[-1] == 0:
        kept.pop()
        exponent += 1
    if len(kept) + max(exponent, 0) > _DECIMAL_DIGITS_MAX:
        return None
    if exponent > 0:
        kept.extend([0] * exponent)
        exponent = 0
    if -exponent > _DECIMAL_SCALE_MAX:
        return None
    if int("".join(map(str, kept))) > _DECIMAL_MANTISSA_MAX:
        return None
    return Decimal((sign, tuple(kept), exponent))


def _encode_big_decimal(encoder: CBOREncoder, value: BigDecimal) -> None:
    """Tag 192 over ``cbor.2``, its scale as written, and as the server widens one otherwise.

    The server sends a bigdecimal that fits a decimal as tag 10, and one that
    does not as its text, so plain ``cbor`` sends it the same way.
    """
    text = format(value, "f")
    if _speaks_v2(encoder):
        encoder.encode(CBORTag(constants.TAG_BIGDECIMAL, text))
    elif (fitting := _as_decimal(value)) is not None:
        encoder.encode(CBORTag(constants.TAG_DECIMAL_STRING, format(fitting, "f")))
    else:
        encoder.encode_string(text)


def _encode_regex(encoder: CBOREncoder, value: Regex) -> None:
    """Tag 193, over ``cbor.2`` only: plain ``cbor`` has no form for a regex."""
    if not _speaks_v2(encoder):
        raise ValueError(
            f"{value!r} cannot be sent over plain cbor, which has no form for a "
            "regex; it needs cbor.2, which SurrealDB 4.0 servers speak"
        )
    encoder.encode(CBORTag(constants.TAG_REGEX, value.pattern))


class _SurrealEncoder(CBOREncoder):
    """CBOR encoder that routes Python sets through SurrealDB's set tag.

    The bundled cbor2 encoder natively serialises ``set``/``frozenset`` using
    CBOR tag 258, but SurrealDB expects its own set tag (56). Dropping the
    built-in set encoders lets sets fall through to :func:`default_encoder`,
    which emits ``constants.TAG_SET``.

    It also refuses an integer SurrealDB cannot represent, rather than letting
    it wrap silently on the server, and a compiled ``re.Pattern``, which cbor2
    would write as IANA tag 35: that names another regex syntax, and SurrealDB
    refuses it.
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
            text = format(_within_decimal_scale(value), "f")
            encoder.encode(CBORTag(constants.TAG_DECIMAL_STRING, text))

        self._encoders[Decimal] = _encode_plain_decimal
        for sized in _SIZED_TAGS:
            self._encoders[sized] = _encode_sized

        self._encoders[PlainDate] = _encode_plain_date
        self._encoders[date] = _encode_date
        self._encoders[PlainTime] = _encode_plain_time
        self._encoders[time] = _encode_time
        self._encoders[Timestamp] = _encode_timestamp
        self._encoders[Interval] = _encode_interval
        self._encoders[BigDecimal] = _encode_big_decimal
        self._encoders[Regex] = _encode_regex
        self._encoders.pop(re.Pattern, None)

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

    The two differ only in SurrealDB 4.0's kinds that plain ``cbor`` has no tag
    for: the sized numbers (:mod:`surrealdb.data.types.sized`), and the date,
    time, timestamp, interval (:mod:`surrealdb.data.types.temporal`),
    bigdecimal and regex. ``cbor.2`` tags them; plain ``cbor`` widens them as
    the server would, and refuses a regex, which it has no form for.
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
