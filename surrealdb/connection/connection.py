import secrets
import string
from typing import Optional

from surrealdb.connection.constants import REQUEST_ID_LENGTH
from surrealdb.data.cbor import encode, decode


class Connection:
    def __init__(
            self,
            base_url: str,
            namespace: Optional[str] = None,
            database: Optional[str] = None
    ):
        self._auth_token = None
        self._base_url = base_url
        self._namespace = namespace
        self._database = database

    async def use(self, namespace: str, database: str) -> None:
        pass

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def _make_request(self, request_payload: bytes) -> bytes:
        pass

    async def send(self, method: str, *params):
        print("Request: ", method, params)
        request_data = {
            'id': request_id(REQUEST_ID_LENGTH),
            'method': method,
            'params': params
        }

        response_data = await self._make_request(encode(request_data))
        response = decode(response_data)

        if response.get("error") is not None:
            raise Exception(response.get("error"))

        print("Result: ", response_data.hex())
        print("Result: ", response.get("result"))
        print("------------------------------------------------------------------------------------------------------------------------")
        return response.get("result")

    def set_token(self, token: Optional[str] = None) -> None:
        self._auth_token = token


def request_id(length: int) -> str:
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(length))
