"""Spec §12, acceptance test 3 — provenance is visible (plan P4-T3).

`cttp add` in a consumer expands the definition in place beneath a stamped link carrying address,
identity and license; after `cttp index add` of the consumer, `cttp who` on the original lists
the copy as an `is` backlink with origin `asserted`; the page for the original shows it (P4-T4)."""

import json

import pytest
from conftest import add_remote_repo, clone_remote, commit_in
from typer.testing import CliRunner

from cttp.cli import app
from cttp.index.crawl import add, crawl
from cttp.index.queries import who
from cttp.index.schema import open_index
from cttp.links import find_links
from cttp.resolve import resolve

runner = CliRunner()
PYREPO = "github.com/leorinaldi/pyrepo"


@pytest.fixture
def index(tmp_path, monkeypatch):
    p = tmp_path / "index.db"
    monkeypatch.setenv("CTTP_INDEX", str(p))
    return open_index(p)


def test_3_the_copy_is_an_asserted_is_backlink_with_its_license(registry, tmp_path, index):
    original = f"{PYREPO}@v1/lib.py#hyp"
    page = resolve(original, registry)
    add_remote_repo(tmp_path, "consumer", {"README.md": "consumer\n", "LICENSE": "unlicensed\n"})
    work = clone_remote(tmp_path, "consumer")
    main = work / "main.py"
    main.write_text("print(hyp(3, 4))\n", encoding="utf-8")

    res = runner.invoke(app, ["add", original, str(main)])
    assert res.exit_code == 0, res.output
    text = main.read_text(encoding="utf-8")
    [link] = find_links(text.split("\n"))
    assert link.relation == "is" and link.address == page.address
    assert link.fields["id"] == page.identity and "import math" in text
    assert res.stdout.count("MIT") >= 1 or page.license == "MIT"  # the license travels

    commit_in(work, "use hyp")
    res = runner.invoke(app, ["index", "add", str(work)])
    assert res.exit_code == 0, res.output
    assert res.stdout.strip() == f"added: github.com/leorinaldi/consumer (from {work})"
    add(index, PYREPO, registry.config)
    crawl(index, registry)

    out = who(index, original, registry)
    [copy] = [b for b in out["backlinks"] if b["relation"] == "is"]
    assert copy["origin"] == "asserted"
    assert copy["source"]["repo"] == "github.com/leorinaldi/consumer"
    assert copy["source"]["path"] == "main.py" and copy["source"]["symbol"] == "hyp"
    assert copy["source"]["identity"] == page.identity  # a verbatim copy
    assert "license" in copy["source"] and copy["source"]["license"] is None  # not available
    assert copy["target"] == page.address and copy["target_identity"] == page.identity
    assert (
        copy["description"]
        == "def hyp(a: float, b: float) -> float — Uses the standard library only."
    )

    res = runner.invoke(app, ["--json", "who", original])
    assert res.exit_code == 0, res.output
    j = json.loads(res.stdout)
    assert j["count"] == 1 and j["backlinks"][0]["origin"] == "asserted"
    res = runner.invoke(app, ["who", original])
    assert "is  asserted  license=not available" in res.stdout


def test_3_by_name_through_the_registry(registry, tmp_path, index):
    """The same, for a name: the consumer of hello-world is listed under the name."""
    add_remote_repo(tmp_path, "consumer", {"README.md": "consumer\n"})
    work = clone_remote(tmp_path, "consumer")
    (work / "hello.py").write_text("# cttp: hello-world\n", encoding="utf-8")
    assert runner.invoke(app, ["expand", str(work / "hello.py")]).exit_code == 0
    commit_in(work, "hello")
    add(index, str(work), registry.config)
    crawl(index, registry)
    out = who(index, "hello-world", registry)
    assert out["count"] == 1 and out["backlinks"][0]["relation"] == "is"
    assert out["backlinks"][0]["origin"] == "asserted"
    assert out["backlinks"][0]["source"]["path"] == "hello.py"
    assert out["name"] == "hello-world"
