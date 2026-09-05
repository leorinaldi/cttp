"""The index: schema and crawl (plan P4-T1). The pyrepo fixture and a consumer that links to it,
crawled into an index in tmp_path; row counts, identity as the key, links with their origin,
idempotence at one rev, and a second rev adding only what changed."""

import json
import subprocess

import pytest
from conftest import add_remote_repo, commit_to_remote
from typer.testing import CliRunner

from cttp import objects
from cttp.cli import app
from cttp.expand import expand_file
from cttp.index.crawl import add, crawl, locator_of_url
from cttp.index.schema import IndexingError, counts, open_index
from cttp.resolve import resolve

runner = CliRunner()
PYREPO = "github.com/leorinaldi/pyrepo"

# pyrepo: lib.py is a file page + 9 definitions, many.py a file page + 51; README and LICENSE
# carry no links and are not pages. Derived refs: right→deep, top→left, top→right, ping→pong,
# pong→ping in lib.py; f1..f50 each to its predecessor in many.py.
PYREPO_PAGES = 1 + 9 + 1 + 51
PYREPO_REFS = 5 + 50


@pytest.fixture
def index(tmp_path, monkeypatch):
    p = tmp_path / "index.db"
    monkeypatch.setenv("CTTP_INDEX", str(p))
    return p


@pytest.fixture
def consumer(registry, tmp_path):
    """A repository `github.com/leorinaldi/consumer` whose main.py holds pyrepo's `deep`,
    expanded beneath a stamped link, a `see` link, and a C file with a `see` link."""
    main = tmp_path / "main.py"
    main.write_text(f"# cttp: {PYREPO}@v1/lib.py#deep\n\nprint(deep(2))\n", encoding="utf-8")
    expand_file(main, registry)
    text = main.read_text(encoding="utf-8")
    assert "id=sha256:" in text and "def deep" in text
    files = {
        "main.py": text,
        "notes.py": f"# cttp-see: {PYREPO}@v1/lib.py#top\nTOP = 3\n",
        "sensor.c": "/* cttp-see: hello-world */\nint main(void) { return 0; }\n",
        "README.md": "consumer\n",
    }
    return add_remote_repo(tmp_path, "consumer", files), text


def test_crawl_counts_and_links(registry, index, consumer, tmp_path):
    locator, text = consumer
    conn = open_index(index)
    assert add(conn, PYREPO, registry.config)["status"] == "added"
    assert add(conn, locator, registry.config)["status"] == "added"
    assert add(conn, locator, registry.config)["status"] == "already registered"
    results = crawl(conn, registry)
    assert [r.status for r in results] == ["crawled", "crawled"]
    by = {r.repo: r for r in results}
    assert by[PYREPO].pages == PYREPO_PAGES and by[PYREPO].links == PYREPO_REFS
    assert by[PYREPO].skipped == []
    # consumer: main.py (file page + the copy of deep, same identity as pyrepo's), notes.py
    # (file page + TOP), sensor.c (a text page, because it carries a link)
    assert by[locator].pages == 5
    # deep is one identity in two places (the consumer is crawled first, so it is new there and
    # not in pyrepo), and notes.py's own text *is* `TOP = 3`, so the file page and the constant
    # are one identity too
    assert by[locator].definitions == 4 and by[PYREPO].definitions == PYREPO_PAGES - 1
    assert by[locator].links == 3
    c = counts(conn)
    assert c["repos"] == 2 and c["revisions"] == 2 and c["names"] == 1
    assert c["definitions"] == PYREPO_PAGES + 3
    assert c["locations"] == PYREPO_PAGES + 5
    assert c["links"] == PYREPO_REFS + 3

    deep = resolve(f"{PYREPO}@v1/lib.py#deep", registry)
    locs = conn.execute(
        "SELECT repo, path, symbol FROM locations WHERE identity = ? ORDER BY repo",
        (deep.identity_full,),
    ).fetchall()
    assert [tuple(x) for x in locs] == [(locator, "main.py", "deep"), (PYREPO, "lib.py", "deep")]

    links = {
        (r["relation"], r["origin"], r["file"]): r
        for r in conn.execute("SELECT * FROM links WHERE repo = ?", (locator,))
    }
    is_link = links[("is", "asserted", "main.py")]
    assert is_link["target_identity"] == deep.identity_full  # from the stamp's id=
    assert is_link["target_form"] == "locator" and is_link["target_symbol"] == "deep"
    assert (
        is_link["line"] == 1
        and is_link["description"] == "def deep(x: int) -> int — The bottom of the chain."
    )
    assert is_link["derived"] == 1 and json.loads(is_link["fields"])["id"].startswith("sha256:")
    assert is_link["source_identity"] == deep.identity_full  # the copy of deep is the source
    see = links[("see", "asserted", "notes.py")]
    top = resolve(f"{PYREPO}@v1/lib.py#top", registry)
    assert see["target_identity"] == top.identity_full  # a pinned locator the index has seen
    c_link = links[("see", "asserted", "sensor.c")]
    assert c_link["target_name"] == "hello-world" and c_link["target_identity"] is None
    right_to_deep = conn.execute(
        "SELECT * FROM links WHERE repo = ? AND relation = 'ref' AND target_symbol = 'deep'",
        (PYREPO,),
    ).fetchone()
    assert right_to_deep["origin"] == "derived" and right_to_deep["name"] == "deep"
    assert right_to_deep["target_identity"] == deep.identity_full
    assert right_to_deep["target_address"] == f"{PYREPO}@{deep.rev[:12]}/lib.py#deep"


