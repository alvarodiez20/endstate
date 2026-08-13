import unittest

from confkit import load_config
from confkit.config import merge
from confkit.env import from_env


DEFAULTS = {"db": {"host": "localhost", "port": "5432"}, "debug": "0"}


class TestConfig(unittest.TestCase):
    def test_defaults_alone(self):
        self.assertEqual(load_config(DEFAULTS), DEFAULTS)

    def test_file_beats_defaults(self):
        config = load_config(DEFAULTS, {"debug": "1"})
        self.assertEqual(config["debug"], "1")
        self.assertEqual(config["db"]["host"], "localhost")

    def test_env_beats_file(self):
        config = load_config(
            DEFAULTS, {"debug": "1"}, {"APP_DEBUG": "2", "APP_DB__PORT": "6000"}
        )
        self.assertEqual(config["debug"], "2")
        self.assertEqual(config["db"]["port"], "6000")
        self.assertEqual(config["db"]["host"], "localhost")

    def test_from_env(self):
        self.assertEqual(
            from_env({"APP_DB__PORT": "1", "OTHER": "x"}), {"db": {"port": "1"}}
        )

    def test_merge_is_recursive(self):
        self.assertEqual(
            merge({"a": {"b": 1, "c": 2}}, {"a": {"c": 3}}), {"a": {"b": 1, "c": 3}}
        )


if __name__ == "__main__":
    unittest.main()
