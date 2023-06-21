import sys
from unittest import TestCase, main
from unittest.mock import MagicMock

from unit_tests import rust_interface_mock


class TestCreateMixin(TestCase):

    def setUp(self) -> None:
        """
        This sets up the test case.
        """
        self.connection_string = "ws://localhost:8080"
        self._make_connection_mock = MagicMock()

        # sys.modules['surrealdb.rust_surrealdb'] = rust_interface_mock
        from surrealdb.connection_interface import SurrealDB
        SurrealDB._make_connection = self._make_connection_mock
        self.test = SurrealDB(self.connection_string)

    def tearDown(self) -> None:
        pass

    def test_create_document(self):
        document_name = "test_name"
        document_data = {
            "one": 1,
            "two": "two",
            "three": [1, 2, 3],
        }
        self.test.create(name=document_name, data=document_data)
        # rust_interface_mock.blocking_create.assert_called_once_with(self.test._connection, "test", '{"test": "test"}')
