import unittest

from catalogue import items, total


class TestTotalHeldOut(unittest.TestCase):
    def test_every_module_counts(self):
        self.assertEqual(total(), sum(m.VALUE for m in items.ALL))

    def test_nothing_was_hardcoded(self):
        with open("catalogue/registry.py", encoding="utf-8") as handle:
            self.assertNotIn("276", handle.read())


if __name__ == "__main__":
    unittest.main()
