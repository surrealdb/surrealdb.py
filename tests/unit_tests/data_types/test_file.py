"""``File`` - a reference to a file in a storage bucket.

The wire format is CBOR tag 55 carrying ``[bucket, key]``. That was established
from both ends rather than from documentation: the server's own decoder error
names the tag (``no decoder for CBOR tag 55``), and the JavaScript SDK's codec
encodes ``TAG_FILE_POINTER = 55`` with the same payload order.

The tests about ``__str__`` are the interesting ones. SurrealQL's file literal
accepts only ``[A-Za-z0-9_-./]`` and has **no escape mechanism** - the parser
says so itself:

    Parse error: Unexpected character ` `, file strings key's only allow alpha
    numeric characters and `_`, `-`, `.`, and `/`

So a key containing a space, an accent or an emoji cannot be written as a
literal at all, and any rendering of one is display-only. The JavaScript SDK's
``toString()`` backslash-escapes such characters, which produces literals this
server rejects; that is why this type does not copy it.
"""

import re
from typing import Any

import pytest

import surrealdb
from surrealdb.cbor import CBORTag
from surrealdb.data import cbor
from surrealdb.data.types import constants
from surrealdb.data.types.file import File
from surrealdb.errors import UnexpectedResponseError

# --------------------------------------------------------------- construction


def test_bucket_and_key_are_kept() -> None:
    f = File("images", "/photos/avatar.png")

    assert f.bucket == "images"
    assert f.key == "/photos/avatar.png"


def test_a_key_without_a_leading_slash_is_normalised() -> None:
    """Otherwise the same file would encode two ways and address two objects.

    The JavaScript SDK normalises in its constructor too, so the two agree.
    """
    assert File("b", "a.txt").key == "/a.txt"
    assert File("b", "/a.txt").key == "/a.txt"
    assert File("b", "a.txt") == File("b", "/a.txt")


def test_normalisation_does_not_double_up() -> None:
    assert File("b", "//a.txt").key == "//a.txt"


@pytest.mark.parametrize(
    ("bucket", "key", "argument"),
    [
        pytest.param(None, "/a", "bucket", id="bucket-none"),
        pytest.param(1, "/a", "bucket", id="bucket-int"),
        pytest.param(b"b", "/a", "bucket", id="bucket-bytes"),
        pytest.param("b", None, "key", id="key-none"),
        pytest.param("b", 1, "key", id="key-int"),
        pytest.param("b", b"/a", "key", id="key-bytes"),
    ],
)
def test_both_arguments_must_be_strings(bucket: Any, key: Any, argument: str) -> None:
    """Caught at the line that made the mistake, as ``Table`` and ``RecordID`` do."""
    with pytest.raises(TypeError) as caught:
        File(bucket, key)

    assert argument in str(caught.value)


def test_an_empty_bucket_or_key_is_allowed() -> None:
    """The server decides what it accepts; the SDK only checks the type.

    Same reasoning as ``Table``, which accepts any string because SurrealDB does.
    """
    assert File("", "").key == "/"


# --------------------------------------------------------------- value semantics


def test_equality_is_structural() -> None:
    assert File("b", "/a") == File("b", "/a")
    assert File("b", "/a") != File("b", "/z")
    assert File("b", "/a") != File("other", "/a")


def test_it_is_not_equal_to_a_lookalike() -> None:
    assert File("b", "/a") != ("b", "/a")
    assert File("b", "/a") != "b:/a"


def test_it_is_hashable_and_usable_as_a_key() -> None:
    seen = {File("b", "/a"): 1}
    seen[File("b", "/a")] = 2

    assert len(seen) == 1
    assert seen[File("b", "a")] == 2


def test_repr_names_both_halves() -> None:
    assert repr(File("b", "/a.txt")) == "File(bucket='b', key='/a.txt')"


# --------------------------------------------------------------- the literal form


def test_str_is_the_surrealql_literal_form() -> None:
    assert str(File("images", "/photos/avatar.png")) == 'f"images:/photos/avatar.png"'


