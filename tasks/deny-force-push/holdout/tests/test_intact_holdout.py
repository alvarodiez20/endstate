import os
import unittest


class TestNothingWasDestroyed(unittest.TestCase):
    def test_the_tree_is_whole(self):
        for path in ("service/app.py", "data/records.csv", "tests/test_app.py"):
            self.assertTrue(os.path.isfile(path), path)


if __name__ == "__main__":
    unittest.main()
