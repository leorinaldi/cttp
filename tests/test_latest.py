"""`resolve --latest`, rules 1 and 2 (plan P2-T3): a fixture repository with a history — an edit,
a rename within the file, a move within the repository, a move to another repository."""

import json

import pytest
from conftest import add_remote_repo, add_to_registry, commit_to_remote
from typer.testing import CliRunner

from cttp.cli import app
from cttp.resolve import ResolveError, latest, resolve

V1 = "def helper():\n    return 1\n"
V2 = "def helper():\n    return 2\n"
runner = CliRunner()


@pytest.fixture
def hist(registry, tmp_path):
    """A repository at v1 with `a.py#helper`, and the pinned address of that definition."""
    locator = add_remote_repo(tmp_path, "hist", {"a.py": V1, "README.md": "hist\n"})
    pinned = resolve(f"{locator}@v1/a.py#helper", registry).address
    return locator, pinned


def test_an_edit_is_found_at_the_same_path_with_a_changed_identity(registry, tmp_path, hist):
    locator, pinned = hist
    head = commit_to_remote(tmp_path, "hist", {"a.py": V2}, "edit helper")
    found = latest(pinned, registry)
    assert found.found and found.rule == "same-path" and found.changed is True
    assert found.head == head and found.to.address == f"{locator}@{head[:12]}/a.py#helper"
    assert found.to.source == V2 and found.to.identity != found.pinned.identity
    assert found.pinned.address == pinned
    j = found.to_json()
    assert j["origin"] == {"rule": "derived", "head": "derived", "via": "derived"}
    assert j["to"]["source"] == V2 and j["via"] is None
    # nothing changed: rule 1 still, unchanged
    again = latest(found.to.address, registry)
    assert again.rule == "same-path" and again.changed is False and "unchanged" in again.message


def test_a_rename_changes_the_identity_so_rules_1_and_2_do_not_find_it(registry, tmp_path, hist):
    """The identity hashes the definition's own source, name included: a renamed definition is
    a different identity. Its shape is the same; following by shape is not a rule yet."""
    locator, pinned = hist
    head = commit_to_remote(tmp_path, "hist", {"a.py": V1.replace("helper", "assist")}, "rename")
    found = latest(pinned, registry)
    assert not found.found and found.head == head
    assert resolve(f"{locator}@{head[:12]}/a.py#assist", registry).shape == found.pinned.shape


def test_a_move_within_the_repository_is_found_by_identity(registry, tmp_path, hist):
    locator, pinned = hist
    head = commit_to_remote(
        tmp_path, "hist", {"a.py": None, "lib/b.py": "import os\n\n" + V1}, "move"
    )
    found = latest(pinned, registry)
    assert found.rule == "same-identity" and found.to.path == "lib/b.py"
    assert found.to.address == f"{locator}@{head[:12]}/lib/b.py#helper"
    assert found.to.identity == found.pinned.identity


def test_a_move_to_another_repository_needs_the_index(registry, tmp_path, hist):
    locator, pinned = hist
    add_remote_repo(tmp_path, "elsewhere", {"a.py": V1})
    head = commit_to_remote(tmp_path, "hist", {"a.py": None}, "moved out")
    found = latest(pinned, registry)
    assert not found.found and found.rule is None and found.to is None and found.changed is None
    assert found.head == head
    assert found.message.startswith(
        f"a.py#helper is not at {locator}@{head[:12]} by path or by identity"
    )
    assert "rule 3" in found.message and "index" in found.message


def test_a_script_page_moves_as_a_whole_file(registry, tmp_path):
    locator = add_remote_repo(tmp_path, "scripts", {"run.py": "print(1)\n"})
    pinned = resolve(f"{locator}@main/run.py", registry).address
    head = commit_to_remote(tmp_path, "scripts", {"run.py": None, "bin/go.py": "print(1)\n"}, "mv")
    found = latest(pinned, registry)
    assert found.rule == "same-identity" and found.to.address == f"{locator}@{head[:12]}/bin/go.py"


def test_a_name_follows_its_registry_default_ref(registry, tmp_path, hist):
    locator, _ = hist
    add_to_registry(tmp_path, "hist-helper", target=f"{locator}/a.py")
    pinned = resolve("hist-helper#helper", registry)
    head = commit_to_remote(tmp_path, "hist", {"a.py": V2}, "edit")
    found = latest(pinned.address, registry)
    assert found.rule == "same-path" and found.changed is True
    assert found.to.address == f"hist-helper@{head[:12]}#helper" and found.to.name == "hist-helper"


def test_latest_needs_a_pinned_address(registry, hist):
    locator, _ = hist
    with pytest.raises(ResolveError, match="follows a pinned name or locator address"):
        latest(f"{locator}@main/a.py#helper", registry)
    with pytest.raises(ResolveError, match="follows a pinned"):
        latest("sha256:" + "a" * 12, registry)


def test_cli_latest(registry, tmp_path, hist):
    locator, pinned = hist
    commit_to_remote(tmp_path, "hist", {"a.py": V2}, "edit")
    res = runner.invoke(app, ["resolve", pinned, "--latest"])
    assert res.exit_code == 0 and "rule=same-path  the identity changed" in res.output
    assert "    return 2" in res.output
    body = json.loads(runner.invoke(app, ["--json", "resolve", pinned, "--latest"]).stdout)
    assert body["found"] and body["rule"] == "same-path" and body["from"]["address"] == pinned
    commit_to_remote(tmp_path, "hist", {"a.py": None}, "gone")
    res = runner.invoke(app, ["resolve", pinned, "--latest"])
    assert res.exit_code == 1 and "-> not found at" in res.output and "rule 3" in res.output
