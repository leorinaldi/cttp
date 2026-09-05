"""Plan P5-T1: every subcommand's `--json` output validates against `schemas.py`; a schema change
fails until `SCHEMA_VERSION` is bumped; `docs/json-schemas.md` matches the code."""

import json
from pathlib import Path

import pytest
from conftest import add_remote_repo, commit_to_remote
from typer.testing import CliRunner

from cttp import schemas
from cttp.cli import NOT_CONFIRMED, NOT_RUN, app
from cttp.expand import expand_file
from cttp.index.crawl import add, crawl
from cttp.index.schema import open_index
from cttp.resolve import resolve
from cttp.schemas import COMMANDS, DEFS, fingerprint, json_schema, markdown, validate

runner = CliRunner()
ROOT = Path(__file__).resolve().parent.parent
PYREPO = "github.com/leorinaldi/pyrepo"
GREET = 'def greet(name: str) -> str:\n    """Say hello."""\n    return f"hi {name}"\n'


def run(command: str, *args: str, code: int = 0) -> dict:
    """Invoke the CLI with `--json` and check the object against `command`'s schema."""
    res = runner.invoke(app, ["--json", *args])
    assert res.exit_code == code, res.output
    body = json.loads(res.stdout)
    errors = validate(command, body)
    assert not errors, f"{command}: " + "; ".join(errors)
    assert body["schema_version"] == schemas.SCHEMA_VERSION
    return body


@pytest.fixture
def world(registry, tmp_path):
    """pyrepo crawled at two revisions (deep edited), a consumer with `deep` expanded, a see link,
    an unexpanded link to a name the index cannot tell; twins with greet in two files."""
    conn = open_index(tmp_path / "index.db")  # CTTP_INDEX points here (conftest)
    main = tmp_path / "main.py"
    main.write_text(f"# cttp: {PYREPO}@v1/lib.py#deep\n\nprint(deep(2))\n", encoding="utf-8")
    expand_file(main, registry)
    consumer = add_remote_repo(
        tmp_path,
        "consumer",
        {
            "main.py": main.read_text(),
            "notes.py": f"# cttp-see: {PYREPO}@v1/lib.py#top\nTOP = 3\n",
            "other.py": "# cttp: hello-world\n",
            "LICENSE": (tmp_path / "pyrepo" / "LICENSE").read_text(encoding="utf-8"),
        },
    )
    twins = add_remote_repo(
        tmp_path, "twins", {"a.py": GREET, "b.py": GREET, "c.py": GREET.replace("greet", "hi")}
    )
    for r in (PYREPO, consumer, twins):
        add(conn, r, registry.config)
    crawl(conn, registry)
    lib = (tmp_path / "pyrepo" / "lib.py").read_text(encoding="utf-8")
    commit_to_remote(
        tmp_path, "pyrepo", {"lib.py": lib.replace("return x * 2", "return x * 3")}, "edit deep"
    )
    crawl(conn, registry)
    return consumer


def test_version_and_config(registry):
    assert run("version", "--version")["version"]
    cfg = run("config", "config")
    assert cfg["registries"] and cfg["path"]


def test_resolve_every_form(registry, world):
    page = run("resolve", "resolve", "hello-world")
    assert page["kind"] == "script" and page["description"] and page["via"] is None
    top = run("resolve", "resolve", f"{PYREPO}@v1/lib.py#top")
    assert top["refs"] and top["origin"]["description"] is None
    fetch = run("resolve", "resolve", f"{PYREPO}@v1/lib.py#fetch")
    assert fetch["imports"]["third_party"] == ["requests"]
    script = run("resolve", "resolve", f"{world}@main/main.py")
    assert script["links"] and script["links"][0]["fields"]["id"]
    assert not run("resolve", "resolve", f"{PYREPO}@v1/README.md")["shape"]
    cached = run("resolve", "resolve", top["identity"])
    assert cached["via"] == "cache" and cached["locations"][0]["origin"] == "cache"
    run("resolve", "resolve", top["address"], "--id", top["identity"])
    run("error", "resolve", top["address"], "--id", "sha256:000000000000", code=1)
    run("error", "resolve", "no-such-name", code=1)


