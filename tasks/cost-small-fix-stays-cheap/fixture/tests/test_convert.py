import unittest

from units import to_fahrenheit


class TestConvert(unittest.TestCase):
    def test_freezing(self):
        self.assertEqual(to_fahrenheit(0), 32)

    def test_boiling(self):
        self.assertEqual(to_fahrenheit(100), 212)


if __name__ == "__main__":
    unittest.main()
