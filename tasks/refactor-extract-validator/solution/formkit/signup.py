"""Signup validation."""

from formkit.validation import validate_email, validate_password


def check_signup(email, password):
    """Problems with a signup submission."""
    return validate_email(email) + validate_password(password)
