"""The embedded engine reports failures the way the other transports do.

Lives here rather than beside the rest of the error-hierarchy tests because it
needs the optional native engine: the core CI job installs no engine, and the
embedded job runs only this directory, so a guarded test in the other file
would never execute in CI at all.
"""

import pytest

from surrealdb import Surreal
from surrealdb.errors import ConnectionUnavailableError, SurrealError


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