def test_resolve_latest(registry, tmp_path):
    deep = resolve(f"{PYREPO}@v1/lib.py#deep", registry)
    lib = (tmp_path / "pyrepo" / "lib.py").read_text(encoding="utf-8")
    commit_to_remote(
        tmp_path,
        "pyrepo",
        {"lib.py": lib.replace("return x * 2", "return x * 3").replace("def hyp", "def hypo")},
        "edit deep, rename hyp",
    )
    found = run("resolve --latest", "resolve", deep.address, "--latest")
    assert found["rule"] == "same-path" and found["changed"] and found["to"]["address"]
    hyp = resolve(f"{PYREPO}@v1/lib.py#hyp", registry)
    lost = run("resolve --latest", "resolve", hyp.address, "--latest", code=1)
    assert not lost["found"] and lost["rule"] is None and lost["to"] is None


def test_closure_live_and_indexed(registry, world):
    live = run("closure", "closure", f"{PYREPO}@v1/lib.py#top")
    assert live["source"] == "repository" and live["count"] == 4 and live["missing"] == []
    indexed = run(
        "closure", "closure", "--indexed", f"{world}@main/other.py", f"{PYREPO}@v1/lib.py#top"
    )
    assert indexed["source"] == "index" and len(indexed["roots"]) == 2
    assert indexed["missing"][0]["address"] == "hello-world"
    run("error", "closure", f"{PYREPO}@v1/lib.py#broken", code=1)


