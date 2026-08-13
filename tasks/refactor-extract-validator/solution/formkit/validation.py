"""Shared field validation."""

import re

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email):
    """Problems with an email address."""
    if not email:
        return ["email is required"]
    if not EMAIL_PATTERN.match(email):
        return ["email is not valid"]
    return []


def validate_password(password):
    """Problems with a password."""
    if not password:
        return ["password is required"]
    if len(password) < 8:
        return ["password is too short"]
    if password.isalpha():
        return ["password needs a digit or symbol"]
    return []
