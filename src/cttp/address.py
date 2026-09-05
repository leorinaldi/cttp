"""The address: grammar (spike: name form only) and identity hashing.

Spec §2. The full grammar — locator and identity forms, the shape hash — arrives in P1-T1/P1-T2.
"""

import hashlib
import re
import textwrap
from dataclasses import dataclass

LABEL = r"[a-z0-9]+(?:-[a-z0-9]+)*"
NAME_RE = re.compile(
    rf"^(?:cttp:)?(?P<name>{LABEL}(?:\.{LABEL})*)"
    r"(?:@(?P<rev>[A-Za-z0-9._/-]+))?"
    r"(?:#(?P<symbol>[A-Za-z_][A-Za-z0-9_.]*))?$"
)
SHORT = 12


class AddressError(ValueError):
    pass


@dataclass(frozen=True)
class Name:
    """The name form of an address: `hello-world`, `hello-world@<rev>`, `hello-world#symbol`."""

    name: str
    rev: str | None = None
    symbol: str | None = None

    def __str__(self) -> str:
        out = self.name
        if self.rev:
            out += f"@{self.rev}"
        if self.symbol:
            out += f"#{self.symbol}"
        return out


def parse_name(text: str) -> Name:
    m = NAME_RE.match(text.strip())
    if not m:
        raise AddressError(f"not a cttp name address: {text!r}")
    return Name(m["name"], m["rev"], m["symbol"])


def normalize(text: str) -> str:
    """Spec §2: dedent to column zero, LF endings, no trailing whitespace, one trailing newline."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = textwrap.dedent(text)
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def identity(text: str) -> str:
    """Full SHA-256 hex of the normalized text."""
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def short(hexdigest: str, n: int = SHORT) -> str:
    return hexdigest[:n]
