"""Operational failures stay inside ``SurrealError``; caller mistakes do not.

The SDK guarantees that a failure it *encounters* - a bad endpoint, a closed
connection, a response it cannot read - is catchable with
``except SurrealError``. Several such failures used to escape as bare builtins,
so the guarantee held only on the paths that had been noticed.

The guarantee deliberately does not extend to a caller passing the wrong type.
That is a programming error, and Python's answer to it is ``TypeError`` /
``ValueError``; wrapping those in ``SurrealError`` would hide bugs inside the
except clause meant for operational failures.
"""

import pytest

from surrealdb import Surreal
from surrealdb.cbor import CBORTag, dumps
from surrealdb.data.cbor import decode, encode
from surrealdb.errors import (
    ConnectionUnavailableError,
    InvalidUrlError,
    SurrealError,
    UnexpectedResponseError,
    UnsupportedEngineError,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # Recognised scheme, malformed remainder.
        ("ws://localhost:99999", InvalidUrlError),
        ("ws://localhost:abc", InvalidUrlError),
        ("http://[::1", InvalidUrlError),
        # Unrecognised scheme - a different mistake with a different fix.
        ("ftp://localhost:8000", UnsupportedEngineError),
        ("rocksdb://tmp/db", UnsupportedEngineError),
        ("localhost:8000", UnsupportedEngineError),
    ],
)
def test_malformed_urls_stay_in_the_hierarchy(
    url: str, expected: type[SurrealError]
) -> None:
    """Every URL failure is a ``SurrealError``, whichever part is wrong.

    Only the scheme lookup was wrapped previously, so an unknown scheme raised
    ``UnsupportedEngineError`` while a bad port raised a bare ``ValueError`` -
    the same call landing inside or outside the hierarchy depending on which
    part of the URL the caller got wrong.
    """
    with pytest.raises(expected) as exc_info:
        Surreal(url)

    assert isinstance(exc_info.value, SurrealError)
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_embedded_use_after_close_matches_the_remote_transports() -> None:
    """A closed embedded connection reports what a closed socket reports.

    The engine is a native extension, so its "Database connection is closed"
    arrived as a bare ``RuntimeError`` while the websocket and HTTP transports
    raised ``ConnectionUnavailableError`` for the same mistake.
    """
    db = Surreal("mem://")
    db.use("test", "test")
    db.create("closed_test:1", {"n": 1})
    db.close()

    with pytest.raises(ConnectionUnavailableError) as exc_info:
        db.query("RETURN 1").first()

    assert isinstance(exc_info.value, SurrealError)
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_unknown_response_tag_is_a_surreal_error() -> None:
    """A tag the SDK cannot decode is the server's doing, so it is operational."""
    with pytest.raises(UnexpectedResponseError) as exc_info:
        decode(dumps(CBORTag(9999, [1])))

    assert isinstance(exc_info.value, SurrealError)


def test_unencodable_value_raises_type_error_not_surreal_error() -> None:
    """A value the SDK cannot encode is the caller's mistake, so it is a ``TypeError``.

    Deliberately outside the hierarchy. It previously raised ``BufferError``,
    which is neither: that builtin means a buffer operation failed.
    """

    class Unencodable:
        pass

    with pytest.raises(TypeError) as exc_info:
        encode({"v": Unencodable()})

    assert not isinstance(exc_info.value, SurrealError)
    assert "Unencodable" in str(exc_info.value)
