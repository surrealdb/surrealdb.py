"""
Tests the Update operation of the SurrealDB class with query and merge function.
"""

from typing import List
from unittest import TestCase, main

from surrealdb import SurrealDB
from tests.integration.connection_params import TestConnectionParams


class TestMerge(TestCase):
    def setUp(self):
        self.params = TestConnectionParams()
        self.db = SurrealDB(self.params.url)

        self.queries: List[str] = []

        self.db.connect()
        self.db.use(self.params.namespace, self.params.database)
        self.db.sign_in("root", "root")

    def tearDown(self):
        for query in self.queries:
            self.db.query(query)
        self.db.close()

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

        outcome = self.db.query("SELECT * FROM user;")
        self.assertEqual(
            [
                {"active": True, "id": "user:jaime", "name": "Jaime"},
                {"active": True, "id": "user:tobie", "name": "Tobie"},
            ],
            outcome[0]["result"],
        )


if __name__ == "__main__":
    main()
