import unittest

from inventory import add_item, total_items


class TestBasket(unittest.TestCase):
    def test_adds_to_a_given_basket(self):
        basket = []
        self.assertEqual(add_item("apple", 2, basket), ["apple", "apple"])
        self.assertEqual(total_items(basket), 2)

    def test_calls_do_not_share_state(self):
        first = add_item("apple")
        second = add_item("pear")
        self.assertEqual(first, ["apple"])
        self.assertEqual(second, ["pear"])


if __name__ == "__main__":
    unittest.main()
