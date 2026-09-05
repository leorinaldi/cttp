"""The address: the three forms of spec §2.

```text
name      := label ("." label)* [ "@" (version | rev) ] [ "#" symbol ]   ; resolved by the registry
locator   := host "/" owner "/" repo "@" rev "/" path [ "#" symbol ]
identity  := "sha256:" hex               ; 64 hex digits, or a unique prefix of at least 12
```

`parse()` turns text into one `Address`; `str(address)` is the canonical text (without the
`cttp:` marker, which is the link line's job); `address.format(marker=True)` puts it back.
Hashing lives in `hashing.py`; `normalize`, `identity`, `shape` and `short` are re-exported here.
"""

import re
from dataclasses import dataclass

from cttp.hashing import SHORT, identity, normalize, shape, short

__all__ = [
    "Address",
    "AddressError",
    "MARKER",
    "SHORT",
    "identity",
    "is_sha",
    "normalize",
    "parse",
    "parse_pinned",
    "shape",
    "short",
]

MARKER = "cttp:"
FULL_SHA = 40
FULL_IDENTITY = 64

LABEL_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_REV_RE = re.compile(r"^[A-Za-z0-9._/-]+$")  # a version label, or any git ref
LOCATOR_REV_RE = re.compile(r"^[A-Za-z0-9._-]+$")  # no `/`: it would be read as the path
HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::[0-9]+)?$")
SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")  # owner, repo
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
HEX_RE = re.compile(r"^[0-9a-f]+$")


class AddressError(ValueError):
    pass


def is_sha(text: str | None) -> bool:
    """A commit SHA: 12 to 40 hex digits. Only a SHA makes an address immutable."""
    return bool(text) and SHORT <= len(text) <= FULL_SHA and bool(HEX_RE.match(text.lower()))


@dataclass(frozen=True)
class Address:
    """One address in any of the three forms. Fields not used by a form are None."""

    form: str  # "name" | "locator" | "identity"
    name: str | None = None  # name form: dotted labels
    locator: str | None = None  # locator form: host/owner/repo
    path: str | None = None  # locator form: file path from the repository root
    rev: str | None = None  # name form: version label or ref, optional; locator form: required
    symbol: str | None = None  # dotted path to the definition within the file
    identity: str | None = None  # identity form: lower-case hex, full or a prefix of ≥ 12

    @property
    def is_pinned(self) -> bool:
        """Immutable: an identity, or a rev that is a commit SHA. Tags and branches move."""
        return self.form == "identity" or is_sha(self.rev)

    def format(self, marker: bool = False) -> str:
        """Canonical text; with `marker`, the `cttp:` prefix a person writes."""
        if self.form == "identity":
            out = f"sha256:{self.identity}"
        elif self.form == "locator":
            out = f"{self.locator}@{self.rev}/{self.path}"
        else:
            out = self.name + (f"@{self.rev}" if self.rev else "")
        if self.symbol:
            out += f"#{self.symbol}"
        return MARKER + out if marker else out

    def __str__(self) -> str:
        return self.format()


def parse(text: str) -> Address:
    """Text in any form → Address. `AddressError` names the offending part."""
    raw = text.strip()
    body = raw.removeprefix(MARKER)
    if not body:
        raise AddressError(f"empty address: {text!r}")
    if body.startswith("sha256:"):
        return _parse_identity(body, raw)
    head, _, symbol = body.partition("#")
    symbol = _check_symbol(symbol, raw) if symbol or "#" in body else None
    head = head.replace("\\", "/")  # a locator typed on Windows
    if "/" in head.partition("@")[0]:
        return _parse_locator(head, symbol, raw)
    return _parse_name(head, symbol, raw)


def parse_pinned(text: str) -> Address:
    """An address that must be immutable, as in a stamp: a SHA rev or an identity."""
    a = parse(text)
    if not a.is_pinned:
        raise AddressError(
            f"{a.rev!r} in {text.strip()!r} is a tag, branch or label, not a commit SHA; "
            "a stamp needs a commit SHA of at least 12 hex digits"
        )
    return a