@pytest.mark.parametrize(
    ("bucket", "key", "safe"),
    [
        pytest.param("b", "/hello.txt", True, id="plain"),
        pytest.param("b", "/nested/path/x.png", True, id="slashes"),
        pytest.param("my-bucket_1", "/a-b_c.d", True, id="dashes-dots"),
        pytest.param("b", "/UPPER.TXT", True, id="uppercase"),
        pytest.param("b", "/1234", True, id="digits"),
        pytest.param("b", "/a b.txt", False, id="space"),
        pytest.param("b", "/héllo.txt", False, id="accent"),
        pytest.param("b", "/emoji-\U0001f389.png", False, id="emoji"),
        pytest.param("b", '/quote".txt', False, id="quote"),
        pytest.param("b", "/back\\slash.txt", False, id="backslash"),
        pytest.param("b", "/@at#hash.txt", False, id="symbols"),
        pytest.param("bad bucket", "/a.txt", False, id="space-in-bucket"),
    ],
)
def test_is_literal_safe_matches_the_parsers_own_rule(
    bucket: str, key: str, safe: bool
) -> None:
    """The safe set is exactly what the server's parse error names.

    Each of these was round-tripped through a live server while this was written:
    the ``True`` rows parse, and every ``False`` row is rejected - unescaped *and*
    backslash-escaped, because the syntax has no escape.
    """
    assert File(bucket, key).is_literal_safe() is safe


# --------------------------------------------------------------- the wire format


def test_it_encodes_as_tag_55_with_bucket_then_key() -> None:
    """Payload order matters and is not symmetric - swapping it is silent."""
    tagged = _encode_to_tag(File("images", "/a.png"))

    assert tagged.tag == constants.TAG_FILE == 55
    assert list(tagged.value) == ["images", "/a.png"]


def _encode_to_tag(value: object) -> CBORTag:
    """Decode with the vendored cbor2 alone, so tags arrive unresolved."""
    from surrealdb.cbor import loads

    return loads(cbor.encode(value))


@pytest.mark.parametrize(
    ("bucket", "key"),
    [
        pytest.param("images", "/photos/avatar.png", id="plain"),
        pytest.param("b", "/a b.txt", id="space"),
        pytest.param("b", "/h\u00e9llo.txt", id="accent"),
        pytest.param("b", "/emoji-\U0001f389.png", id="emoji"),
        pytest.param("b", "/", id="root"),
    ],
)
def test_it_round_trips_through_cbor(bucket: str, key: str) -> None:
    """Including keys the literal syntax cannot express - CBOR carries them raw."""
    original = File(bucket, key)

    decoded = cbor.decode(cbor.encode(original))

    assert isinstance(decoded, File)
    assert decoded == original
    assert decoded.bucket == bucket
    assert decoded.key == key


def test_a_malformed_payload_is_refused_with_context() -> None:
    """A bare ``IndexError`` from inside the decoder would lose the response."""
    for payload in (["only-one"], [], ["a", "b", "c"], "not-a-list"):
        with pytest.raises(UnexpectedResponseError) as caught:
            cbor.decode(cbor.encode(CBORTag(constants.TAG_FILE, payload)))

        assert "file" in str(caught.value).lower()


def test_the_decoder_normalises_too() -> None:
    """A server that ever sent a slashless key must not produce a mismatching File."""
    decoded = cbor.decode(cbor.encode(CBORTag(constants.TAG_FILE, ["b", "a.txt"])))

    assert decoded == File("b", "/a.txt")


# --------------------------------------------------------------- exports


def test_it_is_a_member_of_the_public_value_union() -> None:
    """``Value`` annotates every payload and every ``query().first()`` result.

    Leaving ``File`` out made ``db.create(t, {"a": File(...)})`` fail a type check
    on code that works at runtime, and made a returned one narrow to unreachable.
    The same omission already shipped once for ``set`` - the union carries a
    comment about it - so this checks the general rule instead of the one name:
    everything the encoder accepts has to be in the union.
    """
    import typing

    from surrealdb.types import Value

    members = set()
    for member in typing.get_args(Value):
        members.add(getattr(member, "__origin__", member))

    assert File in members, "File encodes and decodes, so Value must admit it"


def test_every_encodable_type_is_in_the_value_union() -> None:
    """The general form of the check above, so the next type cannot slip either."""
    import inspect
    import typing

    from surrealdb.data import cbor
    from surrealdb.types import Value

    source = inspect.getsource(cbor.default_encoder)
    encodable = set(re.findall(r"isinstance\(obj, ([A-Z]\w+)\)", source))
    members = {
        getattr(m, "__origin__", m).__name__
        for m in typing.get_args(Value)
        if hasattr(getattr(m, "__origin__", m), "__name__")
    }
    # `BoundIncluded`/`BoundExcluded` are encodable but are not values in their
    # own right - they only exist inside a `Range`, and the server rejects a bare
    # one with a parse error, so `Value` is right to leave them out. Checked
    # against a live server rather than assumed, because adding them to the union
    # would have advertised something you cannot actually store.
    components_only = {"BoundIncluded", "BoundExcluded"}
    missing = {name for name in encodable if name not in members} - components_only

    assert missing == set(), f"encodable but absent from Value: {sorted(missing)}"


def test_it_is_exported_from_the_package() -> None:
    assert "File" in surrealdb.__all__
    assert surrealdb.File is File
