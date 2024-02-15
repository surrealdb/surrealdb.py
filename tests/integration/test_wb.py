from unittest import TestCase, main

from surrealdb import SurrealDB


class TestWs(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_async_ws(self):
        connection = SurrealDB("ws://localhost:8000/database/namespace")
        connection.signin({
            "username": "root",
            "password": "root",
        })
        connection.query("CREATE user:tobie SET name = 'Tobie';")
        connection.query("CREATE user:jaime SET name = 'Jaime';")
        outcome = connection.query("SELECT * FROM user;")
        self.assertEqual(
            [{'id': 'user:jaime', 'name': 'Jaime'}, {'id': 'user:tobie', 'name': 'Tobie'}],
            outcome
        )
        outcome = connection.query("UPDATE user SET lastname = 'Morgan Hitchcock';")
        self.assertEqual(
            [{'id': 'user:jaime', "lastname": "Morgan Hitchcock", 'name': 'Jaime'}, {'id': 'user:tobie', "lastname": "Morgan Hitchcock", 'name': 'Tobie'}],
            outcome
        )
        outcome = connection.query("DELETE user;")
        self.assertEqual([], outcome)
        outcome = connection.query("SELECT * FROM user;")
        self.assertEqual([], outcome)
        outcome = connection.query(
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
        outcome = connection.update(
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
        outcome = connection.create(
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
        outcome = connection.delete("person")
        self.assertEqual([], outcome)
        outcome = connection.select("person")
        self.assertEqual([], outcome)

if __name__ == '__main__':
    main()
