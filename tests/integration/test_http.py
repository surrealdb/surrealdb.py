from unittest import TestCase, main

from surrealdb import SurrealDB


class TestHttp(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_http(self):
        connection = SurrealDB("http://localhost:8000/database/namespace")
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
        outcome = connection.query("DELETE user;")
        self.assertEqual([], outcome)
        outcome = connection.query("SELECT * FROM user;")
        self.assertEqual([], outcome)


if __name__ == '__main__':
    main()
