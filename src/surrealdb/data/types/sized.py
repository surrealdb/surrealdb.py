"""SurrealDB 4.0's sized number kinds: i8, u8, i16, u16, i32, u32, u64, f16, f32.

Each is a subclass of ``int`` or ``float``, so it works wherever a number does,
and arithmetic gives back a plain ``int`` or ``float``. What the subclass adds
is the kind: over ``cbor.2`` a sized number is sent with its tag and SurrealDB
stores it at that width, and a sized number read over ``cbor.2`` comes back as
this type. Over plain ``cbor`` (servers before 4.0) the server widens them, so
an ``int``, a ``float`` or, for a ``u64`` above the signed 64-bit range, a
``Decimal`` is sent and read instead.

``I8(5) == 5`` holds, as it does in SurrealDB; compare ``type()`` to tell them
apart.
"""

import math
import struct
from typing import ClassVar, SupportsFloat, SupportsIndex, SupportsInt


class SizedInt(int):
    """An integer of a fixed width. Use a subclass: :class:`I8` to :class:`U64`."""

    MIN: ClassVar[int]
    MAX: ClassVar[int]

    def __new__(cls, value: SupportsInt | SupportsIndex | str = 0) -> "SizedInt":
        if isinstance(value, float) and not value.is_integer():
            raise ValueError(f"{cls.__name__} holds whole numbers, not {value!r}")
        instance = super().__new__(cls, value)
        if not cls.MIN <= instance <= cls.MAX:
            raise ValueError(
                f"{int(instance)} is outside the {cls.__name__} range "
                f"({cls.MIN} to {cls.MAX}); use a wider kind or a plain int"
            )
        return instance

    def __repr__(self) -> str:
        return f"{type(self).__name__}({int(self)})"

    def __reduce__(self) -> tuple[type, tuple[int]]:
        return (type(self), (int(self),))


class I8(SizedInt):
    """A signed 8-bit integer (SurrealDB ``i8``)."""

    MIN = -(2**7)
    MAX = 2**7 - 1


class U8(SizedInt):
    """An unsigned 8-bit integer (SurrealDB ``u8``)."""

    MIN = 0
    MAX = 2**8 - 1


class I16(SizedInt):
    """A signed 16-bit integer (SurrealDB ``i16``)."""

    MIN = -(2**15)
    MAX = 2**15 - 1


class U16(SizedInt):
    """An unsigned 16-bit integer (SurrealDB ``u16``)."""

    MIN = 0
    MAX = 2**16 - 1


class I32(SizedInt):
    """A signed 32-bit integer (SurrealDB ``i32``)."""

    MIN = -(2**31)
    MAX = 2**31 - 1


class U32(SizedInt):
    """An unsigned 32-bit integer (SurrealDB ``u32``)."""

    MIN = 0
    MAX = 2**32 - 1


class U64(SizedInt):
    """An unsigned 64-bit integer (SurrealDB ``u64``), up to 18446744073709551615."""

    MIN = 0
    MAX = 2**64 - 1


class SizedFloat(float):
    """A float of a fixed width. Use a subclass: :class:`F16` or :class:`F32`."""

    FORMAT: ClassVar[str]

    def __new__(cls, value: SupportsFloat | SupportsIndex | str = 0.0) -> "SizedFloat":
        instance = super().__new__(cls, value)
        if not math.isnan(instance) and cls.narrowed(instance) != instance:
            raise ValueError(
                f"{float(instance)!r} cannot be held exactly by {cls.__name__}; "
                f"pass a value {cls.__name__} can represent, or use a plain float"
            )
        return instance

    @classmethod
    def narrowed(cls, value: float) -> float:
        """*value* rounded to this width, or ``inf`` when it is out of range."""
        try:
            narrowed: float = struct.unpack(cls.FORMAT, struct.pack(cls.FORMAT, value))[
                0
            ]
        except OverflowError:
            return math.copysign(math.inf, value)
        return narrowed

    def __repr__(self) -> str:
        return f"{type(self).__name__}({float(self)!r})"

    def __reduce__(self) -> tuple[type, tuple[float]]:
        return (type(self), (float(self),))


class F16(SizedFloat):
    """A half-precision float (SurrealDB ``f16``)."""

    FORMAT = "<e"


class F32(SizedFloat):
    """A single-precision float (SurrealDB ``f32``)."""

    FORMAT = "<f"
