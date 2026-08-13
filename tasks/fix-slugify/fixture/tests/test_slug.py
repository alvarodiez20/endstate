import unittest

from textkit import slugify


class TestSlugify(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_collapses_punctuation(self):
        self.assertEqual(slugify("Hello -- there!"), "hello-there")

    def test_strips_edges(self):
        self.assertEqual(slugify("  Wrapped.  "), "wrapped")

    def test_empty(self):
        self.assertEqual(slugify("!!!"), "")


if __name__ == "__main__":
    unittest.main()
