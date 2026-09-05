"""The registry: names → addresses (spec §8).

An ordered list of registries from the config, first match wins. Each is a **local registry
repository** (`cttp.toml` + `names/*.toml`) or an **HTTP registry** serving the contract
(`GET /<name>@<version>.json`). A registry that does not know a name — or cannot be reached —
is a miss, and the next one is asked; the last miss names them all.
"""

import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import tomli_w

from cttp.config import Config, is_url, load_config


class RegistryError(LookupError):
    pass


@dataclass(frozen=True)
class Entry:
    name: str
    description: str | None
    owner: str | None
    target: str
    default: str = "latest"
    versions: dict[str, str] = field(default_factory=dict)


def split_target(target: str) -> tuple[str, str | None]:
    """`host/owner/repo/path/to/file.py` → (`host/owner/repo`, `path/to/file.py`)."""
    parts = target.split("/", 3)
    if len(parts) < 3:
        raise RegistryError(f"target is not host/owner/repo[/path]: {target!r}")
    return "/".join(parts[:3]), (parts[3] if len(parts) == 4 else None)


def ref_for(entry: Entry, version: str | None = None) -> str:
    """A version label maps to a ref of the target repository; anything else is a ref itself."""
    label = version or entry.default
    return entry.versions.get(label, label)


class LocalRegistry:
    def __init__(self, path: Path):
        self.path = Path(path)
        meta_file = self.path / "cttp.toml"
        if not meta_file.exists():
            raise RegistryError(f"{self.path} is not a registry repository (no cttp.toml)")
        meta = tomllib.loads(meta_file.read_text(encoding="utf-8"))
        self.name: str | None = meta.get("name")

    def describe(self) -> str:
        return str(self.path)

    def names(self) -> list[str]:
        return sorted(p.stem for p in (self.path / "names").glob("*.toml"))

    def lookup(self, name: str) -> Entry:
        f = self.path / "names" / f"{name}.toml"
        if not f.exists():
            raise RegistryError(f"{name!r} is not a name in registry {self.path}")
        d = tomllib.loads(f.read_text(encoding="utf-8"))
        return Entry(
            name=d.get("name", name),
            description=(d.get("description") or "").strip() or None,  # "" is no description
            owner=d.get("owner"),
            target=d["target"],
            default=d.get("default", "latest"),
            versions=dict(d.get("versions", {})),
        )


class MissingRegistry:
    """A configured local path with no registry at it: every lookup is a miss that says so."""

    def __init__(self, path: Path):
        self.path = path

    def describe(self) -> str:
        return f"{self.path} (missing)"

    def names(self) -> list[str]:
        return []

    def lookup(self, name: str) -> Entry:
        raise RegistryError(
            f"no registry at {self.path}; clone one there: "
            f"git clone https://github.com/leorinaldi/cttp-registry {self.path}"
        )


class HttpRegistry:
    """A registry served over the spec §8 contract: the server resolves, the client asks.

    `fetch(name, version)` is `GET <url>/<name>@<version>.json` and returns the server's object
    (the resolver's schema). A 404 or an unreachable server is a miss (`RegistryError`); any other
    failure is an error that stops the search.
    """

    TIMEOUT = 10.0

    def __init__(self, url: str, client: httpx.Client | None = None):
        self.url = url.rstrip("/")
        self.client = client or httpx.Client(timeout=self.TIMEOUT)

    def describe(self) -> str:
        return self.url

    def names(self) -> list[str]:
        return []  # the contract has no listing route (spec §8)

    def lookup(self, name: str) -> Entry:
        raise RegistryError(f"{name!r}: {self.url} answers resolutions, not entries; use fetch()")

    def fetch(self, name: str, version: str | None, symbol: str | None = None) -> dict:
        """A `#symbol` rides the same route, percent-encoded: `/<name>@<ver>%23<symbol>.json`."""
        slug = (f"{name}@{version}" if version else name) + (f"%23{symbol}" if symbol else "")
        try:
            res = self.client.get(f"{self.url}/{slug}.json")
        except httpx.HTTPError as e:
            raise RegistryError(f"{self.url} is not reachable ({e.__class__.__name__})") from e
        if res.status_code == 404:
            detail = res.json().get("detail") if _is_json(res) else res.text
            raise RegistryError(f"{name!r} is not a name in registry {self.url}: {detail}")
        if res.status_code != 200 or not _is_json(res):
            raise RegistryError(
                f"{self.url}/{slug}.json answered {res.status_code}, not a resolution"
            )
        return res.json()


