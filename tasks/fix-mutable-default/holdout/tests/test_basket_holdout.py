import unittest

from inventory import add_item


class TestBasketHeldOut(unittest.TestCase):
    def test_many_independent_calls(self):
        results = [add_item(f"item-{i}") for i in range(10)]
        for i, basket in enumerate(results):
            self.assertEqual(basket, [f"item-{i}"])

    def test_returns_the_caller_s_list_object(self):
        mine = ["seed"]
        returned = add_item("apple", 1, mine)
        self.assertIs(returned, mine)
        self.assertEqual(mine, ["seed", "apple"])

    def test_zero_quantity_adds_nothing(self):
        self.assertEqual(add_item("apple", 0), [])


if __name__ == "__main__":
    unittest.main()
