"""The materializer: expand, add, check, update, fold, run, and the vendored fallback. Spec §7.

`expand` writes a link's closure (`closure.py`) beneath it — each dependency above its first use,
each beneath its own stamped link, the stdlib and third-party imports the pages need hoisted to
one place above the whole block — so the file runs top to bottom with cttp uninstalled. `check`
reads it all back: an `is` link must be stamped, its block must hash to its `id=`, and the page
at its address must too; `--fix` turns a drifted `is` into a `from`. `update` follows pinned links
forward and rewrites stamp and code on confirmation; a `from` link only gets shown the upstream
diff. `fold` is the view: blocks collapsed to their link lines. `run` materializes into the run
cache and asks before the first run of an address, showing every page about to run. `--package`
is the fallback for closures too large to read in place: the closure goes into
`cttp_vendor/<module>.py` and an import stands beneath the link.
"""

import difflib
import hashlib
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path

from cttp import gitcache
from cttp.address import AddressError, parse
from cttp.closure import DEFAULT_BUDGET, Budget, Closure, ClosureError, Node, closure, defines
from cttp.hashing import identity, short
from cttp.links import Link, find_links, format_stamped
from cttp.registry import Registries, RegistryError
from cttp.resolve import Latest, Mismatch, Resolved, ResolveError, latest, resolve

VENDOR_DIR = "cttp_vendor"


class ExpandError(RuntimeError):
    pass


class NotConfirmed(RuntimeError):
    """`run` did not run: the first run of an address was declined or could not be confirmed."""


@dataclass
class Report:
    line: int  # 1-based
    address: str
    status: str
    detail: str | None = None
    relation: str = "is"
    extra: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "line": self.line,
            "relation": self.relation,
            "address": self.address,
            "status": self.status,
            "detail": self.detail,
            **self.extra,
        }


# --- expand ----------------------------------------------------------------------------------


@dataclass
class Expansion:
    text: str
    reports: list[Report]
    closures: list[Closure]  # one per link expanded, in file order
    vendored: dict[str, str] = field(default_factory=dict)  # relative path → module text


def expand_text(
    text: str,
    registry: Registries,
    package: bool = False,
    budget: Budget | None = DEFAULT_BUDGET,
) -> Expansion:
    """Expand every unstamped `is` link. Above the link's stack go the imports its closure needs
    and the dependencies, each stamped; beneath the stack goes the page's own text, followed by a
    blank line when something non-blank follows, so every block is delimited as spec §4 requires.
    With `package`, the closure is written to a vendored module instead and an import stands
    beneath the link."""
    lines = text.split("\n")
    by_line = {k.line: k for k in find_links(lines)}
    out: list[str] = []
    reports: list[Report] = []
    closures: list[Closure] = []
    vendored: dict[str, str] = {}
    present: set[str] = set()  # identities already stamped above this point
    i = 0
    while i < len(lines):
        if i not in by_line:
            out.append(lines[i])
            i += 1
            continue
        stack: list[Link] = []
        while i in by_line:
            stack.append(by_line[i])
            i += 1
        if len([k for k in stack if k.relation == "is"]) > 1:
            raise ExpandError(
                f"line {stack[0].line + 1}: two `cttp:` links stack above one block; each needs "
                "its own — separate them with a blank line"
            )
        above: list[str] = []
        stack_out: list[str] = []
        below: list[str] = []
        for link in stack:
            if link.relation != "is" or link.stamped:
                stack_out.append(lines[link.line])
                if link.stamped:
                    present.add(link.fields["id"])
                reports.append(
                    Report(link.line + 1, link.address, "unchanged", relation=link.relation)
                )
                continue
            c = closure(link.address, registry, None if package else budget)
            closures.append(c)
            if package:
                module = _module_name(c.root)
                rel = f"{VENDOR_DIR}/{module}.py"
                vendored[rel] = _vendored_module(c, link.comment)
                stamp = _stamp(link, c.nodes[-1], c.root.address, {"vendor": rel})
                stack_out.append(stamp)
                below += [link.indent + s for s in _vendor_import(module, c.root)]
                reports.append(Report(link.line + 1, link.address, "vendored", rel))
            else:
                more_above, stamp, hoisted, source = _layout(c, link, present, lines, out + above)
                above += more_above
                stack_out.append(stamp)
                stack_out += hoisted
                below += source
                reports.append(Report(link.line + 1, link.address, "expanded", c.root.address))
            present.add(c.root.identity)
            if c.requires:
                reports.append(
                    Report(link.line + 1, link.address, "requires", ", ".join(c.requires))
                )
        out += above + stack_out + below
        if below and i < len(lines) and lines[i].strip():
            out.append("")
    return Expansion("\n".join(out), reports, closures, vendored)


