"""
Copyright © SurrealDB Ltd

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import base64
import logging
from typing import Any
from urllib.parse import quote

from aiohttp import ClientSession

from surreal.errors import SurrealException
from surreal.utils import load_json

from . import __version__

_log = logging.getLogger(__name__)


def encode_basic_auth(username: str, password: str):
    username_password = f"{quote(username)}:{quote(password)}"

    return f"Basic {base64.b64encode(username_password.encode()).decode()}"


# NOTE: This implements HTTP state and requests
class HTTPClient:
    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        ns: str,
        db: str,
    ) -> None:
        self.url = f"{url}/sql"
        self._session: ClientSession | None = None

        encoded_auth = encode_basic_auth(username=username, password=password)

        self._base_headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"{encoded_auth}",
            "User-Agent": f"surreal.py ({__version__})",
            "NS": ns,
            "DB": db,
        }

    async def _create_session(self) -> None:
        self._session = ClientSession()

    async def execute(self, query: str) -> list[dict[str, Any]]:
        if self._session is None:
            await self._create_session()

        _log.debug(f"Sending query: {query}")

        r = await self._session.post(self.url, data=query, headers=self._base_headers)

        data: list[dict[str, Any]] = load_json(await r.text())

        _log.debug(f"Got back data: {data}")

        ret: list[dict[str, Any]] = []

        for content in data:
            if content["status"] == "OK":
                ret.append(content["result"])
            elif content["status"] == "ERR":
                raise SurrealException(
                    "One of your queries ran into an exception: ",
                    content.get("detail"),
                    content.get("information"),
                )

        return ret

    async def close(self) -> None:
        await self._session.close()
