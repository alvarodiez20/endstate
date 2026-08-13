import unittest

from pipeline import run


class TestPipeline(unittest.TestCase):
    def test_runs_every_stage(self):
        self.assertEqual(run([1, 2, 3]), [2, 4, 6])

    def test_empty_input(self):
        self.assertEqual(run([]), [])


if __name__ == "__main__":
    unittest.main()
