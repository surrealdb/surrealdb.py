"""``surrealkv+versioned://`` enables MVCC time-travel queries.

The scheme is documented in the README, advertised in the CHANGELOG, and named
in ``UnsupportedEngineError``'s own message as a valid embedded form - but it
never worked. The engine matches storage flavours exactly and takes versioning
as a *query parameter*, so ``surrealkv+versioned`` arrived as an unknown
flavour and every path failed with "Unable to load the specified datastore".

These tests assert the behaviour the scheme promises rather than merely that a
connection opens, because opening successfully is exactly what a translation to
plain ``surrealkv://`` would also do while silently dropping versioning.
"""

import datetime
import tempfile
import time
from pathlib import Path

import pytest

from surrealdb import BlockingSurrealConnection, Surreal
from surrealdb.errors import SurrealError


def _write_then_update(db: BlockingSurrealConnection) -> str:
    """Create a record, note the time, then change it. Returns the timestamp."""
    db.use("test", "test")
    db.query("CREATE thing:1 SET n = 1").first()
    stamp = (
        datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    )
    # The version stamp has to fall strictly between the two writes.
    time.sleep(0.05)
    db.query("UPDATE thing:1 SET n = 2").first()
    return stamp


def test_versioned_store_answers_time_travel_queries() -> None:
    """A ``VERSION`` query returns the value as of that moment, not the latest."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "versioned"

        with Surreal(f"surrealkv+versioned://{db_path}") as db:
            stamp = _write_then_update(db)

            assert db.query("SELECT n FROM thing:1").first() == [{"n": 2}]
            assert db.query(f'SELECT n FROM thing:1 VERSION d"{stamp}"').first() == [
                {"n": 1}
            ]


def test_plain_surrealkv_does_not_support_time_travel() -> None:
    """The plain scheme rejects a ``VERSION`` query, so the two are distinguishable.

    This is what stops the versioned scheme from being "fixed" by quietly
    aliasing it to ``surrealkv://``: that would open fine and lose the feature.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "plain"

        with Surreal(f"surrealkv://{db_path}") as db:
            stamp = _write_then_update(db)

            with pytest.raises(SurrealError):
                db.query(f'SELECT n FROM thing:1 VERSION d"{stamp}"').first()


def test_versioned_store_persists_across_connections() -> None:
    """Reopening the same versioned path sees the data written before."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_url = f"surrealkv+versioned://{Path(tmpdir) / 'reopened'}"

        with Surreal(db_url) as db:
            db.use("test", "test")
            db.create("person:one", {"name": "Ada"})

        with Surreal(db_url) as db:
            db.use("test", "test")

            assert db.select("person:one")["name"] == "Ada"


def test_versioned_scheme_preserves_a_caller_query_string() -> None:
    """Versioning is appended to the caller's options rather than replacing them."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "withopts"

        with Surreal(f"surrealkv+versioned://{db_path}?sync=never") as db:
            stamp = _write_then_update(db)

            assert db.query(f'SELECT n FROM thing:1 VERSION d"{stamp}"').first() == [
                {"n": 1}
            ]
