"""Configuration: `~/.config/cttp/config.toml` (XDG), overridable with `CTTP_CONFIG`. Plan P0-T3.

```toml
registries = ["~/.local/share/cttp/registry", "http://localhost:3120"]  # in order, first match wins

[remotes]                                        # locator prefix → URL prefix (longest prefix wins)
"github.com/leorinaldi/" = "/srv/mirrors/leorinaldi/"
```

On first run the file is written with the defaults: `http://localhost:3120` first (`cttp serve`),
the local registry repository at `~/.local/share/cttp/registry` second, and no remotes, so every
locator is fetched from `https://<locator>.git`. Paths in the file may use `~`; relative paths are
relative to the file's directory.
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(ValueError):
    pass


def default_registry_path() -> Path:
    return Path.home() / ".local" / "share" / "cttp" / "registry"


def config_path() -> Path:
    if env := os.environ.get("CTTP_CONFIG"):
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / "cttp" / "config.toml"


DEFAULT_REGISTRIES = ("http://localhost:3120", "~/.local/share/cttp/registry")
DEFAULT_CONFIG = """\
# cttp configuration — see `cttp config`.
#
# Registries, in order: the first that knows a name answers. An http(s) URL is a registry
# serving the cttp contract (`cttp serve` on localhost, cttp.ai later); a path is a local
# registry repository (git clone https://github.com/leorinaldi/cttp-registry <path>).
registries = ["http://localhost:3120", "~/.local/share/cttp/registry"]

# Remotes map a locator prefix to a URL prefix — a mirror, or a local path. Longest prefix
# wins; without a match, host/owner/repo is fetched from https://host/owner/repo.git
[remotes]
"""


def is_url(text: str) -> bool:
    return text.startswith(("http://", "https://"))


@dataclass(frozen=True)
class Config:
    registries: tuple[str, ...]  # each an HTTP URL or a local path to a registry repository
    remotes: dict[str, str] = field(default_factory=dict)
    path: Path | None = None  # the file this came from; None when defaults were used

    def url_for(self, locator: str) -> str:
        """Where to clone `host/owner/repo` from: the longest `[remotes]` prefix, else https."""
        best = max((p for p in self.remotes if locator.startswith(p)), key=len, default=None)
        if best is not None:
            return self.remotes[best] + locator[len(best) :]
        return f"https://{locator}.git"

    def to_json(self) -> dict:
        return {
            "path": str(self.path) if self.path else None,
            "registries": list(self.registries),
            "remotes": dict(self.remotes),
        }


def _resolve_entry(entry: str, base: Path) -> str:
    """A URL as is; a path with `~` expanded and made absolute, keeping any trailing slash."""
    if is_url(entry):
        return entry
    p = Path(entry).expanduser()
    out = str(p if p.is_absolute() else (base / p).resolve())
    return out + "/" if entry.endswith("/") and not out.endswith("/") else out


def parse_config(text: str, path: Path | None) -> Config:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path or 'config'}: {e}") from e
    base = path.parent if path else Path.cwd()
    registries = data.get("registries", list(DEFAULT_REGISTRIES))
    if not isinstance(registries, list) or not all(isinstance(r, str) for r in registries):
        raise ConfigError(f"{path}: `registries` must be a list of strings")
    if not registries:
        raise ConfigError(f"{path}: `registries` is empty")
    remotes = data.get("remotes", {})
    if not isinstance(remotes, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in remotes.items()
    ):
        raise ConfigError(f"{path}: `[remotes]` must map locator prefixes to URL prefixes")
    return Config(
        registries=tuple(_resolve_entry(r, base) for r in registries),
        remotes={k: _resolve_entry(v, base) for k, v in remotes.items()},
        path=path,
    )


def load_config(registry: str | Path | None = None) -> Config:
    """The effective configuration; the file is written with defaults if it does not exist.

    `registry` (or `CTTP_REGISTRY`) replaces the registry list with that one entry.
    """
    path = config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    cfg = parse_config(path.read_text(encoding="utf-8"), path)
    override = registry or os.environ.get("CTTP_REGISTRY")
    if override:
        one = _resolve_entry(str(override), Path.cwd())
        cfg = Config(registries=(one,), remotes=cfg.remotes, path=cfg.path)
    return cfg
