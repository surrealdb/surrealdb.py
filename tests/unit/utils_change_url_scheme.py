from unittest import TestCase, main

from surrealdb.utils import change_url_scheme


class TestChangeUrlScheme(TestCase):

    def test_http_to_https(self):
        url = "http://example.com"
        new_scheme = "https"
        expected = "https://example.com"
        self.assertEqual(change_url_scheme(url, new_scheme), expected)

    def test_https_to_http(self):
        url = "https://example.com"
        new_scheme = "http"
        expected = "http://example.com"
        self.assertEqual(change_url_scheme(url, new_scheme), expected)

    def test_with_port(self):
        url = "http://example.com:8080"
        new_scheme = "https"
        expected = "https://example.com:8080"
        self.assertEqual(change_url_scheme(url, new_scheme), expected)

    def test_with_path(self):
        url = "http://example.com/path/to/resource"
        new_scheme = "https"
        expected = "https://example.com/path/to/resource"
        self.assertEqual(change_url_scheme(url, new_scheme), expected)

    def test_with_query(self):
        url = "http://example.com/path?query=1"
        new_scheme = "https"
        expected = "https://example.com/path?query=1"
        self.assertEqual(change_url_scheme(url, new_scheme), expected)

    def test_with_fragment(self):
        url = "http://example.com/path#section"
        new_scheme = "https"
        expected = "https://example.com/path#section"
        self.assertEqual(change_url_scheme(url, new_scheme), expected)


if __name__ == '__main__':
    main()
    
