"""The embedded engine reopens after ``close()``, and ``invalidate()`` drops access.

**Reconnecting.** ``close()`` shuts the datastore down for good - the handle it
leaves behind answers every request with "Database connection is closed" - while
the native ``connect()`` was a no-op returning success. So ``close()`` then
``connect()`` *reported* a working connection and failed on the next query,
which is the worst of the three possible outcomes. Both websocket transports
have always reopened here.

**Invalidating.** The embedded datastore was built with authentication disabled,
which makes the engine skip every permission check for an anonymous session -
and ``invalidate()``, whose whole job is to drop the caller's identity, resets
the session to exactly that. Invalidating therefore *raised* privilege: a record
user who could not read a ``PERMISSIONS NONE`` table, and could not run
``INFO FOR ROOT``, could do both afterwards. Over websocket and HTTP the same
call has always left the session anonymous and denied.
"""

import shutil
import tempfile
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest

from surrealdb.connections.async_embedded import AsyncEmbeddedSurrealConnection
from surrealdb.connections.blocking_embedded import BlockingEmbeddedSurrealConnection
from surrealdb.errors import (
    ConnectionUnavailableError,
    NotAllowedError,
    NotFoundError,
)

RECORD_AUTH = """
DEFINE TABLE secret SCHEMALESS PERMISSIONS NONE;
CREATE secret:1 SET n = 1;
DEFINE TABLE person SCHEMALESS PERMISSIONS FOR select WHERE id = $auth.id;
DEFINE ACCESS acc ON DATABASE TYPE RECORD
  SIGNUP ( CREATE person SET email = $email, pass = crypto::argon2::generate($pass) )
  SIGNIN ( SELECT * FROM person WHERE email = $email
           AND crypto::argon2::compare(pass, $pass) )
  DURATION FOR SESSION 1h;
"""


@pytest.fixture
def store() -> Generator[str, None, None]:
    directory = Path(tempfile.mkdtemp())
    yield f"surrealkv://{directory / 'db'}"
    shutil.rmtree(directory, ignore_errors=True)


# ------------------------------------------------------------- reconnecting


def test_connect_after_close_gives_a_working_engine() -> None:
    connection = BlockingEmbeddedSurrealConnection("memory")
    connection.use("ns", "db")
    connection.query("CREATE t:1 SET n = 1").execute()
    connection.close()

    connection.connect()
    connection.use("ns", "db")

    # Asked of the engine, not of a flag: the old failure reported success and
    # then refused every request.
    assert connection.query("CREATE t:2 SET n = 2").first() is not None
    connection.close()


def test_a_closed_engine_still_refuses_requests() -> None:
    """``close()`` has to keep meaning closed until ``connect()`` is called."""
    connection = BlockingEmbeddedSurrealConnection("memory")
    connection.use("ns", "db")
    connection.close()

    with pytest.raises(ConnectionUnavailableError):
        connection.query("RETURN 1").execute()


def test_a_reopened_memory_database_starts_empty() -> None:
    """Documented, and asserted so it cannot change silently.

    The datastore that held the data was shut down, so there is nothing to
    reopen - the same way a reconnected websocket gets a new, unauthenticated
    server-side session rather than the one it had.
    """
    connection = BlockingEmbeddedSurrealConnection("memory")
    connection.use("ns", "db")
    connection.query("CREATE t:1 SET n = 1").execute()
    connection.close()

    connection.connect()
    connection.use("ns", "db")

    # The table is gone with the datastore, so this is "not there" rather than
    # "there and empty".
    with pytest.raises(NotFoundError):
        connection.query("SELECT * FROM t").execute()
    connection.close()


def test_a_reopened_file_database_keeps_its_data(store: str) -> None:
    connection = BlockingEmbeddedSurrealConnection(store)
    connection.use("ns", "db")
    connection.query("CREATE t:1 SET n = 1").execute()
    connection.close()

    connection.connect()
    connection.use("ns", "db")

    rows = connection.query("SELECT * FROM t").first()
    assert isinstance(rows, list) and len(rows) == 1
    connection.close()


