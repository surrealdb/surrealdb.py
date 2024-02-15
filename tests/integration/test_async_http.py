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
            outcome = await connection.query("UPDATE user SET lastname = 'Morgan Hitchcock';")
            self.assertEqual(
                [{'id': 'user:jaime', "lastname": "Morgan Hitchcock", 'name': 'Jaime'}, {'id': 'user:tobie', "lastname": "Morgan Hitchcock", 'name': 'Tobie'}],
                outcome
            )
            outcome = await connection.query("DELETE user;")
            self.assertEqual([], outcome)
            outcome = await connection.query("SELECT * FROM user;")
            self.assertEqual([], outcome)
            outcome = await connection.query(
                """
                CREATE person:`失败` CONTENT
                {
                    "user": "me",
                    "pass": "*æ失败",
                    "really": True,
                    "tags": ["python", "documentation"],
                };
                """
            )
            self.assertEqual(
                [{"id": "person:⟨失败⟩", "pass": "*æ失败", "really": True, "tags": [ "python", "documentation" ], "user": "me" }],
                outcome
            )
            outcome = await connection.update(
                "person:`失败`",
                {
                    "user": "still me",
                    "pass": "*æ失败",
                    "really": False,
                    "tags": ["python", "test"],
                }
            )
            self.assertEqual(
                [{"id": "person:⟨失败⟩", "pass": "*æ失败", "really": False, "tags": [ "python", "test" ], "user": "still me" }],
                outcome
            )
            outcome = await connection.create(
                "person:`更多失败`",
                {
                    "user": "me",
                    "pass": "*æ失败",
                    "really": True,
                    "tags": ["python", "documentation"],
                }
            )
            self.assertEqual(
                [{"id": "person:更多失败", "pass": "*æ失败", "really": True, "tags": [ "python", "documentation" ], "user": "me" }],
                outcome
            )
            outcome = await connection.delete("person")
            self.assertEqual([], outcome)
            outcome = await connection.select("person")
            self.assertEqual([], outcome)
        asyncio.run(async_call())


if __name__ == '__main__':
    main()
