import re
import unittest

from textkit import slugify


SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class TestSlugifyHeldOut(unittest.TestCase):
    def test_shape_holds_for_many_inputs(self):
        titles = [
            "A",
            "Already-a-slug",
            "Numbers 123 and more",
            "___underscores___",
            "Mixed CASE Title",
            "trailing dash -",
            "- leading dash",
            "lots   of    spaces",
        ]
        for title in titles:
            slug = slugify(title)
            self.assertTrue(SLUG.match(slug), f"{title!r} -> {slug!r}")

    def test_empty_string(self):
        self.assertEqual(slugify(""), "")

    def test_only_separators(self):
        self.assertEqual(slugify("---   ---"), "")

    def test_is_idempotent(self):
        for title in ["Hello World", "a--b", "Trailing!"]:
            once = slugify(title)
            self.assertEqual(slugify(once), once, title)


if __name__ == "__main__":
    unittest.main()
