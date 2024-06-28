"""
Handles the integration tests for creating and deleting using the create function and QL, and delete in QL.
"""

from typing import List
from unittest import TestCase, main

from surrealdb import SurrealDB
from tests.integration.url import Url


class TestCreate(TestCase):
    def setUp(self):
        self.connection = SurrealDB(Url().url)
        self.queries: List[str] = []

        def login():
            self.connection.signin(
                {
                    "username": "root",
                    "password": "root",
                }
            )

        login()

    def tearDown(self):
        for query in self.queries:
            self.connection.query(query)

    def test_create_ql(self):
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

    def test_create_method(self):
        self.queries = ["DELETE person;"]
        self.connection.create("person")
        outcome_one = self.connection.create("person:tobie", {
            'name': 'Tobie',
            'settings': {
                'active': True,
                'marketing': True,
            },
        })
        self.assertEqual(
            outcome_one,
            {
                "id": "person:tobie",
                "name": "Tobie",
                "settings": {"active": True, "marketing": True}
            }
        )
        outcome = self.connection.query("SELECT * FROM person;")
        self.assertEqual(2, len(outcome))
        self.assertEqual(
            outcome[1],
            {
                    'id': 'person:tobie',
                    'name': 'Tobie',
                    'settings': {'active': True, 'marketing': True
                }
            }
        )

    def test_delete_ql(self):
        self.test_create_ql()
        outcome = self.connection.query("DELETE user;")
        self.assertEqual([], outcome)

        outcome = self.connection.query("SELECT * FROM user;")
        self.assertEqual([], outcome)

    def test_delete_method_single(self):
        self.test_create_ql()
        outcome = self.connection.delete("user:tobie")
        self.assertEqual(
            {"id": "user:tobie","name": "Tobie"},
            outcome
        )
        outcome_two = self.connection.query("SELECT * FROM user;")
        self.assertEqual(
            [{"id": "user:jaime", "name": "Jaime"}],
            outcome_two
        )

    def test_method_full_delete(self):
        self.test_create_ql()
        outcome = self.connection.delete("user")
        self.assertEqual(
            [
                {"id": "user:jaime", "name": "Jaime"},
                {"id": "user:tobie", "name": "Tobie"}
            ],
            outcome
        )
        outcome_two = self.connection.query("SELECT * FROM user;")
        self.assertEqual(
            [],
            outcome_two
        )

    def test_create_person_with_tags_ql(self):
        self.queries = ["DELETE person;"]
        outcome = self.connection.query(
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
            outcome,
        )

    def test_create_person_with_tags(self):
        self.queries = ["DELETE person;"]
        outcome = self.connection.create(
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
                "id": "person:⟨失败⟩",
                "pass": "*æ失败",
                "really": False,
                "tags": ["python", "test"],
                "user": "still me",
            },
            outcome,
        )


if __name__ == "__main__":
    main()