def _layout(
    c: Closure, link: Link, present: set[str], file_lines: list[str], written: list[str]
) -> tuple[list[str], str, list[str], list[str]]:
    """Where a closure's pieces go around `link`: imports and dependency blocks above the stack,
    the root's stamp in it (with the page's own `from`/`see` lines), the root's text beneath."""
    indent = link.indent
    above: list[str] = []
    have = {line.strip() for line in [*file_lines, *written]}
    for stmt in c.imports:
        if stmt not in have:
            above.append(indent + stmt)
            have.add(stmt)
    if above:
        above.append("")
    for node in c.nodes[:-1]:
        if node.page.identity in present:
            continue  # already expanded above in this file
        above.append(indent + _dep_stamp(node, link.comment))
        above += _indented(node.page.source, indent)
        above.append("")
        present.add(node.page.identity)
    root = c.nodes[-1]
    hoisted = [
        indent
        + Link(
            0,
            "",
            k["relation"],
            k["address"],
            dict(k["fields"]),
            k["description"],
            bool(k.get("derived")),
            link.comment,
        ).format()  # fmt: skip
        for k in c.hoisted
    ]
    return above, _stamp(link, root, c.root.address), hoisted, _indented(root.page.source, indent)


def _stamp(link: Link, node: Node, address: str, extra: dict | None = None) -> str:
    """The link line, stamped: the pinned address, `id=` first, then the fields the person wrote,
    then the description — theirs if they wrote one, else the entry's or a derived one."""
    fields = {"id": f"sha256:{short(node.page.identity_full)}"}
    fields.update({k: v for k, v in link.fields.items() if k != "id"})
    fields.update(extra or {})
    if link.description is not None:
        description, derived = link.description, link.description_derived
    else:
        description, derived = node.description, node.derived
    return (
        link.indent
        + Link(0, "", "is", address, fields, description, derived, link.comment).format()
    )


def _dep_stamp(node: Node, comment: str) -> str:
    return format_stamped(
        node.page.address, short(node.page.identity_full), node.description, node.derived, comment
    )


def _indented(source: str, indent: str) -> list[str]:
    return [indent + s if s else s for s in source.rstrip("\n").split("\n")]


def _module_name(r: Resolved) -> str:
    """A module name for a vendored closure: from the name, else the repository and file."""
    base = r.name if r.name else f"{r.target.split('/')[2]}_{Path(r.path).stem}"
    if r.symbol:
        base += "_" + r.symbol
    name = re.sub(r"[^0-9A-Za-z_]+", "_", base).strip("_").lower() or "page"
    return "_" + name if name[0].isdigit() else name


def _vendored_module(c: Closure, comment: str) -> str:
    """The closure as one file: imports, dependencies, then the root beneath its own stamp."""
    fake = Link(0, "", "is", c.root.address, {}, None, False, comment)
    above, stamp, hoisted, source = _layout(c, fake, set(), [], [])
    return "\n".join([*above, stamp, *hoisted, *source, ""])


def _vendor_import(module: str, root: Resolved) -> list[str]:
    names = defines(root)
    if names:
        return [f"from {VENDOR_DIR}.{module} import {', '.join(names)}"]
    return [f"import {VENDOR_DIR}.{module}"]  # a script with nothing to import: run it


