"""A strict decoder for SurrealDB's CBOR, plain ``cbor`` and ``cbor.2``.

It reads only what a SurrealDB 4 server reads, so no input decodes two ways or
quietly loses data: integers within i64, maps with unique text keys, and only
SurrealDB's own tags, each with the payload its spec gives
(surrealdb-protocol ``spec/cbor-tags.yaml``). Anything else raises
:class:`UnexpectedResponseError`.
"""

import re
import struct
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, NoReturn

from surrealdb.data._record_id_text import parse_record_id
from surrealdb.data.types import constants
from surrealdb.data.types.datetime import PreciseDatetime
from surrealdb.data.types.duration import Duration
from surrealdb.data.types.file import File
from surrealdb.data.types.geometry import (
    Geometry,
    GeometryCollection,
    GeometryLine,
    GeometryMultiLine,
    GeometryMultiPoint,
    GeometryMultiPolygon,
    GeometryPoint,
    GeometryPolygon,
)
from surrealdb.data.types.null import Null
from surrealdb.data.types.range import Bound, BoundExcluded, BoundIncluded, Range
from surrealdb.data.types.record_id import RecordID
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
from surrealdb.errors import InvalidGeometryError, UnexpectedResponseError

_I64_MIN = -(2**63)
_I64_MAX = 2**63 - 1
_U64_MAX = 2**64 - 1
_NANOS = 1_000_000_000

# The datetimes SurrealDB holds (chrono's range), and the part of it Python's
# `datetime` can (years 1 to 9999).
_CHRONO_MIN = -8334601228800
_CHRONO_MAX = 8210266876799
_PYTHON_MIN = -62135596800
_PYTHON_MAX = 253402300799

# rust_decimal: a 96-bit mantissa and at most 28 fractional digits.
_DECIMAL = re.compile(r"-?\d+(?:\.(\d+))?")
_DECIMAL_MANTISSA_MAX = 2**96 - 1
_DECIMAL_SCALE_MAX = 28

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

_SIZED_INTS: dict[int, type[SizedInt]] = {
    constants.TAG_I8: I8,
    constants.TAG_U8: U8,
    constants.TAG_I16: I16,
    constants.TAG_U16: U16,
    constants.TAG_I32: I32,
    constants.TAG_U32: U32,
    constants.TAG_U64: U64,
}
_SIZED_FLOATS: dict[int, type[SizedFloat]] = {
    constants.TAG_F16: F16,
    constants.TAG_F32: F32,
}

_REFUSED_TAGS = {
    0: "tag 0 (a datetime as text); SurrealDB sends datetimes as tag 12",
    9: "tag 9 (a uuid as text); SurrealDB sends uuids as tag 37",
    13: "tag 13 (a duration as text); SurrealDB sends durations as tag 14",
}


class _Wide(int):
    """An integer past i64, which only tag 14's seconds and tag 186 may carry."""


class _Break:
    """The end of an indefinite-length item."""


_BREAK = _Break()


def _refuse(message: str) -> NoReturn:
    raise UnexpectedResponseError(f"invalid SurrealDB CBOR: {message}")