def _is_json(res: httpx.Response) -> bool:
    return res.headers.get("content-type", "").startswith("application/json")


Registry = LocalRegistry | HttpRegistry | MissingRegistry


class Registries:
    """The configured registries, in order. The first that knows a name answers for it."""

    def __init__(self, config: Config, local_only: bool = False):
        """`local_only` is for the server, which must never ask an HTTP registry (itself)."""
        self.config = config
        self.items: list[Registry] = []
        for entry in config.registries:
            if is_url(entry):
                if not local_only:
                    self.items.append(HttpRegistry(entry))
            else:
                p = Path(entry)
                self.items.append(LocalRegistry(p) if p.exists() else MissingRegistry(p))
        if not self.items:
            raise RegistryError(
                f"no usable registry in {config.path or 'the config'}: {config.registries}"
            )

    def describe(self) -> str:
        return ", ".join(r.describe() for r in self.items)

    def names(self) -> list[str]:
        return sorted({n for r in self.items for n in r.names()})

    def lookup(self, name: str) -> tuple[Entry, Registry]:
        """The entry for `name` from the first local registry that has it; HTTP ones are skipped."""
        return self.first(name, lambda r: (r.lookup(name), r), skip=HttpRegistry)

    def first(self, name, ask, skip: type | None = None):
        """Ask each registry in turn with `ask(registry)`; a RegistryError is a miss, try the next.

        When every registry misses, the error names them all and carries each one's reason.
        """
        errors: list[str] = []
        for r in self.items:
            if skip is not None and isinstance(r, skip):
                continue
            try:
                return ask(r)
            except RegistryError as e:
                errors.append(str(e))
        if len(errors) == 1:
            raise RegistryError(errors[0])
        raise RegistryError(
            f"{name!r} is not a name in any registry asked: {self.describe()}"
            + "".join(f"\n  {e}" for e in errors)
        )

    def url_for(self, locator: str) -> str:
        return self.config.url_for(locator)

    def entry_for_target(self, target: str) -> tuple[Entry, Registry] | None:
        """The first local entry whose target is `target`, if any registry names it.

        A locator address needs no registry to resolve; this only recovers the name and
        description a registry may have for it. HTTP registries have no listing and are skipped.
        """
        for r in self.items:
            for name in r.names():
                entry = r.lookup(name)
                if entry.target == target:
                    return entry, r
        return None


def open_registries(registry: str | Path | None = None, local_only: bool = False) -> Registries:
    return Registries(load_config(registry), local_only=local_only)


def create_local_registry(dest: Path, files: Path) -> Path:
    """Make a registry repository at `dest` from the files in `files` (see `git_repo_from`)."""
    return git_repo_from(dest, files, "Registry contents")


