"""Password reset validation."""

import re

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def check_reset(email, new_password):
    """Problems with a password reset submission."""
    problems = []
    if not email:
        problems.append("email is required")
    elif not EMAIL_PATTERN.match(email):
        problems.append("email is not valid")
    if not new_password:
        problems.append("password is required")
    elif len(new_password) < 8:
        problems.append("password is too short")
    elif new_password.isalpha():
        problems.append("password needs a digit or symbol")
    return problems