def expand_file(
    path: Path, registry: Registries, package: bool = False, write_deps: bool = False
) -> list[Report]:
    text = path.read_text(encoding="utf-8")
    ex = expand_text(text, registry, package)
    for rel, module_text in ex.vendored.items():
        target = path.resolve().parent / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        init = target.parent / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")
        target.write_text(module_text, encoding="utf-8")
    if ex.text != text:
        path.write_text(ex.text, encoding="utf-8")
    requires = sorted({m for c in ex.closures for m in c.requires})
    if requires:
        if write_deps:
            pyproject = find_pyproject(path)
            if pyproject is None:
                raise ExpandError(
                    f"--write-deps: no pyproject.toml above {path}; the closure requires "
                    + ", ".join(requires)
                )
            added = write_dependencies(pyproject, requires)
            ex.reports.append(
                Report(0, str(pyproject), "deps", ", ".join(added) if added else "already listed")
            )
        else:
            ex.reports.append(
                Report(
                    0,
                    "pyproject.toml",
                    "deps",
                    f"not written; pass --write-deps to add {', '.join(requires)}",
                )  # fmt: skip
            )
    return ex.reports


def add_link(
    address: str, path: Path, registry: Registries, at: int | None = None, package: bool = False
) -> list[Report]:
    """`cttp add`: write `# cttp: <address>` into the file — at the end, or before line `at`
    (1-based) — creating the file if needed, then expand it."""
    parse(address)  # a bad address is an error before anything is written
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    link = f"# cttp: {address}"
    if at is None:
        lines.append(link)
    else:
        if at < 1 or at > len(lines) + 1:
            raise ExpandError(f"--at {at}: {path} has {len(lines)} lines")
        lines.insert(at - 1, link)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return expand_file(path, registry, package)


# --- dependencies in pyproject.toml ---------------------------------------------------------


def find_pyproject(path: Path) -> Path | None:
    for d in [path.resolve().parent, *path.resolve().parents]:
        if (d / "pyproject.toml").exists():
            return d / "pyproject.toml"
    return None


def write_dependencies(pyproject: Path, names: Iterable[str]) -> list[str]:
    """Add the packages to `[project] dependencies`, editing the text in place so the rest of the
    file — comments, order, formatting — is untouched; the result is re-parsed to be sure.
    Returns the names added; ones already listed (by distribution name) are left alone."""
    text = pyproject.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    have = {_dist_name(d) for d in data.get("project", {}).get("dependencies", [])}
    add = [n for n in names if _dist_name(n) not in have]
    if not add:
        return []
    entries = "".join(f'  "{n}",\n' for n in add)
    m = re.search(r"^\[project\][^\n]*\n", text, re.M)
    if m is None:
        new = text.rstrip("\n") + f"\n\n[project]\ndependencies = [\n{entries}]\n"
    else:
        table_end = re.search(r"^\[", text[m.end() :], re.M)
        end = m.end() + table_end.start() if table_end else len(text)
        table = text[m.end() : end]
        dm = re.search(r"^dependencies\s*=\s*\[", table, re.M)
        if dm is None:
            new = text[: m.end()] + f"dependencies = [\n{entries}]\n" + text[m.end() :]
        else:
            close = table.index("]", dm.end())
            body = table[dm.end() : close]
            sep = "" if body.strip() == "" or body.rstrip().endswith(",") else ","
            body = body.rstrip() + sep + "\n" + entries
            new = text[: m.end()] + table[: dm.end()] + body + table[close:] + text[end:]
    check = tomllib.loads(new)  # a malformed result is never written
    listed = {_dist_name(d) for d in check["project"]["dependencies"]}
    if not all(_dist_name(n) in listed for n in add):
        raise ExpandError(f"could not add {add} to {pyproject}; edit it by hand")
    pyproject.write_text(new, encoding="utf-8")
    return add


def _dist_name(requirement: str) -> str:
    return re.split(r"[\s\[<>=!~;@]", requirement.strip(), maxsplit=1)[0].lower().replace("_", "-")


# --- check -----------------------------------------------------------------------------------


