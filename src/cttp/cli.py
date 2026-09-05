"""The `cttp` command. Every subcommand accepts --json (spec §9)."""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from cttp import __version__, gitcache
from cttp.address import AddressError
from cttp.closure import ClosureError
from cttp.config import ConfigError, load_config
from cttp.index.schema import IndexingError
from cttp.links import LinkError
from cttp.registry import RegistryError, open_registries
from cttp.resolve import ResolveError
from cttp.schemas import stamp

app = typer.Typer(add_completion=False, no_args_is_help=True, rich_markup_mode=None)
cache_app = typer.Typer(no_args_is_help=True, rich_markup_mode=None)
app.add_typer(cache_app, name="cache", help="The git and object caches under ~/.cache/cttp.")
index_app = typer.Typer(no_args_is_help=True, rich_markup_mode=None)
app.add_typer(index_app, name="index", help="The index: register repositories and crawl them.")
mcp_app = typer.Typer(invoke_without_command=True, rich_markup_mode=None)
app.add_typer(mcp_app, name="mcp", help="The MCP server (stdio): the agent interface.")
name_app = typer.Typer(no_args_is_help=True, rich_markup_mode=None)
app.add_typer(name_app, name="name", help="Registry names: show an entry, claim one, verify.")
state = {"json": False}

RegistryOpt = Annotated[
    Path | None,
    typer.Option("--registry", help="Use only this registry (a local registry repository)."),
]
JsonOpt = Annotated[bool, typer.Option("--json", help="Emit JSON.")]
IndexOpt = Annotated[
    Path | None,
    typer.Option("--index", help="The index file (default ~/.local/share/cttp/index.db)."),
]
ERRORS = (
    RegistryError, ResolveError, AddressError, gitcache.GitError, ConfigError, LinkError,
    ClosureError, IndexingError,
)  # fmt: skip
NOT_RUN = 2  # exit code of `run` when the first run of an address is not confirmed
NOT_CONFIRMED = 2  # exit code of `update` when a change waited for a confirmation it did not get


def want_json(flag: bool) -> None:
    """`--json` is accepted both before and after the subcommand."""
    state["json"] = state["json"] or flag


def emit(data: dict, text: str) -> None:
    """The command's answer: the JSON object (its schema in `schemas.py`, stamped with the
    schema version) or the text."""
    if state["json"]:
        typer.echo(json.dumps(stamp(data), indent=2))
    else:
        typer.echo(text)


