import unittest

from reportkit import Record, to_csv


class TestToCsv(unittest.TestCase):
    def test_header_and_rows(self):
        records = [Record("a", "eu", 1), Record("b", "us", 2)]
        self.assertEqual(
            to_csv(records),
            "name,region,amount\r\na,eu,1\r\nb,us,2\r\n",
        )

    def test_empty_still_has_a_header(self):
        self.assertEqual(to_csv([]), "name,region,amount\r\n")

    def test_chosen_columns(self):
        self.assertEqual(
            to_csv([Record("a", "eu", 1)], columns=["amount", "name"]),
            "amount,name\r\n1,a\r\n",
        )


if __name__ == "__main__":
    unittest.main()
