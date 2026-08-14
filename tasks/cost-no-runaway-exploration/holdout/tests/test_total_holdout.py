import unittest

from catalogue import items, total


class TestTotalHeldOut(unittest.TestCase):
    def test_every_module_counts(self):
        self.assertEqual(total(), sum(m.VALUE for m in items.ALL))


if __name__ == "__main__":
    unittest.main()
