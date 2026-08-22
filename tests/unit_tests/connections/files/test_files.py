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


# --------------------------------------------------------------- the contents side


def test_a_string_is_refused_rather_than_silently_encoded(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    """The asymmetry this prevents: ``put(f, s)`` then ``get(f) != s``.

    The server stores bytes and ``get`` returns bytes, so a ``str`` accepted here
    would make the write look fine and the read hand back a different type -
    silently, with nothing to indicate the round trip was lossy. Refusing it also
    means the caller names the encoding rather than the SDK assuming UTF-8.
    """
    f = File(bucket, _key())

    with pytest.raises(TypeError) as caught:
        blocking_ws_connection.files.put(f, "text")  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]

    message = str(caught.value)
    assert "not str" in message
    assert "encode" in message, "the message must say how to fix it"
    assert blocking_ws_connection.files.exists(f) is False, "nothing was written"


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"buffer", id="bytes"),
        pytest.param(bytearray(b"buffer"), id="bytearray"),
        pytest.param(memoryview(b"buffer"), id="memoryview"),
    ],
)
def test_every_accepted_buffer_type_round_trips_as_bytes(
    blocking_ws_connection: BlockingWsSurrealConnection,
    bucket: str,
    content: Any,
) -> None:
    """``memoryview`` reaches the CBOR encoder as an unsupported type otherwise."""
    f = File(bucket, _key())

    blocking_ws_connection.files.put(f, content)

    assert blocking_ws_connection.files.get(f) == b"buffer"


def test_a_file_handle_is_refused_and_told_to_read_itself(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    """``put`` takes bytes, so the obvious wrong guess gets a useful answer."""
    import io

    with pytest.raises(TypeError) as caught:
        blocking_ws_connection.files.put(File(bucket, _key()), io.BytesIO(b"x"))  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]

    assert "handle.read()" in str(caught.value)


def test_the_read_hint_is_not_offered_for_values_that_cannot_be_read(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    """Noise in an error message is what makes people stop reading them."""
    with pytest.raises(TypeError) as caught:
        blocking_ws_connection.files.put(File(bucket, _key()), 123)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]

    assert "read it first" not in str(caught.value)


