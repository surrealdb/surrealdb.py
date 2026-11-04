"""How the blocking websocket transport opens its socket, against a fake server."""

import warnings
from collections.abc import Iterator

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from tests.unit_tests.fake_surreal import FakeSurreal


@pytest.fixture
def fake() -> Iterator[FakeSurreal]:
    server = FakeSurreal()
    try:
        yield server
    finally:
        server.close()


def test_the_socket_is_opened_as_websockets_expects(fake: FakeSurreal) -> None:
    """websockets 17.1 warns on the first send of a socket it was not told to open directly.

    The transport holds its socket for the connection's life and closes it
    itself, which is what websockets' ``legacy=True`` asks for; earlier
    versions do not warn, and do not take the flag.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        db = BlockingWsSurrealConnection(fake.url)
        try:
            db.version()
        finally:
            db.close()
    assert [str(w.message) for w in caught if "connect()" in str(w.message)] == []
