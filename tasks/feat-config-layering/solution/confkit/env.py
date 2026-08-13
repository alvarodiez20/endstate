"""Environment variables as nested configuration."""


def from_env(environ, prefix="APP_"):
    """Turn `APP_DB__PORT=5432` into `{"db": {"port": "5432"}}`."""
    config = {}
    for key, value in environ.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix) :].lower().split("__")
        cursor = config
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
    return config
