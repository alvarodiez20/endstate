"""Password reset validation."""

from formkit.validation import validate_email, validate_password


def check_reset(email, new_password):
    """Problems with a password reset submission."""
    return validate_email(email) + validate_password(new_password)
