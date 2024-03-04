"""
This file defines the URL to be used in the integration tests based off of the environment variables.
"""
import os


class Url:
    """
    The URL to be used in the integration tests based off of the environment variables.

    Attributes:
        protocol (str): The protocol to be used in the URL.
        port (int): The port to be used in the URL.
        url (str): The URL to be used in the integration tests.
    """

    def __init__(self) -> None:
        """
        The constructor for the URL class.
        """
        self.url: str = f"{self.protocol}://localhost:{self.port}/database/namespace"

    @property
    def protocol(self) -> str:
        return os.environ.get('CONNECTION_PROTOCOL', 'http')

    @property
    def port(self) -> int:
        return os.environ.get('CONNECTION_PORT', 8000)
