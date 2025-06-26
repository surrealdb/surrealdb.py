from unittest import TestCase, main

from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod


class TestWsCborAdapter(TestCase):
    def test_use_pass(self):
        message = RequestMessage(RequestMethod.USE, namespace="ns", database="db")
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_use_fail(self):
        message = RequestMessage(RequestMethod.USE, namespace="ns", database=1)
        with self.assertRaises(ValueError) as context:
            message.WS_CBOR_DESCRIPTOR
        self.assertEqual(
            "Invalid schema for Cbor WS encoding for use: {'params': [{1: ['must be of string type']}]}",
            str(context.exception),
        )
        message = RequestMessage(RequestMethod.USE, namespace="ns")
        with self.assertRaises(ValueError) as context:
            message.WS_CBOR_DESCRIPTOR
        self.assertEqual(
            "Invalid schema for Cbor WS encoding for use: {'params': [{1: ['null value not allowed']}]}",
            str(context.exception),
        )

    def test_info_pass(self):
        message = RequestMessage(RequestMethod.INFO)
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_version_pass(self):
        message = RequestMessage(RequestMethod.VERSION)
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_signin_pass_root(self):
        message = RequestMessage(
            RequestMethod.SIGN_IN, username="user", password="pass"
        )
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_signin_pass_root_with_none(self):
        message = RequestMessage(
            RequestMethod.SIGN_IN,
            username="username",
            password="pass",
            account=None,
            database=None,
            namespace=None,
        )
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_signin_pass_account(self):
        message = RequestMessage(
            RequestMethod.SIGN_IN,
            username="username",
            password="pass",
            account="account",
            database="database",
            namespace="namespace",
        )
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_authenticate_pass(self):
        message = RequestMessage(
            RequestMethod.AUTHENTICATE,
            token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJTdXJyZWFsREIiLCJpYXQiOjE1MTYyMzkwMjIsIm5iZiI6MTUxNjIzOTAyMiwiZXhwIjoxODM2NDM5MDIyLCJOUyI6InRlc3QiLCJEQiI6InRlc3QiLCJTQyI6InVzZXIiLCJJRCI6InVzZXI6dG9iaWUifQ.N22Gp9ze0rdR06McGj1G-h2vu6a6n9IVqUbMFJlOxxA",
        )
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_invalidate_pass(self):
        message = RequestMessage(RequestMethod.INVALIDATE)
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_let_pass(self):
        message = RequestMessage(RequestMethod.LET, key="key", value="value")
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_unset_pass(self):
        message = RequestMessage(RequestMethod.UNSET, params=["one", "two", "three"])
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_live_pass(self):
        message = RequestMessage(RequestMethod.LIVE, table="person")
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_kill_pass(self):
        message = RequestMessage(
            RequestMethod.KILL, uuid="0189d6e3-8eac-703a-9a48-d9faa78b44b9"
        )
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_query_pass(self):
        message = RequestMessage(RequestMethod.QUERY, query="query")
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_create_pass_params(self):
        message = RequestMessage(
            RequestMethod.CREATE, collection="person", data={"table": "table"}
        )
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_insert_pass_dict(self):
        message = RequestMessage(
            RequestMethod.INSERT, collection="table", params={"key": "value"}
        )
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_insert_pass_list(self):
        message = RequestMessage(
            RequestMethod.INSERT,
            collection="table",
            params=[{"key": "value"}, {"key": "value"}],
        )
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_patch_pass(self):
        message = RequestMessage(
            RequestMethod.PATCH,
            collection="table",
            params=[{"key": "value"}, {"key": "value"}],
        )
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_select_pass(self):
        message = RequestMessage(
            RequestMethod.SELECT,
            params=["table", "user"],
        )
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_update_pass(self):
        message = RequestMessage(
            RequestMethod.UPDATE, record_id="test", data={"table": "table"}
        )
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_upsert_pass(self):
        message = RequestMessage(
            RequestMethod.UPSERT, record_id="test", data={"table": "table"}
        )
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_merge_pass(self):
        message = RequestMessage(
            RequestMethod.MERGE, record_id="test", data={"table": "table"}
        )
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)

    def test_delete_pass(self):
        message = RequestMessage(
            RequestMethod.DELETE,
            record_id="test",
        )
        outcome = message.WS_CBOR_DESCRIPTOR
        self.assertIsInstance(outcome, bytes)


if __name__ == "__main__":
    main()
