import unittest
from decimal import Decimal

from money import round_cents


class TestRoundingHeldOut(unittest.TestCase):
    def test_negative_half_rounds_away_from_zero(self):
        self.assertEqual(round_cents("-0.125"), Decimal("-0.13"))
        self.assertEqual(round_cents("-2.675"), Decimal("-2.68"))

    def test_always_two_places(self):
        for value in ["1", "1.1", "1.005", "0", "-3"]:
            self.assertEqual(-round_cents(value).as_tuple().exponent, 2, value)

    def test_returns_a_decimal(self):
        self.assertIsInstance(round_cents("1.00"), Decimal)

    def test_accepts_floats(self):
        self.assertEqual(round_cents(1.239), Decimal("1.24"))

    def test_below_half_rounds_down(self):
        self.assertEqual(round_cents("0.1249"), Decimal("0.12"))


if __name__ == "__main__":
    unittest.main()
