import unittest

from catalogue import describe
from catalogue import items


class TestDescribeHeldOut(unittest.TestCase):
    def test_every_line_matches_its_module(self):
        expected = "\n".join(f"{m.NAME} = {m.VALUE}" for m in items.ALL)
        self.assertEqual(describe(), expected)


if __name__ == "__main__":
    unittest.main()
