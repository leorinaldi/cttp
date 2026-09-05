"""Plan P7-T1: `cttp name show` and `cttp name claim` (spec §8: proof of control, not accounts).

Against a `tmp_path` registry repository and targets reached through `[remotes]`: a claim with
the declaration present writes the entry (`--no-pr` prints it); a claim without the declaration
is refused naming the missing file; a second owner's claim is refused unless `--transfer`; a
claim with a pull request lands on a `claim/<name>` branch of the registry's origin and leaves
the clone's checkout untouched; `name show hello-world` prints the P0-T2 entry.
"""

import json
import subprocess
from pathlib import Path

import pytest
from conftest import LOCATOR_PREFIX, add_remote_repo
from typer.testing import CliRunner

from cttp import registry as reg
from cttp.cli import app
from cttp.config import load_config
from cttp.registry import Registries, RegistryError, claim, declaration_at, is_name
from cttp.resolve import resolve
from cttp.schemas import validate

runner = CliRunner()
GREET = 'def greet(name: str) -> str:\n    """Say hello."""\n    return f"hi {name}"\n'


def run(*args: str, code: int = 0, schema: str | None = None) -> dict:
    res = runner.invoke(app, ["--json", *args])
    assert res.exit_code == code, res.output
    body = json.loads(res.stdout)
    if schema:
        errors = validate(schema, body)
        assert not errors, "; ".join(errors)
    return body


def make_target(tmp_path: Path, name: str, declaration: str | None, extra: dict | None = None):
    files = {"greet.py": GREET, "LICENSE": (tmp_path / "registry" / "LICENSE").read_text()}
    if declaration is not None:
        files["cttp.toml"] = declaration
    files.update(extra or {})
    return add_remote_repo(tmp_path, name, files)


# --- name show ---------------------------------------------------------------------------------


def test_show_hello_world_prints_the_p0_t2_entry(registry):
    res = runner.invoke(app, ["name", "show", "hello-world"])
    assert res.exit_code == 0, res.output
    assert "owner: github.com/leorinaldi" in res.output
    assert "target: github.com/leorinaldi/cttp-registry/snippets/hello_world.py" in res.output
    assert "versions: latest = main" in res.output and "resolves to hello-world@" in res.output
    body = run("name", "show", "hello-world", schema="name show")
    assert body["entry"]["description"] == "Prints 'hello world'."
    assert body["resolution"]["identity"] == "sha256:75a27070015e"
    assert body["registry"] == registry.items[0].describe()
    run("name", "show", "no-such-name", code=1, schema="error")
    err = run("name", "show", "github.com/leorinaldi/cttp-registry@main/x.py", code=1)
    assert "not a name" in err["error"]


# --- name claim --------------------------------------------------------------------------------


def test_claim_with_the_declaration_writes_the_entry(registry, tmp_path):
    locator = make_target(tmp_path, "greeter", 'name = "greeter"\n')
    body = run(
        "name", "claim", "greeter", "--target", f"{locator}/greet.py",
        "--description", "Greets by name.", "--no-pr", schema="name claim",
    )  # fmt: skip
    assert body["action"] == "claimed" and body["previous_owner"] is None
    assert body["owner"] == "github.com/leorinaldi" and body["pr"] is None
    assert body["declared_at"]["branch"] == "main" and body["declared_at"]["file"] == "cttp.toml"
    assert {c["check"]: c["ok"] for c in body["checks"]} == {
        "declaration": True, "owner": True, "target": True, "labels": True,
    }  # fmt: skip
    written = Path(body["written_to"])
    assert written == tmp_path / "registry" / "names" / "greeter.toml"
    assert written.read_text(encoding="utf-8") == body["text"]
    assert body["text"] == (
        'name = "greeter"\ndescription = "Greets by name."\nowner = "github.com/leorinaldi"\n'
        f'target = "{locator}/greet.py"\ndefault = "latest"\n\n[versions]\nlatest = "main"\n'
    )
    # the registry knows the name at once: LocalRegistry reads the working tree
    r = resolve("greeter", registry)
    assert r.description == "Greets by name." and r.kind == "script"
    assert resolve("greeter#greet", registry).kind == "function"
    # the text form prints the file and says what to do next
    res = runner.invoke(
        app, ["name", "claim", "greeter", "--target", f"{locator}/greet.py", "--no-pr"]
    )
    assert res.exit_code == 0 and "updated greeter" in res.output and "commit it" in res.output
    assert 'name = "greeter"' in res.output