def test_connect_on_an_open_engine_is_a_no_op() -> None:
    """Reopening an engine that was never closed would wipe an in-memory
    database, so the idempotent case has to stay idempotent."""
    connection = BlockingEmbeddedSurrealConnection("memory")
    connection.use("ns", "db")
    connection.query("CREATE t:1 SET n = 1").execute()

    connection.connect()

    rows = connection.query("SELECT * FROM t").first()
    assert isinstance(rows, list) and len(rows) == 1
    connection.close()


def test_a_context_manager_does_not_wipe_an_open_engine() -> None:
    """``__enter__`` goes through ``connect()``, so this is the same property
    seen from the entry point most people use."""
    connection = BlockingEmbeddedSurrealConnection("memory")
    connection.use("ns", "db")
    connection.query("CREATE t:1 SET n = 1").execute()

    with connection:
        rows = connection.query("SELECT * FROM t").first()
        assert isinstance(rows, list) and len(rows) == 1


async def test_the_async_engine_reconnects_too() -> None:
    connection = AsyncEmbeddedSurrealConnection("memory")
    await connection.use("ns", "db")
    await connection.query("CREATE t:1 SET n = 1").execute()
    await connection.close()

    with pytest.raises(ConnectionUnavailableError):
        await connection.query("RETURN 1").execute()

    await connection.connect()
    await connection.use("ns", "db")
    assert await connection.query("CREATE t:2 SET n = 2").first() is not None
    await connection.close()


# ------------------------------------------------------------- invalidating


def _record_user(connection: BlockingEmbeddedSurrealConnection) -> None:
    connection.query(RECORD_AUTH).execute()
    connection.signup(
        {
            "namespace": "ns",
            "database": "db",
            "access": "acc",
            "variables": {"email": f"{uuid.uuid4().hex}@example.com", "pass": "x"},
        }
    )


def test_invalidate_drops_to_anonymous() -> None:
    connection = BlockingEmbeddedSurrealConnection("memory")
    connection.use("ns", "db")
    _record_user(connection)

    connection.invalidate()

    with pytest.raises(NotAllowedError):
        connection.query("SELECT * FROM secret").execute()
    connection.close()


def test_invalidate_does_not_restore_root_access() -> None:
    """The precise inversion: after invalidating, the session could read a
    table the record user it replaced could not."""
    connection = BlockingEmbeddedSurrealConnection("memory")
    connection.use("ns", "db")
    _record_user(connection)
    assert connection.query("SELECT * FROM secret").first() == []

    connection.invalidate()

    with pytest.raises(NotAllowedError):
        connection.query("INFO FOR ROOT").execute()
    connection.close()


def test_permissions_still_apply_to_a_record_user() -> None:
    """The half that already worked, so a fix to the other half cannot quietly
    disable enforcement altogether."""
    connection = BlockingEmbeddedSurrealConnection("memory")
    connection.use("ns", "db")
    _record_user(connection)

    assert connection.query("SELECT * FROM secret").first() == []
    with pytest.raises(NotAllowedError):
        connection.query("INFO FOR ROOT").execute()
    connection.close()


def test_a_fresh_connection_has_full_access() -> None:
    """Opening an embedded database and using it without signing in is the
    documented way to use it, and enforcing authentication must not break it."""
    connection = BlockingEmbeddedSurrealConnection("memory")
    connection.use("ns", "db")

    connection.query("DEFINE TABLE t SCHEMALESS; CREATE t:1 SET n = 1;").execute()
    assert connection.query("INFO FOR ROOT").first() is not None
    rows = connection.query("SELECT * FROM t").first()
    assert isinstance(rows, list) and len(rows) == 1
    connection.close()


async def test_the_async_engine_invalidates_too() -> None:
    connection = AsyncEmbeddedSurrealConnection("memory")
    await connection.use("ns", "db")
    await connection.query(RECORD_AUTH).execute()
    await connection.signup(
        {
            "namespace": "ns",
            "database": "db",
            "access": "acc",
            "variables": {"email": f"{uuid.uuid4().hex}@example.com", "pass": "x"},
        }
    )

    await connection.invalidate()

    with pytest.raises(NotAllowedError):
        await connection.query("SELECT * FROM secret").execute()
    await connection.close()