def test_put_if_not_exists_validates_content_too(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    """Both writers, not just ``put`` - the check is easy to add to one and forget."""
    with pytest.raises(TypeError, match="not str"):
        blocking_ws_connection.files.put_if_not_exists(File(bucket, _key()), "text")  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


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


# --------------------------------------------------- the whole async surface


async def test_every_async_method_is_exercised(
    async_ws_connection: AsyncWsSurrealConnection, bucket: str
) -> None:
    """All eleven, not just the four the transport tests happen to touch.

    Before this, seven of ``AsyncFiles``' methods - put_if_not_exists, delete,
    head, copy, copy_if_not_exists, rename, rename_if_not_exists - could all be
    gutted to ``return None`` and the suite still passed. The blocking surface was
    covered method by method and the async one rode on three smoke tests, so a
    divergence between the two would not have shown up.
    """
    files = async_ws_connection.files
    source = File(bucket, _key("async-src-"))
    target = File(bucket, _key("async-dst-"))

    await files.put(source, b"one")
    assert await files.get(source) == b"one"
    assert await files.exists(source) is True

    # put_if_not_exists must not overwrite
    await files.put_if_not_exists(source, b"two")
    assert await files.get(source) == b"one"

    meta = await files.head(source)
    assert meta is not None
    assert meta.size == 3
    assert meta.file == source

    await files.copy(source, target)
    assert await files.get(target) == b"one"

    # copy_if_not_exists must not overwrite the now-occupied target
    await files.put(target, b"occupied")
    await files.copy_if_not_exists(source, target)
    assert await files.get(target) == b"occupied"

    renamed_key = _key("async-moved-")
    await files.rename(target, renamed_key)
    assert await files.exists(target) is False
    assert await files.get(File(bucket, renamed_key)) == b"occupied"

    # rename_if_not_exists must not clobber an occupied key
    await files.rename_if_not_exists(source, renamed_key)
    assert await files.get(File(bucket, renamed_key)) == b"occupied"
    assert await files.get(source) == b"one"

    listed = await files.list(bucket, prefix="/async-")
    assert {entry.file.key for entry in listed} >= {source.key, renamed_key}

    await files.delete(source)
    assert await files.exists(source) is False
    assert await files.get(source) is None
    assert await files.head(source) is None


async def test_the_async_surface_matches_the_blocking_one(
    async_ws_connection: AsyncWsSurrealConnection,
) -> None:
    """A method on one and not the other is a divergence users would hit."""
    from surrealdb.connections.files import AsyncFiles, BlockingFiles

    def public(cls: type) -> set[str]:
        return {n for n in dir(cls) if not n.startswith("_")}

    assert public(AsyncFiles) == public(BlockingFiles)


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


def test_writes_routed_through_a_transaction_reach_the_bucket(
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


def test_file_writes_are_not_transactional_and_survive_cancel(
    blocking_ws_connection: BlockingWsSurrealConnection,
    bucket: str,
    connection_params: dict[str, Any],
) -> None:
    """Routed through a transaction is not the same as being *in* one.

    ``file::*`` writes to the bucket backend rather than to the transaction, so a
    file written inside one survives ``cancel()`` while a record written beside it
    rolls back. This is the server's behaviour, not the SDK's - a raw
    ``BEGIN; file::put(...); CANCEL;`` string with no SDK transaction object
    anywhere behaves identically.

    Pinned because the obvious test - "visible after commit", directly above -
    passes whether or not the write is transactional, so it cannot tell the two
    apart. The docs previously implied isolation on the strength of exactly that.
    """
    namespace = connection_params["namespace"]
    database = connection_params["database_name"]
    table = f"txnctl_{uuid.uuid4().hex[:8]}"
    blocking_ws_connection.query(f"CREATE {table}:seed SET a = 0").execute()

    session = blocking_ws_connection.new_session()
    try:
        session.use(namespace, database)
        f = File(bucket, _key("cancelled-"))

        transaction = session.begin_transaction()
        transaction.files.put(f, b"survives")
        transaction.query(f"CREATE {table}:rolled SET a = 1").execute()
        transaction.cancel()
    finally:
        session.close_session()

    rows = blocking_ws_connection.query(f"SELECT * FROM {table}").first()
    assert [row["id"].id for row in rows] == ["seed"], "the record write must roll back"
    assert blocking_ws_connection.files.get(f) == b"survives", (
        "the file write is not transactional and must survive the cancel"
    )


# --------------------------------------------------------- the guarded variants


def test_copy_if_not_exists_refuses_to_overwrite(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    """Swapping this for plain ``copy`` was invisible to the suite before."""
    source, target = File(bucket, _key("src-")), File(bucket, _key("dst-"))
    blocking_ws_connection.files.put(source, b"new")
    blocking_ws_connection.files.put(target, b"existing")

    blocking_ws_connection.files.copy_if_not_exists(source, target)

    assert blocking_ws_connection.files.get(target) == b"existing"


def test_copy_if_not_exists_writes_when_the_target_is_free(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    source, target = File(bucket, _key("src-")), File(bucket, _key("dst-"))
    blocking_ws_connection.files.put(source, b"content")

    blocking_ws_connection.files.copy_if_not_exists(source, target)

    assert blocking_ws_connection.files.get(target) == b"content"


def test_rename_if_not_exists_refuses_to_overwrite(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    source = File(bucket, _key("from-"))
    taken_key = _key("taken-")
    blocking_ws_connection.files.put(source, b"moving")
    blocking_ws_connection.files.put(File(bucket, taken_key), b"already here")

    blocking_ws_connection.files.rename_if_not_exists(source, taken_key)

    assert blocking_ws_connection.files.get(File(bucket, taken_key)) == b"already here"
    assert blocking_ws_connection.files.get(source) == b"moving", "source is untouched"


def test_rename_if_not_exists_moves_when_the_key_is_free(
    blocking_ws_connection: BlockingWsSurrealConnection, bucket: str
) -> None:
    source = File(bucket, _key("from-"))
    free_key = _key("to-")
    blocking_ws_connection.files.put(source, b"moving")

    blocking_ws_connection.files.rename_if_not_exists(source, free_key)

    assert blocking_ws_connection.files.get(File(bucket, free_key)) == b"moving"
    assert blocking_ws_connection.files.exists(source) is False
