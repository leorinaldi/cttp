"""The `cttp` command. Every subcommand accepts --json (spec §9)."""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from cttp import __version__, gitcache
from cttp.address import AddressError
from cttp.config import ConfigError, load_config
from cttp.links import LinkError
from cttp.registry import RegistryError, open_registries
from cttp.resolve import Resolved, ResolveError

app = typer.Typer(add_completion=False, no_args_is_help=True, rich_markup_mode=None)
state = {"json": False}

RegistryOpt = Annotated[
    Path | None,
    typer.Option("--registry", help="Use only this registry (a local registry repository)."),
]
JsonOpt = Annotated[bool, typer.Option("--json", help="Emit JSON.")]
ERRORS = (RegistryError, ResolveError, AddressError, gitcache.GitError, ConfigError, LinkError)
NOT_RUN = 2  # exit code of `run` when the first run of an address is not confirmed


def want_json(flag: bool) -> None:
    """`--json` is accepted both before and after the subcommand."""
    state["json"] = state["json"] or flag


def emit(data: dict | list, text: str) -> None:
    if state["json"]:
        typer.echo(json.dumps(data, indent=2))
    else:
        typer.echo(text)


def fail(message: str, code: int = 1) -> None:
    if state["json"]:
        typer.echo(json.dumps({"error": message}), err=False)
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
    json_: JsonOpt = False,
) -> None:
    """Resolve an address to the page it names."""
    want_json(json_)
    from cttp.resolve import resolve as _resolve

    try:
        r = _resolve(address, open_registries(registry), expect=id_)
    except ERRORS as e:
        fail(str(e))
    lic = r.license or "not available"
    head = f"{r.address}  {r.identity}  {r.kind}/{r.language}  license={lic}"
    if r.signature:
        head += f"\n# {r.signature}" + (f" — {r.docstring}" if r.docstring else "")
    if r.description:
        head += f"\n# {r.description}"
    emit(r.to_json(), f"{head}\n{r.source}".rstrip())


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


@app.command()
def expand(files: list[Path], registry: RegistryOpt = None, json_: JsonOpt = False) -> None:
    """Expand every unexpanded `# cttp:` link in the given files, in place."""
    want_json(json_)
    from cttp.expand import ExpandError, expand_file

    results = {}
    try:
        reg = open_registries(registry)
        for f in files:
            results[str(f)] = expand_file(f, reg)
    except (*ERRORS, ExpandError) as e:
        fail(str(e))
    emit(
        {f: [r.to_json() for r in rs] for f, rs in results.items()},
        "\n".join(
            f"{f}:{r.line}: {r.status} {r.address} {r.detail or ''}".rstrip()
            for f, rs in results.items()
            for r in rs
        )
        or "nothing to expand",
    )


@app.command()
def check(files: list[Path], registry: RegistryOpt = None, json_: JsonOpt = False) -> None:
    """Verify every link: stamped, code hashes to its id, resolvable. Exit 1 on any failure."""
    want_json(json_)
    from cttp.expand import check_file

    results = {}
    try:
        reg = open_registries(registry)
        for f in files:
            results[str(f)] = check_file(f, reg)
    except ERRORS as e:
        fail(str(e))
    bad = [r for rs in results.values() for r in rs if r.status != "ok"]
    emit(
        {"ok": not bad, "links": {f: [r.to_json() for r in rs] for f, rs in results.items()}},
        "\n".join(
            f"{f}:{r.line}: {r.status} {r.address} {r.detail or ''}".rstrip()
            for f, rs in results.items()
            for r in rs
        )
        or "no links",
    )
    if bad:
        raise typer.Exit(1)


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


def _ask_before_first_run(r: Resolved) -> bool:
    """Show what is about to run and ask; without a terminal, decline and say how to proceed."""
    from cttp.expand import NotConfirmed

    typer.echo(
        f"first run of {r.address}  {r.identity}  license={r.license or 'not available'}  "
        f"(from {r.registry})",
        err=True,
    )
    if r.description:
        typer.echo(f"  # {r.description}", err=True)
    for line in r.source.rstrip("\n").split("\n"):
        typer.echo(f"  {line}", err=True)
    if not sys.stdin.isatty():
        raise NotConfirmed(f"{r.address}: first run needs confirmation; pass --yes")
    return typer.confirm("Run it?", default=False, err=True)
