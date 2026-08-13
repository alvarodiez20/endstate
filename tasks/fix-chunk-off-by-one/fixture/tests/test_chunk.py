import unittest

from chunker import chunk


class TestChunk(unittest.TestCase):
    def test_exact_multiple(self):
        self.assertEqual(chunk([1, 2, 3, 4], 2), [[1, 2], [3, 4]])

    def test_keeps_the_remainder(self):
        self.assertEqual(chunk([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])

    def test_rejects_zero(self):
        with self.assertRaises(ValueError):
            chunk([1], 0)


if __name__ == "__main__":
    unittest.main()
