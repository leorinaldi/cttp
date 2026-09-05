import socket
import subprocess
from pathlib import Path

import pytest

from cttp.config import load_config
from cttp.registry import Registries, create_local_registry, git_repo_from

FIXTURES = Path(__file__).parent / "fixtures"
LOCATOR_PREFIX = "github.com/leorinaldi/"


class NetworkForbidden(RuntimeError):
    """A test tried to connect a socket. Tests never touch the network (overview §6)."""


@pytest.fixture(autouse=True)
def no_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every socket connection a test would make raises, so a test that reaches the network
    fails loudly. (The in-process test client's event loop makes a socketpair, which needs no
    connect, so that still works.) `@pytest.mark.network` opts a test out — only for one that
    talks to a closed local port."""
    if request.node.get_closest_marker("network"):
        return

    def refuse(self, *args, **kwargs):
        raise NetworkForbidden("tests never connect sockets")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


@pytest.fixture
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A registry repository, bare target repos (thermo, pyrepo, crepo), and a config reaching them
    all — in tmp_path.

    No network: `[remotes]` maps the `github.com/leorinaldi/` prefix at the bare repositories
    under `tmp_path/remotes/`, and `CTTP_HOME` moves the caches there too.
    """
    monkeypatch.setenv("CTTP_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("CTTP_INDEX", str(tmp_path / "index.db"))  # never the real index
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")  # git itself may only read local paths
    monkeypatch.delenv("CTTP_REGISTRY", raising=False)
    reg = create_local_registry(tmp_path / "registry", FIXTURES / "registry")
    thermo = git_repo_from(tmp_path / "thermo", FIXTURES / "thermo", "thermo package")
    pyrepo = git_repo_from(tmp_path / "pyrepo", FIXTURES / "pyrepo", "pyrepo contents")
    crepo = git_repo_from(tmp_path / "crepo", FIXTURES / "crepo", "crepo contents")
    remotes = tmp_path / "remotes" / LOCATOR_PREFIX
    remotes.mkdir(parents=True)
    repos = ((reg, "cttp-registry"), (thermo, "thermo"), (pyrepo, "pyrepo"), (crepo, "crepo"))
    for src, name in repos:
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


def add_remote_repo(tmp_path: Path, name: str, files: dict[str, str]) -> str:
    """A repository of `files` reachable as `github.com/leorinaldi/<name>` through `[remotes]`
    (branch `main`, tag `v1`); returns its locator."""
    src = tmp_path / "src-" / name
    for path, text in files.items():
        (src / path).parent.mkdir(parents=True, exist_ok=True)
        (src / path).write_text(text, encoding="utf-8")
    repo = git_repo_from(tmp_path / name, src, f"{name} contents")
    bare = tmp_path / "remotes" / LOCATOR_PREFIX / name
    subprocess.run(["git", "clone", "--bare", "--quiet", str(repo), str(bare)], check=True)
    return LOCATOR_PREFIX + name


def commit_to_remote(
    tmp_path: Path, name: str, changes: dict[str, str | None], message: str
) -> str:
    """Advance the repository `name` (made by `add_remote_repo`, or the thermo fixture): write each
    path's text, or delete it when None; commit; push to the bare remote. Returns the new SHA."""
    src = tmp_path / name
    for path, text in changes.items():
        if text is None:
            (src / path).unlink()
        else:
            (src / path).parent.mkdir(parents=True, exist_ok=True)
            (src / path).write_text(text, encoding="utf-8")
    git = ["git", "-c", "user.name=cttp", "-c", "user.email=cttp@localhost"]
    subprocess.run([*git, "add", "-A"], cwd=src, check=True, capture_output=True)
    subprocess.run([*git, "commit", "-q", "-m", message], cwd=src, check=True)
    bare = tmp_path / "remotes" / LOCATOR_PREFIX / name
    subprocess.run(["git", "push", "-q", str(bare), "main"], cwd=src, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=src, check=True, capture_output=True, text=True
    ).stdout.strip()


def clone_remote(tmp_path: Path, name: str, into: str = "work") -> Path:
    """A working clone of the bare remote `github.com/leorinaldi/<name>` at
    tmp_path/<into>/<name>, its origin the bare repository — what `cttp index add <path>` reads."""
    bare = tmp_path / "remotes" / LOCATOR_PREFIX / name
    dest = tmp_path / into / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--quiet", str(bare), str(dest)], check=True)
    return dest


def commit_in(path: Path, message: str, push: bool = False) -> str:
    """Commit everything in a working clone (and push to its origin when asked); the new SHA."""
    git = ["git", "-c", "user.name=cttp", "-c", "user.email=cttp@localhost"]
    subprocess.run([*git, "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run([*git, "commit", "-q", "-m", message], cwd=path, check=True)
    if push:
        subprocess.run(["git", "push", "-q", "origin", "HEAD"], cwd=path, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, check=True, capture_output=True, text=True
    ).stdout.strip()
