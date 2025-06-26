from unittest import TestCase, main

from surrealdb.connections.url import Url


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

    def test___init(self):
        for x in range(len(self.urls)):
            i = self.urls[x]
            url = Url(i)
            self.assertEqual(i, url.raw_url)
            self.assertEqual(self.schemes[x], url.scheme.value)
            self.assertEqual("localhost", url.hostname)
            self.assertEqual(5000, url.port)


if __name__ == "__main__":
    main()
