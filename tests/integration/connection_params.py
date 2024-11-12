"""
This file defines the Parameters to be used in the integration tests based off of the environment variables.
"""

import os


class TestConnectionParams:
    """
    The Parameters to be used in the integration tests based off of the environment variables.

    Attributes:
        protocol (str): The protocol to be used in the URL.
        port (int): The port to be used in the URL.
        url (str): The URL to be used in the integration tests.
    """

    @property
    def protocol(self) -> str:
        return os.environ.get("CONNECTION_PROTOCOL", "http")

    @property
    def port(self) -> int:
        return os.environ.get("CONNECTION_PORT", 8000)

    @property
    def url(self) -> str:
        return f"{self.protocol}://localhost:{self.port}"

    @property
    def database(self) -> str:
        return os.environ.get("CONNECTION_NS", "test")

    @property
    def namespace(self) -> str:
        return os.environ.get("CONNECTION_DB", "test")
