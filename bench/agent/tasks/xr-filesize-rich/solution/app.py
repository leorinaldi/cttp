"""Reporting helpers for a backup tool."""

from typing import Iterable
from typing import Optional

# cttp: github.com/Textualize/rich@9d8f9a372cc5/rich/filesize.py#_to_str id=sha256:0c262a546865  ~"def _to_str(size: int, suffixes: Iterable[str], base: int, *, precision: Optional[int]=1, separator: Optional[str]=' ') -> str"
def _to_str(
    size: int,
    suffixes: Iterable[str],
    base: int,
    *,
    precision: Optional[int] = 1,
    separator: Optional[str] = " ",
) -> str:
    if size == 1:
        return "1 byte"
    elif size < base:
        return f"{size:,} bytes"

    for i, suffix in enumerate(suffixes, 2):  # noqa: B007
        unit = base**i
        if size < unit:
            break
    return "{:,.{precision}f}{separator}{}".format(
        (base * size / unit),
        suffix,
        precision=precision,
        separator=separator,
    )

# cttp: github.com/Textualize/rich@9d8f9a372cc5/rich/filesize.py#decimal id=sha256:c7c3ca4c3f7d  ~"def decimal(size: int, *, precision: Optional[int]=1, separator: Optional[str]=' ') -> str — Convert a filesize in to a string (powers of 1000, SI prefixes)."
def decimal(
    size: int,
    *,
    precision: Optional[int] = 1,
    separator: Optional[str] = " ",
) -> str:
    """Convert a filesize in to a string (powers of 1000, SI prefixes).

    In this convention, ``1000 B = 1 kB``.

    This is typically the format used to advertise the storage
    capacity of USB flash drives and the like (*256 MB* meaning
    actually a storage capacity of more than *256 000 000 B*),
    or used by **Mac OS X** since v10.6 to report file sizes.

    Arguments:
        int (size): A file size.
        int (precision): The number of decimal places to include (default = 1).
        str (separator): The string to separate the value from the units (default = " ").

    Returns:
        `str`: A string containing a abbreviated file size and units.

    Example:
        >>> filesize.decimal(30000)
        '30.0 kB'
        >>> filesize.decimal(30000, precision=2, separator="")
        '30.00kB'

    """
    return _to_str(
        size,
        ("kB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"),
        1000,
        precision=precision,
        separator=separator,
    )

def report(path: str, size: int) -> str:
    """One line of the backup report: the path and its size in human units."""
    return f"{path}: {human_size(size)}"


def human_size(size: int, precision: int = 1) -> str:
    """A byte count with decimal (SI) units: `human_size(1500) == "1.5 kB"`."""
    return decimal(size, precision=precision)
