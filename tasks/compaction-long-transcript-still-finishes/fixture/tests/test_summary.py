import unittest

from catalogue import describe


class TestDescribe(unittest.TestCase):
    def test_first_and_last_lines(self):
        lines = describe().splitlines()
        self.assertEqual(lines[0], "item-00 = 0")
        self.assertEqual(lines[-1], "item-19 = 19")

    def test_one_line_per_item(self):
        self.assertEqual(len(describe().splitlines()), 20)


if __name__ == "__main__":
    unittest.main()
