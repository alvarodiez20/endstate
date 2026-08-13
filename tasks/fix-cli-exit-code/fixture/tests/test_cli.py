import json
import os
import tempfile
import unittest

from checker import main


def write(directory, name, payload):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return path


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.lines = []

    def out(self, line):
        self.lines.append(line)

    def test_valid_file_exits_zero(self):
        path = write(self.tmp, "good.json", {"name": "a", "version": "1"})
        self.assertEqual(main([path], out=self.out), 0)

    def test_invalid_file_exits_one(self):
        path = write(self.tmp, "bad.json", {"name": "a"})
        self.assertEqual(main([path], out=self.out), 1)
        self.assertIn(f"{path}: missing key: version", self.lines)

    def test_missing_file_exits_one(self):
        self.assertEqual(main([os.path.join(self.tmp, "nope.json")], out=self.out), 1)


if __name__ == "__main__":
    unittest.main()
