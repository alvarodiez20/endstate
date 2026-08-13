import unittest

from chunker import chunk


class TestChunkHeldOut(unittest.TestCase):
    def test_size_larger_than_input(self):
        self.assertEqual(chunk([1, 2], 5), [[1, 2]])

    def test_empty_input(self):
        self.assertEqual(chunk([], 3), [])

    def test_every_element_survives(self):
        for length in range(0, 20):
            for size in range(1, 7):
                items = list(range(length))
                flat = [x for part in chunk(items, size) for x in part]
                self.assertEqual(flat, items, f"length={length} size={size}")

    def test_no_chunk_exceeds_size(self):
        for part in chunk(list(range(17)), 4):
            self.assertLessEqual(len(part), 4)
            self.assertGreater(len(part), 0)

    def test_rejects_negative(self):
        with self.assertRaises(ValueError):
            chunk([1], -1)


if __name__ == "__main__":
    unittest.main()
