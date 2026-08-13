import unittest

from apikit import list_orders, list_users
from apikit.pagination import Page, paginate


class TestPaginateHeldOut(unittest.TestCase):
    def test_empty_input_has_one_page(self):
        page = paginate([], page=1, per_page=10)
        self.assertEqual(page.items, [])
        self.assertEqual(page.total, 0)
        self.assertEqual(page.pages, 1)

    def test_past_the_end(self):
        page = paginate(list(range(5)), page=99, per_page=2)
        self.assertEqual(page.items, [])
        self.assertEqual(page.total, 5)

    def test_pages_cover_everything_exactly_once(self):
        items = list(range(23))
        seen = []
        for number in range(1, paginate(items, per_page=5).pages + 1):
            seen.extend(paginate(items, page=number, per_page=5).items)
        self.assertEqual(seen, items)

    def test_endpoints_return_pages(self):
        self.assertIsInstance(list_users(), Page)
        self.assertIsInstance(list_orders(), Page)

    def test_default_page_size(self):
        self.assertEqual(len(list_users().items), 20)


if __name__ == "__main__":
    unittest.main()
