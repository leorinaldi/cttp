"""The queries (plan P4-T2) over crawled fixtures: pyrepo, a consumer linking to it, `twins`
(a function duplicated verbatim in two files, and a renamed copy), all in an index in tmp_path."""

import json

import pytest
from conftest import add_remote_repo, commit_to_remote
from typer.testing import CliRunner

from cttp.cli import app
from cttp.closure import closure as live_closure
from cttp.expand import expand_file
from cttp.index.crawl import MAX_FILE_BYTES, add, crawl
from cttp.index.queries import COLLAPSED, closure, dups, history, rank, search, who
from cttp.index.schema import IndexingError, open_index
from cttp.resolve import resolve

runner = CliRunner()
PYREPO = "github.com/leorinaldi/pyrepo"
GREET = 'def greet(name: str) -> str:\n    """Say hello."""\n    return f"hi {name}"\n'
PROSE = 'def d():\n    """A link line reads\n\n    # cttp: <address> [key=value]\n    """\n'
USES_GREET = 'from pkg.core import greet\n\n\ndef t():\n    return greet("a")\n'
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
    assert out["origin"]["by"] == "derived" and out["by"] == "identity"
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


def test_who_sees_a_src_layouts_tests(registry, tmp_path, monkeypatch):
    """The benchmark's worst number: `from pkg.core import greet` in `tests/` is on no ancestor
    path of the package under `src/`, so `who` used to answer a quietly incomplete 0."""
    monkeypatch.setenv("CTTP_INDEX", str(tmp_path / "index.db"))
    conn = open_index(tmp_path / "index.db")
    repo = add_remote_repo(
        tmp_path,
        "srclayout",
        {
            "src/pkg/__init__.py": "",
            "src/pkg/core.py": GREET,
            "tests/test_core.py": (
                'from pkg.core import greet\n\n\ndef test_greet():\n    assert greet("a")\n'
            ),
        },
    )
    add(conn, repo, registry.config)
    crawl(conn, registry)
    out = who(conn, f"{repo}@v1/src/pkg/core.py#greet", registry)
    # the test file as a script page (its imports) and the test function that uses the name
    assert out["count"] == 2 and out["by"] == {"ref": {"derived": 2}}
    script, fn = out["backlinks"]
    assert script["source"]["path"] == "tests/test_core.py" and script["source"]["symbol"] is None
    assert fn["source"]["symbol"] == "test_greet" and fn["name"] == "greet"


# --- coverage: what a `who` answer is an answer over (the P8-T3 follow-up) ----------------------


def test_coverage_names_the_revisions_and_the_directories_reached(world, registry):
    """`who` says what it searched, so an agent can see whether the question was in scope."""
    conn, consumer, twins = world
    cov = who(conn, f"{PYREPO}@v1/lib.py#deep", registry, detail=True)["coverage"]
    assert cov["repos"] == 3 and cov["revisions"] == 4  # pyrepo twice, consumer and twins once
    assert {s["repo"] for s in cov["searched"]} == {PYREPO, consumer, twins}
    pyrepo = [s for s in cov["searched"] if s["repo"] == PYREPO]
    assert [s["current"] for s in pyrepo] == [False, True]  # the edit is the current revision
    assert all(s["paths"] == {".": s["pages"] and s["paths"].get(".")} for s in pyrepo)
    assert cov["origin"] == "derived" and cov["caveats"]


