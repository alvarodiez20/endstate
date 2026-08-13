"""Login validation."""

import re

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def check_login(email, password):
    """Problems with a login submission."""
    problems = []
    if not email:
        problems.append("email is required")
    elif not EMAIL_PATTERN.match(email):
        problems.append("email is not valid")
    if not password:
        problems.append("password is required")
    elif len(password) < 8:
        problems.append("password is too short")
    elif password.isalpha():
        problems.append("password needs a digit or symbol")
    return problems
