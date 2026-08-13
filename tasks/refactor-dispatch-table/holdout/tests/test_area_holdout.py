import unittest

from shapes import area
from shapes.area import register, registered_kinds


class TestAreaHeldOut(unittest.TestCase):
    def test_a_new_shape_needs_no_edit_to_area(self):
        register("hexagon", lambda s: 6 * s["side"])
        self.assertEqual(area({"kind": "hexagon", "side": 2}), 12)

    def test_registering_twice_replaces(self):
        register("blob", lambda s: 1)
        register("blob", lambda s: 2)
        self.assertEqual(area({"kind": "blob"}), 2)

    def test_registered_kinds_is_sorted_and_complete(self):
        kinds = registered_kinds()
        self.assertEqual(kinds, sorted(kinds))
        for expected in ("circle", "rectangle", "square", "trapezoid", "triangle"):
            self.assertIn(expected, kinds)

    def test_error_message_is_unchanged(self):
        with self.assertRaises(ValueError) as caught:
            area({"kind": "nope"})
        self.assertEqual(str(caught.exception), "unknown shape: nope")


if __name__ == "__main__":
    unittest.main()
