import unittest

from formkit import check_login, check_reset, check_signup


class TestForms(unittest.TestCase):
    def test_all_three_accept_valid_input(self):
        for check in (check_signup, check_login, check_reset):
            self.assertEqual(check("a@b.co", "hunter2000"), [], check.__name__)

    def test_bad_email(self):
        self.assertEqual(check_signup("nope", "hunter2000"), ["email is not valid"])

    def test_short_password(self):
        self.assertEqual(check_login("a@b.co", "short"), ["password is too short"])

    def test_alphabetic_password(self):
        self.assertEqual(
            check_reset("a@b.co", "alphabetical"),
            ["password needs a digit or symbol"],
        )


if __name__ == "__main__":
    unittest.main()
