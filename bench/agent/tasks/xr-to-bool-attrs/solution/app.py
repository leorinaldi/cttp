"""Settings read from the environment."""

import os

# cttp: github.com/python-attrs/attrs@8f767776326f/src/attr/converters.py#to_bool id=sha256:421fe9e3563d  ~"def to_bool(val) — Convert 'boolean' strings (for example, from environment variables) to real booleans."
def to_bool(val):
    """
    Convert "boolean" strings (for example, from environment variables) to real
    booleans.

    Values mapping to `True`:

    - ``True``
    - ``"true"`` / ``"t"``
    - ``"yes"`` / ``"y"``
    - ``"on"``
    - ``"1"``
    - ``1``

    Values mapping to `False`:

    - ``False``
    - ``"false"`` / ``"f"``
    - ``"no"`` / ``"n"``
    - ``"off"``
    - ``"0"``
    - ``0``

    Raises:
        ValueError: For any other value.

    .. versionadded:: 21.3.0
    """
    if isinstance(val, str):
        val = val.lower()

    if val in (True, "true", "t", "yes", "y", "on", "1", 1):
        return True
    if val in (False, "false", "f", "no", "n", "off", "0", 0):
        return False

    msg = f"Cannot convert value to bool: {val!r}"
    raise ValueError(msg)

def debug_enabled() -> bool:
    """`APP_DEBUG` from the environment, off by default."""
    return env_flag("APP_DEBUG", default=False)


def env_flag(name: str, default: bool = False) -> bool:
    """The boolean in environment variable `name` ("yes", "0", "off", …), or `default` if unset."""
    value = os.environ.get(name)
    if value is None:
        return default
    return to_bool(value)
