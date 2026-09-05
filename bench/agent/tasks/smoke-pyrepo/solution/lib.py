"""Siblings in a chain, a stdlib import, and a name that does not exist."""

import math


def deep(x: int) -> int:
    """The bottom of the chain."""
    return x * 2


def left(x: int) -> int:
    return x + 1


def right(x: int) -> int:
    return deep(x) - 1


def top(x: int) -> int:
    """Calls two siblings, one of which calls a third."""
    return left(x) + right(x)


def hyp(a: float, b: float) -> float:
    """Uses the standard library only."""
    return math.hypot(a, b)


def broken(x: int) -> int:
    """Calls a name that does not exist anywhere."""
    return missing(x)  # noqa: F821


def ping() -> str:
    return pong()


def pong() -> str:
    return "pong" if False else ping()
