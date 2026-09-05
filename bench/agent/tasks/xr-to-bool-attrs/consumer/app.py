"""Settings read from the environment."""

import os


def debug_enabled() -> bool:
    """`APP_DEBUG` from the environment, off by default."""
    return env_flag("APP_DEBUG", default=False)