def test_coverage_is_complete_when_every_reference_was_attributed(registry, tmp_path, monkeypatch):
    """The src-layout `who` now gets right: nothing skipped, nothing unmapped, no unidentified
    link naming `greet`. `complete` is how an agent knows not to corroborate by hand."""
    monkeypatch.setenv("CTTP_INDEX", str(tmp_path / "index.db"))
    conn = open_index(tmp_path / "index.db")
    repo = add_remote_repo(
        tmp_path,
        "srccomplete",
        {
            "src/pkg/__init__.py": "",
            "src/pkg/core.py": GREET,
            "tests/test_core.py": USES_GREET,
        },
    )
    add(conn, repo, registry.config)
    crawl(conn, registry)
    out = who(conn, f"{repo}@v1/src/pkg/core.py#greet", registry)
    cov = out["coverage"]
    assert out["count"] == 2
    assert cov["complete"] is True
    # nothing to warn about, so nothing but the line: the evidence would be for a settled doubt
    assert all(cov[f] is None for f in COLLAPSED)
    assert cov["summary"].startswith("coverage complete — searched")
    assert f"{repo}@" in cov["summary"] and "(3 file(s))" in cov["summary"]
    assert (cov["repos"], cov["revisions"], cov["files"]) == (1, 1, 3)
    full = who(conn, f"{repo}@v1/src/pkg/core.py#greet", registry, detail=True)["coverage"]
    assert full["skipped"] == 0 and full["unread"] == 0
    assert full["unresolved_matching"] == 0 and full["unmapped_imports"] == []
    assert full["searched"][0]["paths"] == {"src": 2, "tests": 1} and full["caveats"]
    assert full["summary"] == cov["summary"]


def test_the_collapse_is_what_the_cli_prints_and_what_coverage_undoes(
    registry, tmp_path, monkeypatch
):
    """A complete answer is one line; `--coverage` buys the evidence back. What collapses is the
    evidence for a doubt the first line has already settled — never the line itself."""
    monkeypatch.setenv("CTTP_INDEX", str(tmp_path / "index.db"))
    conn = open_index(tmp_path / "index.db")
    repo = add_remote_repo(
        tmp_path, "collapse", {"pkg/__init__.py": "", "pkg/core.py": GREET, "t.py": USES_GREET}
    )
    add(conn, repo, registry.config)
    crawl(conn, registry)
    address = f"{repo}@v1/pkg/core.py#greet"

    short = runner.invoke(app, ["--json", "who", address])
    full = runner.invoke(app, ["--json", "who", address, "--coverage"])
    assert short.exit_code == 0 and full.exit_code == 0
    small, big = json.loads(short.stdout)["coverage"], json.loads(full.stdout)["coverage"]
    assert small["complete"] is True and big["complete"] is True
    assert all(small[f] is None for f in COLLAPSED) and all(big[f] is not None for f in COLLAPSED)
    # the point of the change; the saving grows with the index — one small revision here
    assert len(json.dumps(small)) * 2 < len(json.dumps(big))
    assert small["summary"] == big["summary"]

    lines = runner.invoke(app, ["who", address]).output.splitlines()
    assert not [x for x in lines if x.startswith("searched ")]  # no per-revision block
    assert lines[-1].startswith("coverage complete — searched")
    full_lines = runner.invoke(app, ["who", address, "--coverage"]).output.splitlines()
    assert [x for x in full_lines if x.startswith(f"searched {repo}@")]


def test_coverage_counts_a_binary_as_skipped_but_not_as_a_gap(registry, tmp_path, monkeypatch):
    """A file the crawl could not read is reported; one that could hold neither a link nor a
    reference is not a hole, or `complete` would never be true of a real repository."""
    monkeypatch.setenv("CTTP_INDEX", str(tmp_path / "index.db"))
    conn = open_index(tmp_path / "index.db")
    blob = "x" * (MAX_FILE_BYTES + 1)  # the crawl's other reason to skip a file it cannot read
    repo = add_remote_repo(tmp_path, "withblob", {"lib.py": GREET, "logo.png": blob})
    add(conn, repo, registry.config)
    crawl(conn, registry)
    cov = who(conn, f"{repo}@v1/lib.py#greet", registry, detail=True)["coverage"]
    assert cov["skipped"] == 1 and cov["unread"] == 0 and cov["complete"] is True
    assert cov["searched"][0]["skipped"] == 1


