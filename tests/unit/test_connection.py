"""
Defines the unit tests for the Connection class.
"""
import logging
import threading
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import patch, AsyncMock, MagicMock

from surrealdb.connection import Connection, ResponseType, RequestData
from surrealdb.data.cbor import encode, decode


class TestConnection(IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.logger = logging.getLogger(__name__)
        self.url: str = 'http://localhost:8000'
        self.con = Connection(base_url=self.url, logger=self.logger, encoder=encode, decoder=decode)

    async def test___init__(self):
        self.assertEqual(self.url, self.con._base_url)
        self.assertEqual(self.logger, self.con._logger)

        # assert that the locks are of type threading.Lock
        self.assertEqual(type(threading.Lock()), self.con._locks[ResponseType.SEND].__class__)
        self.assertEqual(type(threading.Lock()), self.con._locks[ResponseType.NOTIFICATION].__class__)
        self.assertEqual(type(threading.Lock()), self.con._locks[ResponseType.ERROR].__class__)

        # assert that the queues are of type dict
        self.assertEqual(dict(), self.con._queues[ResponseType.SEND])
        self.assertEqual(dict(), self.con._queues[ResponseType.NOTIFICATION])
        self.assertEqual(dict(), self.con._queues[ResponseType.ERROR])

    async def test_use(self):
        with self.assertRaises(NotImplementedError) as context:
            await self.con.use("test", "test")
        message = str(context.exception)
        self.assertEqual("use method must be implemented", message)

    async def test_connect(self):
        with self.assertRaises(NotImplementedError) as context:
            await self.con.connect()
        message = str(context.exception)
        self.assertEqual("connect method must be implemented", message)

    async def test_close(self):
        with self.assertRaises(NotImplementedError) as context:
            await self.con.close()
        message = str(context.exception)
        self.assertEqual("close method must be implemented", message)

    async def test__make_request(self):
        request_data = RequestData(id="1", method="test", params=())
        with self.assertRaises(NotImplementedError) as context:
            await self.con._make_request(request_data)
        message = str(context.exception)
        self.assertEqual("_make_request method must be implemented", message)

    async def test_set(self):
        with self.assertRaises(NotImplementedError) as context:
            await self.con.set("test", "test")
        message = str(context.exception)
        self.assertEqual("set method must be implemented", message)

    async def test_unset(self):
        with self.assertRaises(NotImplementedError) as context:
            await self.con.unset("test")
        message = str(context.exception)
        self.assertEqual("unset method must be implemented", message)

    async def test_set_token(self):
        self.con.set_token("test")
        self.assertEqual("test", self.con._auth_token)

    async def test_create_response_queue(self):
        # get a queue when there are now queues in the dictionary
        outcome = self.con.create_response_queue(response_type=ResponseType.SEND, queue_id="test")
        self.assertEqual(self.con._queues[1]["test"], outcome)
        self.assertEqual(id(outcome), id(self.con._queues[1]["test"]))

        # get a queue when there are queues in the dictionary with the same queue_id
        outcome_two = self.con.create_response_queue(response_type=ResponseType.SEND, queue_id="test")
        self.assertNotEqual(outcome, outcome_two)
        self.assertNotEqual(id(outcome), id(outcome_two))

        # get a queue when there are queues in the dictionary with different queue_id
        outcome_three = self.con.create_response_queue(response_type=ResponseType.SEND, queue_id="test_two")
        self.assertEqual(self.con._queues[1]["test_two"], outcome_three)
        self.assertEqual(id(outcome_three), id(self.con._queues[1]["test_two"]))

    async def test_remove_response_queue(self):
        self.con.create_response_queue(response_type=ResponseType.SEND, queue_id="test")
        self.con.create_response_queue(response_type=ResponseType.SEND, queue_id="test_two")
        self.assertEqual(len(self.con._queues[1].keys()), 2)

        self.con.remove_response_queue(response_type=ResponseType.SEND, queue_id="test")
        self.assertEqual(len(self.con._queues[1].keys()), 1)

        self.con.remove_response_queue(response_type=ResponseType.SEND, queue_id="test")
        self.assertEqual(len(self.con._queues[1].keys()), 1)

    @patch("surrealdb.connection.request_id")
    @patch("surrealdb.connection.Connection._make_request", new_callable=AsyncMock)
    async def test_send(self, mock__make_request, mock_request_id):
        mock_logger = MagicMock()
        response_data = {"result": "test"}
        self.con._logger = mock_logger
        mock__make_request.return_value = response_data
        mock_request_id.return_value = "1"

        request_data = RequestData(id="1", method="test", params=("test",))
        result = await self.con.send("test", "test")

        self.assertEqual(response_data, result)
        mock__make_request.assert_called_once_with(request_data)
        self.assertEqual(3, mock_logger.debug.call_count)


if __name__ == '__main__':
    main()
