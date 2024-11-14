from typing import Tuple

import requests

from surrealdb.connection import Connection
from surrealdb.errors import SurrealDbConnectionError


class HTTPConnection(Connection):

    async def use(self, namespace: str, database: str) -> None:
        self._namespace = namespace
        self._database = database

    async def connect(self) -> None:
        if self._base_url is None:
            raise SurrealDbConnectionError('base url not set for http connection')

        response = requests.get(self._base_url + '/health')
        if response.status_code != 200:
            self._logger.debug("HTTP health check successful")
            raise SurrealDbConnectionError('connection failed. check server is up and base url is correct')

    async def _make_request(self, request_payload: bytes) -> Tuple[bool, bytes]:
        if self._namespace is None:
            raise SurrealDbConnectionError('namespace not set')

        if self._database is None:
            raise SurrealDbConnectionError('database not set')

        headers = {
            'Content-Type': 'application/cbor',
            'Accept': 'application/cbor',
            'Surreal-NS': self._namespace,
            'Surreal-DB': self._database
        }

        if self._auth_token is not None:
            headers['Authorization'] = "Bearer " + self._auth_token

        response = requests.post(self._base_url + '/rpc', data=request_payload, headers=headers)

        successful = False
        if response.status_code >= 200 & response.status_code < 300:
            successful = True

        return successful, response.content