def test_claim_without_the_declaration_is_refused_naming_the_file(registry, tmp_path):
    bare = make_target(tmp_path, "bare", None)
    err = run("name", "claim", "bare", "--target", f"{bare}/greet.py", "--no-pr", code=1)
    assert "has no cttp.toml at main" in err["error"] and "declaring the name" in err["error"]
    assert not (tmp_path / "registry" / "names" / "bare.toml").exists()
    other = make_target(tmp_path, "other", 'name = "something-else"\n')
    err = run("name", "claim", "other", "--target", f"{other}/greet.py", "--no-pr", code=1)
    assert "declares 'something-else' in cttp.toml at main" in err["error"]
    assert "not 'other'" in err["error"] and 'name = "other"' in err["error"]
    assert not (tmp_path / "registry" / "names" / "other.toml").exists()


def test_claim_by_another_owner_is_refused_unless_transfer(registry, tmp_path, config_file):
    # a second account: github.com/someone, reached through its own [remotes] prefix
    prefix = "github.com/someone/"
    remotes = tmp_path / "remotes" / prefix
    remotes.mkdir(parents=True)
    src = tmp_path / "src-" / "hello"
    src.mkdir(parents=True)
    (src / "cttp.toml").write_text('names = ["hello-world"]\n', encoding="utf-8")
    (src / "hello.py").write_text('print("hello from someone")\n', encoding="utf-8")
    reg.git_repo_from(tmp_path / "someone-hello", src, "hello contents")
    subprocess.run(
        ["git", "clone", "--bare", "-q", str(tmp_path / "someone-hello"), str(remotes / "hello")],
        check=True,
    )
    config_file.write_text(
        config_file.read_text() + f'"{prefix}" = "{remotes}/"\n', encoding="utf-8"
    )
    target = f"{prefix}hello/hello.py"
    err = run("name", "claim", "hello-world", "--target", target, "--no-pr", code=1)
    assert "owned by github.com/leorinaldi" in err["error"] and "--transfer" in err["error"]
    before = (tmp_path / "registry" / "names" / "hello-world.toml").read_text()
    assert 'owner = "github.com/leorinaldi"' in before  # untouched
    body = run(
        "name", "claim", "hello-world", "--target", target, "--transfer", "--no-pr",
        schema="name claim",
    )  # fmt: skip
    assert body["action"] == "transferred" and body["owner"] == "github.com/someone"
    assert body["previous_owner"] == "github.com/leorinaldi"
    fresh = Registries(load_config())  # the fixture's Registries predates the new remote
    assert resolve("hello-world", fresh).source == 'print("hello from someone")\n'


