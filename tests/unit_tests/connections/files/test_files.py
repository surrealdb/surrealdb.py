"""``db.files`` - the typed helpers over SurrealDB's ``file::*`` functions.

Every helper binds the ``File`` as a parameter rather than writing it into the
query, and these tests lean on that: the keys with spaces, accents and emoji
below **cannot be expressed** as a SurrealQL literal at all, because the
``f"bucket:/key"`` syntax accepts only ``[A-Za-z0-9_-./]`` and has no escape.
Bound, they work. That is the difference the parameter binding buys, so it is
asserted rather than assumed.
"""

import uuid
from typing import Any

import pytest

from surrealdb import File, FileMetadata
from surrealdb.connections.async_http import AsyncHttpSurrealConnection
from surrealdb.connections.async_ws import AsyncWsSurrealConnection
from surrealdb.connections.blocking_http import BlockingHttpSurrealConnection
from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection

# every byte value, so a transport that mangles high bytes or embedded NULs shows
EVERY_BYTE = bytes(range(256)) * 8


def _key(prefix: str = "") -> str:
    return f"/{prefix}{uuid.uuid4().hex[:10]}.bin"


# --------------------------------------------------------------- the round trip


def test_put_then_get_returns_the_same_bytes(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    f = File(bucket, _key())

    blocking_ws_connection.files.put(f, EVERY_BYTE)

    assert blocking_ws_connection.files.get(f) == EVERY_BYTE


def test_an_empty_file_round_trips(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    """``b""`` must come back as ``b""`` and not as ``None``, which means absent."""
    f = File(bucket, _key())

    blocking_ws_connection.files.put(f, b"")

    assert blocking_ws_connection.files.get(f) == b""
    assert blocking_ws_connection.files.exists(f) is True


@pytest.mark.parametrize(
    "key",
    [
        pytest.param("/a b.txt", id="space"),
        pytest.param("/héllo.txt", id="accent"),
        pytest.param("/emoji-\U0001f389.png", id="emoji"),
        pytest.param('/quote".txt', id="quote"),
        pytest.param("/back\\slash.txt", id="backslash"),
        pytest.param("/@at#hash.txt", id="symbols"),
    ],
)
def test_keys_the_literal_syntax_cannot_express_still_work(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str, key: str
) -> None:
    """The reason the helpers bind rather than interpolate.

    Written into a query these produce ``Parse error: ... file strings key's only
    allow alpha numeric characters and `_`, `-`, `.`, and `/``` - and there is no
    escaping that fixes it. Bound, they upload and read back.
    """
    f = File(bucket, key)
    assert f.is_literal_safe() is False

    blocking_ws_connection.files.put(f, b"payload")

    assert blocking_ws_connection.files.get(f) == b"payload"
    assert blocking_ws_connection.files.exists(f) is True


def test_the_key_is_normalised_consistently_on_both_sides(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    """Writing without a leading slash and reading with one is the same file."""
    name = uuid.uuid4().hex[:10]
    blocking_ws_connection.files.put(File(bucket, f"{name}.bin"), b"same")

    assert blocking_ws_connection.files.get(File(bucket, f"/{name}.bin")) == b"same"


# --------------------------------------------------------------- absence


def test_absent_files_report_absence_rather_than_raising(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    gone = File(bucket, _key("gone-"))

    assert blocking_ws_connection.files.get(gone) is None
    assert blocking_ws_connection.files.head(gone) is None
    assert blocking_ws_connection.files.exists(gone) is False


def test_deleting_is_idempotent(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    f = File(bucket, _key())
    blocking_ws_connection.files.put(f, b"x")

    blocking_ws_connection.files.delete(f)
    blocking_ws_connection.files.delete(f)  # must not raise

    assert blocking_ws_connection.files.exists(f) is False


# --------------------------------------------------------------- metadata


def test_head_reports_size_and_a_decoded_file(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    f = File(bucket, _key())
    blocking_ws_connection.files.put(f, EVERY_BYTE)

    meta = blocking_ws_connection.files.head(f)

    assert isinstance(meta, FileMetadata)
    assert meta.size == len(EVERY_BYTE)
    assert meta.file == f
    assert isinstance(meta.file, File), "the file arrives decoded, not as a raw tag"
    assert meta.updated is not None


def test_list_reports_every_file_in_the_bucket(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    keys = {_key("a-"), _key("b-"), _key("c-")}
    for key in keys:
        blocking_ws_connection.files.put(File(bucket, key), b"x")

    listed = blocking_ws_connection.files.list(bucket)

    assert {entry.file.key for entry in listed} == keys
    assert all(isinstance(entry, FileMetadata) for entry in listed)


def test_list_applies_limit_and_prefix(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    for key in ("/docs/one.txt", "/docs/two.txt", "/img/three.png"):
        blocking_ws_connection.files.put(File(bucket, key), b"x")

    assert len(blocking_ws_connection.files.list(bucket, limit=2)) == 2
    assert {
        e.file.key for e in blocking_ws_connection.files.list(bucket, prefix="/docs")
    } == {"/docs/one.txt", "/docs/two.txt"}


def test_list_start_is_exclusive(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    """Documented here because it is the kind of off-by-one that ships quietly."""
    for key in ("/a.txt", "/b.txt", "/c.txt"):
        blocking_ws_connection.files.put(File(bucket, key), b"x")

    listed = blocking_ws_connection.files.list(bucket, start="/b.txt")

    assert [e.file.key for e in listed] == ["/c.txt"]


def test_listing_a_missing_bucket_raises(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    """An empty bucket and a bucket that does not exist are different mistakes.

    Flattening the second to ``[]`` would hide a typo'd bucket name forever.
    """
    with pytest.raises(Exception, match="does not exist"):
        blocking_ws_connection.files.list("no_such_bucket_at_all")


# --------------------------------------------------------------- copy and move


def test_copy_duplicates_and_leaves_the_source(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    source, target = File(bucket, _key("src-")), File(bucket, _key("dst-"))
    blocking_ws_connection.files.put(source, b"content")

    blocking_ws_connection.files.copy(source, target)

    assert blocking_ws_connection.files.get(target) == b"content"
    assert blocking_ws_connection.files.get(source) == b"content"


def test_rename_moves_and_removes_the_source(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    source = File(bucket, _key("from-"))
    destination_key = _key("to-")
    blocking_ws_connection.files.put(source, b"content")

    blocking_ws_connection.files.rename(source, destination_key)

    assert blocking_ws_connection.files.get(File(bucket, destination_key)) == b"content"
    assert blocking_ws_connection.files.exists(source) is False


def test_put_if_not_exists_does_not_overwrite(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    """The server neither writes nor complains, which is easy to misread as a write."""
    f = File(bucket, _key())
    blocking_ws_connection.files.put(f, b"original")

    blocking_ws_connection.files.put_if_not_exists(f, b"replacement")

    assert blocking_ws_connection.files.get(f) == b"original"


def test_put_if_not_exists_writes_when_the_key_is_free(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    f = File(bucket, _key())

    blocking_ws_connection.files.put_if_not_exists(f, b"fresh")

    assert blocking_ws_connection.files.get(f) == b"fresh"


# --------------------------------------------------------------- caller mistakes


def test_a_non_file_target_is_refused_locally(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    with pytest.raises(TypeError, match=r"surrealdb\.File"):
        blocking_ws_connection.files.get("images:/a.png")  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


def test_renaming_to_a_file_says_to_pass_a_key(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    """Server-side this is "Incorrect arguments for function file::rename()".

    Asserting the *suggestion*, not just the type error. A plain "key must be a
    str" also comes out of the generic string check below it, so a test that
    accepted that could not tell whether the File-specific branch still existed -
    and the whole point of that branch is telling the caller what to pass
    instead.
    """
    f = File(bucket, _key())

    with pytest.raises(TypeError) as caught:
        blocking_ws_connection.files.rename(f, File(bucket, "/other.bin"))  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]

    message = str(caught.value)
    assert "key must be a str" in message
    assert "'/other.bin'" in message, "the message must name the key to pass instead"
    assert "same" in message, "and say that rename stays within one bucket"


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        pytest.param({"limit": 0}, ValueError, id="limit-zero"),
        pytest.param({"limit": -1}, ValueError, id="limit-negative"),
        pytest.param({"limit": "2"}, TypeError, id="limit-string"),
        pytest.param({"limit": True}, TypeError, id="limit-bool"),
        pytest.param({"prefix": 1}, TypeError, id="prefix-not-string"),
        pytest.param({"start": 1}, TypeError, id="start-not-string"),
    ],
)
def test_bad_list_options_are_refused_locally(
    blocking_ws_connection: BlockingWsSurrealConnection,
    bucket: str,
    kwargs: dict[str, Any],
    expected: type[Exception],
) -> None:
    with pytest.raises(expected):
        blocking_ws_connection.files.list(bucket, **kwargs)


def test_a_misspelled_option_is_a_type_error_not_a_silent_full_listing(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    """Why ``list`` takes keyword arguments instead of an options dict.

    The server *ignores* option keys it does not recognise - a probe with
    ``{"nonsense": 1}`` returned the whole bucket - so a passthrough dict would
    turn ``limti=2`` into "every file", with nothing to indicate why.
    """
    for key in ("/a.txt", "/b.txt", "/c.txt"):
        blocking_ws_connection.files.put(File(bucket, key), b"x")

    with pytest.raises(TypeError):
        blocking_ws_connection.files.list(bucket, limti=2)  # type: ignore[call-arg]  # pyright: ignore[reportCallIssue]


# --------------------------------------------------------------- every transport


def test_the_blocking_http_transport_agrees(
    blocking_http_connection: BlockingHttpSurrealConnection, bucket: str
) -> None:
    f = File(bucket, _key("http-"))

    blocking_http_connection.files.put(f, EVERY_BYTE)

    assert blocking_http_connection.files.get(f) == EVERY_BYTE
    meta = blocking_http_connection.files.head(f)
    assert meta is not None
    assert meta.size == len(EVERY_BYTE)


async def test_the_async_ws_transport_agrees(
    async_ws_connection: AsyncWsSurrealConnection, bucket: str
) -> None:
    f = File(bucket, _key("aws-"))

    await async_ws_connection.files.put(f, EVERY_BYTE)

    assert await async_ws_connection.files.get(f) == EVERY_BYTE
    listed = await async_ws_connection.files.list(bucket, prefix=f.key)
    assert [entry.file for entry in listed] == [f]


async def test_the_async_http_transport_agrees(
    async_http_connection: AsyncHttpSurrealConnection, bucket: str
) -> None:
    f = File(bucket, _key("ahttp-"))

    await async_http_connection.files.put(f, EVERY_BYTE)

    assert await async_http_connection.files.get(f) == EVERY_BYTE
    assert await async_http_connection.files.exists(f) is True


# --------------------------------------------------------------- sessions and txns


def test_a_session_carries_its_own_context(
    blocking_ws_connection: BlockingWsSurrealConnection,
    bucket: str,
    connection_params: dict[str, Any],
) -> None:
    """``session.files`` must run *as* that session, not on the bare connection.

    It does because the helper holds a query runner, and the session's ``query``
    already binds its own id - so there is no ``session_id`` to forget to pass.
    """
    session = blocking_ws_connection.new_session()
    try:
        session.use(connection_params["namespace"], connection_params["database_name"])
        f = File(bucket, _key("session-"))

        session.files.put(f, b"from a session")

        assert session.files.get(f) == b"from a session"
    finally:
        session.close_session()


def test_writes_inside_a_transaction_are_visible_after_commit(
    blocking_ws_connection: BlockingWsSurrealConnection,
    bucket: str,
    connection_params: dict[str, Any],
) -> None:
    session = blocking_ws_connection.new_session()
    try:
        session.use(connection_params["namespace"], connection_params["database_name"])
        f = File(bucket, _key("txn-"))

        transaction = session.begin_transaction()
        transaction.files.put(f, b"in a transaction")
        assert transaction.files.get(f) == b"in a transaction"
        transaction.commit()

        assert blocking_ws_connection.files.get(f) == b"in a transaction"
    finally:
        session.close_session()
