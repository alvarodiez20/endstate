import unittest

from apikit import list_orders, list_users
from apikit.pagination import paginate


class TestPaginate(unittest.TestCase):
    def test_first_page(self):
        page = paginate(list(range(10)), page=1, per_page=3)
        self.assertEqual(page.items, [0, 1, 2])
        self.assertEqual(page.total, 10)
        self.assertEqual(page.pages, 4)

    def test_last_partial_page(self):
        page = paginate(list(range(10)), page=4, per_page=3)
        self.assertEqual(page.items, [9])

    def test_rejects_bad_arguments(self):
        with self.assertRaises(ValueError):
            paginate([1], page=0)
        with self.assertRaises(ValueError):
            paginate([1], per_page=0)


class TestEndpoints(unittest.TestCase):
    def test_users_are_paginated(self):
        page = list_users(page=2, per_page=10)
        self.assertEqual(page.total, 25)
        self.assertEqual([u["id"] for u in page.items], list(range(11, 21)))

    def test_orders_are_paginated(self):
        page = list_orders(page=1, per_page=5)
        self.assertEqual(page.total, 42)
        self.assertEqual(len(page.items), 5)


if __name__ == "__main__":
    unittest.main()
