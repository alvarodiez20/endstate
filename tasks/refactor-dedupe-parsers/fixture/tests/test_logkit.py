import unittest

from logkit import access, error


class TestParsers(unittest.TestCase):
    def test_access(self):
        self.assertEqual(
            access.parse("2024-01-01 | GET | /a | 200"),
            {"timestamp": "2024-01-01", "method": "GET", "path": "/a", "status": "200"},
        )

    def test_error(self):
        self.assertEqual(
            error.parse("2024-01-01 | WARN | disk full"),
            {"timestamp": "2024-01-01", "level": "WARN", "message": "disk full"},
        )

    def test_wrong_field_count(self):
        self.assertIsNone(access.parse("too | few"))
        self.assertIsNone(error.parse("a | b | c | d"))


if __name__ == "__main__":
    unittest.main()
