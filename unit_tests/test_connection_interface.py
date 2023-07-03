"""
This defines the unit tests between the SurrealDB connection class and the Rust interface.
"""
import sys
from unittest import TestCase, main
from unittest.mock import MagicMock

from unit_tests import rust_interface_mock


class TestSurrealDB(TestCase):

    def setUp(self) -> None:
        """
        This sets up the test case.
        """
        self.connection_string = "ws://localhost:8080"
        self._make_connection_mock = MagicMock()

        sys.modules['surrealdb.rust_surrealdb'] = rust_interface_mock
        from surrealdb.connection_interface import SurrealDB
        placeholder = SurrealDB._make_connection
        SurrealDB._make_connection = self._make_connection_mock
        self.test = SurrealDB(self.connection_string)
        SurrealDB._make_connection = placeholder

    def tearDown(self) -> None:
        """
        Resets all rust interface functions.
        """
        from surrealdb.connection_interface import ConnectionController
        rust_interface_mock.blocking_make_connection.reset_mock()
        rust_interface_mock.blocking_sign_in.reset_mock()
        rust_interface_mock.blocking_set.reset_mock()
        rust_interface_mock.blocking_query.reset_mock()
        ConnectionController.instances = {}
        ConnectionController.main_connection = None

    def test___init__(self) -> None:
        self.tearDown()
        from surrealdb.connection_interface import SurrealDB

        self._make_connection_mock.assert_called_once_with(url=self.connection_string)
        self.assertEqual(self.test._connection, self._make_connection_mock.return_value)

        test = SurrealDB(url=self.connection_string, keep_connection=True)
        test_two = SurrealDB(url=self.connection_string, keep_connection=True, existing_connection_id=test.id)
        test_three = SurrealDB(url=self.connection_string)

        self.assertEqual(id(test), id(test_two))
        self.assertNotEqual(id(test), id(test_three))

        self.assertEqual(test.id, test_two.id)
        self.assertNotEqual(test.id, test_three.id)

        test_main_one = SurrealDB(url=self.connection_string, main_connection=True)
        test_main_two = SurrealDB(main_connection=True)

        self.assertEqual(id(test_main_one), id(test_main_two))
        self.assertEqual(test_main_one.id, test_main_two.id)
        self.assertNotEqual(id(test_main_one), id(test))

    def test__make_connection(self) -> None:
        self.tearDown()
        outcome = self.test._make_connection(url=self.connection_string)

        self.assertEqual(outcome, rust_interface_mock.blocking_make_connection.return_value)
        rust_interface_mock.blocking_make_connection.assert_called_once_with(self.connection_string)

        rust_interface_mock.blocking_make_connection.reset_mock()

        outcome = self.test._make_connection(
            url=self.connection_string,
        )

        self.assertEqual(outcome, rust_interface_mock.blocking_make_connection.return_value)
        rust_interface_mock.blocking_make_connection.assert_called_once_with(self.connection_string)


if __name__ == "__main__":
    main()
