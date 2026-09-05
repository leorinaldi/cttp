"""Reporting helpers for a backup tool."""


def report(path: str, size: int) -> str:
    """One line of the backup report: the path and its size in human units."""
    return f"{path}: {human_size(size)}"
