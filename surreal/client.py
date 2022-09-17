"""
Copyright © SurrealDB Ltd

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
from typing import Any

from surreal.http import HTTPClient


class Surreal:
    def __init__(
        self, url: str, username: str, password: str, ns: str, db: str
    ) -> None:
        self.http = HTTPClient(
            url=url, username=username, password=password, ns=ns, db=db
        )

    async def execute(self, query: str) -> dict[str, Any] | list[dict[str, Any]]:
        """
        Executes this query and returns the data given by the server.

        If the query is a transactional query, the list should be ordered based on the transaction's order.
        """

        execution = await self.http.execute(query=query)

        return execution[0] if len(execution) == 1 else execution

    async def close(self) -> None:
        await self.http.close()
