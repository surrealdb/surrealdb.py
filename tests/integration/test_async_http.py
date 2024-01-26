import asyncio
from unittest import TestCase, main

from surrealdb import AsyncSurrealDB


class TestAsyncHttp(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_async_http(self):
        async def async_call():
            connection = AsyncSurrealDB("http://localhost:8000/database/namespace")
            await connection.connect()
            await connection.signin({
                "username": "root",
                "password": "root",
            })
            await connection.query("CREATE user:tobie SET name = 'Tobie';")
            await connection.query("CREATE user:jaime SET name = 'Jaime';")
            outcome = await connection.query("SELECT * FROM user;")
            self.assertEqual(
                [{'id': 'user:jaime', 'name': 'Jaime'}, {'id': 'user:tobie', 'name': 'Tobie'}],
                outcome
            )
            outcome = await connection.query("DELETE user;")
            self.assertEqual([], outcome)
            outcome = await connection.query("SELECT * FROM user;")
            self.assertEqual([], outcome)

        asyncio.run(async_call())


if __name__ == '__main__':
    main()
