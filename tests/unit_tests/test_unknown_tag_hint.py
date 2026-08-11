"""A rejected CBOR tag explains itself.

SurrealDB 3.x added the CBOR set tag. SurrealDB 2.x has no set representation
at all - it returns SurrealQL sets as plain arrays - so it answers anything
carrying the tag with a bare ``Encountered an unknown CBOR tag``, which does
not say what was wrong or what to do instead. Sets are the only value this SDK
encodes that a supported 2.x server cannot read, so the message is worth
explaining.

The hint is attached from the message alone: no version probe, and nothing that
could fire on an unrelated failure.
"""

import pytest

from surrealdb.errors import parse_query_error, parse_rpc_error

UNKNOWN_TAG = "Error: Encountered an unknown CBOR tag"


def test_rpc_error_explains_an_unknown_tag() -> None:
    error = parse_rpc_error({"code": -32000, "message": UNKNOWN_TAG})

    assert "unknown CBOR tag" in str(error)
    assert "set" in str(error)
    assert "send a list instead" in str(error)


def test_query_error_explains_an_unknown_tag() -> None:
    error = parse_query_error({"result": UNKNOWN_TAG, "status": "ERR"})

    assert "send a list instead" in str(error)


def test_the_original_message_is_kept() -> None:
    """The hint is added to what the server said, never a replacement for it."""
    error = parse_rpc_error({"code": -32000, "message": UNKNOWN_TAG})

    assert str(error).startswith(UNKNOWN_TAG)


@pytest.mark.parametrize(
    "message",
    [
        pytest.param(
            "There was a problem with the database: Parse error", id="parse-error"
        ),
        pytest.param("An error occurred: custom failure", id="thrown"),
        pytest.param("Expected a CBOR text data type", id="other-cbor-complaint"),
        pytest.param("", id="empty"),
    ],
)
def test_unrelated_errors_are_left_alone(message: str) -> None:
    """Only the one message gets the hint - a wrong hint is worse than none."""
    error = parse_rpc_error({"code": -32000, "message": message})

    assert str(error) == message


def test_the_hint_does_not_change_the_error_type() -> None:
    """Explaining the message must not disturb how the error is classified."""
    plain = parse_rpc_error({"code": -32000, "message": "something else"})
    hinted = parse_rpc_error({"code": -32000, "message": UNKNOWN_TAG})

    assert type(hinted) is type(plain)
    assert hinted.kind == plain.kind
    assert hinted.code == plain.code
