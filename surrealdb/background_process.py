import random
import socket
from subprocess import Popen
import time


class BackgroundProcessController(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(BackgroundProcessController, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class BackgroundProcess(metaclass=BackgroundProcessController):

    def __init__(self) -> None:
        self.port: int = self.find_unused_port()
        self.process = Popen(['python', '-c', self.process_code])
        time.sleep(1)

    def __del__(self) -> None:
        self.process.kill()

    def __aexit__(self, exc_type, exc_val, exc_tb):
        self.process.kill()

    @staticmethod
    def find_unused_port() -> int:
        while True:
            port = random.randint(1024, 65535)  # Choose a random port number

            # Create a socket object
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            try:
                # Attempt to bind the socket to the port
                sock.bind(('localhost', port))
                return port  # Port is available, return it
            except OSError:
                # Port is in use, continue to the next iteration
                pass
            finally:
                sock.close()  # Close the socket

    @property
    def process_code(self) -> str:
        return f"from surrealdb.rust_surrealdb import start_background_thread\nstart_background_thread({self.port})"