class Decoder:
    """Decodes one CBOR item that fills the whole input."""

    def __init__(self, data: bytes, *, v2: bool) -> None:
        self._data = data
        self._pos = 0
        self._v2 = v2

    def decode(self) -> Any:
        value = self._value()
        if self._pos != len(self._data):
            _refuse(f"{len(self._data) - self._pos} bytes after the item")
        return value

    def _read(self, n: int) -> bytes:
        end = self._pos + n
        if end > len(self._data):
            _refuse("the input ends inside an item")
        chunk = self._data[self._pos : end]
        self._pos = end
        return chunk

    def _length(self, info: int) -> int | None:
        if info < 24:
            return info
        if info == 24:
            return self._read(1)[0]
        if info == 25:
            return int.from_bytes(self._read(2), "big")
        if info == 26:
            return int.from_bytes(self._read(4), "big")
        if info == 27:
            return int.from_bytes(self._read(8), "big")
        if info == 31:
            return None
        _refuse(f"reserved additional information {info}")

    def _definite(self, info: int) -> int:
        length = self._length(info)
        if length is None:
            _refuse("an indefinite length where only a definite one is allowed")
        return length

    def _value(self) -> Any:
        """The next item, refusing an integer past i64."""
        item = self._item()
        if isinstance(item, _Wide):
            _refuse(f"integer {int(item)} is outside the 64-bit signed range")
        if item is _BREAK:
            _refuse("a break outside an indefinite-length item")
        return item

    def _item(self) -> Any:
        initial = self._read(1)[0]
        major, info = initial >> 5, initial & 0x1F
        if major == 0:
            n = self._definite(info)
            return n if n <= _I64_MAX else _Wide(n)
        if major == 1:
            n = -1 - self._definite(info)
            return n if n >= _I64_MIN else _Wide(n)
        if major == 2:
            return self._string(info, major, bytes)
        if major == 3:
            return self._string(info, major, str)
        if major == 4:
            return self._array(info)
        if major == 5:
            return self._map(info)
        if major == 6:
            return self._tag(self._definite(info))
        return self._simple(info)

    def _string(self, info: int, major: int, kind: type) -> Any:
        length = self._length(info)
        if length is not None:
            return self._chunk(length, kind)
        chunks = []
        while True:
            initial = self._read(1)[0]
            if initial == 0xFF:
                break
            if initial >> 5 != major or initial & 0x1F == 31:
                _refuse(
                    f"an indefinite {kind.__name__} string with a chunk of another kind"
                )
            chunks.append(self._chunk(self._definite(initial & 0x1F), kind))
        return kind().join(chunks)

    def _chunk(self, length: int, kind: type) -> Any:
        raw = self._read(length)
        if kind is bytes:
            return raw
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            _refuse("text that is not UTF-8")

    def _array(self, info: int) -> list[Any]:
        length = self._length(info)
        if length is not None:
            return [self._value() for _ in range(length)]
        items = []
        while (item := self._item()) is not _BREAK:
            if isinstance(item, _Wide):
                _refuse(f"integer {int(item)} is outside the 64-bit signed range")
            items.append(item)
        return items

    def _map(self, info: int) -> dict[str, Any]:
        length = self._length(info)
        result: dict[str, Any] = {}
        count = 0
        while length is None or count < length:
            key = self._item()
            if length is None and key is _BREAK:
                break
            if not isinstance(key, str):
                _refuse(f"an object key that is not text: {key!r}")
            if key in result:
                _refuse(f"duplicate key {key!r} in an object")
            result[key] = self._value()
            count += 1
        return result

    def _simple(self, info: int) -> Any:
        if info == 20:
            return False
        if info == 21:
            return True
        if info == 22:
            return Null
        if info == 25:
            return struct.unpack(">e", self._read(2))[0]
        if info == 26:
            return struct.unpack(">f", self._read(4))[0]
        if info == 27:
            return struct.unpack(">d", self._read(8))[0]
        if info == 31:
            return _BREAK
        _refuse(f"simple value {info}, which SurrealDB does not use")

    def _tag(self, tag: int) -> Any:
        if tag in _SIZED_INTS or tag in _SIZED_FLOATS:
            if not self._v2:
                _refuse(f"tag {tag} (a sized number) outside cbor.2")
            return self._sized(tag)
        if tag == constants.TAG_DURATION_COMPACT:
            return _duration(self._wide_array())
        reader = _TAGS.get(tag)
        if reader is None:
            reason = _REFUSED_TAGS.get(tag, f"tag {tag}, which SurrealDB does not use")
            _refuse(reason)
        return reader(self._value())

    def _wide_array(self) -> Any:
        initial = self._read(1)[0]
        if initial >> 5 != 4:
            self._pos -= 1
            return self._value()
        length = self._definite(initial & 0x1F)
        return [self._item() for _ in range(length)]

    def _sized(self, tag: int) -> Any:
        payload = self._item()
        if tag in _SIZED_INTS:
            kind = _SIZED_INTS[tag]
            if not isinstance(payload, int) or isinstance(payload, bool):
                _refuse(f"tag {tag} ({kind.__name__}) over {payload!r}, not an integer")
            try:
                return kind(int(payload))
            except ValueError as exc:
                _refuse(str(exc))
        if isinstance(payload, _Wide):
            _refuse(f"integer {int(payload)} is outside the 64-bit signed range")
        floating = _SIZED_FLOATS[tag]
        if not isinstance(payload, float):
            _refuse(f"tag {tag} ({floating.__name__}) over {payload!r}, not a float")
        try:
            return floating(payload)
        except ValueError as exc:
            _refuse(str(exc))


