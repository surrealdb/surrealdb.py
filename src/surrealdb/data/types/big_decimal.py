"""SurrealDB 4.0's ``bigdecimal``: a decimal of arbitrary precision."""

from __future__ import annotations

from decimal import Context, Decimal, InvalidOperation

# PostgreSQL numeric's limits, which SurrealDB's bigdecimal takes.
_INTEGER_DIGITS_MAX = 131_072
_FRACTION_DIGITS_MAX = 16_383


class BigDecimal(Decimal):
    """A ``Decimal`` that SurrealDB stores as a ``bigdecimal`` rather than a ``decimal``.

    SurrealDB's ``decimal`` holds a 96-bit mantissa with at most 28 digits after
    the point. A ``bigdecimal`` holds up to 131072 digits before the point and
    16383 after, as PostgreSQL's numeric does, and keeps its scale as written:
    ``BigDecimal("1.50")`` keeps its zero. It is a ``Decimal`` in every way, so
    arithmetic gives back a plain ``Decimal``.

    Over ``cbor.2`` it is sent as tag 192. The server sends a bigdecimal that
    fits a ``decimal`` as a ``decimal``, so such a value reads back as a
    ``Decimal``. Over plain ``cbor`` (servers before 4.0) one that fits is sent
    as a ``decimal``, and one that does not as its text.
    """

    __slots__ = ()

    def __new__(
        cls, value: Decimal | float | str = "0", context: Context | None = None
    ) -> BigDecimal:
        try:
            instance = super().__new__(cls, value, context)
        except InvalidOperation:
            raise ValueError(
                f"{value!r} is not a number; pass one such as '1.50' or 10**40"
            ) from None
        _sign, digits, exponent = instance.as_tuple()
        if not isinstance(exponent, int):
            raise ValueError(
                f"a bigdecimal is a finite number, not {value!r}: SurrealDB has no "
                "NaN or infinite bigdecimal"
            )
        if (
            len(digits) + exponent > _INTEGER_DIGITS_MAX
            or -exponent > _FRACTION_DIGITS_MAX
        ):
            raise ValueError(
                f"{instance} is beyond a bigdecimal's {_INTEGER_DIGITS_MAX} digits "
                f"before the point and {_FRACTION_DIGITS_MAX} after it"
            )
        return instance

    def __repr__(self) -> str:
        return f"BigDecimal('{self}')"
