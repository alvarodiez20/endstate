import math
import unittest

from shapes import area


class TestArea(unittest.TestCase):
    def test_known_shapes(self):
        self.assertEqual(area({"kind": "square", "side": 3}), 9)
        self.assertEqual(area({"kind": "rectangle", "width": 2, "height": 5}), 10)
        self.assertAlmostEqual(area({"kind": "circle", "radius": 1}), math.pi)
        self.assertEqual(area({"kind": "triangle", "base": 4, "height": 3}), 6.0)
        self.assertEqual(
            area({"kind": "trapezoid", "a": 2, "b": 4, "height": 2}), 6.0
        )

    def test_unknown_shape(self):
        with self.assertRaises(ValueError):
            area({"kind": "dodecahedron"})


if __name__ == "__main__":
    unittest.main()
