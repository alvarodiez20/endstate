"""Config loading."""

from confkit.env import from_env


def merge(base, overlay):
    """Return `base` with `overlay` applied, merging nested dicts."""
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(defaults, file_values=None, environ=None, prefix="APP_"):
    """Return the effective configuration."""
    config = merge({}, defaults)
    if file_values:
        config = merge(config, file_values)
    if environ:
        config = merge(config, from_env(environ, prefix=prefix))
    return config
