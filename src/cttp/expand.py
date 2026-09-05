"""The materializer: expand, check, run. Spec §7.

One link at a time, no closure: a page that itself links to other pages is refused until P3-T1.
`run` asks before the first run of an address (source, hash, license) unless told `--yes`.
"""

import hashlib
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cttp import gitcache
from cttp.address import AddressError, parse
from cttp.hashing import identity, short
from cttp.links import Link, find_links, format_stamped
from cttp.registry import Registries, RegistryError
from cttp.resolve import Resolved, ResolveError, resolve


class ExpandError(RuntimeError):
    pass


class NotConfirmed(RuntimeError):
    """`run` did not run: the first run of an address was declined or could not be confirmed."""


@dataclass
class Report:
    line: int  # 1-based
    address: str
    status: str  # expanded | unchanged | ok | unexpanded | drift | unresolvable
    detail: str | None = None
    relation: str = "is"

    def to_json(self) -> dict:
        return {
            "line": self.line,
            "relation": self.relation,
            "address": self.address,
            "status": self.status,
            "detail": self.detail,
        }


def describe(r: Resolved) -> tuple[str | None, bool]:
    """The description for a stamp: the entry's, asserted; else one derived from the page."""
    if r.description is not None:
        return r.description, False
    if r.signature is None:
        return None, False
    head = r.signature
    if r.kind == "function":  # the signature reads as code: `def greet(name) -> str`
        head = (
            head.replace("async ", "async def ", 1) if head.startswith("async ") else f"def {head}"
        )
    elif r.kind == "class":
        head = f"class {head}"
    return head + (f" — {r.docstring}" if r.docstring else ""), True


def expand_text(text: str, registry: Registries) -> tuple[str, list[Report]]:
    """Expand every unstamped `is` link. Its source goes beneath the link's stack, followed by a
    blank line when something non-blank follows, so the block is delimited as spec §4 requires."""
    lines = text.split("\n")
    links = {k.line: k for k in find_links(lines)}
    out: list[str] = []
    reports: list[Report] = []
    pending: list[str] = []  # expanded source waiting for the end of the current stack
    for i, line in enumerate(lines):
        link = links.get(i)
        if link is None:
            if pending and line.strip():
                pending.append("")
            out.extend(pending)
            pending = []
            out.append(line)
            continue
        if link.relation != "is" or link.stamped:
            out.append(line)
            reports.append(Report(i + 1, link.address, "unchanged", relation=link.relation))
            continue
        r = resolve(link.address, registry)
        if inner := find_links(r.source.split("\n")):
            raise ExpandError(
                f"{link.address} resolves to a page that links to {len(inner)} other page(s) "
                f"(first: {inner[0].address}); closure expansion arrives in P3-T1"
            )
        description, derived = describe(r)
        stamp = format_stamped(
            r.address, short(r.identity_full), description, derived, link.comment
        )
        out.append(link.indent + stamp)
        pending.extend(link.indent + s if s else s for s in r.source.rstrip("\n").split("\n"))
        reports.append(Report(i + 1, link.address, "expanded", r.address))
    out.extend(pending)
    return "\n".join(out), reports


def expand_file(path: Path, registry: Registries) -> list[Report]:
    text = path.read_text(encoding="utf-8")
    new, reports = expand_text(text, registry)
    if new != text:
        path.write_text(new, encoding="utf-8")
    return reports


def _check_one(lines: list[str], link: Link, registry: Registries) -> Report:
    """An `is` link must be stamped and its block must hash to its id; every link must resolve.
    `from` and `see` links are never checked for identity (spec §4)."""
    n = link.line + 1
    if link.relation == "is":
        if not link.stamped:
            return Report(n, link.address, "unexpanded")
        block = link.block(lines)
        if not block:
            return Report(n, link.address, "drift", "nothing beneath the link")
        claimed = link.fields["id"].removeprefix("sha256:")
        actual = identity("\n".join(block) + "\n")
        if not actual.startswith(claimed):
            return Report(n, link.address, "drift", f"code hashes to sha256:{short(actual)}")
    try:
        resolve(link.address, registry)
    except (ResolveError, RegistryError, AddressError, gitcache.GitError) as e:
        return Report(n, link.address, "unresolvable", str(e), link.relation)
    return Report(n, link.address, "ok", relation=link.relation)


def check_file(path: Path, registry: Registries) -> list[Report]:
    lines = path.read_text(encoding="utf-8").split("\n")
    return [_check_one(lines, link, registry) for link in find_links(lines)]


def _run_dir(key: str) -> Path:
    return gitcache.home() / "run" / key


Confirm = Callable[[Resolved], bool] | None
"""Asked before the first run of a pinned address; `None` means never ask (`--yes`)."""


def _materialize(r: Resolved, registry: Registries, confirm: Confirm) -> Path:
    """The run-cache entry for a pinned address; its presence means the address was confirmed."""
    main = _run_dir(r.address) / "main.py"
    if not main.exists():
        if confirm is not None and not confirm(r):
            raise NotConfirmed(f"{r.address}: not run")
        main.parent.mkdir(parents=True, exist_ok=True)
        main.write_text(f"# cttp: {r.address}\n", encoding="utf-8")
        expand_file(main, registry)
    return main


def run_address(text: str, registry: Registries, confirm: Confirm = None) -> int:
    """Expand an address into the run cache (asking, the first time) and run it with the host."""
    main = _materialize(resolve(text, registry), registry, confirm)
    return subprocess.run([sys.executable, str(main)]).returncode


def run_file(path: Path, registry: Registries, confirm: Confirm = None) -> int:
    """Expand a copy of the file into the run cache and run that, leaving the file untouched.

    Every address the copy expands is confirmed the way `run <address>` confirms it; code already
    expanded in the file is the user's own and runs as is.
    """
    key = "file-" + hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:12]
    copy = _run_dir(key) / path.name
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, copy)
    text = copy.read_text(encoding="utf-8")
    new, reports = expand_text(text, registry)
    for report in reports:
        if report.status == "expanded":
            _materialize(resolve(report.detail, registry), registry, confirm)
    if new != text:
        copy.write_text(new, encoding="utf-8")
    return subprocess.run([sys.executable, str(copy)], cwd=path.resolve().parent).returncode


def is_address(text: str) -> bool:
    try:
        parse(text)
    except AddressError:
        return False
    return not Path(text).exists()
