import secrets
import string
import logging

from typing import Optional, Tuple
from surrealdb.constants import REQUEST_ID_LENGTH
from surrealdb.data.cbor import encode, decode
from surrealdb.errors import SurrealDbConnectionError


class Connection:
    def __init__(
            self,
            base_url: str,
            logger: logging.Logger,
    ):
        self._auth_token = None
        self._namespace = None
        self._database = None

        self._base_url = base_url
        self._logger = logger

    async def use(self, namespace: str, database: str) -> None:
        pass

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def _make_request(self, request_payload: bytes) -> Tuple[bool, bytes]:
        pass

    async def set(self, key: str, value):
        pass

    async def unset(self, key: str):
        pass

    async def send(self, method: str, *params):
        req_id = request_id(REQUEST_ID_LENGTH)
        request_data = {
            'id': req_id,
            'method': method,
            'params': params
        }
        self._logger.debug(f"Request {req_id}:", request_data)

        try:
            successful, response_data = await self._make_request(encode(request_data))
            response = decode(response_data)

            if response.get("error") is not None or successful is not True:
                error_msg = "request to rpc endpoint failed"
                if response.get("error") is not None:
                    error_msg = response.get("error").get("message")
                raise SurrealDbConnectionError(error_msg)

            self._logger.debug(f"Response {req_id}:", response_data.hex())
            self._logger.debug(f"Decoded Result {req_id}:", response)
            self._logger.debug("----------------------------------------------------------------------------------")

            return response.get("result")
        except Exception as e:
            self._logger.debug(f"Error {req_id}:", e)
            self._logger.debug("----------------------------------------------------------------------------------")
            raise e

    def set_token(self, token: Optional[str] = None) -> None:
        self._auth_token = token


def request_id(length: int) -> str:
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(length))
