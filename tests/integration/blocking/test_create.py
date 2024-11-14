"""
Handles the integration tests for creating and deleting using the create function and QL, and delete in QL.
"""

from typing import List
from unittest import TestCase, main

from surrealdb import SurrealDB, RecordID
from tests.integration.connection_params import TestConnectionParams


class TestCreate(TestCase):
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

    def test_create_ql(self):
        self.queries = ["DELETE user;"]
        self.db.query("CREATE user:tobie SET name = 'Tobie';")
        self.db.query("CREATE user:jaime SET name = 'Jaime';")
        outcome = self.db.query("SELECT * FROM user;")
        self.assertEqual(
            [
                {"id": RecordID.parse("user:jaime"), "name": "Jaime"},
                {"id": RecordID.parse("user:tobie"), "name": "Tobie"},
            ],
            outcome[0]["result"],
        )

    def test_delete_ql(self):
        self.queries = ["DELETE user;"]
        self.test_create_ql()
        outcome = self.db.query("DELETE user;")
        self.assertEqual([], outcome)

        outcome = self.db.query("SELECT * FROM user;")
        self.assertEqual([], outcome[0]["result"])

    def test_create_person_with_tags_ql(self):
        self.queries = ["DELETE person;"]
        outcome = self.db.query(
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
            [
                {
                    "id": "person:⟨失败⟩",
                    "pass": "*æ失败",
                    "really": True,
                    "tags": ["python", "documentation"],
                    "user": "me",
                }
            ],
            outcome[0]["result"],
        )

    def test_create_person_with_tags(self):
        self.queries = ["DELETE person;"]
        outcome = self.db.create(
            "person:`失败`",
            {
                "user": "still me",
                "pass": "*æ失败",
                "really": False,
                "tags": ["python", "test"],
            },
        )
        self.assertEqual(
            {
                "id": RecordID.parse("person:⟨失败⟩"),
                "pass": "*æ失败",
                "really": False,
                "tags": ["python", "test"],
                "user": "still me",
            },
            outcome,
        )


if __name__ == "__main__":
    main()
