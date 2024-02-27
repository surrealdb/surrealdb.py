"""
Tests the Set operation of the AsyncSurrealDB class.
"""
from typing import List
from unittest import TestCase, main

from surrealdb import SurrealDB
from tests.integration.url import Url


class TestSet(TestCase):

    def setUp(self):
        self.connection = SurrealDB(Url().url)
        self.queries: List[str] = []
        self.connection.signin({
            "username": "root",
            "password": "root",
        })

    def tearDown(self):
        for query in self.queries:
            self.connection.query(query)

    def test_set_ql(self):
        self.queries = ["DELETE person;"]
        query = "CREATE person:100 SET name = 'Tobie', company = 'SurrealDB', skills = ['Rust', 'Go', 'JavaScript'];"
        outcome = self.connection.query(query)
        self.assertEqual(
            [
                {
                    'id': 'person:100',
                    'name': 'Tobie',
                    'company': 'SurrealDB',
                    'skills': ['Rust', 'Go', 'JavaScript']
                }
            ],
            outcome
        )

    def test_set(self):
        self.queries = ["DELETE person;"]
        query = "CREATE person:100 SET name = $name;"

        self.connection.set(
            "name",
            {
                "name": "Tobie",
                "last": "Morgan Hitchcock",
            }
        )
        _ = self.connection.query(query)
        outcome = self.connection.query("SELECT * FROM person;")
        self.assertEqual(
            [{'id': 'person:100', 'name': {'last': 'Morgan Hitchcock', 'name': 'Tobie'}}],
            outcome
        )


if __name__ == "__main__":
    main()