def test_crawling_twice_changes_nothing(registry, index):
    conn = open_index(index)
    add(conn, PYREPO, registry.config)
    crawl(conn, registry)
    before = counts(conn)
    again = crawl(conn, registry)
    assert [r.status for r in again] == ["already"]
    assert counts(conn) == before


def test_a_second_rev_adds_a_revision_and_only_the_changed_definitions(registry, index, tmp_path):
    conn = open_index(index)
    add(conn, PYREPO, registry.config)
    crawl(conn, registry)
    before = counts(conn)
    lib = (tmp_path / "pyrepo" / "lib.py").read_text(encoding="utf-8")
    head = commit_to_remote(
        tmp_path, "pyrepo", {"lib.py": lib.replace("return x * 2", "return x * 3")}, "edit deep"
    )
    [r] = crawl(conn, registry)
    assert r.status == "crawled" and r.sha == head
    after = counts(conn)
    assert after["revisions"] == before["revisions"] + 1
    assert after["definitions"] == before["definitions"] + 2  # deep, and lib.py as a file
    assert after["locations"] == before["locations"] + PYREPO_PAGES
    assert r.definitions == 2
    hist = conn.execute(
        "SELECT sha, identity FROM locations WHERE path = 'lib.py' AND symbol = 'deep' ORDER BY sha"
    ).fetchall()
    assert len(hist) == 2 and hist[0]["identity"] != hist[1]["identity"]


def test_an_identity_resolves_from_the_index(registry, index, tmp_path):
    conn = open_index(index)
    add(conn, PYREPO, registry.config)
    crawl(conn, registry)
    deep = resolve(f"{PYREPO}@v1/lib.py#deep", registry)
    objects.clear(repos=False, objects=True)
    assert objects.lookup(deep.identity_full) is None
    r = resolve(deep.identity, registry)
    assert r.via == "index" and r.source == deep.source and r.address == deep.address
    assert r.locations[0]["origin"] == "index" and r.license == "MIT"
    assert r.kind == "function" and r.symbol == "deep" and r.signature == deep.signature
    with pytest.raises(Exception, match="neither the object cache nor the index"):
        resolve("sha256:" + "0" * 12, registry)


def test_add_a_local_clone_and_crawl_it_there(registry, index, tmp_path):
    """A local path registers through its origin remote: the tests' [remotes] map the bare
    repository's path back to the locator, exactly as a mirror URL would."""
    conn = open_index(index)
    bare = tmp_path / "remotes" / "github.com" / "leorinaldi" / "pyrepo"
    clone = tmp_path / "work" / "pyrepo"
    subprocess.run(["git", "clone", "--quiet", str(bare), str(clone)], check=True)
    out = add(conn, str(clone / "lib.py"), registry.config)
    assert out["repo"] == PYREPO and out["local_path"] == str(clone)
    assert out["default_branch"] == "main"
    [r] = crawl(conn, registry)
    assert r.status == "crawled" and r.pages == PYREPO_PAGES
    assert not (tmp_path / "cache" / "repos").exists()  # read from the clone, not the cache


def test_locator_of_url(registry):
    cfg = registry.config
    assert locator_of_url("https://github.com/Owner/Repo.git", cfg) == "github.com/owner/repo"
    assert locator_of_url("git@github.com:owner/repo.git", cfg) == "github.com/owner/repo"
    assert locator_of_url("ssh://git@github.com/owner/repo", cfg) == "github.com/owner/repo"
    with pytest.raises(IndexingError, match="cannot tell a locator"):
        locator_of_url("/nowhere/at/all", cfg)


def test_cli_add_crawl_status(registry, index, tmp_path):
    res = runner.invoke(app, ["index", "status"])
    assert res.exit_code == 1 and "no index at" in res.output
    res = runner.invoke(app, ["index", "add", PYREPO])
    assert res.exit_code == 0 and res.stdout.strip() == f"added: {PYREPO}"
    res = runner.invoke(app, ["--json", "index", "crawl"])
    assert res.exit_code == 0, res.output
    [r] = json.loads(res.stdout)
    assert r["status"] == "crawled" and r["pages"] == PYREPO_PAGES
    res = runner.invoke(app, ["index", "crawl"])
    assert "already crawled" in res.stdout
    res = runner.invoke(app, ["index", "status", "--json"])
    st = json.loads(res.stdout)
    assert st["index"] == str(index) and st["counts"]["repos"] == 1
    assert st["repos"][0]["revisions"][0]["license"] == "MIT"
    res = runner.invoke(app, ["index", "crawl", "github.com/leorinaldi/nope"])
    assert res.exit_code == 1 and "not registered" in res.output
    res = runner.invoke(app, ["index", "add", "not/a/locator/or/path"])
    assert res.exit_code == 1
