import asyncio
import os
import sys
from unittest import IsolatedAsyncioTestCase, main

from surrealdb.connections.async_ws import AsyncWsSurrealConnection


class TestAsyncWsSurrealConnection(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.url = "ws://localhost:8000"
        self.password = "root"
        self.username = "root"
        self.vars_params = {
            "username": self.username,
            "password": self.password,
        }
        self.database_name = "test_db"
        self.namespace = "test_ns"
        self.data = {
            "username": self.username,
            "password": self.password,
        }
        self.connection = AsyncWsSurrealConnection(self.url)
        _ = await self.connection.signin(self.vars_params)
        _ = await self.connection.use(
            namespace=self.namespace, database=self.database_name
        )

    async def test_batch(self):
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        # async batching doesn't work for surrealDB v2.1.0" or lower
        if os.environ.get("SURREALDB_VERSION") == "v2.1.0":
            pass
        elif python_version == "3.9" or python_version == "3.10":
            print(
                "async batching is being bypassed due to python versions 3.9 and 3.10 not supporting async task group"
            )
        else:
            async with asyncio.TaskGroup() as tg:
                tasks = [
                    tg.create_task(
                        self.connection.query(
                            "RETURN sleep(duration::from::millis($d)) or $p**2",
                            dict(d=10 if num % 2 else 0, p=num),
                        )
                    )
                    for num in range(5)
                ]

            outcome = [t.result() for t in tasks]
            self.assertEqual([0, 1, 4, 9, 16], outcome)
        await self.connection.close()


if __name__ == "__main__":
    main()
