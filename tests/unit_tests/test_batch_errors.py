"""Batch failures retain their original cause even when its text mentions rollback."""

from collections.abc import Mapping
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from surrealdb.connections.batch import AsyncBatch, Batch
from surrealdb.errors import (
    InternalError,
    QueryError,
    ServerError,
    ThrownError,
    ValidationError,
)
from surrealdb.types import Value

NOT_EXECUTED = "The query was not executed due to a failed transaction"
COMMIT_ABORTED = "Cannot COMMIT: the transaction was aborted due to a prior error"
APPLICATION_ERROR = "An error occurred: lease lost: a statement was not executed due to a failed transaction"


# --- Test helpers -----------------------------------------------------------


@pytest.fixture(params=[False, True], ids=["blocking", "async"])
def runner(request: pytest.FixtureRequest) -> Mock:
    connection = Mock(server_version="3.3.5")
    connection.query_raw = AsyncMock() if request.param else Mock()
    return connection


async def _execute(runner: Mock) -> list[Value]:
    """Exercise both public entry points while guarding the single-request contract."""
    bindings: Mapping[str, Value] = {"n": 7}
    batch = (
        AsyncBatch(runner) if isinstance(runner.query_raw, AsyncMock) else Batch(runner)
    )
    batch.query("LET $x = $n", bindings).query("RETURN $x")
    try:
        if isinstance(batch, AsyncBatch):
            return await batch.execute()
        return batch.execute()
    finally:
        runner.query_raw.assert_called_once_with(
            "BEGIN TRANSACTION;\nLET $x = $n\n;\nRETURN $x\n;\nCOMMIT TRANSACTION;",
            {"n": 7},
        )
        assert bindings == {"n": 7}


# --- End test helpers -------------------------------------------------------


@pytest.mark.parametrize(
    ("root", "error_type"),
    [
        pytest.param(
            {"kind": "Thrown", "result": APPLICATION_ERROR},
            ThrownError,
            id="structured-application-phrase",
        ),
        pytest.param(
            {"result": APPLICATION_ERROR}, InternalError, id="legacy-application-phrase"
        ),
        pytest.param(
            {"kind": "Thrown", "result": NOT_EXECUTED},
            ThrownError,
            id="thrown-exact-cancellation-text",
        ),
        pytest.param(
            {"kind": "Thrown", "result": COMMIT_ABORTED},
            ThrownError,
            id="thrown-exact-commit-text",
        ),
        pytest.param(
            {"kind": "Query", "details": {"kind": "TimedOut"}, "result": NOT_EXECUTED},
            QueryError,
            id="other-query-detail",
        ),
        pytest.param(
            {"kind": "Internal", "result": NOT_EXECUTED},
            InternalError,
            id="explicit-internal-kind",
        ),
        pytest.param(
            {"kind": "Query", "result": NOT_EXECUTED},
            QueryError,
            id="query-kind-without-detail",
        ),
    ],
)
async def test_batch_preserves_the_first_root_error(
    runner: Mock, root: dict[str, Any], error_type: type[ServerError]
) -> None:
    runner.query_raw.return_value = {
        "result": [
            {"status": "OK", "result": None},
            {
                "status": "ERR",
                "kind": "Query",
                "details": {"kind": "NotExecuted"},
                "result": NOT_EXECUTED,
            },
            {"status": "ERR", **root},
            {
                "status": "ERR",
                "kind": "Query",
                "details": {"kind": "NotExecuted"},
                "result": COMMIT_ABORTED,
            },
        ]
    }
    with pytest.raises(error_type) as caught:
        await _execute(runner)
    assert type(caught.value) is error_type
    assert str(caught.value) == root["result"]
    assert caught.value.details == root.get("details")


async def test_multiple_root_errors_keep_server_order(runner: Mock) -> None:
    runner.query_raw.return_value = {
        "result": [
            {"status": "ERR", "kind": "Thrown", "result": "first failure"},
            {"status": "ERR", "kind": "Thrown", "result": "second failure"},
        ]
    }
    with pytest.raises(ThrownError) as caught:
        await _execute(runner)
    assert str(caught.value) == "first failure"


@pytest.mark.parametrize(
    "cancellation",
    [
        pytest.param(
            {
                "kind": "Query",
                "details": {"kind": "NotExecuted"},
                "result": COMMIT_ABORTED,
            },
            id="structured-commit",
        ),
        pytest.param(
            {
                "kind": "Query",
                "details": {"kind": "Query", "details": {"kind": "NotExecuted"}},
                "result": COMMIT_ABORTED,
            },
            id="double-wrapped-query-detail",
        ),
        pytest.param({"result": NOT_EXECUTED}, id="legacy-cancellation"),
        pytest.param({"result": COMMIT_ABORTED}, id="unstructured-commit-fallback"),
    ],
)
async def test_not_executed_errors_do_not_mask_the_cause(
    runner: Mock, cancellation: dict[str, Any]
) -> None:
    runner.query_raw.return_value = {
        "result": [
            {"status": "ERR", **cancellation},
            {"status": "ERR", "result": "An error occurred: boom"},
        ]
    }
    with pytest.raises(InternalError) as caught:
        await _execute(runner)
    assert str(caught.value) == "An error occurred: boom"


@pytest.mark.parametrize("structured", [False, True], ids=["legacy", "structured"])
async def test_all_not_executed_errors_fall_back_to_the_first(
    runner: Mock, structured: bool
) -> None:
    metadata = (
        {"kind": "Query", "details": {"kind": "NotExecuted"}} if structured else {}
    )
    runner.query_raw.return_value = {
        "result": [
            {"status": "ERR", "result": NOT_EXECUTED, **metadata},
            {"status": "ERR", "result": COMMIT_ABORTED, **metadata},
        ]
    }
    with pytest.raises(QueryError if structured else InternalError) as caught:
        await _execute(runner)
    assert str(caught.value) == NOT_EXECUTED


@pytest.mark.parametrize("version", ["2.3.6", "3.3.5", None])
async def test_success_keeps_statement_results_in_order(
    runner: Mock, version: str | None
) -> None:
    runner.server_version = version
    statements = [{"status": "OK", "result": None}, {"status": "OK", "result": 7}]
    envelope = {"status": "OK", "result": None}
    runner.query_raw.return_value = {
        "result": statements
        if version == "2.3.6"
        else [envelope, *statements, envelope]
    }
    assert await _execute(runner) == [None, 7]


async def test_rpc_error_takes_precedence_over_statement_errors(runner: Mock) -> None:
    runner.query_raw.return_value = {
        "error": {"kind": "Validation", "message": "Invalid params", "code": -32602},
        "result": [{"status": "ERR", "kind": "Thrown", "result": "statement failure"}],
    }
    with pytest.raises(ValidationError) as caught:
        await _execute(runner)
    assert str(caught.value) == "Invalid params"
    assert caught.value.code == -32602
