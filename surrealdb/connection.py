import secrets
import string
import logging
import threading
import uuid
from dataclasses import dataclass

from typing import Dict, Tuple
from surrealdb.constants import REQUEST_ID_LENGTH
from surrealdb.data.cbor import encode, decode
from asyncio import Queue


class ResponseType:
    SEND = 1
    NOTIFICATION = 2
    ERROR = 3


@dataclass
class RequestData:
    id: str
    method: str
    params: Tuple


class Connection:
    _queues: Dict[int, dict]
    _namespace: str | None
    _database: str | None
    _auth_token: str | None

    def __init__(
        self,
        base_url: str,
        logger: logging.Logger,
    ):
        self._locks = {
            ResponseType.SEND: threading.Lock(),
            ResponseType.NOTIFICATION: threading.Lock(),
            ResponseType.ERROR: threading.Lock(),
        }
        self._queues = {
            ResponseType.SEND: dict(),
            ResponseType.NOTIFICATION: dict(),
            ResponseType.ERROR: dict(),
        }

        self._base_url = base_url
        self._logger = logger

    async def use(self, namespace: str, database: str) -> None:
        pass

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def _make_request(self, request_data: RequestData, encoder, decoder):
        pass

    async def set(self, key: str, value):
        pass

    async def unset(self, key: str):
        pass

    def set_token(self, token: str | None = None) -> None:
        self._auth_token = token

    def create_response_queue(self, response_type: int, queue_id: str):
        lock = self._locks[response_type]
        with lock:
            response_type_queues = self._queues.get(response_type)
            if response_type_queues is None:
                response_type_queues = {}

            if response_type_queues.get(queue_id) is None:
                queue: Queue = Queue(maxsize=0)
                response_type_queues[queue_id] = queue
                self._queues[response_type] = response_type_queues
                return queue

    def get_response_queue(self, response_type: int, queue_id: str):
        lock = self._locks[response_type]
        with lock:
            response_type_queues = self._queues.get(response_type)
            if response_type_queues:
                return response_type_queues.get(queue_id)

    def remove_response_queue(self, response_type: int, queue_id: str):
        lock = self._locks[response_type]
        with lock:
            response_type_queues = self._queues.get(response_type)
            if response_type_queues:
                response_type_queues.pop(queue_id, None)

    async def send(self, method: str, *params):
        request_data = RequestData(
            id=request_id(REQUEST_ID_LENGTH), method=method, params=params
        )
        self._logger.debug(f"Request {request_data.id}:", request_data)

        try:
            result = await self._make_request(
                request_data, encoder=encode, decoder=decode
            )

            self._logger.debug(f"Result {request_data.id}:", result)
            self._logger.debug(
                "----------------------------------------------------------------------------------"
            )

            return result
        except Exception as e:
            self._logger.debug(f"Error {request_data.id}:", e)
            self._logger.debug(
                "----------------------------------------------------------------------------------"
            )
            raise e

    async def live_notifications(self, live_query_id: uuid.UUID):
        queue = self.create_response_queue(
            ResponseType.NOTIFICATION, str(live_query_id)
        )
        return queue


def request_id(length: int) -> str:
    return "".join(
        secrets.choice(string.ascii_letters + string.digits) for i in range(length)
    )