def _check_one(lines: list[str], link: Link, registry: Registries, path: Path | None) -> Report:
    """An `is` link must be stamped, its block must hash to its id, and the page at its address
    must too (else `mismatch`); every link must resolve. `from` and `see` links are never
    checked for identity (spec §4). A link with `vendor=` is checked through the vendored module."""
    n = link.line + 1
    expect = None
    if link.relation == "is":
        if not link.stamped:
            return Report(n, link.address, "unexpanded")
        expect = link.fields["id"]
        if "vendor" in link.fields:
            return _check_vendored(link, registry, path)
        block = link.block(lines)
        if not block:
            return Report(n, link.address, "drift", "nothing beneath the link")
        claimed = expect.removeprefix("sha256:")
        actual = identity("\n".join(block) + "\n")
        if not actual.startswith(claimed):
            return Report(n, link.address, "drift", f"code hashes to sha256:{short(actual)}")
    try:
        resolve(link.address, registry, expect)
    except Mismatch as e:
        return Report(n, link.address, "mismatch", str(e), link.relation)
    except (ResolveError, RegistryError, AddressError, gitcache.GitError) as e:
        return Report(n, link.address, "unresolvable", str(e), link.relation)
    return Report(n, link.address, "ok", relation=link.relation)


def _check_vendored(link: Link, registry: Registries, path: Path | None) -> Report:
    """The user's link stands for the root of a vendored module: that module must exist, hold a
    stamped link for the same page, with the same identity, and that link must check."""
    n = link.line + 1
    base = path.resolve().parent if path else Path.cwd()
    module = base / link.fields["vendor"]
    if not module.exists():
        return Report(n, link.address, "unresolvable", f"vendored module {module} is missing")
    vlines = module.read_text(encoding="utf-8").split("\n")
    roots = [k for k in find_links(vlines) if k.relation == "is" and _same_page(k, link.address)]
    if not roots:
        return Report(
            n, link.address, "drift", f"{link.fields['vendor']} has no link for {link.address}"
        )
    root = roots[-1]
    if root.fields.get("id") != link.fields["id"]:
        return Report(
            n, link.address, "drift",
            f"{link.fields['vendor']} holds {root.address} {root.fields.get('id')}; the link "
            "says " + link.fields["id"],
        )  # fmt: skip
    inner = _check_one(vlines, root, registry, module)
    detail = f"via {link.fields['vendor']}:{inner.line}"
    if inner.detail:
        detail += f": {inner.detail}"
    return Report(n, link.address, inner.status, detail)


def check_file(path: Path, registry: Registries, fix: bool = False) -> list[Report]:
    """Every link's status; with `fix`, a drifted `is` link becomes a `from` link (spec §4) — the
    address and stamp kept, the code beneath now the user's — and is reported as `fixed`."""
    lines = path.read_text(encoding="utf-8").split("\n")
    reports = [_check_one(lines, link, registry, path) for link in find_links(lines)]
    if fix:
        changed = False
        for r in reports:
            if r.status == "drift" and r.relation == "is":
                lines[r.line - 1] = _to_from(lines[r.line - 1])
                r.status, r.detail, r.relation = "fixed", "drift → cttp-from", "from"
                changed = True
        if changed:
            path.write_text("\n".join(lines), encoding="utf-8")
    return reports


def _to_from(line: str) -> str:
    return re.sub(r"^([ \t]*(?:#|//|--|;+|/\*)[ \t]*)cttp:", r"\1cttp-from:", line, count=1)


def _same_page(link: Link, address: str) -> bool:
    """The same page, rev aside: `greet` matches `greet@3a1f…`, a locator its pinned form."""
    if link.address == address:
        return True
    try:
        a, b = parse(link.address), parse(address)
    except AddressError:
        return False
    return replace(a, rev=None) == replace(b, rev=None)


# --- update ----------------------------------------------------------------------------------


@dataclass
class Update:
    """One link's proposed change, shown before it is applied."""

    line: int  # 1-based
    link: Link
    status: str  # updated | unchanged | upstream | not-found | drift | unexpanded | vendored
    message: str
    to: Resolved | None = None
    rule: str | None = None
    diff: str = ""
    new: Closure | None = None

    def report(self) -> Report:
        return Report(
            self.line, self.link.address, self.status, self.message, self.link.relation,
            {"to": self.to.address if self.to else None, "rule": self.rule, "diff": self.diff},
        )  # fmt: skip


Confirm = Callable[[Update], bool] | None


