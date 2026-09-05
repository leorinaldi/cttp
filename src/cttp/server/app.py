"""`cttp serve`: the registry contract (spec §8) and the viewer (spec §9) on port 3120.

The three name routes and an index page, over the configured **local** registry repositories —
the server never asks an HTTP registry, which could be itself.
"""

from pathlib import Path

import jinja2
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from cttp import __version__, gitcache
from cttp.address import AddressError
from cttp.registry import RegistryError, open_registries
from cttp.resolve import ResolveError, resolve

app = FastAPI(title="cttp registry", version=__version__)
templates = jinja2.Environment(
    loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"), autoescape=True
)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    reg = open_registries(local_only=True)
    entries = [reg.lookup(n)[0] for n in reg.names()]
    return templates.get_template("index.html").render(entries=entries, registry=reg.describe())


@app.get("/{slug}")
def name_page(slug: str):
    want_json = slug.endswith(".json")
    if want_json:
        slug = slug[: -len(".json")]
    name, _, version = slug.partition("@")
    reg = open_registries(local_only=True)
    try:
        r = resolve(f"{name}@{version}" if version else name, reg)
        entry, _ = reg.lookup(name)
    except (RegistryError, ResolveError, AddressError, gitcache.GitError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if want_json:
        return JSONResponse(r.to_json())
    html = templates.get_template("name.html").render(r=r, entry=entry, registry=reg.describe())
    return HTMLResponse(html)
