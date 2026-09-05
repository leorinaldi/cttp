import subprocess
from pathlib import Path

import pytest

from cttp.config import load_config
from cttp.registry import Registries, create_local_registry, git_repo_from

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
    thermo = git_repo_from(tmp_path / "thermo", FIXTURES / "thermo", "thermo package")
    remotes = tmp_path / "remotes" / LOCATOR_PREFIX
    remotes.mkdir(parents=True)
    for src, name in ((reg, "cttp-registry"), (thermo, "thermo")):
        subprocess.run(
            ["git", "clone", "--bare", "--quiet", str(src), str(remotes / name)], check=True
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


@pytest.fixture
def hello(tmp_path: Path) -> Path:
    """A copy of tests/fixtures/hello/hello.py: one line, `# cttp: hello-world`."""
    f = tmp_path / "hello.py"
    f.write_bytes((FIXTURES / "hello" / "hello.py").read_bytes())
    return f


def add_to_registry(
    tmp_path: Path,
    name: str,
    source: str | None = None,
    description: str = "",
    target: str | None = None,
) -> None:
    """Add a name to the tmp registry repo and push it to the bare remote.

    With `source`, the name points at a new snippet in the registry repo itself; with `target`,
    at that target (a file in another repository the config's `[remotes]` can reach).
    """
    reg = tmp_path / "registry"
    if source is not None:
        (reg / "snippets" / f"{name}.py").write_text(source, encoding="utf-8")
        target = f"github.com/leorinaldi/cttp-registry/snippets/{name}.py"
    (reg / "names" / f"{name}.toml").write_text(
        f'name = "{name}"\ndescription = "{description}"\nowner = "github.com/leorinaldi"\n'
        f'target = "{target}"\ndefault = "latest"\n\n[versions]\nlatest = "main"\n',
        encoding="utf-8",
    )
    git = ["git", "-c", "user.name=cttp", "-c", "user.email=cttp@localhost"]
    subprocess.run([*git, "add", "-A"], cwd=reg, check=True, capture_output=True)
    subprocess.run([*git, "commit", "-q", "-m", f"add {name}"], cwd=reg, check=True)
    bare = tmp_path / "remotes" / LOCATOR_PREFIX / "cttp-registry"
    subprocess.run(["git", "push", "-q", str(bare), "main"], cwd=reg, check=True)