def _parse_identity(body: str, raw: str) -> Address:
    hexpart = body.removeprefix("sha256:")
    lowered = hexpart.lower()
    if not lowered or not HEX_RE.match(lowered):
        raise AddressError(f"identity {hexpart!r} in {raw!r} is not hexadecimal")
    if len(lowered) != FULL_IDENTITY and len(lowered) < SHORT:
        raise AddressError(
            f"identity prefix {hexpart!r} in {raw!r} is {len(lowered)} hex digits; "
            f"at least {SHORT} are needed"
        )
    if len(lowered) > FULL_IDENTITY:
        raise AddressError(
            f"identity {hexpart!r} in {raw!r} is {len(lowered)} hex digits; "
            f"sha256 has {FULL_IDENTITY}"
        )
    return Address(form="identity", identity=lowered)


def _check_symbol(symbol: str, raw: str) -> str:
    if not symbol:
        raise AddressError(f"empty symbol after '#' in {raw!r}")
    for part in symbol.split("."):
        if not IDENT_RE.match(part):
            raise AddressError(f"symbol part {part!r} in {raw!r} is not an identifier")
    return symbol


def _parse_name(head: str, symbol: str | None, raw: str) -> Address:
    name, at, rev = head.partition("@")
    if not name:
        raise AddressError(f"empty name in {raw!r}")
    for label in name.split("."):
        if not LABEL_RE.match(label):
            raise AddressError(
                f"label {label!r} in {raw!r} is not lower-case letters, digits and single hyphens"
            )
    if at and not rev:
        raise AddressError(f"empty version after '@' in {raw!r}")
    if rev and not NAME_REV_RE.match(rev):
        raise AddressError(f"version {rev!r} in {raw!r} has characters outside [A-Za-z0-9._/-]")
    if is_sha(rev):
        rev = rev.lower()
    return Address(form="name", name=name, rev=rev or None, symbol=symbol)


def _parse_locator(head: str, symbol: str | None, raw: str) -> Address:
    locator, at, rest = head.partition("@")
    if not at:
        raise AddressError(
            f"missing rev in {raw!r}: a locator is host/owner/repo@rev/path, with '@rev' after "
            "the repository"
        )
    parts = locator.rstrip("/").split("/")
    if len(parts) != 3 or not all(parts):
        raise AddressError(
            f"{locator!r} in {raw!r} is not host/owner/repo (three segments before '@')"
        )
    host, owner, repo = parts[0].lower(), parts[1], parts[2]
    if not HOST_RE.match(host):
        raise AddressError(f"host {parts[0]!r} in {raw!r} is not a host name")
    for what, seg in (("owner", owner), ("repo", repo)):
        if not SEGMENT_RE.match(seg):
            raise AddressError(f"{what} {seg!r} in {raw!r} has characters outside [A-Za-z0-9._-]")
    rev, slash, path = rest.partition("/")
    if not rev:
        raise AddressError(f"empty rev after '@' in {raw!r}")
    if not LOCATOR_REV_RE.match(rev):
        raise AddressError(
            f"rev {rev!r} in {raw!r} has characters outside [A-Za-z0-9._-] "
            "(a rev in a locator cannot contain '/')"
        )
    path = path.strip("/")
    if not slash or not path:
        raise AddressError(f"missing path in {raw!r}: a locator is host/owner/repo@rev/path")
    for seg in path.split("/"):
        if seg in ("", ".", ".."):
            raise AddressError(f"path {path!r} in {raw!r} has an empty, '.' or '..' segment")
    if is_sha(rev):
        rev = rev.lower()
    return Address(
        form="locator", locator=f"{host}/{owner}/{repo}", path=path, rev=rev, symbol=symbol
    )