def fail(message: str, code: int = 1) -> None:
    if state["json"]:
        typer.echo(json.dumps(stamp({"error": message})), err=False)
    else:
        typer.echo(f"error: {message}", err=True)
    raise typer.Exit(code)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    json_: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
    version: Annotated[bool, typer.Option("--version", help="Print the version.")] = False,
) -> None:
    """cttp — code text transfer protocol."""
    state["json"] = json_
    if version:
        emit({"version": __version__}, f"cttp {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command()
def resolve(
    address: str,
    registry: RegistryOpt = None,
    id_: Annotated[
        str | None,
        typer.Option(
            "--id", help="The identity the page should have (a link's id=); exit 1 on a mismatch."
        ),
    ] = None,
    latest: Annotated[
        bool,
        typer.Option(
            "--latest",
            help="Follow a pinned address forward to the repository's head; exit 1 when not found.",
        ),
    ] = False,
    index: IndexOpt = None,
    json_: JsonOpt = False,
) -> None:
    """Resolve an address to the page it names."""
    want_json(json_)
    from cttp.resolve import resolve as _resolve

    if latest:
        return _resolve_latest(address, registry, index)
    try:
        r = _resolve(address, open_registries(registry), expect=id_)
    except ERRORS as e:
        fail(str(e))
    lic = r.license or "not available"
    head = f"{r.address}  {r.identity}  {r.kind}/{r.language}  license={lic}"
    if r.via:
        head += f"  (from the object {r.via}; seen at {len(r.locations)} location(s))"
        head += "".join(f"\n# seen: {x['address']}  {x['seen']}" for x in r.locations)
    if r.signature:
        head += f"\n# {r.signature}" + (f" — {r.docstring}" if r.docstring else "")
    if r.description:
        head += f"\n# {r.description}"
    emit(r.to_json(), f"{head}\n{r.source}".rstrip())


def _resolve_latest(address: str, registry: Path | None, index: Path | None) -> None:
    from cttp.resolve import latest as _latest

    try:
        found = _latest(address, open_registries(registry), index)
    except ERRORS as e:
        fail(str(e))
    lines = [f"{found.pinned.address}  {found.pinned.identity}"]
    if found.to:
        lines.append(
            f"-> {found.to.address}  {found.to.identity}  rule={found.rule}"
            + (f" via {found.via}" if found.via else "")
            + f"  {found.message}"
        )
        lines += [
            "",
            *(f"  {line}" for line in found.to.source.rstrip("\n").split("\n")),
        ]
    else:
        lines.append(f"-> not found at {found.head[:12]}: {found.message}")
    emit(found.to_json(), "\n".join(lines))
    if not found.found:
        raise typer.Exit(1)


@app.command()
def closure(
    addresses: Annotated[list[str], typer.Argument(help="One address; several with --indexed.")],
    indexed: Annotated[
        bool,
        typer.Option("--indexed", help="From the index's recorded links, not a live walk."),
    ] = False,
    registry: RegistryOpt = None,
    index: IndexOpt = None,
    json_: JsonOpt = False,
) -> None:
    """Everything the page needs to run inline, dependencies first: what `expand` would write."""
    want_json(json_)
    if indexed or len(addresses) > 1:
        return _closure_indexed(addresses, registry, index)
    from cttp.closure import closure as _closure

    try:
        c = _closure(addresses[0], open_registries(registry), budget=None)
    except ERRORS as e:
        fail(str(e))
    lines = [
        f"{n.page.address}  {n.page.identity}  {n.page.kind}  {n.lines} line(s)  via {n.via}"
        for n in c.nodes
    ]
    if c.imports:
        lines.append("imports: " + "; ".join(c.imports))
    lines.append("requires: " + (", ".join(c.requires) or "nothing outside the stdlib"))
    lines.append(f"{len(c.nodes)} definition(s), {c.lines} line(s)")
    emit(c.to_json(), "\n".join(lines))


def _closure_indexed(addresses: list[str], registry: Path | None, index: Path | None) -> None:
    from cttp.index.queries import closure as _closure

    try:
        c = _closure(_open_index(index), addresses, open_registries(registry))
    except ERRORS as e:
        fail(str(e))
    lines = [
        f"{n['address']}  {n['identity']}  {n['kind']}  {n['lines']} line(s)  via {n['via']}"
        for n in c["definitions"]
    ]
    if c["imports"]:
        lines.append("imports: " + "; ".join(c["imports"]))
    lines.append("requires: " + (", ".join(c["requires"]) or "nothing outside the stdlib"))
    lines += [f"missing: {m['address']} ({m['relation']} from {m['from']})" for m in c["missing"]]
    lines.append(f"{c['count']} definition(s), {c['lines']} line(s), from the index")
    emit(c, "\n".join(lines))


@app.command()
def config(registry: RegistryOpt = None, json_: JsonOpt = False) -> None:
    """Show the effective configuration: the file, the registry list, the remotes."""
    want_json(json_)
    try:
        cfg = load_config(registry)
    except ERRORS as e:
        fail(str(e))
    lines = [f"config: {cfg.path or 'not present; defaults'}", "registries:"]
    lines += [f"  {r}" for r in cfg.registries]
    lines.append("remotes:" + ("" if cfg.remotes else " (none)"))
    lines += [f"  {k} -> {v}" for k, v in cfg.remotes.items()]
    emit(cfg.to_json(), "\n".join(lines))


@app.command()
def serve(
    port: Annotated[int, typer.Option("--port")] = 3120,
    registry: RegistryOpt = None,
    json_: JsonOpt = False,
) -> None:
    """Serve the registry contract and the viewer on http://localhost:3120."""
    want_json(json_)
    import os

    import uvicorn

    try:
        reg = open_registries(registry, local_only=True)
    except ERRORS as e:
        fail(str(e))
    if registry:
        os.environ["CTTP_REGISTRY"] = str(registry)
    typer.echo(f"cttp registry {reg.describe()} — http://localhost:{port}", err=True)
    uvicorn.run("cttp.server.app:app", host="127.0.0.1", port=port, log_level="warning")


PackageOpt = Annotated[
    bool,
    typer.Option(
        "--package",
        help="Write the closure into cttp_vendor/<module>.py and an import beneath the link.",
    ),
]
WriteDepsOpt = Annotated[
    bool,
    typer.Option(
        "--write-deps", help="Add third-party requirements to pyproject.toml dependencies."
    ),
]


def _report_lines(results: dict[str, list]) -> str:
    return "\n".join(
        f"{f}:{r.line}: {r.status} {r.address} {r.detail or ''}".rstrip()
        if r.line
        else f"{f}: {r.status} {r.address}: {r.detail or ''}".rstrip()
        for f, rs in results.items()
        for r in rs
    )


@app.command()
def expand(
    files: list[Path],
    registry: RegistryOpt = None,
    package: PackageOpt = False,
    write_deps: WriteDepsOpt = False,
    json_: JsonOpt = False,
) -> None:
    """Expand every unexpanded `# cttp:` link in the given files, in place, with its closure."""
    want_json(json_)
    from cttp.expand import ExpandError, expand_file

    results = {}
    try:
        reg = open_registries(registry)
        for f in files:
            results[str(f)] = expand_file(f, reg, package, write_deps)
    except (*ERRORS, ExpandError) as e:
        fail(str(e))
    emit(
        {"files": {f: [r.to_json() for r in rs] for f, rs in results.items()}},
        _report_lines(results) or "nothing to expand",
    )


@app.command()
def add(
    address: str,
    file: Annotated[
        Path, typer.Argument(help="The file to add the link to; default main.py.")
    ] = Path("main.py"),
    at: Annotated[
        int | None, typer.Option("--at", help="Insert the link before this 1-based line.")
    ] = None,
    registry: RegistryOpt = None,
    package: PackageOpt = False,
    json_: JsonOpt = False,
) -> None:
    """Write `# cttp: <address>` into the file (creating it if needed) and expand it."""
    want_json(json_)
    from cttp.expand import ExpandError, add_link

    try:
        reports = add_link(address, file, open_registries(registry), at, package)
    except (*ERRORS, ExpandError) as e:
        fail(str(e))
    emit(
        {"files": {str(file): [r.to_json() for r in reports]}}, _report_lines({str(file): reports})
    )


@app.command()
def check(
    files: list[Path],
    registry: RegistryOpt = None,
    fix: Annotated[
        bool,
        typer.Option("--fix", help="Turn each drifted `# cttp:` link into `# cttp-from:`."),
    ] = False,
    json_: JsonOpt = False,
) -> None:
    """Verify every link: stamped, code hashes to its id, resolvable. Exit 1 on any failure."""
    want_json(json_)
    from cttp.expand import check_file

    results = {}
    try:
        reg = open_registries(registry)
        for f in files:
            results[str(f)] = check_file(f, reg, fix)
    except ERRORS as e:
        fail(str(e))
    bad = [r for rs in results.values() for r in rs if r.status not in ("ok", "fixed")]
    emit(
        {"ok": not bad, "links": {f: [r.to_json() for r in rs] for f, rs in results.items()}},
        _report_lines(results) or "no links",
    )
    if bad:
        raise typer.Exit(1)


@app.command()
def update(
    targets: Annotated[
        list[str], typer.Argument(help="Files to update, and optionally addresses to select.")
    ],
    all_: Annotated[bool, typer.Option("--all", help="Update every stamped link.")] = False,
    to: Annotated[
        str | None, typer.Option("--to", help="Move to this rev instead of the latest.")
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Apply every change without asking.")] = False,
    registry: RegistryOpt = None,
    json_: JsonOpt = False,
) -> None:
    """Follow pinned links forward and rewrite stamp and code on confirmation.

    Selects links marked track=latest (or all, under a project cttp.toml with track = "latest");
    name addresses to select those links, or pass --all. A `# cttp-from:` link is never rewritten:
    the upstream diff since the fork is shown instead. Exit 2 when a change waits for confirmation.
    """
    want_json(json_)
    from cttp.expand import is_address, update_file

    files = [Path(t) for t in targets if not is_address(t)]
    addresses = [t for t in targets if is_address(t)]
    if not files:
        fail("update needs at least one file to update")
    confirm = None if yes else _ask_before_update
    results = {}
    try:
        reg = open_registries(registry)
        for f in files:
            results[str(f)] = update_file(f, reg, addresses, all_, to, confirm)
    except ERRORS as e:
        fail(str(e))
    except FileNotFoundError as e:
        fail(f"{e.filename}: no such file")
    pending = [r for rs in results.values() for r in rs if r.status == "not-confirmed"]
    text = []
    for f, rs in results.items():
        for r in rs:
            text.append(f"{f}:{r.line}: {r.status} {r.address} {r.detail or ''}".rstrip())
            if r.extra.get("diff") and (state["json"] is False) and r.status == "upstream":
                text += ["  " + line for line in r.extra["diff"].rstrip("\n").split("\n")]
    emit(
        {"ok": not pending, "links": {f: [r.to_json() for r in rs] for f, rs in results.items()}},
        "\n".join(text) or "no links selected",
    )
    if pending:
        raise typer.Exit(NOT_CONFIRMED)


def _interactive() -> bool:
    """Whether a person can answer a prompt. Tests patch this to exercise the prompts."""
    return sys.stdin.isatty()


def _ask_before_update(up) -> bool:
    typer.echo(f"{up.message}", err=True)
    for line in up.diff.rstrip("\n").split("\n"):
        typer.echo(f"  {line}", err=True)
    if not _interactive():
        typer.echo("  (not applied: pass --yes to apply without a terminal)", err=True)
        return False
    return typer.confirm("Apply it?", default=False, err=True)


@app.command()
def fold(
    files: list[Path],
    open_: Annotated[
        list[str] | None,
        typer.Option("--open", help="Leave this link's block unfolded (repeatable)."),
    ] = None,
    json_: JsonOpt = False,
) -> None:
    """Print each file with every expanded block collapsed to its link line. Writes nothing."""
    want_json(json_)
    from cttp.expand import fold_text

    out: dict[str, list] = {}
    texts: list[str] = []
    try:
        for f in files:
            folded, entries = fold_text(f.read_text(encoding="utf-8"), open_ or [])
            out[str(f)] = entries
            texts.append(folded if len(files) == 1 else f"==> {f} <==\n{folded}")
    except LinkError as e:
        fail(str(e))
    except FileNotFoundError as e:
        fail(f"{e.filename}: no such file")
    emit({"files": out}, "\n".join(t.rstrip("\n") for t in texts))


@cache_app.command("status")
def cache_status(json_: JsonOpt = False) -> None:
    """What the caches hold: repositories, objects, run-cache entries."""
    want_json(json_)
    from cttp.objects import status

    st = status()
    emit(
        st,
        f"cache: {st['home']}\n"
        + "\n".join(
            f"  {k}: {st[k]['count']} ({st[k]['bytes'] / 1e6:.1f} MB)"
            for k in ("repos", "objects", "run")
        ),
    )


@cache_app.command("clear")
def cache_clear(
    run: Annotated[
        bool, typer.Option("--run", help="Also clear the run cache (what was confirmed to run).")
    ] = False,
    json_: JsonOpt = False,
) -> None:
    """Remove the cached repositories and objects; the run cache only with --run."""
    want_json(json_)
    from cttp.objects import clear

    removed = clear(run=run)
    emit({"removed": removed}, "\n".join(f"removed {p}" for p in removed) or "nothing to remove")


@app.command()
def run(
    target: str,
    registry: RegistryOpt = None,
    yes: Annotated[
        bool, typer.Option("--yes", help="Run without asking on the first run of an address.")
    ] = False,
    json_: JsonOpt = False,
) -> None:
    """Run an address, or a file with links, without touching the file.

    The first run of an address shows its source, hash and license and asks; later runs of the
    same pinned address do not. Exit code 2 when not confirmed.
    """
    want_json(json_)
    from cttp.expand import ExpandError, NotConfirmed, is_address, run_address, run_file

    confirm = None if yes else _ask_before_first_run
    try:
        reg = open_registries(registry)
        if is_address(target):
            code = run_address(target, reg, confirm)
        else:
            code = run_file(Path(target), reg, confirm)
    except NotConfirmed as e:
        fail(str(e), NOT_RUN)
    except (*ERRORS, ExpandError) as e:
        fail(str(e))
    except FileNotFoundError:
        fail(f"{target!r} is neither an address nor a file")
    sys.exit(code)


def _ask_before_first_run(c) -> bool:
    """Show everything about to run — every page of the closure, with source, identity and
    license — and ask; without a terminal, decline and say how to proceed."""
    from cttp.expand import NotConfirmed

    r = c.root
    deps = f"; {len(c.nodes) - 1} dependenc(ies)" if len(c.nodes) > 1 else ""
    typer.echo(
        f"first run of {r.address}  {r.identity}  license={r.license or 'not available'}  "
        f"(from {r.registry}){deps}",
        err=True,
    )
    for n in c.nodes:
        p = n.page
        if len(c.nodes) > 1:
            typer.echo(
                f"  {p.address}  {p.identity}  license={p.license or 'not available'}", err=True
            )
        if n.description:
            typer.echo(f"  # {n.description}", err=True)
        for line in p.source.rstrip("\n").split("\n"):
            typer.echo(f"  {line}", err=True)
    if c.requires:
        typer.echo(f"  requires: {', '.join(c.requires)}", err=True)
    if not _interactive():
        raise NotConfirmed(f"{r.address}: first run needs confirmation; pass --yes")
    return typer.confirm("Run it?", default=False, err=True)


# --- the index ---------------------------------------------------------------------------------


def _index_path(index: Path | None) -> Path:
    from cttp.index.schema import default_index_path

    return index or default_index_path()


def _open_index(index: Path | None):
    from cttp.index.schema import open_index

    return open_index(_index_path(index), create=False)


@index_app.command("add")
def index_add(
    target: str, registry: RegistryOpt = None, index: IndexOpt = None, json_: JsonOpt = False
) -> None:
    """Register a repository to crawl: host/owner/repo, or a local clone whose origin names one."""
    want_json(json_)
    from cttp.index.crawl import add
    from cttp.index.schema import open_index

    try:
        out = add(open_index(_index_path(index)), target, load_config(registry))
    except ERRORS as e:
        fail(str(e))
    where = f" (from {out['local_path']})" if out["local_path"] else ""
    emit(out, f"{out['status']}: {out['repo']}{where}")


@index_app.command("crawl")
def index_crawl(
    repos: Annotated[
        list[str] | None, typer.Argument(help="Only these registered repositories.")
    ] = None,
    rev: Annotated[
        str | None, typer.Option("--rev", help="Crawl this revision instead of the head.")
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Crawl a revision again even if it was crawled.")
    ] = False,
    registry: RegistryOpt = None,
    index: IndexOpt = None,
    json_: JsonOpt = False,
) -> None:
    """Crawl every registered repository at its head (or --rev): definitions, references, links."""
    want_json(json_)
    from cttp.index.crawl import crawl
    from cttp.index.schema import open_index

    try:
        results = crawl(
            open_index(_index_path(index)), open_registries(registry), rev, repos, force
        )
    except ERRORS as e:
        fail(str(e))
    lines = []
    for r in results:
        if r.status == "already":
            lines.append(f"{r.repo}@{r.sha[:12]}: already crawled")
        else:
            lines.append(
                f"{r.repo}@{r.sha[:12]}: {r.files} file(s), {r.pages} page(s), "
                f"{r.definitions} new identity(ies), {r.links} link(s)"
                + (f", {len(r.skipped)} skipped" if r.skipped else "")
            )
            lines += [f"  skipped {x}" for x in r.skipped]
    emit({"crawled": [r.to_json() for r in results]}, "\n".join(lines))


@index_app.command("status")
def index_status(index: IndexOpt = None, json_: JsonOpt = False) -> None:
    """What the index holds: repositories, revisions, and row counts."""
    want_json(json_)
    from cttp.index.crawl import status
    from cttp.index.schema import open_index

    path = _index_path(index)
    try:
        st = status(open_index(path, create=False), path)
    except ERRORS as e:
        fail(str(e))
    c = st["counts"]
    lines = [
        f"index: {st['index']}",
        "  " + ", ".join(f"{k}: {v}" for k, v in c.items()),
    ]
    for r in st["repos"]:
        revs = ", ".join(v["sha"][:12] for v in r["revisions"]) or "not crawled"
        lines.append(f"  {r['repo']}  [{r['default_branch'] or '?'}]  {revs}")
    emit(st, "\n".join(lines))


# --- the queries (spec §6) ---------------------------------------------------------------------


@app.command()
def who(
    address: str, registry: RegistryOpt = None, index: IndexOpt = None, json_: JsonOpt = False
) -> None:
    """Backlinks: every indexed page linking to the address, by relation and origin."""
    want_json(json_)
    from cttp.index.queries import who as _who

    try:
        out = _who(_open_index(index), address, open_registries(registry))
    except ERRORS as e:
        fail(str(e))
    lines = [
        f"{b['source']['address']}:{b['line']}  {b['relation']}  {b['origin']}  "
        f"license={b['source']['license'] or 'not available'}  -> {b['target']}"
        for b in out["backlinks"]
    ]
    lines.append(f"{out['count']} backlink(s) to {address}")
    emit(out, "\n".join(lines))


@app.command()
def dups(
    shape: Annotated[
        bool, typer.Option("--shape", help="Group by shape (same structure) instead of identity.")
    ] = False,
    index: IndexOpt = None,
    json_: JsonOpt = False,
) -> None:
    """Groups of pages that are the same code, in more than one place."""
    want_json(json_)
    from cttp.index.queries import dups as _dups

    try:
        out = _dups(_open_index(index), by_shape=shape)
    except ERRORS as e:
        fail(str(e))
    lines = []
    for g in out["groups"]:
        lines.append(
            f"{g['key']}  {g['kind']}  {', '.join(g['names'])}  x{g['count']}  {g['lines']} line(s)"
        )
        lines += [f"  {x['address']}" for x in g["locations"]]
    lines.append(f"{out['count']} group(s) by {out['by']}")
    emit(out, "\n".join(lines))


@app.command()
def search(
    text: Annotated[list[str], typer.Argument(help="Words to look for.")],
    limit: Annotated[int, typer.Option("--limit")] = 20,
    index: IndexOpt = None,
    json_: JsonOpt = False,
) -> None:
    """Find pages by name, signature or docstring."""
    want_json(json_)
    from cttp.index.queries import search as _search

    try:
        out = _search(_open_index(index), " ".join(text), limit)
    except ERRORS as e:
        fail(str(e))
    lines = [
        f"{h['address']}  {h['identity']}  {h['kind']}"
        + (f"  {h['signature']}" if h["signature"] else "")
        + (f"  — {h['docstring']}" if h["docstring"] else "")
        for h in out["hits"]
    ]
    lines.append(f"{out['count']} hit(s) for {out['query']!r}")
    emit(out, "\n".join(lines))


@app.command()
def history(
    address: str, registry: RegistryOpt = None, index: IndexOpt = None, json_: JsonOpt = False
) -> None:
    """The identities seen at one place (repository, path, symbol) over crawled revisions."""
    want_json(json_)
    from cttp.index.queries import history as _history

    try:
        out = _history(_open_index(index), address, open_registries(registry))
    except ERRORS as e:
        fail(str(e))
    lines = [
        f"{v['address']}  {v['identity'] or 'absent'}"
        + ("  changed" if v["changed"] and not v["absent"] else "")
        for v in out["revisions"]
    ]
    lines.append(f"{len(out['identities'])} identity(ies) over {out['count']} revision(s)")
    emit(out, "\n".join(lines))


@app.command()
def rank(
    limit: Annotated[int, typer.Option("--limit")] = 20,
    index: IndexOpt = None,
    json_: JsonOpt = False,
) -> None:
    """Pages ordered by how many distinct pages link to them."""
    want_json(json_)
    from cttp.index.queries import rank as _rank

    try:
        out = _rank(_open_index(index), limit)
    except ERRORS as e:
        fail(str(e))
    lines = [
        f"{r['backlinks']:4}  {r['address']}  {r['identity']}  {r['kind']}" for r in out["ranked"]
    ]
    lines.append(f"{out['count']} ranked")
    emit(out, "\n".join(lines))


# --- names (spec §8) ---------------------------------------------------------------------------


def _entry_lines(entry) -> list[str]:
    lines = []
    if entry.description:
        lines.append(f"  description: {entry.description}")
    lines.append(f"  owner: {entry.owner or 'not available'}")
    lines.append(f"  target: {entry.target}")
    lines.append(f"  default: {entry.default}")
    versions = ", ".join(f"{k} = {v}" for k, v in entry.versions.items()) or "(none)"
    lines.append(f"  versions: {versions}")
    return lines


@name_app.command("show")
def name_show(name: str, registry: RegistryOpt = None, json_: JsonOpt = False) -> None:
    """A registry entry — target, owner, labels — and what the name resolves to."""
    want_json(json_)
    from cttp.address import parse
    from cttp.registry import entry_json
    from cttp.resolve import resolve as _resolve

    try:
        a = parse(name)
        if a.form != "name":
            raise AddressError(f"{name!r} is not a name; `name show` takes a registry name")
        reg = open_registries(registry)
        entry, which = reg.lookup(a.name)
        r = _resolve(str(a), reg)
    except ERRORS as e:
        fail(str(e))
    lic = r.license or "not available"
    lines = [f"{entry.name}  (registry {which.describe()})", *_entry_lines(entry)]
    lines.append(f"resolves to {r.address}  {r.identity}  {r.kind}/{r.language}  license={lic}")
    if r.signature:
        lines.append(f"# {r.signature}" + (f" — {r.docstring}" if r.docstring else ""))
    emit(
        {
            "name": entry.name,
            "registry": which.describe(),
            "entry": entry_json(entry),
            "resolution": r.to_json(),
            "origin": {"entry": "asserted", "resolution": "derived"},
        },
        "\n".join(lines),
    )


@name_app.command("claim")
def name_claim(
    name: str,
    target: Annotated[
        str, typer.Option("--target", help="host/owner/repo[/path]: what the name points at.")
    ],
    description: Annotated[
        str | None, typer.Option("--description", help="One line, copied onto link lines.")
    ] = None,
    version: Annotated[
        list[str] | None,
        typer.Option("--version", help="label=ref (repeatable); default: latest=<branch>."),
    ] = None,
    default: Annotated[
        str | None, typer.Option("--default", help="The label the short form resolves to.")
    ] = None,
    transfer: Annotated[
        bool,
        typer.Option("--transfer", help="Take over another owner's name (a PR they approve)."),
    ] = False,
    no_pr: Annotated[
        bool,
        typer.Option("--no-pr", help="Write names/<name>.toml into the clone; no pull request."),
    ] = False,
    registry: RegistryOpt = None,
    json_: JsonOpt = False,
) -> None:  # fmt: skip
    """Claim a name for a target that declares it in its cttp.toml (spec §8: proof of control).

    Writes names/<name>.toml and opens a pull request against the registry repository with `gh`
    (the entry is committed on a claim/<name> branch in a temporary worktree; the clone's checkout
    is untouched). With --no-pr the file is written into the clone for you to commit.
    """
    want_json(json_)
    from cttp.registry import claim as _claim

    versions: dict[str, str] = {}
    for item in version or []:
        label, sep, ref = item.partition("=")
        if not sep or not label or not ref:
            fail(f"--version takes label=ref, not {item!r}")
        versions[label] = ref
    try:
        c = _claim(
            name, target, open_registries(registry), description, default, versions or None,
            transfer=transfer, pr=not no_pr,
        )  # fmt: skip
    except ERRORS as e:
        fail(str(e))
    head = f"{c.action} {c.entry.name} -> {c.entry.target}  owner={c.entry.owner}"
    if c.previous_owner and c.previous_owner != c.entry.owner:
        head += f"  (was {c.previous_owner})"
    lines = [
        head,
        f"declared in {c.declaration.file} at {c.declaration.branch} "
        f"({c.declaration.sha[:12]}) of {c.declaration.locator}",
    ]
    lines += [f"  {k.check}: {k.detail}" for k in c.checks]
    if c.written_to:
        lines.append(f"wrote {c.written_to}:")
        lines += [f"  {line}" for line in c.text.rstrip("\n").split("\n")]
        lines.append("commit it to the registry repository, or open a pull request")
    else:
        lines.append(f"pushed {c.branch}; pull request: {c.pr}")
    emit(c.to_json(), "\n".join(lines))


# --- the MCP server (spec §9) ------------------------------------------------------------------


@mcp_app.callback()
def mcp(
    ctx: typer.Context,
    registry: RegistryOpt = None,
    index: IndexOpt = None,
    json_: JsonOpt = False,
) -> None:
    """Run the MCP server over stdio: resolve, who, closure, search, dups, fold as tools."""
    want_json(json_)
    if ctx.invoked_subcommand is not None:
        return
    import os

    from cttp.mcp import serve

    try:
        open_registries(registry)
    except ERRORS as e:
        fail(str(e))
    if registry:
        os.environ["CTTP_REGISTRY"] = str(registry)
    if index:
        os.environ["CTTP_INDEX"] = str(index)
    serve()


@mcp_app.command("install")
def mcp_install(
    claude_code: Annotated[
        bool,
        typer.Option("--claude-code", help="Run the `claude mcp add` line, not just print it."),
    ] = False,
    json_: JsonOpt = False,
) -> None:
    """Print (or with --claude-code run) the `claude mcp add` line that attaches the server."""
    want_json(json_)
    import shlex
    import subprocess

    from cttp.mcp import install_command

    command = install_command()
    output = None
    if claude_code:
        try:
            done = subprocess.run(command, capture_output=True, text=True)
        except FileNotFoundError:
            fail("`claude` is not on PATH; install Claude Code first, or run the line by hand")
        output = (done.stdout + done.stderr).strip()
        if done.returncode != 0:
            fail(f"`{shlex.join(command)}` failed: {output}")
    emit(
        {"command": command, "ran": claude_code, "output": output},
        shlex.join(command) if output is None else output,
    )
