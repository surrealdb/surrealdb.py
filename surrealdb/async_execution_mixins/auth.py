"""
This file defines the interface between python and the Rust SurrealDB library for logging in.
"""
from typing import Dict, Optional

from surrealdb.rust_surrealdb import blocking_authenticate
from surrealdb.rust_surrealdb import blocking_sign_in
from surrealdb.rust_surrealdb import blocking_sign_up

from surrealdb.errors import SurrealDbError


class AsyncSignInMixin:
    """
    This class is responsible for the interface between python and the Rust SurrealDB library for logging in.
    """
    async def signin(self: "SurrealDB", data: Optional[Dict[str, str]] = None) -> None:
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
        await blocking_sign_in(self._connection, password, username)

    async def signup(self: "SurrealDB", namespace: str, database: str, data: Optional[Dict[str, str]] = None) -> str:
        """
        Signs up to an auth scope within a namespace and database.

        :param namespace: the namespace the auth scope is associated with
        :param database: the database the auth scope is associated with
        :param data: the data to sign up with
        :return: an JWT for that auth scope
        """
        return await blocking_sign_up(self._connection, data, namespace, database)

    async def authenticate(self: "SurrealDB", jwt: str) -> bool:
        """
        Authenticates a JWT.

        :param jwt: the JWT to authenticate
        :return: None
        """
        try:
            return await blocking_authenticate(self._connection, jwt)
        except Exception as e:
            SurrealDbError(e)
