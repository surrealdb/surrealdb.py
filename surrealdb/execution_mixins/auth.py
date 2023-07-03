"""
This file defines the interface between python and the Rust SurrealDB library for logging in.
"""
from typing import Dict, Optional

from surrealdb.rust_surrealdb import blocking_sign_in
from surrealdb.errors import SurrealDbError


class SignInMixin:
    """
    This class is responsible for the interface between python and the Rust SurrealDB library for logging in.
    """
    def signin(self: "SurrealDB", data: Optional[Dict[str, str]] = None) -> None:
        """
        Signs in to the database.

        :param password: the password to sign in with
        :param username: the username to sign in with

        :return: None
        """
        if data is None:
            data = dict()
        data = {key.lower(): value for key, value in data.items()}

        password: str = data.get("password", data.get("pass", data.get("p", "root")))
        username: str = data.get("username", data.get("user", data.get("u", "root")))

        try:
            blocking_sign_in(self._connection, password, username)
        except Exception as e:
            SurrealDbError(e)
