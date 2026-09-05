"""The queries (plan P4-T2) over crawled fixtures: pyrepo, a consumer linking to it, `twins`
(a function duplicated verbatim in two files, and a renamed copy), all in an index in tmp_path."""

import json

import pytest
from conftest import add_remote_repo, commit_to_remote
from typer.testing import CliRunner

from cttp.cli import app
from cttp.closure import closure as live_closure
from cttp.expand import expand_file
from cttp.index.crawl import add, crawl
from cttp.index.queries import closure, dups, history, rank, search, who
from cttp.index.schema import IndexingError, open_index
from cttp.resolve import resolve

runner = CliRunner()
PYREPO = "github.com/leorinaldi/pyrepo"
GREET = 'def greet(name: str) -> str:\n    """Say hello."""\n    return f"hi {name}"\n'
SALUTE = (
    'def salute(name: str) -> str:\n    """A greeting for a friend."""\n    return f"yo {name}"\n'
)


@pytest.fixture
def world(registry, tmp_path, monkeypatch):
    """pyrepo at two revisions (deep edited), a consumer with `deep` expanded and a see link, and
    twins: a.py and b.py both define greet verbatim, c.py defines hello with greet's shape."""
    monkeypatch.setenv("CTTP_INDEX", str(tmp_path / "index.db"))
    conn = open_index(tmp_path / "index.db")
    main = tmp_path / "main.py"
    main.write_text(f"# cttp: {PYREPO}@v1/lib.py#deep\n\nprint(deep(2))\n", encoding="utf-8")
    expand_file(main, registry)
    consumer = add_remote_repo(
        tmp_path,
        "consumer",
        {
            "main.py": main.read_text(),
            "notes.py": f"# cttp-see: {PYREPO}@v1/lib.py#top\nTOP = 3\n",
            "LICENSE": (tmp_path / "pyrepo" / "LICENSE").read_text(encoding="utf-8"),
        },
    )
    twins = add_remote_repo(
        tmp_path,
        "twins",
        {"a.py": GREET, "b.py": GREET + "\n\n" + SALUTE, "c.py": GREET.replace("greet", "hello")},
    )
    for r in (PYREPO, consumer, twins):
        add(conn, r, registry.config)
    crawl(conn, registry)
    lib = (tmp_path / "pyrepo" / "lib.py").read_text(encoding="utf-8")
    commit_to_remote(
        tmp_path, "pyrepo", {"lib.py": lib.replace("return x * 2", "return x * 3")}, "edit deep"
    )
    crawl(conn, registry)
    return conn, consumer, twins


def test_who_lists_the_asserted_copy_and_the_derived_sibling(world, registry):
    conn, consumer, _ = world
    deep = f"{PYREPO}@v1/lib.py#deep"
    out = who(conn, deep, registry)
    assert out["count"] == 2 and out["by"] == {"is": {"asserted": 1}, "ref": {"derived": 1}}
    copy, sibling = out["backlinks"]
    assert copy["relation"] == "is" and copy["origin"] == "asserted"
    assert copy["source"]["repo"] == consumer and copy["source"]["path"] == "main.py"
    assert copy["source"]["symbol"] == "deep" and copy["source"]["kind"] == "function"
    assert copy["source"]["identity"] == copy["target_identity"]  # a verbatim copy
    assert copy["source"]["license"] == "MIT" and copy["line"] == 1
    assert copy["target"].startswith(f"{PYREPO}@") and copy["target"].endswith("/lib.py#deep")
    assert sibling["relation"] == "ref" and sibling["origin"] == "derived"
    assert sibling["source"]["symbol"] == "right" and sibling["name"] == "deep"
    assert sibling["source"]["address"].endswith("/lib.py#right")
    # by identity, and by name through the registry snapshot
    ident = resolve(deep, registry).identity
    assert who(conn, ident, registry)["count"] == 2
    assert who(conn, "hello-world", registry)["count"] == 0  # nothing crawled links to it
    with pytest.raises(IndexingError, match="not in the index"):
        who(conn, "sha256:" + "f" * 12)


def test_dups_by_identity_and_by_shape(world):
    conn, _, twins = world
    out = dups(conn)
    [group] = [g for g in out["groups"] if "greet" in g["names"]]
    assert group["count"] == 2 and group["names"] == ["greet"] and group["kind"] == "function"
    assert {x["path"] for x in group["locations"]} == {"a.py", "b.py"}
    assert all(x["repo"] == twins for x in group["locations"])
    # deep was edited after the consumer copied it: at the current revisions the copy is a
    # stale copy, not a duplicate, so there is no deep group
    assert not [g for g in out["groups"] if "deep" in g["names"]]
    assert out["origin"]["identity"] == "derived"
    # by shape: the renamed copy joins, and so does salute — same structure, other literals
    by_shape = dups(conn, by_shape=True)
    [group] = [g for g in by_shape["groups"] if "greet" in g["names"]]
    assert group["names"] == ["greet", "hello", "salute"] and group["count"] == 4
    assert len(group["identities"]) == 3
    assert {x["path"] for x in group["locations"]} == {"a.py", "b.py", "c.py"}