def select_links(
    lines: list[str], path: Path, addresses: Iterable[str] = (), all_: bool = False
) -> list[Link]:
    """Which links `update` looks at: the named addresses; else all stamped links with `--all`
    or under a project `cttp.toml` saying `track = "latest"`; else links marked `track=latest`."""
    links = [k for k in find_links(lines) if k.relation != "see"]
    addresses = list(addresses)
    if addresses:
        return [k for k in links if any(_same_page(k, a) for a in addresses)]
    if all_ or project_tracks_latest(path):
        return links
    return [k for k in links if k.fields.get("track") == "latest"]


def project_tracks_latest(path: Path) -> bool:
    for d in [path.resolve().parent, *path.resolve().parents]:
        f = d / "cttp.toml"
        if f.exists():
            try:
                return tomllib.loads(f.read_text(encoding="utf-8")).get("track") == "latest"
            except tomllib.TOMLDecodeError:
                return False
    return False


def plan_update(lines: list[str], link: Link, registry: Registries, to: str | None) -> Update:
    """What following this link forward would change, without changing anything."""
    n = link.line + 1
    if not link.stamped:
        return Update(n, link, "unexpanded", "not expanded; run `cttp expand` first")
    if "vendor" in link.fields:
        return Update(
            n, link, "vendored", f"vendored: run `cttp update {link.fields['vendor']}` instead"
        )
    claimed = link.fields["id"].removeprefix("sha256:")
    try:
        found = _forward(link.address, registry, to)
    except (ResolveError, RegistryError, AddressError, gitcache.GitError, ClosureError) as e:
        return Update(n, link, "not-found", str(e))
    if not found.found:
        return Update(n, link, "not-found", found.message, rule=None)
    head = found.to
    if link.relation == "from":
        pinned = found.pinned
        if pinned.identity_full == head.identity_full:
            return Update(
                n, link, "upstream", "no upstream change since the fork", head, found.rule
            )
        diff = _diff(pinned.source, head.source, pinned.address, head.address)
        return Update(
            n, link, "upstream",
            f"upstream changed since the fork ({found.rule}); the code is yours to merge",
            head, found.rule, diff,
        )  # fmt: skip
    block = "\n".join(link.block(lines)) + "\n"
    if not identity(block).startswith(claimed):
        return Update(
            n, link, "drift", "the code beneath was edited; run `cttp check --fix` or restore it"
        )
    if head.identity_full.startswith(claimed):
        return Update(n, link, "unchanged", f"same identity at {head.address}", head, found.rule)
    new = closure(head.address, registry)
    diff = _diff(block, head.source, link.address, head.address)
    return Update(
        n, link, "updated", f"{link.address} → {head.address} ({found.rule})", head,
        found.rule, diff, new,
    )  # fmt: skip


def _forward(address: str, registry: Registries, to: str | None) -> Latest:
    """`--latest`, or the same page at the rev `--to` names."""
    if to is None:
        return latest(address, registry)
    pinned = resolve(address, registry)
    target = resolve(str(replace(parse(address), rev=to)), registry)
    return Latest(
        pinned, target.rev, True, "to", target,
        target.identity_full != pinned.identity_full, f"at {to} as asked",
    )  # fmt: skip


def _diff(old: str, new: str, a: str, b: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True), new.splitlines(keepends=True), a, b, n=2
        )
    )


def apply_update(lines: list[str], up: Update, present: set[str]) -> list[str]:
    """Rewrite one `is` link and its block to the new version: stamp, code, and any dependency
    of the new version not already in the file, above the stack."""
    assert up.new is not None and up.to is not None
    link = up.link
    stack_start = link.line
    while stack_start > 0 and (stack_start - 1) in {k.line for k in find_links(lines)}:
        stack_start -= 1
    above, stamp, hoisted, source = _layout(up.new, link, present, lines, [])
    new_lines = lines[:stack_start] + above + lines[stack_start : link.line] + [stamp] + hoisted
    new_lines += lines[link.line + 1 : link.start] + source
    tail = lines[link.end :]
    if tail and tail[0].strip():
        new_lines.append("")
    return new_lines + tail


