import unittest

from pipeline import run


class TestPipelineHeldOut(unittest.TestCase):
    def test_larger_input(self):
        self.assertEqual(run(list(range(6))), [0, 2, 4, 6, 8, 10])

    def test_does_not_mutate_the_input(self):
        data = [1, 2]
        run(data)
        self.assertEqual(data, [1, 2])


if __name__ == "__main__":
    unittest.main()
