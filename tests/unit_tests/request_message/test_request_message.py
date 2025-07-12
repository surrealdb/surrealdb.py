from unittest import TestCase, main
import warnings

from surrealdb.request_message.message import RequestMessage
from surrealdb.request_message.methods import RequestMethod


class TestRequestMessage(TestCase):
    def setUp(self):
        self.method = RequestMethod.USE

    def test_init_new_style(self):
        """Test the new params list style"""
        request_message = RequestMessage(self.method, params=["ns", "db"])

        self.assertEqual(request_message.method, self.method)
        self.assertEqual(request_message.kwargs, {"params": ["ns", "db"]})

    def test_init_old_style_deprecation(self):
        """Test that the old kwargs style emits a deprecation warning"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            request_message = RequestMessage(self.method, one="two", three="four")

            self.assertEqual(request_message.method, self.method)
            self.assertEqual(request_message.kwargs, {"one": "two", "three": "four"})
            
            # Check that deprecation warning was emitted
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))
            self.assertIn("kwargs-based API", str(w[0].message))


if __name__ == "__main__":
    main()