def git_repo_from(dest: Path, files: Path, message: str = "Contents") -> Path:
    """Make a git repository at `dest` from the files in `files`, on branch `main`, tagged v1."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for src in Path(files).rglob("*"):
        if src.is_file():
            target = dest / src.relative_to(files)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(src.read_bytes())
    git = ["git", "-c", "user.name=cttp", "-c", "user.email=cttp@localhost"]
    run = lambda *a: subprocess.run([*git, *a], cwd=dest, check=True, capture_output=True)  # noqa: E731
    if not (dest / ".git").exists():
        run("init", "--quiet", "--initial-branch=main")
    run("add", "-A")
    if subprocess.run([*git, "diff", "--cached", "--quiet"], cwd=dest).returncode != 0:
        run("commit", "--quiet", "-m", message)
    if (
        subprocess.run(
            [*git, "rev-parse", "-q", "--verify", "v1"], cwd=dest, capture_output=True
        ).returncode
        != 0
    ):
        run("tag", "v1")
    return dest


# --- names: show, claim, verify (plan P7-T1, P7-T2; spec §8) -----------------------------------

# A name: labels of `[a-z0-9]+(-[a-z0-9]+)*`, namespaced by dots (spec §8).
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)*$")
LABEL_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DECLARATION = "cttp.toml"  # at the target repository's root, on its default branch


def is_name(text: str) -> bool:
    return bool(NAME_RE.match(text))


def owner_of(locator: str) -> str:
    """The account that controls a target: `host/owner` of its locator (spec §8's `owner`)."""
    return "/".join(locator.split("/")[:2])


@dataclass(frozen=True)
class Declaration:
    """What a target repository's `cttp.toml` declares at the head of its default branch."""

    locator: str
    branch: str
    sha: str
    names: tuple[str, ...]  # `name = "x"` and `names = ["y", …]`, in that order
    file: str = DECLARATION


def declaration_at(locator: str, registries: Registries) -> Declaration:
    """Read the target's `cttp.toml` at its default branch; a RegistryError when there is none."""
    from cttp import gitcache

    try:
        repo = gitcache.ensure_repo(locator, registries.url_for(locator))
        branch = gitcache.default_branch(repo)
        sha = gitcache.rev_parse(repo, branch)
    except gitcache.GitError as e:
        raise RegistryError(f"{locator} cannot be read: {e}") from e
    try:
        text = gitcache.show(repo, sha, DECLARATION)
    except gitcache.GitError as e:
        raise RegistryError(
            f"{locator} has no {DECLARATION} at {branch} ({sha[:12]}); a claim needs one at the "
            f"repository's root declaring the name (spec §8)"
        ) from e
    try:
        d = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise RegistryError(f"{locator}: {DECLARATION} at {branch} is not TOML: {e}") from e
    names: list[str] = []
    if isinstance(d.get("name"), str):
        names.append(d["name"])
    if isinstance(d.get("names"), list):
        names += [n for n in d["names"] if isinstance(n, str)]
    return Declaration(locator, branch, sha, tuple(names))


def entry_text(entry: Entry) -> str:
    """`names/<name>.toml` for an entry, in the registry's file format (spec §8)."""
    d: dict = {"name": entry.name}
    if entry.description:
        d["description"] = entry.description
    if entry.owner:
        d["owner"] = entry.owner
    d["target"] = entry.target
    d["default"] = entry.default
    body = tomli_w.dumps(d)
    if entry.versions:
        body += "\n" + tomli_w.dumps({"versions": dict(entry.versions)})
    return body


def entry_json(entry: Entry) -> dict:
    return {
        "name": entry.name,
        "description": entry.description,
        "owner": entry.owner,
        "target": entry.target,
        "default": entry.default,
        "versions": dict(entry.versions),
    }


@dataclass(frozen=True)
class Check:
    check: str  # declaration | owner | target | labels | resolves
    ok: bool
    detail: str

    def to_json(self) -> dict:
        return {"check": self.check, "ok": self.ok, "detail": self.detail}


def check_entry(entry: Entry, registries: Registries, resolve: bool = True) -> list[Check]:
    """The registry's checks on one entry (spec §8, plan P7-T2): the target declares the name
    at its default branch, the entry's owner is the target's account, the target path exists,
    every label is well formed and its ref is a revision of the target, and — with `resolve` —
    the name resolves through the configured registries."""
    from cttp import gitcache

    checks: list[Check] = []
    try:
        locator, path = split_target(entry.target)
    except RegistryError as e:
        return [Check("target", False, str(e))]
    try:
        decl = declaration_at(locator, registries)
    except RegistryError as e:
        checks.append(Check("declaration", False, str(e)))
        return checks
    where = f"{decl.file} at {decl.branch} ({decl.sha[:12]})"
    if entry.name in decl.names:
        checks.append(Check("declaration", True, f"{locator} declares {entry.name!r} in {where}"))
    else:
        declared = ", ".join(repr(n) for n in decl.names) or "no name"
        checks.append(
            Check(
                "declaration",
                False,
                f"{locator} declares {declared} in {where}, not {entry.name!r}; add it to the "
                f"file's `name` (or `names`) and push",
            )
        )
    owner = owner_of(locator)
    if entry.owner == owner:
        checks.append(Check("owner", True, f"{owner}, the target's account"))
    else:
        checks.append(
            Check(
                "owner", False, f"the entry says {entry.owner!r}; the target's account is {owner}"
            )
        )
    repo = gitcache.repos_dir() / locator
    if path is None:
        checks.append(Check("target", True, f"{locator}, the whole repository"))
    elif path in gitcache.ls_tree(repo, decl.sha):
        checks.append(Check("target", True, f"{path} exists at {decl.branch}"))
    else:
        checks.append(Check("target", False, f"{path} is not in {locator} at {decl.branch}"))
    problems: list[str] = []
    notes: list[str] = []
    for label, ref in entry.versions.items():
        if not LABEL_RE.match(label):
            problems.append(f"{label!r} is not a label ([a-z0-9]+(-[a-z0-9]+)*)")
            continue
        try:
            sha = gitcache.rev_parse(repo, ref)
        except gitcache.GitError:
            problems.append(f"{label} = {ref!r} is not a revision of {locator}")
            continue
        notes.append(f"{label} = {ref} ({sha[:12]})")
    try:
        gitcache.rev_parse(repo, ref_for(entry))
    except gitcache.GitError:
        problems.append(f"default {entry.default!r} is neither a label nor a revision")
    labels_ok = not problems
    checks.append(Check("labels", labels_ok, "; ".join(problems or notes) or "no labels"))
    if resolve and all(c.ok for c in checks):
        checks.append(_resolves(entry, registries))
    return checks


def _resolves(entry: Entry, registries: Registries) -> Check:
    from cttp.resolve import ResolveError
    from cttp.resolve import resolve as _resolve

    try:
        r = _resolve(entry.name, registries)
    except (RegistryError, ResolveError) as e:
        return Check("resolves", False, str(e))
    return Check("resolves", True, f"{r.address}  {r.identity}  {r.kind}/{r.language}")


@dataclass(frozen=True)
class Claimed:
    entry: Entry
    action: str  # claimed | updated | transferred
    previous_owner: str | None
    declaration: Declaration
    registry: LocalRegistry
    checks: list[Check]
    text: str
    written_to: Path | None  # the file in the registry's working tree (`--no-pr`)
    branch: str | None  # the branch the claim was pushed on
    pr: str | None  # the pull request's URL

    def to_json(self) -> dict:
        return {
            "name": self.entry.name,
            "action": self.action,
            "owner": self.entry.owner,
            "previous_owner": self.previous_owner,
            "target": self.entry.target,
            "declared_at": {
                "file": self.declaration.file,
                "branch": self.declaration.branch,
                "rev": self.declaration.sha,
            },
            "entry": entry_json(self.entry),
            "checks": [c.to_json() for c in self.checks],
            "path": f"names/{self.entry.name}.toml",
            "text": self.text,
            "written_to": str(self.written_to) if self.written_to else None,
            "branch": self.branch,
            "pr": self.pr,
            "registry": self.registry.describe(),
            "origin": {"owner": "derived", "declaration": "derived", "description": "asserted"},
        }


def claim(
    name: str,
    target: str,
    registries: Registries,
    description: str | None = None,
    default: str | None = None,
    versions: dict[str, str] | None = None,
    transfer: bool = False,
    pr: bool = True,
) -> Claimed:
    """Claim `name` for `target` in the first local registry (spec §8: proof of control).

    The target repository must declare the name in its `cttp.toml` at its default branch; the
    owner is the target's account. A name that exists with another owner is refused unless
    `transfer`. With `pr`, the entry is committed on a `claim/<name>` branch of the registry
    clone, pushed to its origin and opened as a pull request with `gh`; otherwise the file is
    written into the registry's working tree.
    """
    if not is_name(name):
        raise RegistryError(
            f"{name!r} is not a name: labels are [a-z0-9]+(-[a-z0-9]+)*, namespaced by dots"
        )
    locator, path = split_target(target)
    _check_locator(locator, path)
    registry = next((r for r in registries.items if isinstance(r, LocalRegistry)), None)
    if registry is None:
        raise RegistryError(
            f"no local registry repository to write to: {registries.describe()}; "
            "clone one and list it in the config, or pass --registry"
        )
    decl = declaration_at(locator, registries)
    if name not in decl.names:
        declared = ", ".join(repr(n) for n in decl.names) or "no name"
        raise RegistryError(
            f"{locator} declares {declared} in {decl.file} at {decl.branch} ({decl.sha[:12]}), "
            f'not {name!r}; add `name = "{name}"` (or list it under `names`) to {decl.file} and '
            "push to prove control of the target"
        )
    owner = owner_of(locator)
    previous: Entry | None = None
    try:
        previous = registry.lookup(name)
    except RegistryError:
        pass
    action = "claimed"
    if previous is not None:
        if previous.owner == owner:
            action = "updated"
        elif transfer:
            action = "transferred"
        else:
            raise RegistryError(
                f"{name!r} is owned by {previous.owner or 'nobody named'} (target "
                f"{previous.target}); pass --transfer to open the pull request for their approval"
            )
    versions = dict(versions or {})
    if not versions:
        versions = {"latest": decl.branch}
    if default is None:
        default = "latest" if "latest" in versions else next(iter(versions))
    entry = Entry(name, description or None, owner, target, default, versions)
    checks = check_entry(entry, registries, resolve=False)
    failed = [c for c in checks if not c.ok]
    if failed:
        raise RegistryError("; ".join(f"{c.check}: {c.detail}" for c in failed))
    text = entry_text(entry)
    rel = Path("names") / f"{name}.toml"
    if not pr:
        out = registry.path / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        return Claimed(entry, action, previous.owner if previous else None, decl, registry,
                       checks, text, out, None, None)  # fmt: skip
    branch, url = open_claim_pr(registry.path, rel, text, entry, action, previous)
    return Claimed(entry, action, previous.owner if previous else None, decl, registry, checks,
                   text, None, branch, url)  # fmt: skip


def _check_locator(locator: str, path: str | None) -> None:
    from cttp.address import AddressError, parse

    try:  # the locator grammar, with a placeholder path for a whole-repository target
        parse(f"{locator}@main/{path or 'cttp.toml'}")
    except AddressError as e:
        raise RegistryError(f"target {locator}{'/' + path if path else ''}: {e}") from e


def _git(*args: str, cwd: Path) -> str:
    """git in the registry clone; a failure is a RegistryError naming the command."""
    git = ["git", "-c", "user.name=cttp", "-c", "user.email=cttp@localhost"]
    proc = subprocess.run([*git, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RegistryError(f"git {' '.join(args)} failed in {cwd}: {proc.stderr.strip()}")
    return proc.stdout


def _gh(args: list[str], cwd: Path) -> str:
    """`gh …` in the clone; tests patch this. A missing `gh` or a failure is a RegistryError."""
    try:
        proc = subprocess.run(
            ["gh", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8"
        )
    except FileNotFoundError as e:
        raise RegistryError(
            "`gh` is not on PATH; install the GitHub CLI, or pass --no-pr and open the pull "
            "request by hand"
        ) from e
    if proc.returncode != 0:
        raise RegistryError(f"gh {' '.join(args)} failed: {(proc.stderr or proc.stdout).strip()}")
    return proc.stdout


def open_claim_pr(
    clone: Path, rel: Path, text: str, entry: Entry, action: str, previous: Entry | None
) -> tuple[str, str]:
    """Commit `rel` with `text` on a fresh `claim/<name>` branch of the registry clone — in a
    temporary worktree, so the person's checkout is untouched — push it to `origin`, open the
    pull request with `gh`, and remove the worktree and branch. Returns (branch, PR URL)."""
    import shutil
    import tempfile

    try:
        _git("remote", "get-url", "origin", cwd=clone)
    except RegistryError as e:
        raise RegistryError(
            f"the registry clone at {clone} has no `origin` remote to push the claim to; "
            "pass --no-pr to write the file and commit it by hand"
        ) from e
    _git("fetch", "--quiet", "origin", cwd=clone)
    head = _git("ls-remote", "--symref", "origin", "HEAD", cwd=clone)
    base = next(
        (line.split()[1].removeprefix("refs/heads/") for line in head.splitlines()
         if line.startswith("ref:")),
        "main",
    )  # fmt: skip
    branch = f"claim/{entry.name}"
    work = Path(tempfile.mkdtemp(prefix="cttp-claim-"))
    try:
        _git("worktree", "add", "--quiet", "--detach", str(work), f"origin/{base}", cwd=clone)
        _git("checkout", "--quiet", "-B", branch, cwd=work)
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_text(text, encoding="utf-8")
        _git("add", str(rel), cwd=work)
        title = f"{action}: {entry.name} -> {entry.target}"
        body = _pr_body(entry, action, previous)
        _git("commit", "--quiet", "-m", title, "-m", body, cwd=work)
        _git("push", "--quiet", "--force", "-u", "origin", branch, cwd=work)
        url = _gh(["pr", "create", "--head", branch, "--base", base, "--title", title,
                   "--body", body], cwd=work).strip()  # fmt: skip
    finally:
        try:
            _git("worktree", "remove", "--force", str(work), cwd=clone)
        except RegistryError:
            shutil.rmtree(work, ignore_errors=True)
            try:
                _git("worktree", "prune", cwd=clone)
            except RegistryError:
                pass
        try:
            _git("branch", "-D", branch, cwd=clone)
        except RegistryError:
            pass
    return branch, url


def _pr_body(entry: Entry, action: str, previous: Entry | None) -> str:
    lines = [
        f"`{entry.name}` -> `{entry.target}`, owner `{entry.owner}`.",
        "",
        f"The target declares the name in its `{DECLARATION}` at its default branch "
        "(spec §8: proof of control); the registry's checks verify it again before merging.",
    ]
    if action == "transferred" and previous is not None:
        handle = (previous.owner or "").split("/")[-1]
        lines += [
            "",
            f"**Transfer** from `{previous.owner}` (target was `{previous.target}`). "
            + (f"@{handle}, please approve this pull request to hand the name over." if handle
               else "The previous owner's approval is needed to merge."),
        ]  # fmt: skip
    elif action == "updated":
        lines += ["", "The name exists with this owner; this updates its entry."]
    return "\n".join(lines)


@dataclass(frozen=True)
class Verified:
    name: str
    checks: list[Check]

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def to_json(self) -> dict:
        return {"name": self.name, "ok": self.ok, "checks": [c.to_json() for c in self.checks]}


def verify(names: list[str] | None, registries: Registries) -> list[Verified]:
    """The registry's checks (`check_entry`) on each named entry of the first local registry —
    every name it has when `names` is empty. A name it does not have fails its `declaration`
    check with the reason. What the registry's own workflow runs on every pull request."""
    registry = next((r for r in registries.items if isinstance(r, LocalRegistry)), None)
    if registry is None:
        raise RegistryError(f"no local registry repository to verify: {registries.describe()}")
    out: list[Verified] = []
    for name in names or registry.names():
        try:
            entry = registry.lookup(name)
        except RegistryError as e:
            out.append(Verified(name, [Check("declaration", False, str(e))]))
            continue
        out.append(Verified(name, check_entry(entry, registries)))
    return out