def test_coverage_counts_an_unparsable_python_file_as_unread(registry, tmp_path, monkeypatch):
    """A Python file the crawl could not parse could have referenced anything: the answer has a
    hole, and says so."""
    monkeypatch.setenv("CTTP_INDEX", str(tmp_path / "index.db"))
    conn = open_index(tmp_path / "index.db")
    repo = add_remote_repo(tmp_path, "broken", {"lib.py": GREET, "bad.py": "def (:\n"})
    add(conn, repo, registry.config)
    crawl(conn, registry)
    cov = who(conn, f"{repo}@v1/lib.py#greet", registry)["coverage"]
    assert cov["skipped"] == 1 and cov["unread"] == 1 and cov["complete"] is False


def test_coverage_reports_an_import_it_could_not_map(registry, tmp_path, monkeypatch):
    """`pkg` lives under `lib/`, which is no source root, so `from pkg.core import greet` maps to
    nothing and the reference is never recorded. `who` answers 0 — and admits why."""
    monkeypatch.setenv("CTTP_INDEX", str(tmp_path / "index.db"))
    conn = open_index(tmp_path / "index.db")
    repo = add_remote_repo(
        tmp_path,
        "otherroot",
        {
            "lib/pkg/__init__.py": "",
            "lib/pkg/core.py": GREET,
            "tests/test_core.py": USES_GREET,
        },
    )
    add(conn, repo, registry.config)
    crawl(conn, registry)
    out = who(conn, f"{repo}@v1/lib/pkg/core.py#greet", registry)
    cov = out["coverage"]
    assert out["count"] == 0  # the reference the extractor could not resolve
    assert cov["complete"] is False
    assert [(u["module"], u["files"]) for u in cov["unmapped_imports"]] == [("pkg", 1)]


def test_who_follows_a_re_export_to_the_definition(registry, tmp_path, monkeypatch):
    """`from pkg import greet` reaches `__init__.py`, which only imports the name. The crawl
    records the reference against `core.py#greet` — the definition the re-export means — so `who`
    on the definition lists its users and the answer is complete."""
    monkeypatch.setenv("CTTP_INDEX", str(tmp_path / "index.db"))
    conn = open_index(tmp_path / "index.db")
    repo = add_remote_repo(
        tmp_path,
        "reexport",
        {
            "pkg/__init__.py": "from pkg.core import greet\ns = salute = greet\n",
            "pkg/core.py": GREET,
            "user.py": (
                'import pkg\nfrom pkg import greet\n\n\ndef t():\n    return greet("a")\n\n\n'
                'def u():\n    return pkg.s("b")\n'
            ),
        },
    )
    add(conn, repo, registry.config)
    (out,) = crawl(conn, registry)
    # user.py's file page and `t` reach `greet`, `u` reaches `pkg.s`; the `__init__`'s own
    # import names the definition directly
    assert out.forwarded == 3
    res = who(conn, f"{repo}@v1/pkg/core.py#greet", registry)
    assert [(b["source"]["path"], b["source"]["symbol"], b["name"]) for b in res["backlinks"]] == [
        ("pkg/__init__.py", None, "greet"),
        ("user.py", None, "greet"),
        ("user.py", "t", "greet"),
        ("user.py", "u", "pkg.s"),
    ]
    assert all(b["target"].endswith("/pkg/core.py#greet") for b in res["backlinks"])
    assert res["coverage"]["complete"] is True
    # the CLI says how many references the crawl forwarded
    out = runner.invoke(app, ["index", "crawl", "--force"])
    assert out.exit_code == 0 and "3 forwarded" in out.output


