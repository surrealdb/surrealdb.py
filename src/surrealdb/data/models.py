from dataclasses import dataclass, field
from typing import Any, Union

from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table


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
    result: list[dict[str, Any]]


@dataclass
class GraphQLOptions:
    """
    Represents the options parameter for graphql method.

    Attributes:
        pretty: (optional, default false): A boolean indicating whether the output should be pretty-printed.
        format: (optional, default "json"): The response format. Currently, only "json" is supported.
    """

    pretty: bool = field(default=False)
    format: str = field(default="json")


def table_or_record_id(resource_str: str) -> Union[Table, RecordID]:
    if ":" in resource_str:
        table, record_id = resource_str.split(":")
        if len(table) == 0 or len(record_id) == 0:
            raise BlockingIOError("invalid table or record id string")
        return RecordID(table, record_id)

    return Table(resource_str)
