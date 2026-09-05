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
from cttp.address import AddressError, identity, parse_name, short
from cttp.links import LINK_RE, Link, find_links, format_stamped
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

    def to_json(self) -> dict:
        return {
            "line": self.line,
            "address": self.address,
            "status": self.status,
            "detail": self.detail,
        }


def block_end(lines: list[str], start: int) -> int:
    """The block beneath a link runs to the next link line or EOF, trailing blanks dropped."""
    end = start
    while end < len(lines) and not LINK_RE.match(lines[end]):
        end += 1
    while end > start and lines[end - 1].strip() == "":
        end -= 1
    return end


def expand_text(text: str, registry: Registries) -> tuple[str, list[Report]]:
    lines = text.split("\n")
    out: list[str] = []
    reports: list[Report] = []
    for i, line in enumerate(lines):
        link = next((k for k in find_links([line])), None)
        if link is None or link.stamped:
            out.append(line)
            if link is not None:
                reports.append(Report(i + 1, link.address, "unchanged"))
            continue
        r = resolve(link.address, registry)
        if inner := find_links(r.source.split("\n")):
            raise ExpandError(
                f"{link.address} resolves to a page that links to {len(inner)} other page(s) "
                f"(first: {inner[0].address}); closure expansion arrives in P3-T1"
            )
        stamp = format_stamped(r.name, short(r.rev), short(r.identity_full), r.description)
        out.append(link.indent + stamp)
        out.extend(link.indent + s if s else s for s in r.source.rstrip("\n").split("\n"))
        reports.append(Report(i + 1, link.address, "expanded", r.address))
    return "\n".join(out), reports


def expand_file(path: Path, registry: Registries) -> list[Report]:
    text = path.read_text(encoding="utf-8")
    new, reports = expand_text(text, registry)
    if new != text:
        path.write_text(new, encoding="utf-8")
    return reports


def _check_one(lines: list[str], link: Link, registry: Registries) -> Report:
    n = link.line + 1
    if not link.stamped:
        return Report(n, link.address, "unexpanded")
    block = lines[link.line + 1 : block_end(lines, link.line + 1)]
    if not block:
        return Report(n, link.address, "drift", "nothing beneath the link")
    claimed = link.fields["id"].removeprefix("sha256:")
    actual = identity("\n".join(block) + "\n")
    if not actual.startswith(claimed):
        return Report(n, link.address, "drift", f"code hashes to sha256:{short(actual)}")
    try:
        resolve(link.address, registry)
    except (ResolveError, RegistryError, AddressError, gitcache.GitError) as e:
        return Report(n, link.address, "unresolvable", str(e))
    return Report(n, link.address, "ok")


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
        parse_name(text)
    except AddressError:
        return False
    return not Path(text).exists()
