import threading
from typing import Any

import requests

from surrealdb.connection import Connection, RequestData
from surrealdb.errors import SurrealDbConnectionError


class HTTPConnection(Connection):
    _request_variables: dict[str, Any]
    _request_variables_lock = threading.Lock()

    async def use(self, namespace: str, database: str) -> None:
        self._namespace = namespace
        self._database = database

    async def set(self, key: str, value):
        with self._request_variables_lock:
            self._request_variables[key] = value

    async def unset(self, key: str):
        with self._request_variables_lock:
            del self._request_variables[key]

    async def connect(self) -> None:
        if self._base_url is None:
            raise SurrealDbConnectionError("base url not set for http connection")

        response = requests.get(self._base_url + "/health")
        if response.status_code != 200:
            self._logger.debug("HTTP health check successful")
            raise SurrealDbConnectionError(
                "connection failed. check server is up and base url is correct"
            )

    async def _make_request(self, request_data: RequestData, encoder, decoder):
        if self._namespace is None:
            raise SurrealDbConnectionError("namespace not set")

        if self._database is None:
            raise SurrealDbConnectionError("database not set")

        headers = {
            "Content-Type": "application/cbor",
            "Accept": "application/cbor",
            "Surreal-NS": self._namespace,
            "Surreal-DB": self._database,
        }

        if self._auth_token is not None:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        request_payload = encoder(
            {
                "id": request_data.id,
                "method": request_data.method,
                "params": request_data.params,
            }
        )

        response = requests.post(
            f"{self._base_url}/rpc", data=request_payload, headers=headers
        )
        response_data = decoder(response.content)

        if 200 > response.status_code > 299 or response_data.get("error"):
            raise SurrealDbConnectionError(response_data.get("error").get("message"))

        return response_data.get("result")