def _pair(value: Any, what: str) -> list[Any]:
    if not isinstance(value, list) or len(value) != 2:
        _refuse(f"{what} must be a two-element array, got {value!r}")
    return value


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool | SizedInt)


def _none(value: Any) -> None:
    if value is not Null:
        _refuse(f"tag 6 (NONE) must carry null, got {value!r}")


def _table(value: Any) -> Table:
    if not isinstance(value, str):
        _refuse(f"a table name must be text, got {value!r}")
    return Table._unchecked(value)  # pyright: ignore[reportPrivateUsage]


def _record_key(key: Any) -> Any:
    if isinstance(key, SizedInt):
        if not _I64_MIN <= key <= _I64_MAX:
            _refuse(f"record id key {int(key)} is outside the 64-bit signed range")
        return int(key)
    if _is_int(key) or isinstance(key, str | uuid.UUID | list | dict):
        return key
    if isinstance(key, Range):
        for bound in (key.begin, key.end):
            if isinstance(bound, BoundIncluded | BoundExcluded):
                _record_key(bound.value)
        return key
    _refuse(f"a record id key cannot be {type(key).__name__} {key!r}")


def _record_id(value: Any) -> RecordID:
    if isinstance(value, str):
        try:
            table, key = parse_record_id(value)
        except ValueError as exc:
            _refuse(str(exc))
        return RecordID._unchecked(table, key)  # pyright: ignore[reportPrivateUsage]
    table, key = _pair(value, "a record id")
    if not isinstance(table, str):
        _refuse(f"a record id's table must be text, got {table!r}")
    return RecordID._unchecked(table, _record_key(key))  # pyright: ignore[reportPrivateUsage]


def _decimal(value: Any) -> Decimal:
    if not isinstance(value, str) or (match := _DECIMAL.fullmatch(value)) is None:
        _refuse(f"tag 10 must carry a decimal number as text, got {value!r}")
    scale = len(match.group(1) or "")
    mantissa = int(value.replace("-", "").replace(".", ""))
    if scale > _DECIMAL_SCALE_MAX or mantissa > _DECIMAL_MANTISSA_MAX:
        _refuse(
            f"decimal {value} is beyond a 96-bit mantissa with 28 fractional digits"
        )
    try:
        return Decimal(value)
    except InvalidOperation:
        _refuse(f"tag 10 must carry a decimal number as text, got {value!r}")


