"""Nothing a server can send should surface as a bare ``AttributeError``.

Three separate places read a value's shape without checking it, and all three
failed the same way - an ``AttributeError`` raised from inside the SDK, outside
the ``SurrealError`` tree, with a message naming neither the operation nor the
value:

* an RPC envelope that decodes to something other than a map;
* an ``error`` field that is a bare string rather than an object. SurrealDB
  2.x answers ``create("person", {"a": "x\\x00y"})`` this way - the NUL byte
  fails serialisation before the error object is built - and reading ``kind``
  off it raised ``AttributeError: 'str' object has no attribute 'get'``;
* a non-class passed as ``into=``, which blew up in the SDK's own error
  formatter while trying to render ``cls.__name__`` for a different complaint.

Server-free: every one of these is about how a value is read, so they run on
every CI leg rather than only where a server of the right version is up.
"""

from typing import Any

import pytest

from surrealdb.connections.utils_mixin import UtilsMixin
from surrealdb.data.cbor import encode
from surrealdb.errors import (
    ServerError,
    SurrealError,
    UnexpectedResponseError,
    parse_rpc_error,
)

# ------------------------------------------------------- non-map RPC envelope


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param([1, 2, 3], id="list"),
        pytest.param("just a string", id="string"),
        pytest.param(42, id="integer"),
        pytest.param(None, id="null"),
        pytest.param(True, id="boolean"),
    ],
)
def test_a_response_that_is_not_a_map_raises_a_surreal_error(payload: Any) -> None:
    with pytest.raises(UnexpectedResponseError) as caught:
        UtilsMixin.decode_response(encode(payload), "querying")

    # Both halves of a usable message: what we were doing, and what arrived.
    assert "querying" in str(caught.value)
    assert type(payload).__name__ in str(caught.value)
    assert isinstance(caught.value, SurrealError)


def test_a_map_response_is_returned_untouched() -> None:
    """The guard must not change the ordinary path."""
    assert UtilsMixin.decode_response(
        encode({"id": "1", "result": []}), "querying"
    ) == {
        "id": "1",
        "result": [],
    }


def test_an_undecodable_body_still_reports_the_operation() -> None:
    with pytest.raises(UnexpectedResponseError) as caught:
        UtilsMixin.decode_response(b"\xff\xff not cbor", "signing in")

    assert "signing in" in str(caught.value)


def test_a_huge_non_map_response_is_not_dumped_whole() -> None:
    """A megabyte of unexpected payload does not belong in a traceback."""
    with pytest.raises(UnexpectedResponseError) as caught:
        UtilsMixin.decode_response(encode(["x" * 100] * 500), "querying")

    assert len(str(caught.value)) < 500


# ----------------------------------------------------- non-object error field


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("Parse error: unexpected character", id="bare-string"),
        pytest.param(["a", "b"], id="list"),
        pytest.param(-32000, id="integer"),
    ],
)
def test_an_error_that_is_not_an_object_still_parses(raw: Any) -> None:
    error = parse_rpc_error(raw)

    assert isinstance(error, ServerError)
    # The text the server sent has to survive - it is the only thing the
    # caller has to go on.
    assert str(raw) in str(error)


def test_a_non_object_error_reaches_the_caller_through_check_response() -> None:
    """The shape 2.x actually sends, through the method that actually reads it."""
    response = {"id": "1", "error": "Serialization error: contained NUL byte"}

    with pytest.raises(SurrealError) as caught:
        UtilsMixin.check_response_for_error(response, "creating")

    assert "contained NUL byte" in str(caught.value)


def test_a_non_object_cause_does_not_break_the_chain() -> None:
    error = parse_rpc_error({"kind": "Query", "message": "outer", "cause": "inner"})

    assert isinstance(error.server_cause, ServerError)
    assert "inner" in str(error.server_cause)


def test_an_object_error_is_still_parsed_structurally() -> None:
    """The guard must not swallow the structured path it sits in front of."""
    error = parse_rpc_error({"kind": "NotFound", "message": "gone", "code": -32000})

    assert error.kind == "NotFound"
    assert error.code == -32000
    assert str(error) == "gone"
