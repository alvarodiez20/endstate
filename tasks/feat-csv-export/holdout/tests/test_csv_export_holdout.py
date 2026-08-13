import csv
import io
import unittest

import reportkit
from reportkit import Record, to_csv


class TestToCsvHeldOut(unittest.TestCase):
    def test_exported_from_the_package(self):
        self.assertIn("to_csv", reportkit.__all__)

    def test_quotes_embedded_separators(self):
        out = to_csv([Record('a,b "quoted"', "eu", 3)])
        rows = list(csv.reader(io.StringIO(out)))
        self.assertEqual(rows[1][0], 'a,b "quoted"')

    def test_round_trips_through_the_csv_module(self):
        records = [Record(f"name-{i}", "eu", i) for i in range(5)]
        rows = list(csv.DictReader(io.StringIO(to_csv(records))))
        self.assertEqual([r["name"] for r in rows], [f"name-{i}" for i in range(5)])
        self.assertEqual([r["amount"] for r in rows], [str(i) for i in range(5)])

    def test_order_is_preserved(self):
        records = [Record("z", "eu", 1), Record("a", "eu", 2)]
        rows = list(csv.reader(io.StringIO(to_csv(records))))
        self.assertEqual([r[0] for r in rows[1:]], ["z", "a"])


if __name__ == "__main__":
    unittest.main()
