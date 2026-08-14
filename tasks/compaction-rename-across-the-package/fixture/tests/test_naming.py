import unittest

from catalogue.naming import labels


class TestLabels(unittest.TestCase):
    def test_every_item_has_a_label(self):
        self.assertEqual(labels()[0], "item-00")
        self.assertEqual(len(labels()), 16)


if __name__ == "__main__":
    unittest.main()
