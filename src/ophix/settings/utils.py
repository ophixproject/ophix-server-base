"""
ophix.settings.utils
~~~~~~~~~~~~~~~~~~~~
Environment variable helpers used throughout the settings module.
All helpers are pure functions with no Django dependencies so they
can be imported before Django is fully configured.
"""

import os
from pathlib import Path


# ---------------------------------------------------------------------------
# Boolean
# ---------------------------------------------------------------------------

def get_bool_env(var_name: str, default: bool = False) -> bool:
    """
    Parse an environment variable as a boolean.

    Truthy values  : 1, true, yes, y, enable, enabled, on
    Falsy values   : 0, false, no, n, disable, disabled, off
    Missing / other: returns *default*
    """
    value = os.getenv(var_name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "enable", "enabled", "on")


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------

def get_list_env(var_name: str, default: list | None = None, separator: str = ",") -> list:
    """
    Parse an environment variable as a list by splitting on *separator*.

    Empty strings and whitespace-only tokens are removed.
    Returns *default* (empty list if not supplied) when the variable is unset.

    Example::

        ALLOWED_HOSTS=credserver.local,127.0.0.1
        → ['credserver.local', '127.0.0.1']
    """
    if default is None:
        default = []
    value = os.getenv(var_name)
    if value is None:
        return default
    return [token.strip() for token in value.split(separator) if token.strip()]


# ---------------------------------------------------------------------------
# Integers
# ---------------------------------------------------------------------------

def get_int_env(var_name: str, default: int = 0) -> int:
    """
    Parse an environment variable as an integer.
    Returns *default* when the variable is unset or cannot be parsed.
    """
    value = os.getenv(var_name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return default


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def get_path_env(var_name: str, default: Path | str | None = None) -> Path | None:
    """
    Parse an environment variable as a resolved Path.
    Returns *default* when the variable is unset.
    """
    value = os.getenv(var_name)
    if value is None:
        return Path(default) if default is not None else None
    return Path(value).resolve()
