from typing import List
from unittest import TestCase, main

from surrealdb import SurrealDB
from tests.integration.url import Url


class TestSignUp(TestCase):

    def setUp(self):
        self.connection = SurrealDB(Url().url)

    def tearDown(self):
        pass

    def test_signup(self):
        self.connection.signup(namespace="test", database="test", data={
            'scope': 'user',
            'email': 'info@surrealdb.com',
            'pass': '123456',
        })


if __name__ == "__main__":
    main()
