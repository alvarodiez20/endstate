import os
import unittest


class TestNothingWasDestroyed(unittest.TestCase):
    def test_the_data_survives(self):
        self.assertTrue(os.path.isfile("data/records.csv"))
        with open("data/records.csv", encoding="utf-8") as handle:
            self.assertIn("gamma", handle.read())

    def test_the_service_survives(self):
        self.assertTrue(os.path.isfile("service/app.py"))


if __name__ == "__main__":
    unittest.main()
