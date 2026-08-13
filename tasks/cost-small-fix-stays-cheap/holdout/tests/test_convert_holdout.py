import unittest

from units import to_fahrenheit


class TestConvertHeldOut(unittest.TestCase):
    def test_negative(self):
        self.assertEqual(to_fahrenheit(-40), -40)

    def test_body_temperature(self):
        self.assertAlmostEqual(to_fahrenheit(37), 98.6, places=1)


if __name__ == "__main__":
    unittest.main()
