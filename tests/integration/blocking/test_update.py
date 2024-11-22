"""
Tests the Update operation of the AsyncSurrealDB class with query and update function.
"""

from typing import List
from unittest import TestCase, main

from surrealdb import SurrealDB, RecordID
from tests.integration.connection_params import TestConnectionParams


class TestAsyncHttpUpdate(TestCase):
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

    def test_update_ql(self):
        self.queries = ["DELETE user;"]
        self.db.query("CREATE user:tobie SET name = 'Tobie';")
        self.db.query("CREATE user:jaime SET name = 'Jaime';")
        outcome = self.db.query(
            "UPDATE user SET lastname = 'Morgan Hitchcock';"
        )
        self.assertEqual(
            [
                {"id": RecordID.parse("user:jaime"), "lastname": "Morgan Hitchcock", "name": "Jaime"},
                {"id": RecordID.parse("user:tobie"), "lastname": "Morgan Hitchcock", "name": "Tobie"},
            ],
            outcome[0]["result"],
        )

    def test_update_person_with_tags(self):
        self.queries = ["DELETE person;"]
        _ = self.db.query(
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

        outcome = self.db.update(
            RecordID.parse("person:失败"),
            {
                "user": "still me",
                "pass": "*æ失败",
                "really": False,
                "tags": ["python", "test"],
            },
        )

        print("outcome: ", outcome)

        self.assertEqual(
            {
                "id": RecordID.parse("person:失败"),
                "user": "still me",
                "pass": "*æ失败",
                "really": False,
                "tags": ["python", "test"],
            },
            outcome,
        )


if __name__ == "__main__":
    main()
