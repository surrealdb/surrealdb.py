"""
Tests the Patch operation of the SurrealDB class.
"""

import datetime
from typing import List
from unittest import TestCase, main

from surrealdb import SurrealDB
from surrealdb.connection_interface import ConnectionController
from tests.integration.url import Url


class TestBlockingPatch(TestCase):
    def setUp(self):
        self.connection = SurrealDB(Url().url, main_connection=True)
        self.queries: List[str] = []

        self.connection.signin(
            {
                "username": "root",
                "password": "root",
            }
        )

    def tearDown(self):
        for query in self.queries:
            self.connection.query(query)

    def test_patch(self):
        self.queries = ["DELETE person;"]
        self.connection.create("person")
        now = str(datetime.datetime.utcnow())
        outcome = self.connection.patch("person", [{
            'op': "replace",
            'path': "/created_at",
            'value': now
        }])
        self.assertEqual(
            now,
            outcome[0]["created_at"]
        )

    def test_complex_patch(self):
        self.queries = ["DELETE person;"]
        self.connection.create("person")
        outcome = self.connection.patch('person:tobie', [
             { 'op': "replace", 'path': "/settings/active", 'value': False },
             { 'op': "add", "path": "/tags", "value": ["developer", "engineer"] },
             { 'op': "remove", "path": "/temp" },
        ])
        self.assertEqual(
            {
                "id": 'person:tobie',
                "settings": {"active": False},
                "tags": ["developer", "engineer"]
            },
            outcome
        )

    def test__context(self):
        self.queries = ["DELETE person;"]
        with self.connection as temp_con:
            temp_con.create("person")
            outcome = self.connection.patch('person:tobie', [
                {'op': "replace", 'path': "/settings/active", 'value': False},
                {'op': "add", "path": "/tags", "value": ["developer", "engineer"]},
                {'op': "remove", "path": "/temp"},
            ])
            self.assertEqual(
                {
                    "id": 'person:tobie',
                    "settings": {"active": False},
                    "tags": ["developer", "engineer"]
                },
                outcome
            )


if __name__ == "__main__":
    main()
