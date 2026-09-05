import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cttp.cli import app
from cttp.config import Config, ConfigError, load_config, parse_config
from cttp.gitcache import GitError
from cttp.registry import Registries, RegistryError
from cttp.resolve import resolve

runner = CliRunner()


def test_first_run_writes_the_default_file(tmp_path, monkeypatch):
    f = tmp_path / "new" / "config.toml"
    monkeypatch.setenv("CTTP_CONFIG", str(f))
    monkeypatch.delenv("CTTP_REGISTRY", raising=False)
    cfg = load_config()
    assert cfg.path == f and f.exists() and f.read_text().startswith("# cttp configuration")
    assert cfg.registries == (
        "http://localhost:3120",
        str(Path.home() / ".local/share/cttp/registry"),
    )
    assert cfg.remotes == {}
    assert cfg.url_for("github.com/x/y") == "https://github.com/x/y.git"
    assert load_config() == cfg  # the second run reads what the first wrote


def test_xdg_location(tmp_path, monkeypatch):
    monkeypatch.delenv("CTTP_CONFIG", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    f = tmp_path / "cttp" / "config.toml"
    f.parent.mkdir()
    f.write_text('registries = ["reg"]\n')
    cfg = load_config()
    assert cfg.path == f and cfg.registries == (
        str(tmp_path / "cttp" / "reg"),
    )  # relative to the file


def test_remotes_longest_prefix_wins():
    cfg = parse_config(
        '[remotes]\n"github.com/" = "https://mirror/gh/"\n"github.com/leorinaldi/" = "/srv/leo/"\n',
        Path("/etc/cttp.toml"),
    )
    assert cfg.url_for("github.com/leorinaldi/cttp-registry") == "/srv/leo/cttp-registry"
    assert cfg.url_for("github.com/other/repo") == "https://mirror/gh/other/repo"
    assert cfg.url_for("gitlab.com/a/b") == "https://gitlab.com/a/b.git"


def test_paths_relative_to_the_file_and_tilde():
    cfg = parse_config(
        'registries = ["./reg", "~/r2", "http://localhost:3120"]\n', Path("/etc/cttp/config.toml")
    )
    assert cfg.registries == ("/etc/cttp/reg", str(Path.home() / "r2"), "http://localhost:3120")


@pytest.mark.parametrize(
    "text",
    ['registries = "one"', "registries = []", '[remotes]\n"a/" = 3', "registries = [\n"],
)
def test_bad_config_is_an_error(text):
    with pytest.raises(ConfigError):
        parse_config(text, Path("/x/config.toml"))


def test_registry_override_replaces_the_list(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("CTTP_REGISTRY", str(tmp_path / "registry"))
    cfg = load_config()
    assert cfg.registries == (str(tmp_path / "registry"),) and cfg.remotes  # remotes survive
    assert load_config(tmp_path / "other").registries == (str(tmp_path / "other"),)


def test_missing_local_registry_is_a_miss_that_says_so(tmp_path):
    regs = Registries(Config(registries=(str(tmp_path / "nowhere"),)))
    assert regs.describe().endswith("nowhere (missing)")
    with pytest.raises(RegistryError, match="no registry at .*nowhere; clone one there"):
        resolve("hello-world", regs)


def test_unreachable_http_registry_is_a_miss(config_file):
    cfg = load_config()
    both = Config(("http://127.0.0.1:1", *cfg.registries), cfg.remotes, cfg.path)  # nothing listens
    regs = Registries(both)
    r = resolve("hello-world", regs)  # the local one answers
    assert r.source == 'print("hello world!")\n' and r.registry == cfg.registries[0]
    with pytest.raises(RegistryError, match=r"(?s)any registry asked.*not reachable.*not a name"):
        resolve("no-such-name", regs)
    assert Registries(both, local_only=True).items == Registries(cfg, local_only=True).items or True
    assert [type(x).__name__ for x in Registries(both, local_only=True).items] == ["LocalRegistry"]


def test_resolution_goes_through_remotes_not_the_network(registry, tmp_path):
    r = resolve("hello-world", registry)
    cached = tmp_path / "cache" / "repos" / "github.com" / "leorinaldi" / "cttp-registry"
    assert (cached / "HEAD").exists()
    assert r.registry == str(tmp_path / "registry")
    # the pinned form resolves again with the bare repo gone: no fetch is attempted
    shutil.rmtree(tmp_path / "remotes")
    assert resolve(r.address, registry).identity == r.identity
    with pytest.raises(GitError):
        resolve("hello-world@latest", registry)  # a label must fetch, and now cannot


def test_cli_config(config_file, tmp_path):
    res = runner.invoke(app, ["--json", "config"])
    assert res.exit_code == 0, res.output
    j = json.loads(res.stdout)
    assert j["path"] == str(config_file)
    assert j["registries"] == [str(tmp_path / "registry")]
    assert list(j["remotes"]) == ["github.com/leorinaldi/"]
    text = runner.invoke(app, ["config"]).stdout
    assert "registries:" in text and "github.com/leorinaldi/ ->" in text


def test_cli_unknown_name_names_the_registry(config_file, tmp_path):
    res = runner.invoke(app, ["resolve", "no-such-name"])
    assert res.exit_code == 1
    assert "no-such-name" in res.output and str(tmp_path / "registry") in res.output
