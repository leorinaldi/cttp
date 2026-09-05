"""The registry: names → addresses. Spike: a local registry repository only (spec §8).

P0-T4 adds the HTTP backend; P0-T3 adds the config file that lists registries.
"""

import os
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


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


class LocalRegistry:
    def __init__(self, path: Path):
        self.path = Path(path)
        meta_file = self.path / "cttp.toml"
        if not meta_file.exists():
            raise RegistryError(f"{self.path} is not a registry repository (no cttp.toml)")
        meta = tomllib.loads(meta_file.read_text(encoding="utf-8"))
        self.repo: str | None = meta.get("repo")

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

    def ref_for(self, entry: Entry, version: str | None = None) -> str:
        """A version label maps to a ref of the target repository; anything else is a ref itself."""
        label = version or entry.default
        return entry.versions.get(label, label)

    def url_for(self, locator: str) -> str:
        """Spike: the registry repo itself is served from its local path; all else from https."""
        if self.repo and locator == self.repo:
            return str(self.path)
        return f"https://{locator}.git"


def default_registry_path() -> Path:
    return Path.home() / ".local" / "share" / "cttp" / "registry"


def open_registry(path: str | Path | None = None) -> LocalRegistry:
    chosen = Path(path or os.environ.get("CTTP_REGISTRY") or default_registry_path())
    if not chosen.exists():
        raise RegistryError(
            f"no registry at {chosen}; run scripts/make_local_registry.py or pass --registry"
        )
    return LocalRegistry(chosen)


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
