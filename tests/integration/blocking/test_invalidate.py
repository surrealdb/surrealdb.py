from unittest import TestCase, main

from surrealdb import SurrealDB
from tests.integration.url import Url


class TestInvalidate(TestCase):

    def setUp(self):
        self.connection = SurrealDB(Url().url)

    def tearDown(self):
        for query in self.queries:
            self.connection.query(query)

    def test_invalidate(self):
        self.queries = ["DELETE user;"]
        self.connection.query("CREATE user:tobie SET name = 'Tobie';")
        self.connection.query("CREATE user:jaime SET name = 'Jaime';")

        outcome = self.connection.query("SELECT * FROM user;")
        self.assertEqual(
            [
                {"id": "user:jaime", "name": "Jaime"},
                {"id": "user:tobie", "name": "Tobie"},
            ],
            outcome,
        )

        self.connection.invalidate()
        outcome = self.connection.query("SELECT * FROM user;")
        self.assertEqual(
            [
                {"id": "user:jaime", "name": "Jaime"},
                {"id": "user:tobie", "name": "Tobie"},
            ],
            outcome,
        )


if __name__ == "__main__":
    main()
