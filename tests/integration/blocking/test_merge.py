"""
Tests the Update operation of the SurrealDB class with query and merge function.
"""
import os
from typing import List
from unittest import TestCase, main

from surrealdb import SurrealDB
from tests.integration.url import Url


class TestMerge(TestCase):

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

    def test_merge_person_with_tags(self):
        self.queries = ["DELETE user;"]

        self.connection.query("CREATE user:tobie SET name = 'Tobie';")
        self.connection.query("CREATE user:jaime SET name = 'Jaime';")

        _ = self.connection.merge(
            "user",
            {
                "active": True,
            }
        )
        self.assertEqual([
            {'active': True, 'id': 'user:jaime', 'name': 'Jaime'},
            {'active': True, 'id': 'user:tobie', 'name': 'Tobie'}
        ],
            self.connection.query("SELECT * FROM user;")
        )


if __name__ == "__main__":
    main()
