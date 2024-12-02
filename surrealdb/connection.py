import secrets
import string
import logging
import threading
import uuid
from dataclasses import dataclass

from typing import Dict, Tuple
from surrealdb.constants import (
    REQUEST_ID_LENGTH,
    METHOD_SELECT,
    METHOD_CREATE,
    METHOD_INSERT,
    METHOD_PATCH,
    METHOD_UPDATE,
    METHOD_UPSERT,
    METHOD_DELETE,
    METHOD_MERGE,
    METHOD_LIVE,
)
from asyncio import Queue
from surrealdb.data.models import table_or_record_id


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
    _locks: Dict[int, threading.Lock]
    _namespace: str | None = None
    _database: str | None = None
    _auth_token: str | None = None

    def __init__(
        self,
        base_url: str,
        logger: logging.Logger,
        encoder,
        decoder,
    ):
        self._encoder = encoder
        self._decoder = decoder

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

    async def _make_request(self, request_data: RequestData):
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

    @staticmethod
    def _prepare_method_params(method: str, params) -> Tuple:
        prepared_params = params
        if method in [
            METHOD_SELECT,
            METHOD_CREATE,
            METHOD_INSERT,
            METHOD_PATCH,
            METHOD_UPDATE,
            METHOD_UPSERT,
            METHOD_DELETE,
            METHOD_MERGE,
            METHOD_LIVE,
        ]:  # The first parameters for these methods are expected to be record id or table
            if len(prepared_params) > 0 and isinstance(prepared_params[0], str):
                thing = table_or_record_id(prepared_params[0])
                prepared_params = prepared_params[:0] + (thing,) + prepared_params[1:]
        return prepared_params

    async def send(self, method: str, *params):
        prepared_params = self._prepare_method_params(method, params)
        request_data = RequestData(
            id=request_id(REQUEST_ID_LENGTH), method=method, params=prepared_params
        )
        self._logger.debug(f"Request {request_data.id}:", request_data)

        try:
            result = await self._make_request(request_data)

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
