"""
A basic async connection to a SurrealDB instance.
"""

import asyncio
from asyncio import AbstractEventLoop, Future, Queue, Task
from collections.abc import AsyncGenerator
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import websockets

from surrealdb.connections.async_template import AsyncTemplate
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import UtilsMixin
from surrealdb.data.cbor import decode
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod


class AsyncWsSurrealConnection(AsyncTemplate, UtilsMixin):
    """
    A single async connection to a SurrealDB instance. To be used once and discarded.

    Attributes:
        url: The URL of the database to process queries for.
    """

    def __init__(
        self,
        url: str,
    ) -> None:
        """
        The constructor for the AsyncSurrealConnection class.

        :param url: The URL of the database to process queries for.
        """
        self.url: Url = Url(url)
        self.raw_url: str = f"{self.url.raw_url}/rpc"
        self.host: Optional[str] = self.url.hostname
        self.port: Optional[int] = self.url.port
        self.token: Optional[str] = None
        self.socket = None
        self.loop: Optional[AbstractEventLoop] = None
        self.qry: dict[str, Future] = {}
        self.recv_task: Optional[Task[None]] = None
        self.live_queues: dict[str, list] = {}

    async def _recv_task(self):
        assert self.socket
        async for data in self.socket:
            response = decode(data)
            if response_id := response.get("id"):
                if fut := self.qry.get(response_id):
                    fut.set_result(response)
            elif response_result := response.get("result"):
                live_id = str(response_result["id"])
                for queue in self.live_queues.get(live_id, []):
                    queue.put_nowait(response_result)
            else:
                self.check_response_for_error(response, "_recv_task")

    async def _send(
        self, message: RequestMessage, process: str, bypass: bool = False
    ) -> dict:
        await self.connect()
        assert (
            self.socket is not None and self.loop is not None
        )  # will always not be None as the self.connect ensures there's a connection

        # setup future to wait for response
        fut = self.loop.create_future()
        query_id = message.id
        self.qry[query_id] = fut
        try:
            # correlate message to query, send and forget it
            await self.socket.send(message.WS_CBOR_DESCRIPTOR)
            del message

            # wait for response
            response = await fut
        finally:
            del self.qry[query_id]

        if bypass is False:
            self.check_response_for_error(response, process)

        if isinstance(response, dict):
            return response
        else:
            return {}

    async def connect(self, url: Optional[str] = None) -> None:
        if self.socket:
            return

        # overwrite params if passed in
        if url is not None:
            self.url = Url(url)
            self.raw_url = f"{self.url.raw_url}/rpc"
            self.host = self.url.hostname
            self.port = self.url.port

        self.socket = await websockets.connect(
            self.raw_url,
            max_size=None,
            subprotocols=[websockets.Subprotocol("cbor")],
        )
        self.loop = asyncio.get_running_loop()
        self.recv_task = asyncio.create_task(self._recv_task())

    async def authenticate(self, token: str) -> None:
        message = RequestMessage(RequestMethod.AUTHENTICATE, token=token)
        await self._send(message, "authenticating")

    async def invalidate(self) -> None:
        message = RequestMessage(RequestMethod.INVALIDATE)
        await self._send(message, "invalidating")
        self.token = None

    async def signup(self, vars: Dict) -> str:
        message = RequestMessage(RequestMethod.SIGN_UP, data=vars)
        response = await self._send(message, "signup")
        self.check_response_for_result(response, "signup")
        return response["result"]

    async def signin(self, vars: Dict[str, Any]) -> str:
        message = RequestMessage(
            RequestMethod.SIGN_IN,
            username=vars.get("username"),
            password=vars.get("password"),
            access=vars.get("access"),
            database=vars.get("database"),
            namespace=vars.get("namespace"),
            variables=vars.get("variables"),
        )
        response = await self._send(message, "signing in")
        self.check_response_for_result(response, "signing in")
        self.token = response["result"]
        return response["result"]

    async def info(self) -> dict:
        message = RequestMessage(RequestMethod.INFO)
        outcome = await self._send(message, "getting database information")
        self.check_response_for_result(outcome, "getting database information")
        return outcome["result"]

    async def use(self, namespace: str, database: str) -> None:
        message = RequestMessage(
            RequestMethod.USE,
            namespace=namespace,
            database=database,
        )
        await self._send(message, "use")

    async def query(
        self, query: str, vars: Optional[dict] = None
    ) -> Union[List[dict], dict]:
        if vars is None:
            vars = {}
        message = RequestMessage(
            RequestMethod.QUERY,
            query=query,
            params=vars,
        )
        response = await self._send(message, "query")
        self.check_response_for_result(response, "query")
        return response["result"][0]["result"]

    async def query_raw(self, query: str, params: Optional[dict] = None) -> dict:
        if params is None:
            params = {}
        message = RequestMessage(
            RequestMethod.QUERY,
            query=query,
            params=params,
        )
        response = await self._send(message, "query", bypass=True)
        return response

    async def version(self) -> str:
        message = RequestMessage(RequestMethod.VERSION)
        response = await self._send(message, "getting database version")
        self.check_response_for_result(response, "getting database version")
        return response["result"]

    async def let(self, key: str, value: Any) -> None:
        message = RequestMessage(RequestMethod.LET, key=key, value=value)
        await self._send(message, "letting")

    async def unset(self, key: str) -> None:
        message = RequestMessage(RequestMethod.UNSET, params=[key])
        await self._send(message, "unsetting")

    async def select(
        self, thing: Union[str, RecordID, Table]
    ) -> Union[List[dict], dict]:
        message = RequestMessage(RequestMethod.SELECT, params=[thing])
        response = await self._send(message, "select")
        self.check_response_for_result(response, "select")
        return response["result"]

    async def create(
        self,
        thing: Union[str, RecordID, Table],
        data: Optional[Union[Union[List[dict], dict], dict]] = None,
    ) -> Union[List[dict], dict]:
        if isinstance(thing, str):
            if ":" in thing:
                buffer = thing.split(":")
                thing = RecordID(table_name=buffer[0], identifier=buffer[1])
        message = RequestMessage(RequestMethod.CREATE, collection=thing, data=data)
        response = await self._send(message, "create")
        self.check_response_for_result(response, "create")
        return response["result"]

    async def update(
        self, thing: Union[str, RecordID, Table], data: Optional[Dict] = None
    ) -> Union[List[dict], dict]:
        message = RequestMessage(RequestMethod.UPDATE, record_id=thing, data=data)
        response = await self._send(message, "update")
        self.check_response_for_result(response, "update")
        return response["result"]

    async def merge(
        self, thing: Union[str, RecordID, Table], data: Optional[Dict] = None
    ) -> Union[List[dict], dict]:
        message = RequestMessage(RequestMethod.MERGE, record_id=thing, data=data)
        response = await self._send(message, "merge")
        self.check_response_for_result(response, "merge")
        return response["result"]

    async def patch(
        self, thing: Union[str, RecordID, Table], data: Optional[List[Dict]] = None
    ) -> Union[List[dict], dict]:
        message = RequestMessage(RequestMethod.PATCH, collection=thing, params=data)
        response = await self._send(message, "patch")
        self.check_response_for_result(response, "patch")
        return response["result"]

    async def delete(
        self, thing: Union[str, RecordID, Table]
    ) -> Union[List[dict], dict]:
        message = RequestMessage(RequestMethod.DELETE, record_id=thing)
        response = await self._send(message, "delete")
        self.check_response_for_result(response, "delete")
        return response["result"]

    async def insert(
        self, table: Union[str, Table], data: Union[List[dict], dict]
    ) -> Union[List[dict], dict]:
        message = RequestMessage(RequestMethod.INSERT, collection=table, params=data)
        response = await self._send(message, "insert")
        self.check_response_for_result(response, "insert")
        return response["result"]

    async def insert_relation(
        self, table: Union[str, Table], data: Union[List[dict], dict]
    ) -> Union[List[dict], dict]:
        message = RequestMessage(
            RequestMethod.INSERT_RELATION, table=table, params=data
        )
        response = await self._send(message, "insert_relation")
        self.check_response_for_result(response, "insert_relation")
        return response["result"]

    async def live(self, table: Union[str, Table], diff: bool = False) -> UUID:
        message = RequestMessage(
            RequestMethod.LIVE,
            table=table,
        )
        response = await self._send(message, "live")
        self.check_response_for_result(response, "live")
        uuid = response["result"]
        assert uuid not in self.live_queues
        self.live_queues[str(uuid)] = []
        return uuid

    async def subscribe_live(
        self, query_uuid: Union[str, UUID]
    ) -> AsyncGenerator[Dict, None]:
        result_queue = Queue()
        suid = str(query_uuid)
        self.live_queues[suid].append(result_queue)

        async def _iter():
            while True:
                ret = await result_queue.get()
                yield ret["result"]

        return _iter()

    async def kill(self, query_uuid: Union[str, UUID]) -> None:
        message = RequestMessage(RequestMethod.KILL, uuid=query_uuid)
        await self._send(message, "kill")
        self.live_queues.pop(str(query_uuid), None)

    async def upsert(
        self, thing: Union[str, RecordID, Table], data: Optional[Dict] = None
    ) -> Union[List[dict], dict]:
        message = RequestMessage(RequestMethod.UPSERT, record_id=thing, data=data)
        response = await self._send(message, "upsert")
        self.check_response_for_result(response, "upsert")
        return response["result"]

    async def close(self):
        if self.recv_task:
            self.recv_task.cancel()
            try:
                await self.recv_task
            except asyncio.CancelledError:
                pass

        if self.socket is not None:
            await self.socket.close()

    async def __aenter__(self) -> "AsyncWsSurrealConnection":
        """
        Asynchronous context manager entry.
        Initializes a websocket connection and returns the connection instance.
        """
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """
        Asynchronous context manager exit.
        Closes the websocket connection upon exiting the context.
        """
        await self.close()
