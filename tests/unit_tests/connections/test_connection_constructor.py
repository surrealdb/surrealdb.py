from unittest import TestCase, main

from surrealdb import (
    AsyncHttpSurrealConnection,
    AsyncSurreal,
    AsyncWsSurrealConnection,
    BlockingHttpSurrealConnection,
    BlockingWsSurrealConnection,
    Surreal,
)


class TestUrl(TestCase):
    def setUp(self) -> None:
        self.urls = [
            "http://localhost:5000",
            "https://localhost:5000",
            "http://localhost:5000/",
            "https://localhost:5000/",
            "ws://localhost:5000",
            "wss://localhost:5000",
            "ws://localhost:5000/",
            "wss://localhost:5000/",
        ]
        self.schemes = ["http", "https", "http", "https", "ws", "wss", "ws", "wss"]

    def test_blocking___init__(self):
        outcome = Surreal("ws://localhost:5000")
        self.assertEqual(type(outcome), BlockingWsSurrealConnection)

        outcome = Surreal("http://localhost:5000")
        self.assertEqual(type(outcome), BlockingHttpSurrealConnection)

    def test_async___init__(self):
        outcome = AsyncSurreal("ws://localhost:5000")
        self.assertEqual(type(outcome), AsyncWsSurrealConnection)

        outcome = AsyncSurreal("http://localhost:5000")
        self.assertEqual(type(outcome), AsyncHttpSurrealConnection)


if __name__ == "__main__":
    main()
