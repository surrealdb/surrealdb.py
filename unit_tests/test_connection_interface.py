"""
This defines the unit tests between the SurrealDB connection class and the Rust interface.
"""
import sys
from unittest import TestCase, main
from unittest.mock import MagicMock

import rust_interface_mock


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
        rust_interface_mock.blocking_make_connection.reset_mock()
        rust_interface_mock.blocking_close_connection.reset_mock()
        rust_interface_mock.blocking_check_connection.reset_mock()

    def test___init__(self) -> None:
        self.tearDown()
        self._make_connection_mock.assert_called_once_with(url=self.connection_string, existing_connection_id=None)
        self.assertEqual(self.test._connection, self._make_connection_mock.return_value)
        self.assertEqual(self.test._keep_connection, False)

    def test___del__(self) -> None:
        self.tearDown()
        close_mock = MagicMock()
        self.test.close = close_mock

        self.test.__del__()
        close_mock.assert_called_once_with()

        close_mock.reset_mock()
        self.test._keep_connection = True
        self.test.__del__()
        close_mock.assert_not_called()

    def test___del__call(self):
        self.tearDown()
        close_mock = MagicMock()
        self.test.close = close_mock
        del(self.test)
        close_mock.assert_called_once_with()
        close_mock.reset_mock()

    def test___atexit__(self) -> None:
        self.tearDown()
        close_mock = MagicMock()
        self.test.close = close_mock

        self.test.__atexit__()
        close_mock.assert_called_once_with()

        close_mock.reset_mock()
        self.test._keep_connection = True
        self.test.__atexit__()
        close_mock.assert_not_called()

    def test__make_connection(self) -> None:
        self.tearDown()
        outcome = self.test._make_connection(url=self.connection_string, existing_connection_id=None)

        self.assertEqual(outcome, rust_interface_mock.blocking_make_connection.return_value)
        rust_interface_mock.blocking_make_connection.assert_called_once_with(self.connection_string)

        rust_interface_mock.blocking_make_connection.reset_mock()
        rust_interface_mock.blocking_check_connection.return_value = True

        outcome = self.test._make_connection(
            url=self.connection_string,
            existing_connection_id=self.connection_string
        )

        self.assertEqual(outcome, self.connection_string)
        rust_interface_mock.blocking_make_connection.assert_not_called()
        rust_interface_mock.blocking_check_connection.assert_called_once_with(self.connection_string)

        rust_interface_mock.blocking_check_connection.reset_mock()
        rust_interface_mock.blocking_check_connection.return_value = False

        with self.assertRaises(ValueError) as context:
            self.test._make_connection(
                url=self.connection_string,
                existing_connection_id=self.connection_string
            )
        self.assertEqual(str(context.exception), "Connection ID is invalid")

    def test_close(self) -> None:
        self.tearDown()
        self.test._connection = self.connection_string
        self.test.close()
        rust_interface_mock.blocking_close_connection.assert_called_once_with(self.connection_string)

    def test_check_connection(self) -> None:
        self.tearDown()
        self.test._connection = self.connection_string
        outcome = self.test.check_connection()

        rust_interface_mock.blocking_check_connection.assert_called_once_with(self.connection_string)
        self.assertEqual(outcome, rust_interface_mock.blocking_check_connection.return_value)


if __name__ == "__main__":
    main()
