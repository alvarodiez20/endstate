import unittest

from confkit import load_config
from confkit.config import merge
from confkit.env import from_env


class TestConfigHeldOut(unittest.TestCase):
    def test_merge_does_not_mutate_its_inputs(self):
        base = {"a": {"b": 1}}
        overlay = {"a": {"c": 2}}
        merge(base, overlay)
        self.assertEqual(base, {"a": {"b": 1}})
        self.assertEqual(overlay, {"a": {"c": 2}})

    def test_load_config_does_not_mutate_defaults(self):
        defaults = {"a": {"b": 1}}
        load_config(defaults, {"a": {"b": 2}})
        self.assertEqual(defaults, {"a": {"b": 1}})

    def test_deep_nesting(self):
        self.assertEqual(
            from_env({"APP_A__B__C": "x"}), {"a": {"b": {"c": "x"}}}
        )

    def test_prefix_is_respected(self):
        self.assertEqual(from_env({"OTHER_A": "x"}, prefix="OTHER_"), {"a": "x"})
        self.assertEqual(from_env({"OTHER_A": "x"}), {})

    def test_empty_environment(self):
        self.assertEqual(from_env({}), {})

    def test_overlay_scalar_replaces_a_dict(self):
        self.assertEqual(merge({"a": {"b": 1}}, {"a": 2}), {"a": 2})


if __name__ == "__main__":
    unittest.main()
