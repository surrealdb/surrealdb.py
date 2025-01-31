from unittest import TestCase, main

from surrealdb.request_message.descriptors.json_http import HttpMethod
from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod


class TestJsonHttpDescriptor(TestCase):

    def test_signin_pass_root(self):
        message = RequestMessage(
            1,
            RequestMethod.SIGN_IN,
            username="user",
            password="pass"
        )
        json_body, method, endpoint = message.JSON_HTTP_DESCRIPTOR
        self.assertEqual('{"user": "user", "pass": "pass"}', json_body)
        self.assertEqual(HttpMethod.POST, method)
        self.assertEqual("signin", endpoint)

    def test_signin_pass_root_with_none(self):
        message = RequestMessage(
            1,
            RequestMethod.SIGN_IN,
            username="username",
            password="pass",
            account=None,
            database=None,
            namespace=None
        )
        json_body, method, endpoint = message.JSON_HTTP_DESCRIPTOR
        self.assertEqual('{"user": "username", "pass": "pass"}', json_body)
        self.assertEqual(HttpMethod.POST, method)
        self.assertEqual("signin", endpoint)

    def test_signin_pass_account(self):
        message = RequestMessage(
            1,
            RequestMethod.SIGN_IN,
            username="username",
            password="pass",
            account="account",
            database="database",
            namespace="namespace"
        )
        json_body, method, endpoint = message.JSON_HTTP_DESCRIPTOR
        self.assertEqual(
            '{"ns": "namespace", "db": "database", "ac": "account", "user": "username", "pass": "pass"}',
            json_body
        )
        self.assertEqual(HttpMethod.POST, method)
        self.assertEqual("signin", endpoint)


if __name__ == '__main__':
    main()
