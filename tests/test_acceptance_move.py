"""Spec §12, acceptance test 2 — a link survives a move (plan P4-T3).

Fixture repository A defines a function; a consumer links to it, pinned. A is edited to rename
the function and move it to fixture repository B, with a `# cttp-from:` link left on the moved
definition. `cttp resolve --latest` on the original address returns the definition in B and
states which rule found it. The variant with no `cttp-from` link is found by identity alone when
B has been crawled — which means no rename, since the identity includes the name."""

import json

import pytest
from conftest import add_remote_repo, commit_to_remote
from typer.testing import CliRunner

from cttp.cli import app
from cttp.index.crawl import add, crawl
from cttp.index.schema import open_index
from cttp.resolve import latest, resolve

runner = CliRunner()
HELPER = 'def helper(x: int) -> int:\n    """Twice."""\n    return x * 2\n'


@pytest.fixture
def index(tmp_path, monkeypatch):
    p = tmp_path / "index.db"
    monkeypatch.setenv("CTTP_INDEX", str(p))
    return open_index(p)


@pytest.fixture
def a_and_consumer(registry, tmp_path):
    """A at v1 with a.py#helper; a consumer file with the pinned link, expanded."""
    a = add_remote_repo(tmp_path, "a", {"a.py": HELPER, "README.md": "A\n"})
    pinned = resolve(f"{a}@v1/a.py#helper", registry)
    consumer = tmp_path / "consumer.py"
    consumer.write_text(f"# cttp: {a}@v1/a.py#helper\n\nprint(helper(2))\n", encoding="utf-8")
    assert runner.invoke(app, ["expand", str(consumer)]).exit_code == 0
    assert pinned.address in consumer.read_text()
    return a, pinned, consumer


def test_2_a_renamed_move_across_repositories_is_found_by_its_from_link(
    registry, tmp_path, index, a_and_consumer
):
    a, pinned, _ = a_and_consumer
    b = add_remote_repo(
        tmp_path,
        "b",
        {"lib/b.py": f"# cttp-from: {pinned.address}\n" + HELPER.replace("helper", "assist")},
    )
    commit_to_remote(tmp_path, "a", {"a.py": None}, "moved helper to b, renamed")
    for repo in (a, b):
        add(index, repo, registry.config)
    crawl(index, registry)

    found = latest(pinned.address, registry)
    assert found.found and found.rule == "backlink" and found.via == "index"
    assert found.to.address.startswith(f"{b}@") and found.to.address.endswith("/lib/b.py#assist")
    assert found.to.symbol == "assist" and found.to.source == HELPER.replace("helper", "assist")
    assert found.to.identity != pinned.identity and found.to.shape == pinned.shape
    assert "links back to it with `from`" in found.message
    j = found.to_json()
    assert j["rule"] == "backlink" and j["via"] == "index" and j["origin"]["via"] == "derived"

    res = runner.invoke(app, ["resolve", "--latest", pinned.address])
    assert res.exit_code == 0, res.output
    assert "rule=backlink via index" in res.stdout and "#assist" in res.stdout
    res = runner.invoke(app, ["--json", "resolve", "--latest", pinned.address])
    assert json.loads(res.stdout)["to"]["symbol"] == "assist"


def test_2_variant_a_plain_move_across_repositories_is_found_by_identity(
    registry, tmp_path, index, a_and_consumer
):
    a, pinned, _ = a_and_consumer
    b = add_remote_repo(tmp_path, "b", {"src/util.py": "import os\n\n" + HELPER})
    commit_to_remote(tmp_path, "a", {"a.py": None}, "moved helper to b")
    # before B is crawled, nothing knows
    add(index, a, registry.config)
    crawl(index, registry)
    found = latest(pinned.address, registry)
    assert not found.found and "has it nowhere else" in found.message
    # after
    add(index, b, registry.config)
    crawl(index, registry)
    found = latest(pinned.address, registry)
    assert found.found and found.rule == "same-identity" and found.via == "index"
    assert found.to.address.endswith("/src/util.py#helper") and found.to.address.startswith(b)
    assert found.to.identity == pinned.identity and found.changed is False


def test_2_without_an_index_the_message_says_so(registry, tmp_path, a_and_consumer, monkeypatch):
    a, pinned, _ = a_and_consumer
    monkeypatch.setenv("CTTP_INDEX", str(tmp_path / "none.db"))
    commit_to_remote(tmp_path, "a", {"a.py": None}, "gone")
    found = latest(pinned.address, registry)
    assert not found.found and "there is no index at" in found.message
    assert "cttp index add" in found.message
    res = runner.invoke(app, ["resolve", "--latest", pinned.address])
    assert res.exit_code == 1 and "no index" in res.stdout


def test_rules_1_and_2_still_come_first(registry, tmp_path, index, a_and_consumer):
    """A copy elsewhere in the index does not outrank the definition still at its own head."""
    a, pinned, _ = a_and_consumer
    b = add_remote_repo(tmp_path, "b", {"copy.py": HELPER})
    for repo in (a, b):
        add(index, repo, registry.config)
    crawl(index, registry)
    found = latest(pinned.address, registry)
    assert found.rule == "same-path" and found.via is None and found.to.address.startswith(a)
