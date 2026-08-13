import unittest
from decimal import Decimal

from money import format_cents, round_cents


class TestRounding(unittest.TestCase):
    def test_ordinary_value(self):
        self.assertEqual(round_cents("1.234"), Decimal("1.23"))

    def test_half_rounds_up(self):
        self.assertEqual(round_cents("0.125"), Decimal("0.13"))

    def test_the_classic_float_case(self):
        self.assertEqual(round_cents("2.675"), Decimal("2.68"))

    def test_formatting(self):
        self.assertEqual(format_cents("1.5"), "1.50")


if __name__ == "__main__":
    unittest.main()
