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


class TestCliHeldOut(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.lines = []

    def out(self, line):
        self.lines.append(line)

    def test_no_arguments_is_success(self):
        self.assertEqual(main([], out=self.out), 0)

    def test_one_bad_among_many_fails_the_run(self):
        good = write(self.tmp, "good.json", {"name": "a", "version": "1"})
        bad = write(self.tmp, "bad.json", {"version": "1"})
        self.assertEqual(main([good, bad], out=self.out), 1)

    def test_every_file_is_still_reported(self):
        bad = write(self.tmp, "bad.json", {})
        good = write(self.tmp, "good.json", {"name": "a", "version": "1"})
        main([bad, good], out=self.out)
        self.assertIn(f"{good}: ok", self.lines)
        self.assertIn(f"{bad}: missing key: name", self.lines)

    def test_all_good_still_exits_zero(self):
        paths = [
            write(self.tmp, f"{i}.json", {"name": "a", "version": "1"}) for i in range(3)
        ]
        self.assertEqual(main(paths, out=self.out), 0)


if __name__ == "__main__":
    unittest.main()
