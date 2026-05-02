import uuid
from types import TracebackType
from typing import Any, cast, overload

import aiohttp

from surrealdb.connections.async_template import AsyncTemplate
from surrealdb.connections.builders import (
    _AsyncCrudBuilder,
    _AsyncInsertBuilder,
    _AsyncQueryBuilder,
)
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import UtilsMixin
from surrealdb.data.cbor import decode
from surrealdb.data.types.record_id import RecordID, RecordIdType
from surrealdb.data.types.table import Table
from surrealdb.errors import UnsupportedFeatureError
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod
from surrealdb.types import Tokens, Value, parse_auth_result


class AsyncHttpSurrealConnection(AsyncTemplate, UtilsMixin):
    """
    A single async connection to a SurrealDB instance using HTTP. To be used once and discarded.

    # Notes
    A new HTTP session is created for each query to send a request to the SurrealDB server.

    Attributes:
        url: The URL of the database to process queries for.
        id: The ID of the connection.
    """

    def __init__(
        self,
        url: str,
    ) -> None:
        """
        Constructor for the AsyncHttpSurrealConnection class.

        :param url: (str) The URL of the database to process queries for.
        """
        self.url: Url = Url(url)
        self.raw_url: str = self.url.raw_url
        self.host: str | None = self.url.hostname
        self.port: int | None = self.url.port
        self.token: str | None = None
        self.id: str = str(uuid.uuid4())
        self.namespace: str | None = None
        self.database: str | None = None
        self.vars: dict[str, Value] = dict()
        self._session: aiohttp.ClientSession | None = None

    async def _send(
        self,
        message: RequestMessage,
        operation: str,
        bypass: bool = False,
    ) -> dict[str, Any]:
        data = message.WS_CBOR_DESCRIPTOR
        url = f"{self.url.raw_url}/rpc"
        headers: dict[str, str] = {}
        headers["Accept"] = "application/cbor"
        headers["content-type"] = "application/cbor"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.namespace:
            headers["Surreal-NS"] = self.namespace
        if self.database:
            headers["Surreal-DB"] = self.database

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method="POST",
                url=url,
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                response.raise_for_status()
                raw_cbor = await response.read()
                data = decode(raw_cbor)
                if bypass is False:
                    self.check_response_for_error(data, operation)
                return data

    def set_token(self, token: str) -> None:
        """
        Sets the token for authentication.

        :param token: (str) The token to use for the connection.
        """
        self.token = token

    async def authenticate(self, token: str) -> None:
        self.token = token
        message = RequestMessage(RequestMethod.AUTHENTICATE, token=self.token)
        self.id = message.id
        await self._send(message, "authenticating")

    async def invalidate(self) -> None:
        message = RequestMessage(RequestMethod.INVALIDATE)
        self.id = message.id
        await self._send(message, "invalidating")
        self.token = None

    async def signup(self, vars: dict[str, Value]) -> Tokens:
        message = RequestMessage(RequestMethod.SIGN_UP, data=vars)
        self.id = message.id
        response = await self._send(message, "signup")
        self.check_response_for_result(response, "signup")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        return tokens

    async def signin(self, vars: dict[str, Value]) -> Tokens:
        message = RequestMessage(RequestMethod.SIGN_IN, params=vars)
        self.id = message.id
        response = await self._send(message, "signing in")
        self.check_response_for_result(response, "signing in")
        tokens = parse_auth_result(response["result"])
        self.token = tokens.access
        return tokens

    async def info(self) -> Value:
        message = RequestMessage(RequestMethod.INFO)
        self.id = message.id
        response = await self._send(
            message, "getting database information", bypass=True
        )

        self.check_response_for_result(response, "getting database information")
        return cast(dict[str, Value], response["result"])

    async def use(self, namespace: str, database: str) -> None:
        message = RequestMessage(
            RequestMethod.USE,
            namespace=namespace,
            database=database,
        )
        self.id = message.id
        _ = await self._send(message, "use")
        self.namespace = namespace
        self.database = database

    def query(
        self, query: str, vars: dict[str, Value] | None = None
    ) -> _AsyncQueryBuilder:
        return _AsyncQueryBuilder(
            executor=self._make_executor(),
            query=query,
            variables=vars,
        )

    async def query_raw(
        self, query: str, params: dict[str, Value] | None = None
    ) -> dict[str, Any]:
        if params is None:
            params = {}
        for key, value in self.vars.items():
            params[key] = value
        message = RequestMessage(
            RequestMethod.QUERY,
            query=query,
            params=params,
        )
        self.id = message.id
        response = await self._send(message, "query", bypass=True)
        return response

    def _make_executor(self) -> Any:
        async def _executor(query: str, params: dict[str, Any]) -> dict[str, Any]:
            return await self.query_raw(query, params)

        return _executor

    # CRUD overloads --------------------------------------------------------

    @overload
    def create(
        self, record: RecordID, data: Value | None = None
    ) -> _AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: Table, data: Value | None = None
    ) -> _AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def create(
        self, record: str, data: Value | None = None
    ) -> _AsyncCrudBuilder[dict[str, Value]]: ...
    def create(
        self, record: RecordIdType, data: Value | None = None
    ) -> _AsyncCrudBuilder[Any]:
        return _AsyncCrudBuilder(
            executor=self._make_executor(),
            operation="CREATE",
            record=record,
            op_name="create",
            data=data,
            always_unwrap=True,
        )

    @overload
    def update(
        self, record: RecordID, data: Value | None = None
    ) -> _AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def update(
        self, record: Table, data: Value | None = None
    ) -> _AsyncCrudBuilder[list[Value]]: ...
    @overload
    def update(
        self, record: str, data: Value | None = None
    ) -> _AsyncCrudBuilder[Value]: ...
    def update(
        self, record: RecordIdType, data: Value | None = None
    ) -> _AsyncCrudBuilder[Any]:
        return _AsyncCrudBuilder(
            executor=self._make_executor(),
            operation="UPDATE",
            record=record,
            op_name="update",
            data=data,
        )

    @overload
    def upsert(
        self, record: RecordID, data: Value | None = None
    ) -> _AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def upsert(
        self, record: Table, data: Value | None = None
    ) -> _AsyncCrudBuilder[list[Value]]: ...
    @overload
    def upsert(
        self, record: str, data: Value | None = None
    ) -> _AsyncCrudBuilder[Value]: ...
    def upsert(
        self, record: RecordIdType, data: Value | None = None
    ) -> _AsyncCrudBuilder[Any]:
        return _AsyncCrudBuilder(
            executor=self._make_executor(),
            operation="UPSERT",
            record=record,
            op_name="upsert",
            data=data,
        )

    @overload
    def delete(self, record: RecordID) -> _AsyncCrudBuilder[dict[str, Value]]: ...
    @overload
    def delete(self, record: Table) -> _AsyncCrudBuilder[list[Value]]: ...
    @overload
    def delete(self, record: str) -> _AsyncCrudBuilder[Value]: ...
    def delete(self, record: RecordIdType) -> _AsyncCrudBuilder[Any]:
        return _AsyncCrudBuilder(
            executor=self._make_executor(),
            operation="DELETE",
            record=record,
            op_name="delete",
        )

    def insert(
        self,
        table: str | Table,
        data: Value | None = None,
        *,
        relation: bool = False,
    ) -> _AsyncInsertBuilder:
        return _AsyncInsertBuilder(
            executor=self._make_executor(),
            table=table,
            data=data,
            relation=relation,
        )

    async def run(
        self,
        name: str,
        args: list[Value] | None = None,
        version: str | None = None,
    ) -> Value:
        kwargs: dict[str, Any] = {"name": name}
        if version is not None:
            kwargs["version"] = version
        if args is not None:
            kwargs["args"] = args
        message = RequestMessage(RequestMethod.RUN, **kwargs)
        self.id = message.id
        response = await self._send(message, "run")
        self.check_response_for_result(response, "run")
        return response["result"]

    async def let(self, key: str, value: Value) -> None:
        self.vars[key] = value

    async def unset(self, key: str) -> None:
        self.vars.pop(key)

    async def select(self, record: RecordIdType) -> Value:
        variables: dict[str, Any] = {}
        resource_ref = self._resource_to_variable(record, variables, "_resource")
        query = f"SELECT * FROM {resource_ref}"

        response = await self.query_raw(query, variables)
        self.check_response_for_error(response, "select")
        self._check_query_result(response["result"][0])
        return response["result"][0]["result"]

    async def version(self) -> str:
        message = RequestMessage(RequestMethod.VERSION)
        self.id = message.id
        response = await self._send(message, "getting database version")
        self.check_response_for_result(response, "getting database version")
        return response["result"]

    async def __aenter__(self) -> "AsyncHttpSurrealConnection":
        """
        Asynchronous context manager entry.
        Initializes an aiohttp session and returns the connection instance.
        """
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Asynchronous context manager exit.
        Closes the aiohttp session upon exiting the context.
        """
        if self._session is not None:
            await self._session.close()

    async def attach(self) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    async def detach(self, session_id: Any) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    async def begin(self, session_id: Any = None) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    async def commit(self, txn_id: Any, session_id: Any = None) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    async def cancel(self, txn_id: Any, session_id: Any = None) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )

    async def new_session(self) -> None:
        raise UnsupportedFeatureError(
            "Multi-session and client-side transactions are only supported for WebSocket connections"
        )
