"""
Defines the base Connection class for sending and receiving requests.
"""
import logging
import secrets
import string
import threading
import uuid
from asyncio import Queue
from dataclasses import dataclass
from typing import Dict, Tuple

from surrealdb.constants import REQUEST_ID_LENGTH
from surrealdb.data.cbor import encode, decode


class ResponseType:
    """
    Enum-like class representing response types for the connection.

    Attributes:
        SEND (int): Response type for standard requests.
        NOTIFICATION (int): Response type for notifications.
        ERROR (int): Response type for errors.
    """
    SEND = 1
    NOTIFICATION = 2
    ERROR = 3


@dataclass
class RequestData:
    """
    Represents the data for a request sent over the connection.

    Attributes:
        id (str): Unique identifier for the request.
        method (str): The method name to invoke.
        params (Tuple): Parameters for the method.
    """
    id: str
    method: str
    params: Tuple


class Connection:
    """
    Base class for managing a connection to the database.

    Manages request/response lifecycle, including the use of queues for
    handling asynchronous communication.

    Attributes:
        _queues (Dict[int, dict]): Mapping of response types to their queues.
        _namespace (str | None): Current namespace in use.
        _database (str | None): Current database in use.
        _auth_token (str | None): Authentication token.
    """
    _queues: Dict[int, dict]
    _namespace: str | None
    _database: str | None
    _auth_token: str | None

    def __init__(
        self,
        base_url: str,
        logger: logging.Logger,
    ):
        """
        Initialize the Connection instance.

        Args:
            base_url (str): The base URL of the server.
            logger (logging.Logger): Logger for debugging and tracking activities.
        """
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
        """
        Set the namespace and database for subsequent operations.

        Args:
            namespace (str): The namespace to use.
            database (str): The database to use.
        """
        raise NotImplementedError("use method must be implemented")

    async def connect(self) -> None:
        """
        Establish a connection to the server.
        """
        raise NotImplementedError("connect method must be implemented")

    async def close(self) -> None:
        """
        Close the connection to the server.
        """
        raise NotImplementedError("close method must be implemented")

    async def _make_request(self, request_data: RequestData, encoder, decoder) -> dict:
        """
        Internal method to send a request and handle the response.

        Args:
            request_data (RequestData): The data to send.
            encoder (function): Function to encode the request.
            decoder (function): Function to decode the response.
        return:
            dict: The response data from the request.
        """
        raise NotImplementedError("_make_request method must be implemented")

    async def set(self, key: str, value) -> None:
        """
        Set a key-value pair in the database.

        Args:
            key (str): The key to set.
            value: The value to set.
        """
        raise NotImplementedError("set method must be implemented")

    async def unset(self, key: str) -> None:
        """
        Unset a key-value pair in the database.

        Args:
            key (str): The key to unset.
        """
        raise NotImplementedError("unset method must be implemented")

    def set_token(self, token: str | None = None) -> None:
        """
        Set the authentication token for the connection.

        Args:
            token (str): The authentication token to be set
        """
        self._auth_token = token

    def create_response_queue(self, response_type: int, queue_id: str) -> Queue:
        """
        Create a response queue for a given response type.

        Args:
            response_type (int): The response type for the queue (1: SEND, 2: NOTIFICATION, 3: ERROR).
            queue_id (str): The unique identifier for the queue.
        Returns:
            Queue: The response queue for the given response type and queue ID
            (existing queues will be overwritten if same ID is used, cannot get existing queue).
        """
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

    def get_response_queue(self, response_type: int, queue_id: str) -> Queue | None:
        """
        Get a response queue for a given response type.

        Args:
            response_type (int): The response type for the queue (1: SEND, 2: NOTIFICATION, 3: ERROR).
            queue_id (str): The unique identifier for the queue.

        Returns:
            Queue: The response queue for the given response type and queue ID
            (existing queues will be overwritten if same ID is used).
        """
        lock = self._locks[response_type]
        with lock:
            response_type_queues = self._queues.get(response_type)
            if response_type_queues:
                return response_type_queues.get(queue_id)

    def remove_response_queue(self, response_type: int, queue_id: str) -> None:
        """
        Remove a response queue for a given response type.

        Notes:
            Does not alert if the key is missing

        Args:
            response_type (int): The response type for the queue (1: SEND, 2: NOTIFICATION, 3: ERROR).
            queue_id (str): The unique identifier for the queue.
        """
        lock = self._locks[response_type]
        with lock:
            response_type_queues = self._queues.get(response_type)
            if response_type_queues:
                response_type_queues.pop(queue_id, None)

    async def send(self, method: str, *params) -> dict:
        """
        Sends a request to the server with a unique ID and returns the response.

        Args:
            method (str): The method of the request.
            params: Parameters for the request.

        Returns:
            dict: The response data from the request.
        """
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

    async def live_notifications(self, live_query_id: uuid.UUID) -> Queue:
        """
        Create a response queue for live notifications by essentially creating a NOTIFICATION response queue.

        Args:
            live_query_id (uuid.UUID): The unique identifier for the live query.

        Returns:
            Queue: The response queue for the live notifications.
        """
        queue = self.create_response_queue(
            ResponseType.NOTIFICATION, str(live_query_id)
        )
        return queue


def request_id(length: int) -> str:
    return "".join(
        secrets.choice(string.ascii_letters + string.digits) for i in range(length)
    )
