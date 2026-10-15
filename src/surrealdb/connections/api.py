"""``api()``: call an endpoint defined with ``DEFINE API``.

Compiled to ``RETURN api::invoke($path, $request)``, as the JS SDK does, so it
works over every transport and inside sessions and transactions. Needs
SurrealDB 3.0 or later, with the experimental ``define_api`` capability.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from surrealdb.errors import UnexpectedResponseError, parse_query_error
from surrealdb.types import Value

API_METHODS = ("get", "post", "put", "patch", "delete", "trace")


@dataclass(frozen=True)
class ApiResponse:
    """What an API endpoint answered."""

    status: int
    body: Value = None
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Whether the status is in the 2xx range."""
        return 200 <= self.status < 300

    @classmethod
    def from_result(cls, result: Any) -> "ApiResponse":
        if not isinstance(result, dict) or not isinstance(result.get("status"), int):
            raise UnexpectedResponseError(
                f"api::invoke returned {type(result).__name__}, not a response "
                "with a status"
            )
        headers = result.get("headers")
        return cls(
            status=result["status"],
            body=result.get("body"),
            headers=dict(headers) if isinstance(headers, dict) else {},
        )


def build_api_query(
    path: str,
    method: str,
    body: Value,
    headers: Mapping[str, str] | None,
    query: Mapping[str, str] | None,
) -> tuple[str, dict[str, Value]]:
    """``RETURN api::invoke($_path, $_request)`` and its bound values."""
    if not isinstance(path, str) or not path.startswith("/"):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ValueError(f"api() takes a path starting with '/'; got {path!r}")
    verb = method.lower() if isinstance(method, str) else method  # pyright: ignore[reportUnnecessaryIsInstance]
    if verb not in API_METHODS:
        raise ValueError(
            f"api() takes a method of {', '.join(API_METHODS)}; got {method!r}"
        )
    request: dict[str, Value] = {"method": verb}
    if body is not None:
        request["body"] = body
    if headers:
        request["headers"] = dict(headers)
    if query:
        request["query"] = dict(query)
    return "RETURN api::invoke($_path, $_request);", {
        "_path": path,
        "_request": request,
    }


def statement_results(result: Any, process: str) -> list[Value]:
    """Each statement's result from a ``query``-shaped answer, raising the
    first statement that failed."""
    if not isinstance(result, list):
        raise UnexpectedResponseError(
            f"{process} returned {type(result).__name__}, not a list of "
            "statement results"
        )
    values: list[Value] = []
    for statement in result:
        if not isinstance(statement, dict):
            values.append(statement)
            continue
        if statement.get("status") == "ERR":
            raise parse_query_error(statement)
        values.append(statement.get("result"))
    return values


def graphql_params(
    query: str, variables: Mapping[str, Value] | None, operation_name: str | None
) -> list[Value]:
    params: list[Value] = [query]
    if variables is not None or operation_name is not None:
        params.append(dict(variables) if variables is not None else {})
    if operation_name is not None:
        params.append(operation_name)
    return params
