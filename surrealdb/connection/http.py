import requests

from surrealdb.connection.connection import Connection


class HTTPConnection(Connection):

    async def use(self, namespace: str, database: str) -> None:
        self._namespace = namespace
        self._database = database

    async def connect(self) -> None:
        if self._base_url is None:
            raise Exception('base url not set')

        response = requests.get(self._base_url + '/health')
        if response.status_code != 200:
            raise Exception('connection failed. check server is up or base url is correct')

    async def _make_request(self, request_payload: bytes) -> bytes:
        if self._namespace is None:
            raise Exception('namespace not set')

        if self._database is None:
            raise Exception('database not set')

        headers = {
            'Content-Type': 'application/cbor',
            'Accept': 'application/cbor',
            'Surreal-NS': self._namespace,
            'Surreal-DB': self._database
        }

        if self._auth_token is not None:
            headers['Authorization'] = "Bearer " + self._auth_token

        response = requests.post(self._base_url + '/rpc', data=request_payload, headers=headers)

        if response.status_code >= 200 & response.status_code < 300:
            return response.content

        raise Exception('rpc request failed')
