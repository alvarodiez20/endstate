import glob
import unittest

from catalogue.naming import labels


class TestLabelsHeldOut(unittest.TestCase):
    def test_all_sixteen_in_order(self):
        self.assertEqual(labels(), [f"item-{i:02d}" for i in range(16)])

    def test_the_old_name_is_gone_everywhere(self):
        for path in glob.glob("catalogue/item_*.py"):
            with open(path, encoding="utf-8") as handle:
                body = handle.read()
            self.assertNotIn("NAME =", body, path)
            self.assertIn("LABEL =", body, path)


if __name__ == "__main__":
    unittest.main()
