import unittest

from logkit import access, error
from logkit.base import parse_line


class TestParsersHeldOut(unittest.TestCase):
    def test_shared_function_is_general(self):
        self.assertEqual(parse_line("a|b", ("x", "y")), {"x": "a", "y": "b"})
        self.assertIsNone(parse_line("a", ("x", "y")))

    def test_whitespace_is_stripped_everywhere(self):
        parsed = access.parse("  2024-01-01  |  GET  |  /a  |  200  ")
        self.assertEqual(parsed["method"], "GET")
        self.assertEqual(parsed["status"], "200")

    def test_empty_fields_are_kept(self):
        self.assertEqual(error.parse("a | b | ")["message"], "")

    def test_empty_line(self):
        self.assertIsNone(access.parse(""))

    def test_fields_are_still_declared(self):
        self.assertEqual(len(access.FIELDS), 4)
        self.assertEqual(len(error.FIELDS), 3)


if __name__ == "__main__":
    unittest.main()
