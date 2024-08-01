from typing import List
from unittest import TestCase, main

from surrealdb import SurrealDB
from tests.integration.url import Url


class TestNamespace(TestCase):
    def setUp(self):
        self.connection = SurrealDB(Url().url)
        self.queries: List[str] = []

    def tearDown(self):
        self.wipe_db()

    def wipe_db(self):
        for query in self.queries:
            self.connection.query(query)

    def test_namespace(self):
        self.queries = ["DELETE user;"]
        self.connection.use_database('test')
        self.connection.use_namespace('test')

    def test_namespace_in_sequence(self):
        self.queries = ["DELETE user;"]
        self.connection.use_database('test')
        self.connection.use_namespace('test')

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
        self.connection.use_database('database')
        self.connection.use_namespace('namespace')

        outcome = self.connection.query("SELECT * FROM user;")
        self.assertEqual([], outcome)

        self.connection.use_database('test')
        self.connection.use_namespace('test')

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
