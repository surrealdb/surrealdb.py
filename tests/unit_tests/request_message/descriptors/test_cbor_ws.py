from typing import Any

import pytest

from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod


def test_use_pass() -> None:
    message = RequestMessage(RequestMethod.USE, namespace="ns", database="db")
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_use_fail() -> None:
    message = RequestMessage(RequestMethod.USE, namespace="ns", database=1)
    with pytest.raises(ValueError) as context:
        message.WS_CBOR_DESCRIPTOR
    assert (
        "Invalid schema for Cbor WS encoding for use: params.1: Input should be a valid string"
        == str(context.value)
    )
    message = RequestMessage(RequestMethod.USE, namespace="ns")
    with pytest.raises(ValueError) as context:
        message.WS_CBOR_DESCRIPTOR
    assert (
        "Invalid schema for Cbor WS encoding for use: params.1: Input should be a valid string"
        == str(context.value)
    )


def test_info_pass() -> None:
    message = RequestMessage(RequestMethod.INFO)
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_version_pass() -> None:
    message = RequestMessage(RequestMethod.VERSION)
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_signin_pass_root() -> None:
    message = RequestMessage(RequestMethod.SIGN_IN, username="user", password="pass")
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_signin_pass_root_with_none() -> None:
    message = RequestMessage(
        RequestMethod.SIGN_IN,
        username="username",
        password="pass",
        account=None,
        database=None,
        namespace=None,
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_signin_pass_account() -> None:
    message = RequestMessage(
        RequestMethod.SIGN_IN,
        username="username",
        password="pass",
        account="account",
        database="database",
        namespace="namespace",
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_authenticate_pass() -> None:
    message = RequestMessage(
        RequestMethod.AUTHENTICATE,
        token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJTdXJyZWFsREIiLCJpYXQiOjE1MTYyMzkwMjIsIm5iZiI6MTUxNjIzOTAyMiwiZXhwIjoxODM2NDM5MDIyLCJOUyI6InRlc3QiLCJEQiI6InRlc3QiLCJTQyI6InVzZXIiLCJJRCI6InVzZXI6dG9iaWUifQ.N22Gp9ze0rdR06McGj1G-h2vu6a6n9IVqUbMFJlOxxA",
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_invalidate_pass() -> None:
    message = RequestMessage(RequestMethod.INVALIDATE)
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_let_pass() -> None:
    message = RequestMessage(RequestMethod.LET, key="key", value="value")
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_unset_pass() -> None:
    message = RequestMessage(RequestMethod.UNSET, params=["one", "two", "three"])
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_live_pass() -> None:
    message = RequestMessage(RequestMethod.LIVE, table="person")
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_kill_pass() -> None:
    message = RequestMessage(
        RequestMethod.KILL, uuid="0189d6e3-8eac-703a-9a48-d9faa78b44b9"
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_query_pass() -> None:
    message = RequestMessage(RequestMethod.QUERY, query="query")
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_create_pass_params() -> None:
    message = RequestMessage(
        RequestMethod.CREATE, collection="person", data={"table": "table"}
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_insert_pass_dict() -> None:
    message = RequestMessage(
        RequestMethod.INSERT, collection="table", params={"key": "value"}
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_insert_pass_list() -> None:
    message = RequestMessage(
        RequestMethod.INSERT,
        collection="table",
        params=[{"key": "value"}, {"key": "value"}],
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_patch_pass() -> None:
    message = RequestMessage(
        RequestMethod.PATCH,
        collection="table",
        params=[{"key": "value"}, {"key": "value"}],
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_select_pass() -> None:
    message = RequestMessage(
        RequestMethod.SELECT,
        params=["table", "user"],
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_update_pass() -> None:
    message = RequestMessage(
        RequestMethod.UPDATE, record_id="test", data={"table": "table"}
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_upsert_pass() -> None:
    message = RequestMessage(
        RequestMethod.UPSERT, record_id="test", data={"table": "table"}
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_merge_pass() -> None:
    message = RequestMessage(
        RequestMethod.MERGE, record_id="test", data={"table": "table"}
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_delete_pass() -> None:
    message = RequestMessage(
        RequestMethod.DELETE,
        record_id="test",
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)