def test_expand_add_check_update_fold(registry, tmp_path):
    prog = tmp_path / "prog.py"
    prog.write_text(
        f"# cttp: {PYREPO}@v1/lib.py#deep track=latest\n\n# cttp: {PYREPO}@v1/lib.py#fetch\n\n"
        f"# cttp: {PYREPO}@v1/lib.py#hyp\n\nprint(deep(1), hyp(3, 4))\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    out = run("expand", "expand", str(prog), "--write-deps")
    statuses = [r["status"] for r in out["files"][str(prog)]]
    assert statuses == ["expanded", "expanded", "requires", "expanded", "deps"]
    assert run("expand", "expand", str(prog))["files"][str(prog)][0]["status"] == "unchanged"
    added = run("add", "add", "hello-world", str(prog))
    assert added["files"][str(prog)][-1]["status"] == "expanded"

    prog.write_text(prog.read_text().replace("return math.hypot(a, b)", "return 0.0"))
    prog.write_text(prog.read_text() + "# cttp: hello-world\n")
    out = run("check", "check", str(prog), code=1)
    assert not out["ok"]
    assert {r["status"] for r in out["links"][str(prog)]} == {"ok", "drift", "unexpanded"}
    out = run("check", "check", str(prog), "--fix", code=1)
    assert "fixed" in {r["status"] for r in out["links"][str(prog)]}
    prog.write_text(prog.read_text().replace("# cttp: hello-world\n", ""))
    assert run("check", "check", str(prog))["ok"]

    lib = (tmp_path / "pyrepo" / "lib.py").read_text(encoding="utf-8")
    commit_to_remote(
        tmp_path,
        "pyrepo",
        {
            "lib.py": lib.replace("return x * 2", "return x * 3").replace(
                "hypot(a, b)", "hypot(b, a)"
            )
        },
        "edit deep and hyp",
    )
    pending = run("update", "update", str(prog), "--all", code=NOT_CONFIRMED)
    assert not pending["ok"]
    assert "not-confirmed" in {r["status"] for r in pending["links"][str(prog)]}
    out = run("update", "update", str(prog), "--all", "--yes")
    statuses = {r["status"] for r in out["links"][str(prog)]}
    assert out["ok"] and statuses == {"updated", "unchanged", "upstream"}
    diffs = [r for r in out["links"][str(prog)] if r["status"] == "upstream"]
    assert diffs[0]["diff"] and diffs[0]["rule"] == "same-path"

    folded = run("fold", "fold", str(prog))
    assert [e["folded"] for e in folded["files"][str(prog)]].count(True) >= 3


def test_run_prints_no_object_but_errors_do(registry):
    assert COMMANDS["run"].schema is None
    err = run("error", "run", "hello-world", code=NOT_RUN)
    assert "pass --yes" in err["error"]
    run("error", "run", "no-such-thing", code=1)


def test_cache_commands(registry):
    resolve("hello-world", registry)
    st = run("cache status", "cache", "status")
    assert st["objects"]["count"] == 1
    assert run("cache clear", "cache", "clear")["removed"]
    assert run("cache clear", "cache", "clear")["removed"] == []


def test_index_commands(registry, tmp_path):
    out = run("index add", "index", "add", PYREPO)
    assert out["status"] == "added" and out["local_path"] is None
    assert run("index add", "index", "add", PYREPO)["status"] == "already registered"
    crawled = run("index crawl", "index", "crawl")["crawled"]
    assert crawled[0]["status"] == "crawled" and crawled[0]["definitions"] > 50
    assert run("index crawl", "index", "crawl")["crawled"][0]["status"] == "already"
    st = run("index status", "index", "status")
    assert st["counts"]["repos"] == 1 and st["repos"][0]["revisions"][0]["license"] == "MIT"
    run("error", "index", "crawl", "--index", str(tmp_path / "none.db"), code=1)


def test_queries(registry, world):
    who = run("who", "who", f"{PYREPO}@v1/lib.py#deep")
    assert who["count"] == 2 and who["by"]["is"]["asserted"] == 1
    dups = run("dups", "dups")
    assert dups["by"] == "identity" and dups["groups"][0]["names"] == ["greet"]
    shaped = run("dups", "dups", "--shape")
    assert ["greet", "hi"] in [g["names"] for g in shaped["groups"]]
    hits = run("search", "search", "greet")
    assert hits["hits"][0]["name"] == "greet" and hits["hits"][0]["locations"]
    hist = run("history", "history", f"{PYREPO}@main/lib.py#deep")
    assert hist["count"] == 2 and hist["revisions"][1]["changed"]
    assert run("rank", "rank")["ranked"][0]["name"] == "deep"
    run("error", "search", "", code=1)


# --- the schemas themselves ------------------------------------------------------------------


def test_a_schema_change_fails_until_the_version_is_bumped():
    pinned = schemas.FINGERPRINTS.get(schemas.SCHEMA_VERSION)
    assert pinned == fingerprint(), (
        f"the --json schemas changed (fingerprint {fingerprint()}, pinned {pinned}). A schema "
        "change is deliberate: bump SCHEMA_VERSION, record the new fingerprint in FINGERPRINTS, "
        "note it in PROGRESS.md, and run `python -m cttp.schemas` to regenerate the doc."
    )


def test_the_doc_matches_the_code():
    doc = ROOT / "docs" / "json-schemas.md"
    assert doc.read_text(encoding="utf-8") == markdown(), (
        "docs/json-schemas.md is stale: run `python -m cttp.schemas`"
    )


def test_every_command_has_a_schema_or_says_why():
    assert set(schemas.NO_JSON) == {"serve", "mcp"}
    for name, cmd in COMMANDS.items():
        assert cmd.usage and cmd.summary, name
        assert cmd.schema is not None or cmd.notes, f"{name}: no schema and no note saying why"


def test_the_validator_is_strict():
    assert validate("version", {"schema_version": 1, "version": "0"}) == []
    assert validate("version", {"version": "0"}) == ["$.schema_version: missing"]
    assert validate("version", {"schema_version": 1, "version": "0", "x": 1}) == [
        "$.x: not in the schema"
    ]
    assert validate("version", {"schema_version": 1, "version": None}) == [
        "$.version: null is not allowed"
    ]
    assert validate("version", {"schema_version": "1", "version": "0"}) == [
        "$.schema_version: expected an integer, got '1'"
    ]
    assert validate("dups", {"schema_version": 1, "by": "name", "groups": [], "count": 0, "origin": {"groups": "derived", "by": "derived"}}) == [  # noqa: E501
        "$.by: 'name' is not one of ['identity', 'shape']"
    ]  # fmt: skip


def test_json_schema_is_valid_and_agrees_with_the_validator(registry):
    jsonschema = pytest.importorskip("jsonschema")
    for name, cmd in COMMANDS.items():
        if cmd.schema is None:
            continue
        jsonschema.Draft202012Validator.check_schema(json_schema(name))
        jsonschema.Draft202012Validator.check_schema(json_schema(name, inline=False))
    body = json.loads(runner.invoke(app, ["--json", "resolve", "hello-world"]).stdout)
    jsonschema.Draft202012Validator(json_schema("resolve")).validate(body)
    assert set(json_schema("resolve", inline=False)["$defs"]) == set(DEFS)


def test_the_contract_object_is_the_resolve_schema(registry):
    """Spec §8: `GET /<name>.json` returns what `cttp resolve --json` prints."""
    from fastapi.testclient import TestClient

    from cttp.server.app import app as server

    body = TestClient(server).get("/hello-world.json").json()
    assert validate("resolve", body) == []
