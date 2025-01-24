import asyncio
from asyncio import Task

from websockets import Subprotocol, ConnectionClosed, connect
from websockets.asyncio.client import ClientConnection

from surrealdb.connection import Connection, ResponseType, RequestData
from surrealdb.constants import METHOD_USE, METHOD_SET, METHOD_UNSET
from surrealdb.errors import SurrealDbConnectionError


class WebsocketConnection(Connection):
    _ws: ClientConnection
    _receiver_task: Task

    async def connect(self):
        try:
            self._ws = await connect(
                self._base_url + "/rpc", subprotocols=[Subprotocol("cbor")], max_size=1048576
            )
            self._receiver_task = asyncio.create_task(self._listen_to_ws(self._ws))
        except Exception as e:
            raise SurrealDbConnectionError("cannot connect db server", e)

    async def use(self, namespace: str, database: str) -> None:
        self._namespace = namespace
        self._database = database

        await self.send(METHOD_USE, namespace, database)

    async def set(self, key: str, value) -> None:
        """
        Set a key-value pair in the database.

        Args:
            key (str): The key to set.
            value: The value to set.
        """
        await self.send(METHOD_SET, key, value)

    async def unset(self, key: str):
        """
        Unset a key-value pair in the database.

        Args:
            key (str): The key to unset.
        """
        await self.send(METHOD_UNSET, key)

    async def close(self):
        if self._receiver_task:
            self._receiver_task.cancel()

        if self._ws:
            await self._ws.close()

    async def _make_request(self, request_data: RequestData):
        request_payload = self._encoder(
            {
                "id": request_data.id,
                "method": request_data.method,
                "params": request_data.params,
            }
        )

        try:
            queue = self.create_response_queue(ResponseType.SEND, request_data.id)
            await self._ws.send(request_payload)

            response_data = await asyncio.wait_for(
                queue.get(), self._timeout
            )  # Set timeout

            if response_data.get("error"):
                raise SurrealDbConnectionError(
                    response_data.get("error").get("message")
                )
            return response_data.get("result")

        except ConnectionClosed as e:
            raise SurrealDbConnectionError(e)
        except asyncio.TimeoutError:
            raise SurrealDbConnectionError(
                f"Request timed-out after {self._timeout} seconds"
            )
        except Exception as e:
            raise e
        finally:
            self.remove_response_queue(ResponseType.SEND, request_data.id)

    async def _listen_to_ws(self, ws):
        async for message in ws:
            try:
                response_data = self._decoder(message)

                response_id = response_data.get("id")
                if response_id:
                    queue = self.get_response_queue(ResponseType.SEND, response_id)
                    await queue.put(response_data)
                    continue

                live_id = response_data.get("result").get("id")  # returned as uuid
                queue = self.get_response_queue(ResponseType.NOTIFICATION, str(live_id))
                if queue is None:
                    self._logger.error(f"No notification queue set for {live_id}")
                    continue
                await queue.put(response_data.get("result"))
            except asyncio.CancelledError:
                self._logger.info(f"Stopped listening for RPC responses")
                break
            except Exception as e:
                self._logger.error(e)
                continue
