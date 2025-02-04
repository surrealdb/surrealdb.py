import uuid
from typing import Optional, Any, Dict, Union, List

import aiohttp

from surrealdb.connections.async_template import AsyncTemplate
from surrealdb.connections.url import Url
from surrealdb.connections.utils_mixin import UtilsMixin
from surrealdb.data.cbor import decode
from surrealdb.data.types.record_id import RecordID
from surrealdb.data.types.table import Table
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod


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
        self.host: str = self.url.hostname
        self.port: Optional[int] = self.url.port
        self.token: Optional[str] = None
        self.id: str = str(uuid.uuid4())
        self.namespace: Optional[str] = None
        self.database: Optional[str] = None
        self.vars = dict()

    async def _send(
        self,
        message: RequestMessage,
        operation: str,
        bypass: bool = False,
    ) -> Dict[str, Any]:
        """
        Sends an HTTP request to the SurrealDB server.

        :param endpoint: (str) The endpoint of the SurrealDB API to send the request to.
        :param method: (str) The HTTP method (e.g., "POST", "GET", "PUT", "DELETE").
        :param headers: (dict) Optional headers to include in the request.
        :param payload: (dict) Optional JSON payload to include in the request body.

        :return: (dict) The decoded JSON response from the server.
        """
        # json_body, method, endpoint = message.JSON_HTTP_DESCRIPTOR
        data = message.WS_CBOR_DESCRIPTOR
        url = f"{self.url.raw_url}/rpc"
        headers = dict()
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
                # json=json.dumps(json_body),
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

    async def authenticate(self) -> None:
        message = RequestMessage(self.id, RequestMethod.AUTHENTICATE, token=self.token)
        return await self._send(message, "authenticating")

    async def invalidate(self) -> None:
        message = RequestMessage(self.id, RequestMethod.INVALIDATE)
        await self._send(message, "invalidating")
        self.token = None

    async def signup(self, vars: Dict) -> str:
        message = RequestMessage(self.id, RequestMethod.SIGN_UP, data=vars)
        response = await self._send(message, "signup")
        self.check_response_for_result(response, "signup")
        self.token = response["result"]
        return response["result"]

    async def signin(self, vars: dict) -> dict:
        message = RequestMessage(
            self.id,
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
        message = RequestMessage(self.id, RequestMethod.INFO)
        response = await self._send(message, "getting database information")
        self.check_response_for_result(response, "getting database information")
        return response["result"]

    async def use(self, namespace: str, database: str) -> None:
        message = RequestMessage(
            self.token,
            RequestMethod.USE,
            namespace=namespace,
            database=database,
        )
        _ = await self._send(message, "use")
        self.namespace = namespace
        self.database = database

    async def query(self, query: str, params: Optional[dict] = None) -> dict:
        if params is None:
            params = {}
        for key, value in self.vars.items():
            params[key] = value
        message = RequestMessage(
            self.id,
            RequestMethod.QUERY,
            query=query,
            params=params,
        )
        response = await self._send(message, "query")
        self.check_response_for_result(response, "query")
        return response["result"][0]["result"]

    async def query_raw(self, query: str, params: Optional[dict] = None) -> dict:
        if params is None:
            params = {}
        for key, value in self.vars.items():
            params[key] = value
        message = RequestMessage(
            self.id,
            RequestMethod.QUERY,
            query=query,
            params=params,
        )
        response = await self._send(message, "query", bypass=True)
        return response

    async def create(
        self,
        thing: Union[str, RecordID, Table],
        data: Optional[Union[Union[List[dict], dict], dict]] = None,
    ) -> Union[List[dict], dict]:
        if isinstance(thing, str):
            if ":" in thing:
                buffer = thing.split(":")
                thing = RecordID(table_name=buffer[0], identifier=buffer[1])
        message = RequestMessage(
            self.id, RequestMethod.CREATE, collection=thing, data=data
        )
        response = await self._send(message, "create")
        self.check_response_for_result(response, "create")
        return response["result"]

    async def delete(
        self, thing: Union[str, RecordID, Table]
    ) -> Union[List[dict], dict]:
        message = RequestMessage(self.id, RequestMethod.DELETE, record_id=thing)
        response = await self._send(message, "delete")
        self.check_response_for_result(response, "delete")
        return response["result"]

    async def insert(
        self, table: Union[str, Table], data: Union[List[dict], dict]
    ) -> Union[List[dict], dict]:
        message = RequestMessage(
            self.id, RequestMethod.INSERT, collection=table, params=data
        )
        response = await self._send(message, "insert")
        self.check_response_for_result(response, "insert")
        return response["result"]

    async def insert_relation(
        self, table: Union[str, Table], data: Union[List[dict], dict]
    ) -> Union[List[dict], dict]:
        message = RequestMessage(
            self.id, RequestMethod.INSERT_RELATION, table=table, params=data
        )
        response = await self._send(message, "insert_relation")
        self.check_response_for_result(response, "insert_relation")
        return response["result"]

    async def let(self, key: str, value: Any) -> None:
        self.vars[key] = value

    async def unset(self, key: str) -> None:
        self.vars.pop(key)

    async def merge(
        self, thing: Union[str, RecordID, Table], data: Optional[Dict] = None
    ) -> Union[List[dict], dict]:
        message = RequestMessage(
            self.id, RequestMethod.MERGE, record_id=thing, data=data
        )
        response = await self._send(message, "merge")
        self.check_response_for_result(response, "merge")
        return response["result"]

    async def patch(
        self, thing: Union[str, RecordID, Table], data: Optional[List[dict]] = None
    ) -> Union[List[dict], dict]:
        message = RequestMessage(
            self.id, RequestMethod.PATCH, collection=thing, params=data
        )
        response = await self._send(message, "patch")
        self.check_response_for_result(response, "patch")
        return response["result"]

    async def select(self, thing: str) -> Union[List[dict], dict]:
        message = RequestMessage(self.id, RequestMethod.SELECT, params=[thing])
        response = await self._send(message, "select")
        self.check_response_for_result(response, "select")
        return response["result"]

    async def update(
        self, thing: Union[str, RecordID, Table], data: Optional[Dict] = None
    ) -> Union[List[dict], dict]:
        message = RequestMessage(
            self.id, RequestMethod.UPDATE, record_id=thing, data=data
        )
        response = await self._send(message, "update")
        self.check_response_for_result(response, "update")
        return response["result"]

    async def version(self) -> str:
        message = RequestMessage(self.id, RequestMethod.VERSION)
        response = await self._send(message, "getting database version")
        self.check_response_for_result(response, "getting database version")
        return response["result"]

    async def upsert(
        self, thing: Union[str, RecordID, Table], data: Optional[Dict] = None
    ) -> Union[List[dict], dict]:
        message = RequestMessage(
            self.id, RequestMethod.UPSERT, record_id=thing, data=data
        )
        response = await self._send(message, "upsert")
        self.check_response_for_result(response, "upsert")
        return response["result"]

    async def __aenter__(self) -> "AsyncHttpSurrealConnection":
        """
        Asynchronous context manager entry.
        Initializes an aiohttp session and returns the connection instance.
        """
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """
        Asynchronous context manager exit.
        Closes the aiohttp session upon exiting the context.
        """
        if hasattr(self, "_session"):
            await self._session.close()
