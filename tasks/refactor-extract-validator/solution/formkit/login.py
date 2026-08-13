"""Login validation."""

from formkit.validation import validate_email, validate_password


def check_login(email, password):
    """Problems with a login submission."""
    return validate_email(email) + validate_password(password)
