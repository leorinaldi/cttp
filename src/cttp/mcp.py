"""`cttp mcp`: the agent interface as an MCP server over stdio. Spec §9, plan P5-T2.

Six tools — `resolve`, `who`, `closure`, `search`, `dups`, `fold` — each calling the same function
the CLI calls and returning the same object `cttp <command> --json` prints (`schemas.py`), as the
call's `structuredContent` with the JSON as text beside it; each tool publishes its P5-T1 schema
as `outputSchema`. The design rule is spec §9's: return the definition, not the file. A failure
is a tool error carrying the message the CLI would print after `error:`.

`cttp mcp` runs the server; `cttp mcp install` prints (or, with `--claude-code`, runs) the
`claude mcp add` line that attaches it to Claude Code.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.tools.base import Tool
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from cttp import __version__, gitcache
from cttp.address import AddressError
from cttp.closure import ClosureError
from cttp.config import ConfigError
from cttp.index.schema import IndexingError, default_index_path, open_index
from cttp.links import LinkError
from cttp.registry import RegistryError, open_registries
from cttp.resolve import ResolveError
from cttp.schemas import COMMANDS, json_schema, stamp

ERRORS = (
    RegistryError, ResolveError, AddressError, gitcache.GitError, ConfigError, LinkError,
    ClosureError, IndexingError, FileNotFoundError,
)  # fmt: skip
TOOLS = ("resolve", "who", "closure", "search", "dups", "fold")
INSTRUCTIONS = (
    "cttp lets code point at code: every definition has an address, a reference is a link "
    "(`# cttp: <address>`), and an index answers who links where. Use `resolve` for one "
    "definition's text, `closure` for exactly what a definition needs to run, `fold` to read a "
    "file as its links, `who` for backlinks, `search` to find a definition by name or docstring, "
    "and `dups` for copies worth turning into links. Every result is the object "
    "`cttp <tool> --json` prints; `docs/json-schemas.md` documents it."
)


def _result(data: dict) -> CallToolResult:
    obj = stamp(data)
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(obj, indent=2))],
        structured_content=obj,
    )


def _describe(command: str) -> str:
    c = COMMANDS[command]
    parts = [c.summary]
    if c.when:
        parts.append(c.when)
    parts += c.notes
    return " ".join(parts) + f" Same object as `{c.usage}`."


# --- the tools ---------------------------------------------------------------------------------


def resolve(address: str, id: str | None = None) -> CallToolResult:
    """The page an address names — a name, a locator, or an identity — with its own text."""
    from cttp.resolve import resolve as _resolve

    try:
        return _result(_resolve(address, open_registries(), expect=id).to_json())
    except ERRORS as e:
        raise ToolError(str(e)) from e


def who(address: str) -> CallToolResult:
    """Backlinks: every indexed page linking to the address."""
    from cttp.index.queries import who as _who

    try:
        return _result(_who(_index(), address, open_registries()))
    except ERRORS as e:
        raise ToolError(str(e)) from e


def closure(addresses: list[str], indexed: bool = False) -> CallToolResult:
    """The definitions a page needs to run inline, dependencies first. Several addresses, or
    `indexed`, read the index's recorded links instead of walking the repositories."""
    try:
        if indexed or len(addresses) != 1:
            from cttp.index.queries import closure as _indexed

            return _result(_indexed(_index(), addresses, open_registries()))
        from cttp.closure import closure as _closure

        return _result(_closure(addresses[0], open_registries(), budget=None).to_json())
    except ERRORS as e:
        raise ToolError(str(e)) from e


def search(text: str, limit: int = 20) -> CallToolResult:
    """Pages whose name, signature or docstring match the words."""
    from cttp.index.queries import search as _search

    try:
        return _result(_search(_index(), text, limit))
    except ERRORS as e:
        raise ToolError(str(e)) from e


def dups(shape: bool = False) -> CallToolResult:
    """Groups of pages that are the same code in more than one place."""
    from cttp.index.queries import dups as _dups

    try:
        return _result(_dups(_index(), by_shape=shape))
    except ERRORS as e:
        raise ToolError(str(e)) from e


def fold(file: str, open: list[str] | None = None) -> CallToolResult:  # noqa: A002
    """A file as its links: every expanded block collapsed to its link line, with line ranges."""
    from cttp.expand import fold_text

    try:
        _, entries = fold_text(Path(file).read_text(encoding="utf-8"), open or [])
    except ERRORS as e:
        raise ToolError(str(e)) from e
    return _result({"files": {file: entries}})


def _index():
    return open_index(default_index_path(), create=False)


# --- the server --------------------------------------------------------------------------------

FUNCTIONS = {"resolve": resolve, "who": who, "closure": closure}
FUNCTIONS |= {"search": search, "dups": dups, "fold": fold}
REACHES_OUT = {"resolve", "closure"}  # may clone or fetch a repository; the rest read local files


def build_server() -> MCPServer:
    """The server with the six tools; every tool is read-only and idempotent."""
    tools = []
    for name in TOOLS:
        tool = Tool.from_function(
            FUNCTIONS[name],
            name=name,
            description=_describe(name),
            annotations=ToolAnnotations(
                title=f"cttp {name}",
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=name in REACHES_OUT,
            ),
            structured_output=False,  # the function builds the CallToolResult itself
        )
        tool.fn_metadata.output_schema = json_schema(name)  # advertised; P5-T1 tests validate it
        tools.append(tool)
    return MCPServer("cttp", version=__version__, instructions=INSTRUCTIONS, tools=tools)


def serve() -> None:
    build_server().run("stdio")


def install_command() -> list[str]:
    """The `claude mcp add` line that attaches this server to Claude Code."""
    exe = shutil.which("cttp") or sys.argv[0]
    return [
        "claude",
        "mcp",
        "add",
        "--transport",
        "stdio",
        "cttp",
        "--",
        str(Path(exe).resolve()),
        "mcp",
    ]
