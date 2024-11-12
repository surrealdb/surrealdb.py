from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class Patch:
    """
    Represents a patch to a SurrealDB record based on the JSON Patch Spec https://jsonpatch.com/.

    Attributes:
        op: The Patch operation. One of add, remove, replace, move, copy or test.
        path: The path for the JSON pointer.
        value: The value for the operation.
    """
    op: str
    path: str
    value: Any


@dataclass(frozen=True)
class QueryResponse:
    """
    Represents a http response from a SurrealDB server.

    Attributes:
        time: The time the request was processed.
        status: The status of the request.
        result: The result of the request.
    """

    time: str
    status: str
    result: List[Dict[str, Any]]
