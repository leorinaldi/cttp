"""The registry: names → addresses (spec §8).

An ordered list of registries from the config, first match wins. Each is a **local registry
repository** (`cttp.toml` + `names/*.toml`) or an **HTTP registry** serving the contract
(`GET /<name>@<version>.json`). A registry that does not know a name — or cannot be reached —
is a miss, and the next one is asked; the last miss names them all.
"""

import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import httpx

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
            description=d.get("description"),
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

    def fetch(self, name: str, version: str | None) -> dict:
        slug = f"{name}@{version}" if version else name
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
        run("commit", "--quiet", "-m", "Registry contents")
    if (
        subprocess.run(
            [*git, "rev-parse", "-q", "--verify", "v1"], cwd=dest, capture_output=True
        ).returncode
        != 0
    ):
        run("tag", "v1")
    return dest
