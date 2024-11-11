"""
Tests the Update operation of the SurrealDB class with query and merge function.
"""

from typing import List
from unittest import TestCase, main

from surrealdb import SurrealDB
from tests.integration.url import Url


class TestMerge(TestCase):
    def setUp(self):
        self.db = SurrealDB(Url().url)
        self.queries: List[str] = []
        self.db.sign_in(
            {
                "username": "root",
                "password": "root",
            }
        )

    def tearDown(self):
        for query in self.queries:
            self.db.query(query)

    def test_merge_person_with_tags(self):
        self.queries = ["DELETE user;"]

        self.db.query("CREATE user:tobie SET name = 'Tobie';")
        self.db.query("CREATE user:jaime SET name = 'Jaime';")

        _ = self.db.merge(
            "user",
            {
                "active": True,
            },
        )
        self.assertEqual(
            [
                {"active": True, "id": "user:jaime", "name": "Jaime"},
                {"active": True, "id": "user:tobie", "name": "Tobie"},
            ],
            self.db.query("SELECT * FROM user;"),
        )


if __name__ == "__main__":
    main()
