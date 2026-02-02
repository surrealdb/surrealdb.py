from uuid import UUID

import pytest

from surrealdb.data.cbor import decode
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
    message = RequestMessage(
        RequestMethod.SIGN_IN,
        params={"username": "user", "password": "pass"},
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_signin_pass_root_with_none() -> None:
    message = RequestMessage(
        RequestMethod.SIGN_IN,
        params={"username": "username", "password": "pass"},
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_signin_pass_account() -> None:
    message = RequestMessage(
        RequestMethod.SIGN_IN,
        params={
            "username": "username",
            "password": "pass",
            "access": "account",
            "database": "database",
            "namespace": "namespace",
        },
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_signin_params_required() -> None:
    message = RequestMessage(RequestMethod.SIGN_IN)
    with pytest.raises(ValueError, match="params dict"):
        _ = message.WS_CBOR_DESCRIPTOR


def test_signin_params_bearer() -> None:
    message = RequestMessage(
        RequestMethod.SIGN_IN,
        params={
            "namespace": "ns",
            "database": "db",
            "access": "bearer_api",
            "key": "surreal-bearer-abc123",
        },
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)


def test_signin_params_refresh() -> None:
    message = RequestMessage(
        RequestMethod.SIGN_IN,
        params={
            "namespace": "ns",
            "database": "db",
            "access": "user_access",
            "refresh": "surreal-refresh-xyz",
        },
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


def test_use_with_session_txn() -> None:
    session_id = UUID("0189d6e3-8eac-703a-9a48-d9faa78b44b9")
    txn_id = UUID("0189d6e3-8eac-703a-9a48-d9faa78b44ba")
    message = RequestMessage(
        RequestMethod.USE,
        namespace="ns",
        database="db",
        session=session_id,
        txn=txn_id,
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)
    payload = decode(outcome)
    assert payload.get("session") == str(session_id)
    assert payload.get("txn") == str(txn_id)


def test_query_with_session() -> None:
    session_id = UUID("0189d6e3-8eac-703a-9a48-d9faa78b44b9")
    message = RequestMessage(
        RequestMethod.QUERY,
        query="SELECT 1",
        params={},
        session=session_id,
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)
    payload = decode(outcome)
    assert payload.get("session") == str(session_id)


def test_attach_pass() -> None:
    session_id = UUID("0189d6e3-8eac-703a-9a48-d9faa78b44b9")
    message = RequestMessage(RequestMethod.ATTACH, session=session_id)
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)
    payload = decode(outcome)
    assert payload.get("method") == "attach"
    assert payload.get("session") == str(session_id)


def test_attach_requires_session() -> None:
    message = RequestMessage(RequestMethod.ATTACH)
    with pytest.raises(ValueError, match="attach requires session"):
        _ = message.WS_CBOR_DESCRIPTOR


def test_detach_pass() -> None:
    session_id = UUID("0189d6e3-8eac-703a-9a48-d9faa78b44b9")
    message = RequestMessage(RequestMethod.DETACH, session=session_id)
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)
    payload = decode(outcome)
    assert payload.get("method") == "detach"
    assert payload.get("session") == str(session_id)


def test_detach_requires_session() -> None:
    message = RequestMessage(RequestMethod.DETACH)
    with pytest.raises(ValueError, match="detach requires session"):
        _ = message.WS_CBOR_DESCRIPTOR


def test_begin_pass() -> None:
    message = RequestMessage(RequestMethod.BEGIN)
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)
    payload = decode(outcome)
    assert payload.get("method") == "begin"


def test_begin_with_session() -> None:
    session_id = UUID("0189d6e3-8eac-703a-9a48-d9faa78b44b9")
    message = RequestMessage(RequestMethod.BEGIN, session=session_id)
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)
    payload = decode(outcome)
    assert payload.get("method") == "begin"
    assert payload.get("session") == str(session_id)


def test_commit_pass() -> None:
    txn_id = UUID("0189d6e3-8eac-703a-9a48-d9faa78b44b9")
    message = RequestMessage(RequestMethod.COMMIT, txn=txn_id)
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)
    payload = decode(outcome)
    assert payload.get("method") == "commit"
    assert payload.get("params") == [str(txn_id)]


def test_commit_with_session() -> None:
    txn_id = UUID("0189d6e3-8eac-703a-9a48-d9faa78b44b9")
    session_id = UUID("0189d6e3-8eac-703a-9a48-d9faa78b44ba")
    message = RequestMessage(
        RequestMethod.COMMIT, txn=txn_id, session=session_id
    )
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)
    payload = decode(outcome)
    assert payload.get("method") == "commit"
    assert payload.get("params") == [str(txn_id)]
    assert payload.get("session") == str(session_id)


def test_commit_requires_txn() -> None:
    message = RequestMessage(RequestMethod.COMMIT)
    with pytest.raises(ValueError, match="commit requires txn"):
        _ = message.WS_CBOR_DESCRIPTOR


def test_cancel_pass() -> None:
    txn_id = UUID("0189d6e3-8eac-703a-9a48-d9faa78b44b9")
    message = RequestMessage(RequestMethod.CANCEL, txn=txn_id)
    outcome = message.WS_CBOR_DESCRIPTOR
    assert isinstance(outcome, bytes)
    payload = decode(outcome)
    assert payload.get("method") == "cancel"
    assert payload.get("params") == [str(txn_id)]


def test_cancel_requires_txn() -> None:
    message = RequestMessage(RequestMethod.CANCEL)
    with pytest.raises(ValueError, match="cancel requires txn"):
        _ = message.WS_CBOR_DESCRIPTOR