def test_the_declaration_form_and_labels(registry, tmp_path):
    locator = make_target(
        tmp_path, "multi", 'name = "multi"\nnames = ["multi.greet", "multi.other"]\n'
    )
    d = declaration_at(locator, registry)
    assert d.names == ("multi", "multi.greet", "multi.other") and d.branch == "main"
    body = run(
        "name", "claim", "multi.greet", "--target", f"{locator}/greet.py",
        "--version", "stable=v1", "--version", "latest=main", "--default", "stable", "--no-pr",
    )  # fmt: skip
    assert body["entry"]["versions"] == {"stable": "v1", "latest": "main"}
    assert body["entry"]["default"] == "stable"
    assert resolve("multi.greet", registry).address.startswith("multi.greet@")
    # a whole-repository target
    body = run("name", "claim", "multi", "--target", locator, "--no-pr")
    assert body["checks"][2]["detail"].endswith("the whole repository")
    assert resolve("multi#greet", registry).kind == "function"
    # refused: a bad name, a bad label, a ref that is not a revision, a path that is not there
    for args, expect in (
        (["Bad_Name", "--target", locator], "is not a name"),
        (["multi.other", "--target", locator, "--version", "Stable=v1"], "not a label"),
        (["multi.other", "--target", locator, "--version", "old=v0"], "not a revision"),
        (["multi.other", "--target", f"{locator}/nope.py"], "nope.py is not in"),
        (["multi.other", "--target", "nowhere"], "not host/owner/repo"),
        (["multi.other", "--target", locator, "--version", "stable"], "label=ref"),
    ):
        err = run("name", "claim", *args, "--no-pr", code=1)
        assert expect in err["error"], (args, err)
    assert not (tmp_path / "registry" / "names" / "multi.other.toml").exists()
    assert is_name("a.b-c.d") and not is_name("a..b") and not is_name("-a")


def test_claim_opens_a_pull_request_on_a_branch(registry, tmp_path, monkeypatch):
    """The entry goes on `claim/<name>` at the registry's origin, through a worktree: the
    clone's checkout is untouched, and `gh pr create` is run in that worktree."""
    locator = make_target(tmp_path, "greeter", 'name = "greeter"\n')
    clone = tmp_path / "registry"
    bare = tmp_path / "remotes" / LOCATOR_PREFIX / "cttp-registry"
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=clone, check=True)
    calls = []

    def fake_gh(args, cwd):
        calls.append((args, Path(cwd)))
        assert (Path(cwd) / "names" / "greeter.toml").exists()
        return "https://github.com/leorinaldi/cttp-registry/pull/1\n"

    monkeypatch.setattr(reg, "_gh", fake_gh)
    c = claim("greeter", f"{locator}/greet.py", registry, description="Greets.")
    assert c.pr == "https://github.com/leorinaldi/cttp-registry/pull/1"
    assert c.branch == "claim/greeter" and c.written_to is None
    args, cwd = calls[0]
    assert args[:2] == ["pr", "create"] and "--head" in args and "claim/greeter" in args
    assert not cwd.exists()  # the worktree is gone
    # the branch is at the origin with the file; the clone has neither the file nor the branch
    text = subprocess.run(
        ["git", "show", "claim/greeter:names/greeter.toml"],
        cwd=bare, capture_output=True, text=True,
    ).stdout  # fmt: skip
    assert text == c.text and 'description = "Greets."' in text
    assert not (clone / "names" / "greeter.toml").exists()
    branches = subprocess.run(
        ["git", "branch", "--list"], cwd=clone, capture_output=True, text=True
    ).stdout
    assert "claim/greeter" not in branches
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=clone, capture_output=True, text=True
    ).stdout
    assert status == ""
    worktrees = subprocess.run(
        ["git", "worktree", "list"], cwd=clone, capture_output=True, text=True
    ).stdout
    assert len(worktrees.strip().splitlines()) == 1
    # the CLI reports the same, and a clone without an origin says to use --no-pr
    body = run("name", "claim", "greeter", "--target", f"{locator}/greet.py", schema="name claim")
    assert body["pr"].endswith("/pull/1") and body["branch"] == "claim/greeter"
    subprocess.run(["git", "remote", "remove", "origin"], cwd=clone, check=True)
    err = run("name", "claim", "greeter", "--target", f"{locator}/greet.py", code=1)
    assert "no `origin` remote" in err["error"] and "--no-pr" in err["error"]


def test_claim_needs_a_local_registry(registry, tmp_path, monkeypatch):
    from cttp.config import Config

    http_only = Registries(Config(("http://localhost:1",), registry.config.remotes))
    with pytest.raises(RegistryError, match="no local registry repository"):
        claim("x", "github.com/leorinaldi/x", http_only, pr=False)
