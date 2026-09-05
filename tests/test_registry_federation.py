"""Plan P7-T2: federation — the configured registries are asked in order, the first that knows a
name answers, and the answer names which registry it was; and `cttp name verify`, the checks
the registry repository runs on every pull request."""

import json
from pathlib import Path

from conftest import add_remote_repo
from typer.testing import CliRunner

from cttp.cli import app
from cttp.config import Config, load_config
from cttp.registry import Registries, create_local_registry, verify
from cttp.resolve import resolve
from cttp.schemas import validate

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"
GREET = 'def greet(name: str) -> str:\n    """Say hello."""\n    return f"hi {name}"\n'


def second_registry(tmp_path: Path, names: dict[str, str]) -> Path:
    """A second local registry repository at tmp_path/second with `names` (name → target)."""
    src = tmp_path / "second-src"
    (src / "names").mkdir(parents=True)
    (src / "cttp.toml").write_text('name = "second"\n', encoding="utf-8")
    for name, target in names.items():
        (src / "names" / f"{name}.toml").write_text(
            f'name = "{name}"\ndescription = "From the second registry."\n'
            f'owner = "github.com/leorinaldi"\ntarget = "{target}"\ndefault = "latest"\n\n'
            '[versions]\nlatest = "main"\n',
            encoding="utf-8",
        )
    return create_local_registry(tmp_path / "second", src)


def test_a_name_in_the_second_registry_only_resolves_and_names_it(config_file, tmp_path):
    locator = add_remote_repo(
        tmp_path, "greeter", {"cttp.toml": 'name = "greeter"\n', "g.py": GREET}
    )
    second = second_registry(
        tmp_path,
        {"greeter": f"{locator}/g.py", "hello-world": f"{locator}/g.py"},
    )
    cfg = load_config()
    first = cfg.registries[0]
    both = Registries(Config((first, str(second)), cfg.remotes, cfg.path))
    assert [type(r).__name__ for r in both.items] == ["LocalRegistry", "LocalRegistry"]
    r = resolve("greeter", both)
    assert r.registry == str(second) and r.description == "From the second registry."
    # a name in both: the first wins
    h = resolve("hello-world", both)
    assert h.registry == first and h.source == 'print("hello world!")\n'
    # the CLI names the registry too, and reversing the order reverses the answer
    config_file.write_text(
        f'registries = ["{second}", "{first}"]\n' + config_file.read_text().split("\n", 1)[1],
        encoding="utf-8",
    )
    out = json.loads(runner.invoke(app, ["--json", "resolve", "hello-world"]).stdout)
    assert out["registry"] == str(second) and out["source"] == GREET
    shown = json.loads(runner.invoke(app, ["--json", "name", "show", "greeter"]).stdout)
    assert shown["registry"] == str(second)
    # a name in neither: the error names both, in order
    res = runner.invoke(app, ["resolve", "nothing-here"])
    assert res.exit_code == 1
    assert res.output.index(str(second)) < res.output.index(first)


def test_name_verify_passes_a_good_entry_and_fails_a_bad_one(registry, tmp_path):
    good = add_remote_repo(
        tmp_path,
        "greeter",
        {"cttp.toml": 'name = "greeter"\nnames = ["wrong-owner"]\n', "g.py": GREET},
    )
    names = tmp_path / "registry" / "names"
    res = runner.invoke(app, ["name", "claim", "greeter", "--target", f"{good}/g.py", "--no-pr"])
    assert res.exit_code == 0, res.output
    # hand-written entries a pull request might carry
    undeclared = add_remote_repo(
        tmp_path, "quiet", {"cttp.toml": 'name = "other"\n', "q.py": GREET}
    )
    (names / "quiet.toml").write_text(
        f'name = "quiet"\nowner = "github.com/leorinaldi"\ntarget = "{undeclared}/q.py"\n'
        'default = "latest"\n\n[versions]\nlatest = "main"\n',
        encoding="utf-8",
    )
    (names / "wrong-owner.toml").write_text(
        f'name = "wrong-owner"\nowner = "github.com/someone"\ntarget = "{good}/g.py"\n'
        'default = "latest"\n\n[versions]\nlatest = "main"\nold = "v0"\n',
        encoding="utf-8",
    )
    results = {v.name: v for v in verify([], Registries(load_config()))}
    assert set(results) == {"hello-world", "greeter", "quiet", "wrong-owner"}
    assert results["hello-world"].ok and results["greeter"].ok
    assert [c.check for c in results["greeter"].checks] == [
        "declaration", "owner", "target", "labels", "resolves",
    ]  # fmt: skip
    assert results["greeter"].checks[-1].detail.startswith("greeter@")
    quiet = {c.check: c for c in results["quiet"].checks}
    assert not quiet["declaration"].ok and "declares 'other'" in quiet["declaration"].detail
    assert "resolves" not in quiet  # not attempted after a failure
    wrong = {c.check: c for c in results["wrong-owner"].checks}
    assert wrong["declaration"].ok and not wrong["owner"].ok and not wrong["labels"].ok
    assert "github.com/leorinaldi" in wrong["owner"].detail
    assert "old = 'v0' is not a revision" in wrong["labels"].detail
    # the CLI: exit 1 with the failures named; a name the registry lacks fails too
    res = runner.invoke(app, ["name", "verify"])
    assert res.exit_code == 1 and "4 name(s), 2 failed" in res.output
    assert "wrong-owner  FAILED" in res.output and "greeter  ok" in res.output
    res = runner.invoke(app, ["--json", "name", "verify", "greeter", "hello-world"])
    assert res.exit_code == 0, res.output
    body = json.loads(res.stdout)
    assert validate("name verify", body) == [] and body["ok"] and body["count"] == 2
    res = runner.invoke(app, ["--json", "name", "verify", "no-such-name"])
    body = json.loads(res.stdout)
    assert res.exit_code == 1 and not body["ok"]
    assert "not a name in registry" in body["names"][0]["checks"][0]["detail"]