def _datetime(value: Any) -> PreciseDatetime:
    seconds, nanoseconds = _pair(value, "a datetime")
    if (
        not _is_int(seconds)
        or not _is_int(nanoseconds)
        or not 0 <= nanoseconds < _NANOS
    ):
        _refuse(f"a datetime must be [seconds, nanoseconds], got {value!r}")
    if not _CHRONO_MIN <= seconds <= _CHRONO_MAX:
        _refuse(f"datetime seconds {seconds} are outside SurrealDB's range")
    if not _PYTHON_MIN <= seconds <= _PYTHON_MAX:
        raise UnexpectedResponseError(
            f"the datetime {seconds} seconds from the epoch is outside the years 1 to "
            "9999 that Python's datetime holds"
        )
    moment = _EPOCH + timedelta(seconds=seconds, microseconds=nanoseconds // 1000)
    return PreciseDatetime(
        moment.year,
        moment.month,
        moment.day,
        moment.hour,
        moment.minute,
        moment.second,
        moment.microsecond,
        tzinfo=timezone.utc,
        nanosecond=nanoseconds % 1000,
    )


def _duration(value: Any) -> Duration:
    if not isinstance(value, list) or len(value) > 2:
        _refuse(f"a duration must be [seconds?, nanoseconds?], got {value!r}")
    seconds, nanoseconds = [*value, 0, 0][:2]
    if not _is_int(seconds) or not 0 <= seconds <= _U64_MAX:
        _refuse(f"duration seconds must be 0 to {_U64_MAX}, got {seconds!r}")
    if not _is_int(nanoseconds) or not 0 <= nanoseconds < _NANOS:
        _refuse(f"duration nanoseconds must be 0 to {_NANOS - 1}, got {nanoseconds!r}")
    return Duration(int(seconds) * _NANOS + nanoseconds)


def _uuid(value: Any) -> uuid.UUID:
    if not isinstance(value, bytes) or len(value) != 16:
        _refuse(f"tag 37 must carry 16 bytes, got {value!r}")
    return uuid.UUID(bytes=value)


def _bound(value: Any) -> Any:
    if value is Null or isinstance(value, Bound):
        return value
    _refuse(f"a range bound must be tag 50, tag 51 or null, got {value!r}")


def _range(value: Any) -> Range:
    begin, end = _pair(value, "a range")
    return Range(_bound(begin), _bound(end))


def _file(value: Any) -> File:
    bucket, key = _pair(value, "a file")
    if not isinstance(bucket, str) or not isinstance(key, str):
        _refuse(f"a file must be [bucket, key] as text, got {value!r}")
    return File._unchecked(bucket, key)  # pyright: ignore[reportPrivateUsage]


def _set(value: Any) -> SurrealSet:
    if not isinstance(value, list):
        _refuse(f"tag 56 must carry an array, got {value!r}")
    unique: list[Any] = []
    for item in value:
        if not any(_identical(item, seen) for seen in unique):
            unique.append(item)
    return SurrealSet(unique)


def _identical(a: Any, b: Any) -> bool:
    return type(a) is type(b) and bool(a == b)


def _point(value: Any) -> GeometryPoint:
    x, y = _pair(value, "a point")
    for c in (x, y):
        if isinstance(c, bool) or not isinstance(c, int | float):
            _refuse(f"a point's coordinates must be numbers, got {value!r}")
    return GeometryPoint(float(x), float(y))


def _members(value: Any, kind: type, what: str, minimum: int = 0) -> list[Any]:
    if not isinstance(value, list) or len(value) < minimum:
        _refuse(f"{what} must be an array of at least {minimum}, got {value!r}")
    if not all(isinstance(member, kind) for member in value):
        _refuse(f"{what} holds something other than {kind.__name__}")
    return value


def _line(value: Any) -> GeometryLine:
    points = _members(value, GeometryPoint, "a line", 2)
    return GeometryLine(*points)


def _closed(ring: GeometryLine) -> GeometryLine:
    points = ring.geometry_points
    if points[0] == points[-1]:
        return ring
    return GeometryLine(*points, points[0])


def _polygon(value: Any) -> GeometryPolygon:
    rings = _members(value, GeometryLine, "a polygon", 1)
    try:
        return GeometryPolygon(*(_closed(ring) for ring in rings))
    except (ValueError, InvalidGeometryError) as exc:
        _refuse(str(exc))


def _multi_point(value: Any) -> GeometryMultiPoint:
    return GeometryMultiPoint(*_members(value, GeometryPoint, "a multipoint"))


def _multi_line(value: Any) -> GeometryMultiLine:
    return GeometryMultiLine(*_members(value, GeometryLine, "a multiline"))


def _multi_polygon(value: Any) -> GeometryMultiPolygon:
    return GeometryMultiPolygon(*_members(value, GeometryPolygon, "a multipolygon"))


def _collection(value: Any) -> GeometryCollection:
    kinds = (Geometry, GeometryCollection)
    if not isinstance(value, list) or not all(isinstance(g, kinds) for g in value):
        _refuse(f"a geometry collection must hold geometries, got {value!r}")
    return GeometryCollection(*value)


_TAGS: dict[int, Callable[[Any], Any]] = {
    constants.TAG_NONE: _none,
    constants.TAG_TABLE_NAME: _table,
    constants.TAG_RECORD_ID: _record_id,
    constants.TAG_DECIMAL_STRING: _decimal,
    constants.TAG_DATETIME_COMPACT: _datetime,
    constants.TAG_UUID: _uuid,
    constants.TAG_RANGE: _range,
    constants.TAG_BOUND_INCLUDED: BoundIncluded,
    constants.TAG_BOUND_EXCLUDED: BoundExcluded,
    constants.TAG_FILE: _file,
    constants.TAG_SET: _set,
    constants.TAG_GEOMETRY_POINT: _point,
    constants.TAG_GEOMETRY_LINE: _line,
    constants.TAG_GEOMETRY_POLYGON: _polygon,
    constants.TAG_GEOMETRY_MULTI_POINT: _multi_point,
    constants.TAG_GEOMETRY_MULTI_LINE: _multi_line,
    constants.TAG_GEOMETRY_MULTI_POLYGON: _multi_polygon,
    constants.TAG_GEOMETRY_COLLECTION: _collection,
}
