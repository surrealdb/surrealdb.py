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
from __future__ import annotations

from json import JSONDecodeError
from types import TracebackType
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Type

import httpx

from ..common import json as jsonlib
from ..common.exceptions import SurrealException
from ..models.response import SurrealResponse

__all__ = ("HTTPClient",)


class HTTPClient:
    """Represents a http connection to a SurrealDB server.

    Parameters
    ----------
    url: :class:`str`
        The URL of the SurrealDB server.
    namespace: :class:`str`
        The namespace to use for the connection.
    database: :class:`str`
        The database to use for the connection.
    username: :class:`str`
        The username to use for the connection.
    password: :class:`str`
        The password to use for the connection.
    """

    def __init__(
        self,
        url: str,
        *,
        namespace: str,
        database: str,
        username: str,
        password: str,
    ) -> None:
        self._url = url
        self._namespace = namespace
        self._database = database
        self._username = username
        self._password = password

        self._http = httpx.AsyncClient(
            base_url=self._url,
            auth=httpx.BasicAuth(
                username=self._username,
                password=self._username,
            ),
            headers={
                "NS": self._namespace,
                "DB": self._database,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    async def __aenter__(self) -> HTTPClient:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]] = None,
        exc_value: Optional[BaseException] = None,
        traceback: Optional[TracebackType] = None,
    ) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        """Connects to http client."""
        await self._http.__aenter__()

    async def disconnect(self) -> None:
        """Disconnects from the http client."""
        await self._http.aclose()

    async def _request(
        self,
        method: str,
        uri: str,
        data: Optional[str] = None,
    ) -> SurrealResponse:
        surreal_response = await self._http.request(
            method=method,
            url=uri,
            content=data,
        )
        surreal_raw_data = await surreal_response.aread()

        try:
            surreal_json: List[Dict[str, Any]] = jsonlib.loads(surreal_raw_data)
            surreal_data = surreal_json[0]
        except JSONDecodeError:
            raise SurrealException(
                f"Invalid JSON response from SurrealDB: {surreal_raw_data}",
            )
        else:
            if surreal_data["status"] != "OK":
                raise SurrealException(
                    f"Query failed: {surreal_data}",
                )

            if surreal_response.status_code not in range(200, 300):
                raise SurrealException(
                    f"Query failed with status code {surreal_response.status_code}: {surreal_data}",
                )

            response_obj = SurrealResponse(**surreal_data)

        return response_obj

    async def execute(self, query: str) -> List[Dict[str, Any]]:
        """Executes a query against the SurrealDB server.

        Parameters
        ----------
        query: :class:`str`
            The query to execute.

        Returns
        -------
        :class:`List[Dict[str, Any]]`
            The results of the query.
        """
        response = await self._request(method="POST", uri="/sql", data=query)
        return response.result

    async def create_all(self, table: str, data: Any) -> List[Dict[str, Any]]:
        """Creates multiple items in a table.

        Parameters
        ----------
        table: :class:`str`
            The table to create the item in.
        data: :class:`Any`
            The data to insert into the table.

        Returns
        -------
        :class:`Dict[str, Any]`
            The items created
        """
        response = await self._request(
            method="POST",
            uri=f"/key/{table}",
            data=jsonlib.dumps(data),
        )

        return response.result

    async def create_one(self, table: str, id: str, data: Any) -> Dict[str, Any]:
        """Creates a single item in a table.

        Parameters
        ----------
        table: :class:`str`
            The table to create the item in.
        id: :class:`str`
            The id of the item to select.
        data: :class:`Any`
            The data to insert into the table.

        Returns
        -------
        :class:`Dict[str, Any]`
            The item created.
        """
        response = await self._request(
            method="POST",
            uri=f"/key/{table}/{id}",
            data=jsonlib.dumps(data),
        )

        return response.result[0]

    async def select_all(self, table: str) -> List[Dict[str, Any]]:
        """Selects all items in a table.

        Parameters
        ----------
        table: :class:`str`
            The table to select from.

        Returns
        -------
        :class:`Dict[str, Any]`
            All items retrieved from the table.
        """
        response = await self._request(method="GET", uri=f"/key/{table}")
        return response.result

    async def select_one(self, table: str, id: str) -> Dict[str, Any]:
        """Selects a single item in a table.

        Parameters
        ----------
        table: :class:`str`
            The table to select from.
        id: :class:`str`
            The id of the item to select.

        Returns
        -------
        :class:`Dict[str, Any]`
            The item selected.
        """
        response = await self._request(method="GET", uri=f"/key/{table}/{id}")
        if not response.result:
            raise SurrealException(f"Key {id} not found in table {table}")

        return response.result[0]

    async def replace_one(self, table: str, id: str, data: Any) -> Dict[str, Any]:
        """Replaces a single item in a table.

        This method requires the entire data structure
        to be sent and will create or update the item.

        Parameters
        ----------
        table: :class:`str`
            The table the item is in.
        id: :class:`str`
            The id of the item to replace.
        data: :class:`Any`
            The data replace the original item with.

        Returns
        -------
        :class:`Dict[str, Any]`
            The new item.
        """
        response = await self._request(
            method="PUT",
            uri=f"/key/{table}/{id}",
            data=jsonlib.dumps(data),
        )
        return response.result[0]

    async def upsert_one(self, table: str, id: str, data: Any) -> Dict[str, Any]:
        """Upserts a single item in a table.

        This method requires only the fields you wish to be updated,
        assuming that this id exists. If it doesn't exist, it will be created
        with the data.

        Parameters
        ----------
        table: :class:`str`
            The table the item is in.
        id: :class:`str`
            The id of the item to upsert.
        data: :class:`Any`
            The data to upsers the original item with.

        Returns
        -------
        :class:`Dict[str, Any]`
            The difference between the old and new item.
        """
        response = await self._request(
            method="PATCH",
            uri=f"/key/{table}/{id}",
            data=jsonlib.dumps(data),
        )

        return response.result[0]

    async def delete_all(self, table: str) -> None:
        """Deletes all items in a table.

        Parameters
        ----------
        table: :class:`str`
            The table to delete all items from.
        """
        await self._request(method="DELETE", uri=f"/key/{table}")

    async def delete_one(self, table: str, id: str) -> None:
        """Deletes one item in a table.

        Parameters
        ----------
        table: :class:`str`
            The table the item is in.
        id: :class:`str`
            The id of the item to delete.
        """
        await self._request(method="DELETE", uri=f"/key/{table}/{id}")
