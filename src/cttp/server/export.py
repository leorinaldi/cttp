"""`cttp serve --export <dir>`: the registry contract as static files (plan P7-T3, spec §8).

Every route of the contract for every name in the local registries, rendered through the same
ASGI app `cttp serve` runs and written byte for byte: `/` → `index.html`, `/<name>` →
`<name>/index.html`, `/<name>.json` → `<name>.json`, and `/<name>@<label>.json` →
`<name>@<label>.json` for each version label. A static host serving the directory — GitHub Pages
behind `cttp.ai` — then answers `GET /<name>.json` exactly as the live server does, so the two
are interchangeable by construction. Symbol routes (`%23<symbol>`) are unbounded and not
exported; an HTTP registry for a symbol asks a live server.
"""

from dataclasses import dataclass
from pathlib import Path

from cttp.registry import Registries


@dataclass(frozen=True)
class Exported:
    route: str
    path: Path  # relative to the directory
    bytes: int

    def to_json(self) -> dict:
        return {"route": self.route, "path": str(self.path), "bytes": self.bytes}


@dataclass(frozen=True)
class Export:
    directory: Path
    names: list[str]
    files: list[Exported]

    def to_json(self) -> dict:
        return {
            "directory": str(self.directory),
            "names": list(self.names),
            "files": [f.to_json() for f in self.files],
            "count": len(self.files),
        }


def routes_for(registries: Registries) -> list[tuple[str, Path]]:
    """(route, file) for every route of the contract over the registries' names."""
    out: list[tuple[str, Path]] = [("/", Path("index.html"))]
    for name in registries.names():
        entry, _ = registries.lookup(name)
        out.append((f"/{name}", Path(name) / "index.html"))
        out.append((f"/{name}.json", Path(f"{name}.json")))
        for label in entry.versions:
            out.append((f"/{name}@{label}.json", Path(f"{name}@{label}.json")))
    return out


def export(directory: Path, registries: Registries) -> Export:
    """Write every route to `directory`; a route the server answers with an error stops the
    export (`ExportError`) rather than writing a wrong file."""
    from fastapi.testclient import TestClient

    from cttp.server.app import app

    directory = Path(directory)
    files: list[Exported] = []
    with TestClient(app) as client:
        for route, rel in routes_for(registries):
            res = client.get(route)
            if res.status_code != 200:
                raise ExportError(f"{route} answered {res.status_code}: {res.text[:200]}")
            target = directory / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(res.content)
            files.append(Exported(route, rel, len(res.content)))
    return Export(directory, registries.names(), files)


class ExportError(RuntimeError):
    pass
