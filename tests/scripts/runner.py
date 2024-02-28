"""
Testing script that runs all the tests and handles the Docker containers as well as the tests.
"""
import os
import time
import unittest

import docker

TEST_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")
ROOT_DIR = os.path.join(TEST_DIR, "..")
os.environ["PYTHONPATH"] = ROOT_DIR
DOCKER_CLIENT = docker.from_env()


class DbInstance:
    """
    Handles the Docker container for the SurrealDB.

    Attributes:
        version (str): The version of the SurrealDB to run.
        port (int): The port to run the SurrealDB on.
        container (docker.models.containers.Container): The Docker container instance.
        id (str): The id of the Docker container.
    """
    def __init__(self, version: str) -> None:
        """
        The constructor for the DbInstance class.

        :param version: The version of the SurrealDB to run.
        """
        self.version = f"v{version}"
        self.port = int(f"8{version.replace('.', '')}")
        self.container = None
        self.id = None

    def start(self) -> None:
        """
        Starts the Docker container.

        :return: None
        """
        self.container = DOCKER_CLIENT.containers.run(
            image=f"surrealdb/surrealdb:{self.version}",
            command="start",
            environment={
                "SURREAL_USER": "root",
                "SURREAL_PASS": "root",
                "SURREAL_LOG": "trace",
            },
            ports={'8000/tcp': self.port},
            detach=True
        )
        self.id = self.container.id

    def stop(self) -> None:
        """
        Stops the Docker container.

        :return: None
        """
        self.container.stop()


def run_tests(port: int, protocol: str) -> None:
    os.environ["CONNECTION_PROTOCOL"] = f"{protocol}"
    os.environ["CONNECTION_PORT"] = f"{port}"
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(start_dir=TEST_DIR, pattern='test*.py')
    test_runner = unittest.TextTestRunner(verbosity=2)
    _ = test_runner.run(test_suite)


if __name__ == "__main__":
    for version in ["1.2.1", "1.2.0", "1.0.1", "1.1.1", "1.1.0", "1.0.1"]:
        container = DbInstance(version=version)
        container.start()
        time.sleep(1)
        run_tests(port=container.port, protocol="http")
        run_tests(port=container.port, protocol="ws")

        # container_check = DOCKER_CLIENT.containers.get(container.id)
        container.stop()
        # container_check.stop()
