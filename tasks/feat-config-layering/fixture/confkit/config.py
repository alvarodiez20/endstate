"""Config loading."""


def load_config(defaults, file_values=None, environ=None, prefix="APP_"):
    """Return the effective configuration."""
    return dict(defaults)
