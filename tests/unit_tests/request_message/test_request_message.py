from unittest import TestCase, main

from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod


class TestRequestMessage(TestCase):
    def setUp(self):
        self.method = RequestMethod.USE

    def test_init(self):
        request_message = RequestMessage(self.method, one="two", three="four")

        self.assertEqual(request_message.method, self.method)
        self.assertEqual(request_message.kwargs, {"one": "two", "three": "four"})


if __name__ == "__main__":
    main()
