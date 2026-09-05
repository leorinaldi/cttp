"""The object cache: every resolved page, by identity, under ~/.cache/cttp/objects. Spec §5.

`objects/<sha256>` is the page's normalized source and `objects/<sha256>.json` a sidecar with its
metadata and every location — pinned locator address, name, registry, license — it was seen at.
An identity address resolves from here without a network, and a page whose origin has vanished
survives wherever it was ever resolved. The index (Phase 4) is the second place to ask; until it
exists the hook says so.
"""

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from cttp import gitcache

METADATA = (
    "kind", "language", "symbol", "signature", "docstring", "span", "shape", "shape_full",
    "refs", "imports",
)  # fmt: skip
LOCATION = ("address", "target", "path", "rev", "name", "registry", "description", "license")


class ObjectError(LookupError):
    pass


class AmbiguousIdentity(ObjectError):
    def __init__(self, prefix: str, candidates: list[str]):
        self.candidates = candidates
        super().__init__(
            f"sha256:{prefix} is a prefix of {len(candidates)} cached identities; say which: "
            + ", ".join(f"sha256:{c[:16]}" for c in candidates)
        )


@dataclass
class Stored:
    identity: str  # full sha256 hex
    source: str
    meta: dict
    locations: list[dict] = field(default_factory=list)  # most recently seen last

    @property
    def latest(self) -> dict:
        return self.locations[-1]


def objects_dir() -> Path:
    return gitcache.home() / "objects"


def store(r) -> Path:
    """Record a resolved page (`resolve.Resolved`) under its identity; a location seen before is
    refreshed, not duplicated. Returns the object's path."""
    path = objects_dir() / r.identity_full
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(r.source, encoding="utf-8")
    sidecar = path.with_suffix(".json")
    data = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else {}
    data.update({k: getattr(r, k) for k in METADATA})
    location = {k: getattr(r, k) for k in LOCATION if k != "address"}
    location["address"] = locator_address(r)
    location["seen"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    locations = [x for x in data.get("locations", []) if x["address"] != location["address"]]
    data["locations"] = [*locations, location]
    sidecar.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def locator_address(r) -> str:
    """The pinned locator form of a resolution, whatever form its address took."""
    from cttp.address import Address
    from cttp.hashing import short

    locator, path = r.target.rsplit("/" + r.path, 1)[0], r.path
    return str(Address("locator", locator=locator, path=path, rev=short(r.rev), symbol=r.symbol))


def lookup(prefix: str) -> Stored | None:
    """The cached page whose identity starts with `prefix` (12+ hex); None when the cache has no
    such page; `AmbiguousIdentity` when it has several."""
    prefix = prefix.removeprefix("sha256:").lower()
    root = objects_dir()
    if not root.exists():
        return None
    matches = sorted(p.name for p in root.glob(f"{prefix}*") if p.suffix != ".json")
    if not matches:
        return None
    if len(matches) > 1:
        raise AmbiguousIdentity(prefix, matches)
    return load(matches[0])


def load(identity: str) -> Stored:
    path = objects_dir() / identity
    data = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    return Stored(
        identity=identity,
        source=path.read_text(encoding="utf-8"),
        meta={k: data.get(k) for k in METADATA},
        locations=data.get("locations", []),
    )


def index_lookup(prefix: str) -> None:
    """The index's answer for an identity. The index is Phase 4; until then, nothing is indexed."""
    return None


# --- both caches -------------------------------------------------------------------------------


def status() -> dict:
    """What the caches hold: repositories, objects, run-cache entries, with sizes in bytes."""
    home = gitcache.home()
    repos = [p.parent for p in gitcache.repos_dir().rglob("HEAD") if p.parent.is_dir()]
    objects = (
        [p for p in objects_dir().glob("*") if p.suffix != ".json"]
        if objects_dir().exists()
        else []
    )
    runs = [p for p in (home / "run").glob("*") if p.is_dir()] if (home / "run").exists() else []
    return {
        "home": str(home),
        "repos": {"count": len(repos), "bytes": sum(_size(p) for p in repos)},
        "objects": {"count": len(objects), "bytes": _size(objects_dir())},
        "run": {"count": len(runs), "bytes": _size(home / "run")},
    }


def clear(repos: bool = True, objects: bool = True, run: bool = False) -> list[str]:
    """Remove the chosen caches; returns what was removed. The run cache is the record of what
    was confirmed to run, so it goes only when asked."""
    removed = []
    for wanted, path in (
        (repos, gitcache.repos_dir()),
        (objects, objects_dir()),
        (run, gitcache.home() / "run"),
    ):
        if wanted and path.exists():
            shutil.rmtree(path)
            removed.append(str(path))
    return removed


def _size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
