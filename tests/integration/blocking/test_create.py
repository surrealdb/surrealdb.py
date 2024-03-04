"""
Handles the integration tests for creating and deleting using the create function and QL, and delete in QL.
"""
import os
from typing import List
from unittest import TestCase, main

from surrealdb import SurrealDB
from tests.integration.url import Url


class TestCreate(TestCase):

    def setUp(self):
        self.connection = SurrealDB(Url().url)
        self.queries: List[str] = []

        def login():
            self.connection.signin({
                "username": "root",
                "password": "root",
            })

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
            [{'id': 'user:jaime', 'name': 'Jaime'}, {'id': 'user:tobie', 'name': 'Tobie'}],
            outcome
        )

    def test_delete_ql(self):
        self.queries = ["DELETE user;"]
        self.test_create_ql()
        outcome = self.connection.query("DELETE user;")
        self.assertEqual([], outcome)

        outcome = self.connection.query("SELECT * FROM user;")
        self.assertEqual([], outcome)

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
            [{"id": "person:⟨失败⟩", "pass": "*æ失败", "really": True, "tags": ["python", "documentation"],
              "user": "me"}],
            outcome
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
            }
        )
        self.assertEqual(
            {"id": "person:⟨失败⟩", "pass": "*æ失败", "really": False, "tags": ["python", "test"],
             "user": "still me"},
            outcome
        )


if __name__ == '__main__':
    main()
