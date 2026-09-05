"""The registry: names → addresses (spec §8).

An ordered list of registries from the config, first match wins. Each is a **local registry
repository** (`cttp.toml` + `names/*.toml`) or an HTTP registry (P0-T4).
"""

import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

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


class HttpRegistry:
    """A registry served over the spec §8 contract. The client arrives in P0-T4."""

    def __init__(self, url: str):
        self.url = url.rstrip("/")

    def describe(self) -> str:
        return self.url

    def names(self) -> list[str]:
        return []

    def lookup(self, name: str) -> Entry:
        raise RegistryError(f"{name!r}: HTTP registry {self.url} is not supported yet (P0-T4)")


Registry = LocalRegistry | HttpRegistry


class Registries:
    """The configured registries, in order. The first that knows a name answers for it."""

    def __init__(self, config: Config):
        self.config = config
        self.items: list[Registry] = []
        for entry in config.registries:
            if is_url(entry):
                self.items.append(HttpRegistry(entry))
            else:
                p = Path(entry)
                if not p.exists():
                    raise RegistryError(
                        f"no registry at {p}; clone one there (git clone "
                        "https://github.com/leorinaldi/cttp-registry "
                        f"{p}) or set `registries` in {config.path or 'the config file'}"
                    )
                self.items.append(LocalRegistry(p))

    def describe(self) -> str:
        return ", ".join(r.describe() for r in self.items)

    def names(self) -> list[str]:
        return sorted({n for r in self.items for n in r.names()})

    def lookup(self, name: str) -> tuple[Entry, Registry]:
        errors: list[str] = []
        for r in self.items:
            try:
                return r.lookup(name), r
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


def open_registries(registry: str | Path | None = None) -> Registries:
    return Registries(load_config(registry))


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
