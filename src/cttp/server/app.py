"""`cttp serve`: the registry contract (spec §8) and the viewer (spec §9) on port 3120.

The name routes and the contract are served over the configured **local** registry repositories —
the server never asks an HTTP registry, which could be itself. The viewer's other pages — search
at `/`, a definition at `/d/<identity>`, a repository at `/r/<host>/<owner>/<repo>`, duplicates at
`/dups`, and the name page's history and *who links here* — read the index (`CTTP_INDEX`, else
the global one) and say plainly when there is none. Every page separates derived facts from
asserted ones the same way: `base.html` chooses the layout once (two labelled columns), and
inline facts carry a tag.
"""

from pathlib import Path

import jinja2
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from cttp import __version__, gitcache
from cttp.address import AddressError, parse
from cttp.index import queries
from cttp.index.schema import IndexingError, default_index_path, open_index
from cttp.registry import RegistryError, open_registries
from cttp.resolve import ResolveError, resolve
from cttp.schemas import stamp

app = FastAPI(title="cttp registry", version=__version__)
templates = jinja2.Environment(
    loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"), autoescape=True
)
ERRORS = (RegistryError, ResolveError, AddressError, gitcache.GitError, IndexingError)


def render(name: str, **ctx) -> HTMLResponse:
    reg = open_registries(local_only=True)
    index_path = default_index_path()
    ctx.setdefault("registry", reg.describe())
    ctx.setdefault("index_path", str(index_path))
    ctx.setdefault("has_index", index_path.exists())
    return HTMLResponse(templates.get_template(name).render(**ctx))


def index_conn():
    """The index, or None when there is none yet — every page says so rather than failing."""
    p = default_index_path()
    return open_index(p, create=False) if p.exists() else None


def _safe(fn, *args):
    """A query's answer, or None when the index cannot answer (an address it has not seen)."""
    try:
        return fn(*args)
    except IndexingError:
        return None


@app.get("/", response_class=HTMLResponse)
def index(q: str | None = None) -> HTMLResponse:
    reg = open_registries(local_only=True)
    entries = [reg.lookup(n)[0] for n in reg.names()]
    conn = index_conn()
    hits = None
    if q and q.strip():
        hits = _safe(queries.search, conn, q, 50) if conn else None
    st = None
    if conn:
        from cttp.index.crawl import status

        st = status(conn, default_index_path())
    return render("index.html", entries=entries, q=q or "", hits=hits, status=st)


@app.get("/dups", response_class=HTMLResponse)
def dups_page(shape: bool = False) -> HTMLResponse:
    conn = index_conn()
    groups = queries.dups(conn, by_shape=shape) if conn else None
    return render("dups.html", groups=groups, shape=shape)


@app.get("/d/{identity}", response_class=HTMLResponse)
def definition_page(identity: str) -> HTMLResponse:
    conn = index_conn()
    if conn is None:
        raise HTTPException(status_code=404, detail="no index yet: `cttp index crawl` first")
    prefix = identity.removeprefix("sha256:").lower()
    hits = conn.execute(
        "SELECT identity FROM definitions WHERE identity LIKE ? LIMIT 10", (prefix + "%",)
    ).fetchall()
    if not hits:
        raise HTTPException(status_code=404, detail=f"sha256:{prefix} is not in the index")
    if len(hits) > 1:
        raise HTTPException(
            status_code=404,
            detail=f"sha256:{prefix} is a prefix of {len(hits)} identities; say which: "
            + ", ".join(f"sha256:{h['identity'][:16]}" for h in hits),
        )
    ident = hits[0]["identity"]
    d = queries.definition(conn, ident)
    locs = queries.locations_of(conn, ident)
    current = {x["address"] for x in queries.locations_of(conn, ident, current=True)}
    at = locs[-1] if locs else None
    page = queries.page_json(conn, d, at) if at else None
    backlinks = _safe(queries.who, conn, f"sha256:{ident}")
    return render(
        "definition.html",
        d=d,
        page=page,
        locations=locs,
        current=current,
        backlinks=backlinks,
        identity=ident,
    )


@app.get("/r/{host}/{owner}/{repo}", response_class=HTMLResponse)
def repo_page(host: str, owner: str, repo: str) -> HTMLResponse:
    conn = index_conn()
    locator = f"{host}/{owner}/{repo}".lower()
    if conn is None:
        raise HTTPException(status_code=404, detail="no index yet: `cttp index crawl` first")
    row = conn.execute("SELECT * FROM repos WHERE locator = ?", (locator,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{locator} is not in the index")
    revisions = conn.execute(
        "SELECT * FROM revisions WHERE repo = ? ORDER BY committed_at DESC, rowid DESC", (locator,)
    ).fetchall()
    current = revisions[0] if revisions else None
    files: dict[str, list] = {}
    if current:
        for r in conn.execute(
            "SELECT l.*, d.kind, d.name, d.signature FROM locations l "
            "JOIN definitions d ON d.identity = l.identity WHERE l.repo = ? AND l.sha = ? "
            "ORDER BY l.path, l.span_first, l.symbol IS NOT NULL",
            (locator, _current_sha(conn, locator)),
        ):
            files.setdefault(r["path"], []).append(r)
    return render("repo.html", repo=dict(row), revisions=revisions, current=current, files=files)


def _current_sha(conn, locator: str) -> str | None:
    row = conn.execute(
        "SELECT sha FROM revisions WHERE repo = ? ORDER BY rowid DESC LIMIT 1", (locator,)
    ).fetchone()
    return row["sha"] if row else None


@app.get("/{slug}")
def name_page(slug: str):
    want_json = slug.endswith(".json")
    if want_json:
        slug = slug[: -len(".json")]
    reg = open_registries(local_only=True)
    try:
        a = parse(slug)  # `name[@version][#symbol]`; the `#` arrives percent-encoded as %23
        if a.form != "name":
            raise AddressError(f"{slug!r} is not a name; the contract serves names only")
        r = resolve(str(a), reg)
        entry, _ = reg.lookup(a.name)
    except ERRORS as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if want_json:
        return JSONResponse(stamp(r.to_json()))
    conn = index_conn()
    backlinks = _safe(queries.who, conn, str(a), reg) if conn else None
    hist = _safe(queries.history, conn, str(a), reg) if conn else None
    return render("name.html", r=r, entry=entry, backlinks=backlinks, history=hist)