def test_coverage_flags_unidentified_links_that_name_this_address(registry, tmp_path, monkeypatch):
    """A name a package binds some way the extractor cannot follow — a lazy `__getattr__` — leaves
    `from pkg import greet` on `__init__.py#greet`, which the index cannot identify. A `who` of 0
    that did not say so is the answer an agent cannot trust."""
    monkeypatch.setenv("CTTP_INDEX", str(tmp_path / "index.db"))
    conn = open_index(tmp_path / "index.db")
    repo = add_remote_repo(
        tmp_path,
        "lazy",
        {
            "pkg/__init__.py": (
                "def __getattr__(name):\n    from . import core\n    return getattr(core, name)\n"
            ),
            "pkg/core.py": GREET + "\n\n" + SALUTE,  # two definitions: the file page is its own
            "user.py": 'from pkg import greet\n\n\ndef t():\n    return greet("a")\n',
        },
    )
    add(conn, repo, registry.config)
    crawl(conn, registry)
    out = who(conn, f"{repo}@v1/pkg/core.py#greet", registry)
    cov = out["coverage"]
    assert out["count"] == 0
    assert cov["unresolved_matching"] == 2 and cov["complete"] is False  # the file page and `t`
    # a definition nothing re-exports is unaffected by the same index's unidentified links
    other = who(conn, f"{repo}@v1/pkg/__init__.py", registry, detail=True)["coverage"]
    assert other["unresolved_targets"] == cov["unresolved_targets"]


def test_coverage_cannot_tell_on_an_index_that_predates_the_skipped_record(
    registry, tmp_path, monkeypatch
):
    """An index crawled by an older cttp has no record of what it could not read. `null`, and
    `complete` null with it — never a cheerful `0`."""
    monkeypatch.setenv("CTTP_INDEX", str(tmp_path / "index.db"))
    conn = open_index(tmp_path / "index.db")
    repo = add_remote_repo(tmp_path, "older", {"lib.py": GREET})
    add(conn, repo, registry.config)
    crawl(conn, registry)
    conn.execute("UPDATE revisions SET skipped = NULL")
    conn.commit()
    cov = who(conn, f"{repo}@v1/lib.py#greet", registry)["coverage"]
    assert cov["skipped"] is None and cov["unread"] is None and cov["complete"] is None
    assert cov["searched"] and cov["caveats"]  # only a complete answer collapses
    out = runner.invoke(app, ["who", f"{repo}@v1/lib.py#greet"]).output
    assert out.count("coverage unknown — searched") == 1 and "crawl --force" in out


def test_the_index_migrates_a_table_written_without_the_skipped_column(tmp_path):
    """`CREATE TABLE IF NOT EXISTS` leaves an existing table alone, so a column added later needs
    its own `ALTER TABLE`; a reader tolerates its absence instead of taking the write lock."""
    from cttp.index.schema import has_column

    path = tmp_path / "old.db"
    conn = open_index(path)
    conn.execute("DROP TABLE revisions")
    conn.execute(
        "CREATE TABLE revisions (repo TEXT NOT NULL REFERENCES repos(locator), sha TEXT NOT NULL,"
        " committed_at INTEGER, license TEXT, crawled_at TEXT NOT NULL, files INTEGER NOT NULL,"
        " PRIMARY KEY (repo, sha))"
    )
    conn.commit()
    conn.close()
    assert not has_column(open_index(path, create=False), "revisions", "skipped")
    assert has_column(open_index(path), "revisions", "skipped")  # a writer migrates it


def test_coverage_counts_a_link_line_the_crawl_had_to_ignore(registry, tmp_path, monkeypatch):
    """Prose that looks like a link costs the line, not the file — but an asserted link may be
    what was lost, so it is a hole in the answer and not a silent one."""
    monkeypatch.setenv("CTTP_INDEX", str(tmp_path / "index.db"))
    conn = open_index(tmp_path / "index.db")
    repo = add_remote_repo(
        tmp_path,
        "prose",
        {"lib.py": GREET, "doc.py": PROSE},
    )
    add(conn, repo, registry.config)
    crawl(conn, registry)
    cov = who(conn, f"{repo}@v1/lib.py#greet", registry)["coverage"]
    assert cov["ignored_links"] == 1 and cov["unread"] == 0
    assert cov["complete"] is False
    out = runner.invoke(app, ["who", f"{repo}@v1/lib.py#greet"]).output
    assert "1 link line(s) ignored" in out
