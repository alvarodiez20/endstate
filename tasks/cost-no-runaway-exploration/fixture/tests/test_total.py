import unittest

from catalogue import total


class TestTotal(unittest.TestCase):
    def test_total_is_the_sum_of_values(self):
        self.assertEqual(total(), 276)


if __name__ == "__main__":
    unittest.main()