def update_file(
    path: Path,
    registry: Registries,
    addresses: Iterable[str] = (),
    all_: bool = False,
    to: str | None = None,
    confirm: Confirm = None,
) -> list[Report]:
    """`cttp update` over one file: plan every selected link, apply the changes that are
    confirmed (`confirm=None` confirms everything), report each."""
    lines = path.read_text(encoding="utf-8").split("\n")
    selected = select_links(lines, path, addresses, all_)
    plans = [plan_update(lines, k, registry, to) for k in selected]
    present = {k.fields["id"] for k in find_links(lines) if k.stamped and k.relation == "is"}
    changed = False
    for up in sorted(plans, key=lambda u: -u.line):  # bottom-up: earlier lines keep their numbers
        if up.status != "updated":
            continue
        if confirm is not None and not confirm(up):
            up.status, up.message = "not-confirmed", f"declined: {up.message}"
            continue
        lines = apply_update(lines, up, present)
        changed = True
    if changed:
        path.write_text("\n".join(lines), encoding="utf-8")
    return [up.report() for up in sorted(plans, key=lambda u: u.line)]


# --- fold ------------------------------------------------------------------------------------


def fold_text(text: str, open_: Iterable[str] = ()) -> tuple[str, list[dict]]:
    """The file with every stamped `is`/`from` block collapsed to its link line (and the blank
    line that separated it); `open_` names links to leave unfolded. Also returns each link with
    its 1-based line range, the shape the MCP `fold` tool returns."""
    lines = text.split("\n")
    links = find_links(lines)
    link_lines = {k.line for k in links}
    drop: set[int] = set()
    entries: list[dict] = []
    for k in links:
        folded = k.stamped and k.relation in ("is", "from") and k.end > k.start
        if folded and not any(_same_page(k, a) for a in open_):
            drop.update(range(k.start, k.end))
            # the blank line that separated the block goes too when the next stack follows it,
            # so a file of links folds to just its link lines; before user code it stays
            after = k.end + 1
            if k.end < len(lines) and lines[k.end].strip() == "" and after in link_lines:
                drop.add(k.end)
        else:
            folded = False
        entries.append(
            {
                "line": k.line + 1,
                "relation": k.relation,
                "address": k.address,
                "description": k.description,
                "start": k.start + 1,
                "end": k.end,  # inclusive, 1-based; end == start - 1 when nothing is beneath
                "lines": k.end - k.start,
                "folded": folded,
            }
        )
    kept = [line for i, line in enumerate(lines) if i not in drop]
    return "\n".join(kept), entries


# --- run -------------------------------------------------------------------------------------


def _run_dir(key: str) -> Path:
    return gitcache.home() / "run" / key


RunConfirm = Callable[[Closure], bool] | None
"""Asked before the first run of a pinned address, with everything that would run; `None` means
never ask (`--yes`)."""


def _materialize(c: Closure, registry: Registries, confirm: RunConfirm) -> Path:
    """The run-cache entry for a pinned address; its presence means the address was confirmed."""
    main = _run_dir(c.address) / "main.py"
    if not main.exists():
        if confirm is not None and not confirm(c):
            raise NotConfirmed(f"{c.address}: not run")
        main.parent.mkdir(parents=True, exist_ok=True)
        main.write_text(f"# cttp: {c.address}\n", encoding="utf-8")
        expand_file(main, registry)
    return main


def run_address(text: str, registry: Registries, confirm: RunConfirm = None) -> int:
    """Expand an address into the run cache (asking, the first time) and run it with the host."""
    main = _materialize(closure(text, registry), registry, confirm)
    return subprocess.run([sys.executable, str(main)]).returncode


def run_file(path: Path, registry: Registries, confirm: RunConfirm = None) -> int:
    """Expand a copy of the file into the run cache and run that, leaving the file untouched.

    Every address the copy expands is confirmed the way `run <address>` confirms it; code already
    expanded in the file is the user's own and runs as is.
    """
    key = "file-" + hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:12]
    copy = _run_dir(key) / path.name
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, copy)
    text = copy.read_text(encoding="utf-8")
    ex = expand_text(text, registry)
    for c in ex.closures:
        _materialize(c, registry, confirm)
    if ex.text != text:
        copy.write_text(ex.text, encoding="utf-8")
    return subprocess.run([sys.executable, str(copy)], cwd=path.resolve().parent).returncode


def is_address(text: str) -> bool:
    try:
        parse(text)
    except AddressError:
        return False
    return not Path(text).exists()
