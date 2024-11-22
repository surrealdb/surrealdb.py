"""
Tests the Set operation of the AsyncSurrealDB class.
"""

from typing import List
from unittest import TestCase, main

from surrealdb import SurrealDB, RecordID
from tests.integration.connection_params import TestConnectionParams


class TestSet(TestCase):
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

    def test_set_ql(self):
        self.queries = ["DELETE person;"]
        query = "CREATE person:100 SET name = 'Tobie', company = 'SurrealDB', skills = ['Rust', 'Go', 'JavaScript'];"
        outcome = self.db.query(query)
        self.assertEqual(
            [
                {
                    "id": RecordID.parse("person:100"),
                    "name": "Tobie",
                    "company": "SurrealDB",
                    "skills": ["Rust", "Go", "JavaScript"],
                }
            ],
            outcome[0]["result"],
        )

    def test_set(self):
        self.queries = ["DELETE person;"]
        query = "CREATE person:100 SET name = $name;"

        self.db.set(
            "name",
            {
                "name": "Tobie",
                "last": "Morgan Hitchcock",
            },
        )
        _ = self.db.query(query)
        outcome = self.db.query("SELECT * FROM person;")
        self.assertEqual(
            [
                {
                    "id": RecordID.parse("person:100"),
                    "name": {"last": "Morgan Hitchcock", "name": "Tobie"},
                }
            ],
            outcome[0]["result"],
        )


if __name__ == "__main__":
    main()
