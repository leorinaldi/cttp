import subprocess
from pathlib import Path

import pytest

from cttp.config import load_config
from cttp.registry import Registries, create_local_registry

FIXTURES = Path(__file__).parent / "fixtures"
LOCATOR_PREFIX = "github.com/leorinaldi/"


@pytest.fixture
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A registry repository, a bare target repo, and a config reaching both — all in tmp_path.

    No network: `[remotes]` maps the `github.com/leorinaldi/` prefix at the bare repositories
    under `tmp_path/remotes/`, and `CTTP_HOME` moves the caches there too.
    """
    monkeypatch.setenv("CTTP_HOME", str(tmp_path / "cache"))
    monkeypatch.delenv("CTTP_REGISTRY", raising=False)
    reg = create_local_registry(tmp_path / "registry", FIXTURES / "registry")
    remotes = tmp_path / "remotes" / LOCATOR_PREFIX
    remotes.mkdir(parents=True)
    subprocess.run(
        ["git", "clone", "--bare", "--quiet", str(reg), str(remotes / "cttp-registry")],
        check=True,
    )
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        f'registries = ["{reg}"]\n\n[remotes]\n"{LOCATOR_PREFIX}" = "{remotes}/"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("CTTP_CONFIG", str(cfg))
    return cfg


@pytest.fixture
def registry(config_file: Path) -> Registries:
    return Registries(load_config())
