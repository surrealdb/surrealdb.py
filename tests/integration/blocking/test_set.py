"""
Tests the Set operation of the AsyncSurrealDB class.
"""
import asyncio
from typing import List
from unittest import TestCase, main

from surrealdb import SurrealDB
import os


class TestSet(TestCase):

    def setUp(self):
        self.connection = SurrealDB(
            f"{os.environ.get('CONNECTION_PROTOCOL', 'http')}://localhost:8000/database/namespace"
        )
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
        query = "CREATE person:100;"

        _ = self.connection.query(query)
        # _ = self.connection.set(
        #     "person:`100`",
        #     {
        #         "name": "Tobie",
        #         "company": "SurrealDB",
        #         "skills": ["Rust", "Go", "JavaScript"]
        #     }
        # )
        # self.assertEqual(
        #     [
        #         {
        #             'id': 'person:100',
        #             'name': 'Tobie',
        #             'company': 'SurrealDB',
        #             'skills': ['Rust', 'Go', 'JavaScript']
        #         }
        #     ],
        #     outcome
        # )


if __name__ == "__main__":
    main()
