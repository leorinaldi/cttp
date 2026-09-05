"""Plan P5-T2: the MCP server lists six tools, each answering exactly what the CLI's `--json`
prints, with the P5-T1 schema as its output schema; `cttp mcp install` prints the attach line."""

import json

import anyio
import pytest
from conftest import add_remote_repo
from mcp.client import Client
from typer.testing import CliRunner

from cttp.cli import app
from cttp.expand import expand_file
from cttp.index.crawl import add, crawl
from cttp.index.schema import open_index
from cttp.mcp import TOOLS, build_server, install_command
from cttp.schemas import json_schema, validate

runner = CliRunner()
PYREPO = "github.com/leorinaldi/pyrepo"
GREET = 'def greet(name: str) -> str:\n    """Say hello."""\n    return f"hi {name}"\n'


@pytest.fixture
def world(registry, tmp_path):
    """pyrepo and twins crawled; `main.py` with `deep` expanded."""
    conn = open_index(tmp_path / "index.db")
    main = tmp_path / "main.py"
    main.write_text(f"# cttp: {PYREPO}@v1/lib.py#deep\n\nprint(deep(2))\n", encoding="utf-8")
    expand_file(main, registry)
    twins = add_remote_repo(tmp_path, "twins", {"a.py": GREET, "b.py": GREET})
    for r in (PYREPO, twins):
        add(conn, r, registry.config)
    crawl(conn, registry)
    return main


def call(name: str, arguments: dict):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments)

    return anyio.run(go)


def cli(*args: str) -> dict:
    res = runner.invoke(app, ["--json", *args])
    assert res.exit_code == 0, res.output
    return json.loads(res.stdout)


def test_lists_six_tools_with_schemas_and_read_only_hints():
    async def go():
        async with Client(build_server()) as client:
            return (await client.list_tools()).tools

    tools = anyio.run(go)
    assert [t.name for t in tools] == list(TOOLS)
    assert list(TOOLS) == ["resolve", "who", "closure", "search", "dups", "fold"]
    for t in tools:
        assert t.output_schema == json_schema(t.name)
        assert t.annotations.read_only_hint and not t.annotations.destructive_hint
        assert "Same object as `cttp " in t.description


def test_every_tool_answers_what_the_cli_prints(registry, world):
    top, deep = f"{PYREPO}@v1/lib.py#top", f"{PYREPO}@v1/lib.py#deep"
    cases = {
        "resolve": ({"address": top}, ["resolve", top]),
        "who": ({"address": deep}, ["who", deep]),
        "closure": ({"addresses": [top]}, ["closure", top]),
        "search": ({"text": "greet"}, ["search", "greet"]),
        "dups": ({}, ["dups"]),
        "fold": ({"file": str(world)}, ["fold", str(world)]),
    }
    for name, (arguments, args) in cases.items():
        result = call(name, arguments)
        assert not result.is_error, result.content
        assert result.structured_content == cli(*args), name
        assert json.loads(result.content[0].text) == result.structured_content
        assert validate("fold" if name == "fold" else name, result.structured_content) == []


def test_closure_indexed_and_resolve_by_identity(registry, world):
    top = call("resolve", {"address": f"{PYREPO}@v1/lib.py#top"}).structured_content
    by_id = call("resolve", {"address": top["identity"]}).structured_content
    assert by_id["via"] == "cache" and by_id["source"] == top["source"]
    two = call("closure", {"addresses": [f"{PYREPO}@v1/lib.py#hyp", f"{PYREPO}@v1/lib.py#top"]})
    assert two.structured_content["source"] == "index" and len(two.structured_content["roots"]) == 2
    one = call("closure", {"addresses": [f"{PYREPO}@v1/lib.py#top"], "indexed": True})
    assert one.structured_content["source"] == "index"


def test_failures_are_tool_errors_with_the_cli_message(registry, world):
    res = call("resolve", {"address": "no-such-name"})
    assert res.is_error and "no-such-name" in res.content[0].text
    res = call("resolve", {"address": f"{PYREPO}@v1/lib.py#top", "id": "sha256:000000000000"})
    assert res.is_error and "sha256:000000000000" in res.content[0].text
    res = call("closure", {"addresses": [f"{PYREPO}@v1/lib.py#broken"]})
    assert res.is_error and "missing" in res.content[0].text
    res = call("fold", {"file": "/nonexistent.py"})
    assert res.is_error
    res = call("search", {"text": ""})
    assert res.is_error and "search needs some text" in res.content[0].text


def test_install_line(registry):
    command = install_command()
    assert command[:3] == ["claude", "mcp", "add"] and command[-1] == "mcp"
    res = runner.invoke(app, ["mcp", "install"])
    assert res.exit_code == 0 and res.stdout.startswith("claude mcp add --transport stdio cttp --")
    out = cli("mcp", "install")
    assert validate("mcp install", out) == [] and out["ran"] is False and out["output"] is None
