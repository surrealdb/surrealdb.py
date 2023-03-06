"""
Copyright © SurrealDB Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from dataclasses import dataclass
from typing import Any, Dict, List

__all__ = (
    "SurrealResponse",
    "RPCResponse",
)


@dataclass(frozen=True)
class SurrealResponse:
    """Represents a http response from a SurrealDB server.

    Attributes:
        time: The time the request was processed.
        status: The status of the request.
        result: The result of the request.
    """

    time: str
    status: str
    result: List[Dict[str, Any]]


@dataclass(frozen=True)
class RPCResponse:
    """Represents an RPC response from a SurrealDB server.

    Attributes:
        id: The ID of the request.
        result: The result of the request.
    """

    id: str
    result: Any = None