def test_dups_does_not_pair_a_file_with_its_only_definition(world):
    conn, _, _ = world
    assert not [g for g in dups(conn)["groups"] if "notes.py" in g["names"]]


def test_search_by_name_and_docstring(world):
    conn, _, _ = world
    out = search(conn, "greet")
    names = [h["name"] for h in out["hits"]]
    assert "greet" in names and "salute" in names
    assert out["hits"][0]["name"] == "greet" and out["hits"][0]["address"].endswith("#greet")
    assert {h["name"] for h in search(conn, "bottom chain")["hits"]} == {"deep"}  # both revs
    assert search(conn, "nothing-like-this")["count"] == 0
    with pytest.raises(IndexingError, match="needs some text"):
        search(conn, "  ")


def test_history_lists_both_identities_in_order(world, registry):
    conn, _, _ = world
    out = history(conn, f"{PYREPO}@v1/lib.py#deep", registry)
    assert out["count"] == 2 and len(out["identities"]) == 2
    first, second = out["revisions"]
    assert first["changed"] and second["changed"] and not second["absent"]
    assert first["identity"] == resolve(f"{PYREPO}@v1/lib.py#deep", registry).identity
    assert second["identity"] == resolve(f"{PYREPO}@main/lib.py#deep", registry).identity
    assert first["shape"] == second["shape"]  # a literal changed; the shape did not
    unchanged = history(conn, f"{PYREPO}@v1/lib.py#left", registry)
    assert [v["changed"] for v in unchanged["revisions"]] == [True, False]


def test_rank_puts_the_most_linked_first(world):
    conn, _, _ = world
    out = rank(conn)
    top = out["ranked"][0]
    assert top["name"] == "deep" and top["backlinks"] == 2
    assert top["by"] == {"is": {"asserted": 1}, "ref": {"derived": 1}}
    assert all(r["backlinks"] <= 2 for r in out["ranked"])


def test_closure_from_the_index_matches_the_live_one(world, registry):
    conn, _, _ = world
    top = f"{PYREPO}@v1/lib.py#top"
    live = live_closure(top, registry).to_json()
    indexed = closure(conn, [top], registry)
    assert [n["symbol"] for n in indexed["definitions"]] == [
        n["symbol"] for n in live["definitions"]
    ]
    assert [n["identity"] for n in indexed["definitions"]] == [
        n["identity"] for n in live["definitions"]
    ]
    assert indexed["count"] == live["count"] == 4 and indexed["lines"] == live["lines"]
    for a, b in zip(indexed["definitions"], live["definitions"], strict=True):
        assert a["via"] == b["via"] and a["needs"] == b["needs"] and a["defines"] == b["defines"]
        assert a["source"] == b["source"] and a["description"] == b["description"]
    assert indexed["missing"] == [] and indexed["requires"] == []
    several = closure(conn, [f"{PYREPO}@v1/lib.py#hyp", top], registry)
    assert [n["symbol"] for n in several["definitions"]] == ["hyp", "left", "deep", "right", "top"]
    assert several["stdlib"] == ["math"] and several["imports"] == ["import math"]
    assert len(several["roots"]) == 2 and several["roots"][1].endswith("/lib.py#top")


def test_cli_queries(world):
    conn, consumer, _ = world
    deep = f"{PYREPO}@v1/lib.py#deep"
    res = runner.invoke(app, ["who", deep, "--json"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout)["count"] == 2
    res = runner.invoke(app, ["who", deep])
    assert "is  asserted  license=MIT" in res.stdout and "2 backlink(s)" in res.stdout
    res = runner.invoke(app, ["dups", "--shape"])
    assert res.exit_code == 0 and "greet, hello" in res.stdout
    res = runner.invoke(app, ["--json", "search", "greet"])
    assert json.loads(res.stdout)["hits"][0]["name"] == "greet"
    res = runner.invoke(app, ["history", deep])
    assert res.exit_code == 0 and "2 identity(ies) over 2 revision(s)" in res.stdout
    res = runner.invoke(app, ["rank", "--limit", "3", "--json"])
    assert json.loads(res.stdout)["ranked"][0]["name"] == "deep"
    res = runner.invoke(app, ["closure", "--indexed", f"{PYREPO}@v1/lib.py#top"])
    assert res.exit_code == 0 and "4 definition(s)" in res.stdout and "from the index" in res.stdout
    res = runner.invoke(app, ["closure", f"{PYREPO}@v1/lib.py#hyp", f"{PYREPO}@v1/lib.py#top"])
    assert "5 definition(s)" in res.stdout


def test_queries_need_an_index(registry, tmp_path, monkeypatch):
    monkeypatch.setenv("CTTP_INDEX", str(tmp_path / "none.db"))
    res = runner.invoke(app, ["who", "hello-world"])
    assert res.exit_code == 1 and "no index at" in res.output
