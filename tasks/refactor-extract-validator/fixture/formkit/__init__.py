"""Form handling."""

from formkit.login import check_login
from formkit.reset import check_reset
from formkit.signup import check_signup

__all__ = ["check_login", "check_reset", "check_signup"]
