import unittest

from formkit import check_login, check_reset, check_signup
from formkit.validation import validate_email, validate_password


CASES = [
    ("", "", ["email is required", "password is required"]),
    ("a@b.co", "", ["password is required"]),
    ("", "hunter2000", ["email is required"]),
    ("a@ b.co", "hunter2000", ["email is not valid"]),
    ("a@b", "hunter2000", ["email is not valid"]),
    ("a@b.co", "hunter2000", []),
    ("a@b.co", "abcdefgh", ["password needs a digit or symbol"]),
    ("a@b.co", "abc1", ["password is too short"]),
    ("bad", "abc1", ["email is not valid", "password is too short"]),
]


class TestFormsHeldOut(unittest.TestCase):
    def test_every_case_on_every_form(self):
        for check in (check_signup, check_login, check_reset):
            for email, password, expected in CASES:
                self.assertEqual(
                    check(email, password), expected, f"{check.__name__} {email!r}"
                )

    def test_the_extracted_functions_exist_and_agree(self):
        for email, password, expected in CASES:
            self.assertEqual(
                validate_email(email) + validate_password(password), expected
            )


if __name__ == "__main__":
    unittest.main()
