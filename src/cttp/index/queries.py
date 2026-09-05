"""What the index answers. Spec §6, plan P4-T2.

Every query reads one SQLite file and returns plain data with `origin` on every derived or
asserted fact. "Current" means each repository's most recently crawled revision (the last row
written for it — a `--rev` crawl makes that rev current on purpose); that is what `dups`,
`rank` and `search` report over. `history` orders revisions by commit time, then crawl order;
`who` sees every crawled revision.
"""

import json
import sqlite3
from pathlib import Path

from cttp.address import Address
from cttp.hashing import short
from cttp.index.schema import IndexingError, default_index_path, open_index

# --- the identity hook the resolver falls through to -------------------------------------------


def lookup_identity(prefix: str, path: Path | None = None):
    """`objects.index_lookup`: the page whose identity starts with `prefix`, as a `Stored`, with
    every crawled location; None when there is no index or no such page."""
    from cttp.objects import METADATA, AmbiguousIdentity, Stored

    p = path or default_index_path()
    if not p.exists():
        return None
    conn = open_index(p, create=False)
    prefix = prefix.removeprefix("sha256:").lower()
    hits = conn.execute(
        "SELECT identity FROM definitions WHERE identity LIKE ? LIMIT 2", (prefix + "%",)
    ).fetchall()
    if not hits:
        return None
    if len(hits) > 1:
        raise AmbiguousIdentity(prefix, [h["identity"] for h in hits])
    ident = hits[0]["identity"]
    d = definition(conn, ident)
    locs = locations_of(conn, ident)
    if not locs:
        return None
    at = locs[-1]
    page = page_json(conn, d, at)
    meta = {k: page.get(k) for k in METADATA}
    return Stored(
        identity=ident,
        source=d["source"],
        meta=meta,
        locations=[
            {
                "address": x["address"],
                "target": x["target"],
                "path": x["path"],
                "rev": x["sha"],
                "name": x["name"],
                "registry": x["registry"],
                "description": x["description"],
                "license": x["license"],
                "seen": x["crawled_at"],
            }
            for x in locs
        ],
        via="index",
    )


# --- rows as dicts -----------------------------------------------------------------------------


def definition(conn: sqlite3.Connection, ident: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM definitions WHERE identity = ?", (ident,)).fetchone()
    if row is None:
        raise IndexingError(f"sha256:{ident[:16]} is not in the index")
    return row


def locations_of(conn: sqlite3.Connection, ident: str, current: bool = False) -> list[dict]:
    """Every place an identity was seen, oldest first (by commit time, then crawl time); with
    `current`, only places at each repository's most recently crawled revision."""
    sql = (
        "SELECT l.*, v.license, v.crawled_at, v.committed_at FROM locations l "
        "JOIN revisions v ON v.repo = l.repo AND v.sha = l.sha WHERE l.identity = ? "
    )
    if current:
        sql += (
            "AND v.sha = (SELECT sha FROM revisions WHERE repo = l.repo "
            "ORDER BY rowid DESC LIMIT 1) "
        )
    sql += "ORDER BY v.committed_at, v.rowid, l.repo, l.path, l.symbol"
    return [_location(conn, r) for r in conn.execute(sql, (ident,))]


def _location(conn, r) -> dict:
    target = f"{r['repo']}/{r['path']}"
    entry = conn.execute(
        "SELECT name, registry, description FROM names WHERE target = ? ORDER BY name LIMIT 1",
        (target,),
    ).fetchone()
    return {
        "address": str(
            Address(
                "locator",
                locator=r["repo"],
                path=r["path"],
                rev=short(r["sha"]),
                symbol=r["symbol"],
            )
        ),
        "repo": r["repo"],
        "sha": r["sha"],
        "path": r["path"],
        "symbol": r["symbol"],
        "span": [r["span_first"], r["span_last"]],
        "target": target,
        "license": r["license"],
        "name": entry["name"] if entry else None,
        "registry": entry["registry"] if entry else None,
        "description": entry["description"] if entry else None,
        "crawled_at": r["crawled_at"],
        "committed_at": r["committed_at"],
        "origin": "derived",
    }


def links_from(conn, ident: str, repo: str, sha: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM links WHERE source_identity = ? AND repo = ? AND sha = ? "
        "ORDER BY line, rowid",
        (ident, repo, sha),
    ).fetchall()


def page_json(conn, d: sqlite3.Row, at: dict) -> dict:
    """A definition as the resolver's object (spec §8), seen at location `at`."""
    rows = links_from(conn, d["identity"], at["repo"], at["sha"])
    imports = json.loads(d["imports"])
    return {
        "name": at["name"],
        "address": at["address"],
        "rev": at["sha"],
        "identity": f"sha256:{short(d['identity'])}",
        "identity_full": d["identity"],
        "shape": f"sha256:{short(d['shape'])}" if d["shape"] else None,
        "shape_full": d["shape"],
        "kind": d["kind"],
        "language": d["language"],
        "symbol": at["symbol"],
        "signature": d["signature"],
        "docstring": d["docstring"],
        "span": at["span"],
        "source": d["source"],
        "description": at["description"],
        "license": at["license"],
        "target": at["target"],
        "path": at["path"],
        "registry": at["registry"],
        "refs": [
            {
                "address": r["target_address"],
                "name": r["name"],
                "relation": "ref",
                "origin": "derived",
            }
            for r in rows
            if r["relation"] == "ref"
        ],
        "imports": imports,
        "links": [
            {
                "address": r["target_address"],
                "relation": r["relation"],
                "fields": json.loads(r["fields"] or "{}"),
                "description": r["description"],
                "derived": bool(r["derived"]),
                "line": r["line"] - at["span"][0] + 1,
                "indent": " " * (r["indent"] or 0),
                "origin": "asserted",
            }
            for r in rows
            if r["relation"] != "ref"
        ],
        "unresolved": json.loads(d["unresolved"]),
    }


# --- an address, in the index ------------------------------------------------------------------


class Target:
    """What an address names, as far as the index can tell: the identities seen there and the
    place (repo, path, symbol) it points at."""

    def __init__(self, text: str):
        self.text = text
        self.identities: list[str] = []
        self.name: str | None = None
        self.locator: str | None = None
        self.path: str | None = None
        self.symbol: str | None = None
        self.rev: str | None = None

    @property
    def place(self) -> tuple[str, str, str | None] | None:
        return (self.locator, self.path, self.symbol) if self.locator and self.path else None

    def to_json(self) -> dict:
        return {
            "address": self.text,
            "identities": [f"sha256:{i}" for i in self.identities],
            "name": self.name,
            "repo": self.locator,
            "path": self.path,
            "symbol": self.symbol,
        }


def target_of(conn: sqlite3.Connection, text: str, registries=None) -> Target:
    """Resolve `text` inside the index; when the index has never seen it and `registries` are
    given, resolve it for real (the object cache or a registry) to learn its identity."""
    from cttp.address import AddressError, parse

    t = Target(text)
    try:
        a = parse(text)
    except AddressError as e:
        raise IndexingError(str(e)) from e
    if a.form == "identity":
        t.identities = [
            r["identity"]
            for r in conn.execute(
                "SELECT identity FROM definitions WHERE identity LIKE ?", (a.identity + "%",)
            )
        ]
    else:
        t.symbol, t.rev = a.symbol, a.rev
        _place_of(conn, t, a, registries)
    if not t.identities and registries is not None:
        from cttp.resolve import ResolveError, resolve

        try:
            r = resolve(text, registries)
        except (ResolveError, LookupError) as e:
            raise IndexingError(f"{text!r} is not in the index and does not resolve: {e}") from e
        from cttp.registry import split_target

        t.identities = [r.identity_full]
        t.locator, t.path, t.symbol = *split_target(r.target), r.symbol
        t.name = t.name or r.name
    if not t.identities:
        raise IndexingError(f"{text!r} is not in the index")
    return t


def _place_of(conn, t: Target, a, registries) -> None:
    """Fill the place a name or locator address points at, and the identities seen there."""
    from cttp.address import is_sha

    if a.rev and not is_sha(a.rev) and registries is not None:
        # a label names a rev only the repository can tell; resolve it for real (git is cached)
        from cttp.resolve import ResolveError, resolve

        try:
            r = resolve(t.text, registries)
        except (ResolveError, LookupError) as e:
            raise IndexingError(f"{t.text!r} does not resolve: {e}") from e
        t.rev = r.rev
    if a.form == "locator":
        t.locator, t.path = a.locator, a.path
    else:
        t.name = a.name
        entry = conn.execute(
            "SELECT target, versions FROM names WHERE name = ? ORDER BY registry LIMIT 1", (a.name,)
        ).fetchone()
        if entry:
            from cttp.registry import split_target

            t.locator, t.path = split_target(entry["target"])
            if t.rev and not is_sha(t.rev):
                label = json.loads(entry["versions"]).get(t.rev)
                t.rev = label if label and is_sha(label) else None
    if t.locator:
        sql = "SELECT DISTINCT identity FROM locations WHERE repo = ? AND symbol IS ?"
        args: list = [t.locator, t.symbol]
        if t.path:
            sql += " AND path = ?"
            args.append(t.path)
        if t.rev and is_sha(t.rev):
            sql += " AND sha LIKE ?"
            args.append(t.rev.lower() + "%")
        t.identities = [r["identity"] for r in conn.execute(sql, args)]


def _current_sha(conn, repo: str) -> str | None:
    row = conn.execute(
        "SELECT sha FROM revisions WHERE repo = ? ORDER BY rowid DESC LIMIT 1",
        (repo,),
    ).fetchone()
    return row["sha"] if row else None


def _source_location(conn, ident: str, repo: str, sha: str, file: str) -> dict | None:
    """The page `ident` as it sits in `file` at (repo, sha): the definition there, or the file."""
    row = conn.execute(
        "SELECT l.*, v.license, v.crawled_at, v.committed_at FROM locations l "
        "JOIN revisions v ON v.repo = l.repo AND v.sha = l.sha "
        "WHERE l.identity = ? AND l.repo = ? AND l.sha = ? AND l.path = ? "
        "ORDER BY l.symbol IS NULL LIMIT 1",
        (ident, repo, sha, file),
    ).fetchone()
    return _location(conn, row) if row else None


# --- who ---------------------------------------------------------------------------------------

RELATION_ORDER = {"is": 0, "from": 1, "see": 2, "ref": 3}


def who(conn: sqlite3.Connection, text: str, registries=None) -> dict:
    """Backlinks: every page linking to the address, by relation and origin, across every crawled
    repository. A link counts when its target identity is one seen at the address, or when it
    names the same place (same name and symbol, or same repository, path and symbol at any rev).
    A page that links at several crawled revisions is listed once, at the latest."""
    t = target_of(conn, text, registries)
    clauses, args = [], []
    if t.identities:
        clauses.append(f"target_identity IN ({','.join('?' * len(t.identities))})")
        args += t.identities
    if t.name:
        clauses.append(
            "(target_identity IS NULL AND target_form = 'name' AND target_name = ? "
            "AND target_symbol IS ?)"
        )
        args += [t.name, t.symbol]
    if t.place:
        clauses.append(
            "(target_identity IS NULL AND target_form = 'locator' AND target_locator = ? "
            "AND target_path = ? AND target_symbol IS ?)"
        )
        args += list(t.place)
    rows = conn.execute(
        f"SELECT k.*, v.committed_at, v.crawled_at FROM links k "
        f"JOIN revisions v ON v.repo = k.repo AND v.sha = k.sha "
        f"WHERE {' OR '.join(clauses)} "
        f"ORDER BY v.committed_at DESC, v.rowid DESC",
        args,
    ).fetchall()
    seen: dict[tuple, dict] = {}
    for r in rows:
        key = (r["source_identity"], r["repo"], r["file"], r["relation"], r["target_address"])
        if key in seen:
            continue
        src = _source_location(conn, r["source_identity"], r["repo"], r["sha"], r["file"])
        d = definition(conn, r["source_identity"])
        seen[key] = {
            "source": {
                "identity": f"sha256:{short(r['source_identity'])}",
                "identity_full": r["source_identity"],
                "address": src["address"] if src else None,
                "repo": r["repo"],
                "sha": r["sha"],
                "path": r["file"],
                "symbol": src["symbol"] if src else None,
                "kind": d["kind"],
                "name": d["name"],
                "signature": d["signature"],
                "license": src["license"] if src else None,
            },
            "relation": r["relation"],
            "origin": r["origin"],
            "line": r["line"],
            "target": r["target_address"],
            "target_identity": (
                f"sha256:{short(r['target_identity'])}" if r["target_identity"] else None
            ),
            "description": r["description"],
            "name": r["name"],
        }
    backlinks = sorted(
        seen.values(),
        key=lambda b: (
            RELATION_ORDER.get(b["relation"], 9),
            b["origin"] != "asserted",
            b["source"]["repo"],
            b["source"]["path"],
            b["line"],
        ),
    )
    by = {}
    for b in backlinks:
        by.setdefault(b["relation"], {}).setdefault(b["origin"], 0)
        by[b["relation"]][b["origin"]] += 1
    return {
        **t.to_json(),
        "backlinks": backlinks,
        "count": len(backlinks),
        "by": by,
        "origin": {"backlinks": "derived", "relation": "per link: its origin"},
    }


# --- dups --------------------------------------------------------------------------------------


def _current_locations(conn) -> list[dict]:
    """Every location at each repository's current revision, with its definition's name."""
    rows = conn.execute(
        "SELECT l.*, v.license, v.crawled_at, v.committed_at, d.shape, d.name, d.kind, "
        "d.signature, d.lines FROM locations l "
        "JOIN revisions v ON v.repo = l.repo AND v.sha = l.sha "
        "JOIN definitions d ON d.identity = l.identity "
        "WHERE v.sha = (SELECT sha FROM revisions WHERE repo = l.repo "
        "ORDER BY rowid DESC LIMIT 1) "
        "ORDER BY l.repo, l.path, l.symbol"
    ).fetchall()
    out = []
    for r in rows:
        loc = _location(conn, r)
        loc.update(
            identity=r["identity"], shape=r["shape"], name=r["name"], kind=r["kind"],
            signature=r["signature"], lines=r["lines"],
        )  # fmt: skip
        out.append(loc)
    # a file whose whole text is one definition is that definition: keep the definition only
    by_place: dict[tuple, list[dict]] = {}
    for loc in out:
        by_place.setdefault((loc["repo"], loc["path"]), []).append(loc)
    kept = []
    for locs in by_place.values():
        symbol_ids = {x["identity"] for x in locs if x["symbol"]}
        kept += [x for x in locs if x["symbol"] or x["identity"] not in symbol_ids]
    return kept


def dups(conn: sqlite3.Connection, by_shape: bool = False) -> dict:
    """Groups of pages sharing an identity — the same code in more than one place at the current
    revisions — or, with `by_shape`, sharing a shape: the same structure under different names
    or literals. Largest groups first."""
    key = "shape" if by_shape else "identity"
    groups: dict[str, list[dict]] = {}
    for loc in _current_locations(conn):
        if loc[key] is None:
            continue
        groups.setdefault(loc[key], []).append(loc)
    out = []
    for k, locs in groups.items():
        idents = sorted({x["identity"] for x in locs})
        if len(locs) < 2:
            continue
        if by_shape and len(idents) < 2 and len(locs) < 2:
            continue
        out.append(
            {
                key: f"sha256:{short(k)}",
                f"{key}_full": k,
                "identities": [f"sha256:{short(i)}" for i in idents],
                "names": sorted({x["name"] for x in locs}),
                "kind": locs[0]["kind"],
                "lines": locs[0]["lines"],
                "count": len(locs),
                "locations": [
                    {
                        "address": x["address"],
                        "identity": f"sha256:{short(x['identity'])}",
                        "repo": x["repo"],
                        "path": x["path"],
                        "symbol": x["symbol"],
                        "license": x["license"],
                        "name": x["name"],
                    }
                    for x in locs
                ],
            }
        )
    out.sort(key=lambda g: (-g["count"], -g["lines"], g["names"]))
    return {
        "by": key,
        "groups": out,
        "count": len(out),
        "origin": {"groups": "derived", key: "derived"},
    }


# --- closure -----------------------------------------------------------------------------------


def closure(conn: sqlite3.Connection, texts: list[str], registries=None) -> dict:
    """The transitive set of pages the given ones reference — through `is` links and derived
    references the index recorded — in dependency order, roots last. The same shape as
    `cttp closure` (plan P3-T1), from the index alone: a target the index cannot tell is listed
    under `missing`, not fetched."""
    roots: list[tuple[str, dict]] = []
    for text in texts:
        t = target_of(conn, text, registries)
        ident = t.identities[-1]
        at = _pick(locations_of(conn, ident), t)
        if at is None:
            raise IndexingError(f"{text!r}: the index has no location for it")
        roots.append((ident, at))
    order: list[dict] = []
    seen: set[str] = set()
    missing: list[dict] = []
    imports: list[str] = []
    stdlib: set[str] = set()
    requires: set[str] = set()

    def visit(ident: str, at: dict, via: str) -> None:
        if ident in seen:
            return
        seen.add(ident)
        d = definition(conn, ident)
        needs: list[str] = []
        for k in links_from(conn, ident, at["repo"], at["sha"]):
            if k["relation"] not in ("is", "ref"):
                continue
            if not k["target_identity"]:
                missing.append(
                    {
                        "from": at["address"],
                        "address": k["target_address"],
                        "relation": k["relation"],
                    }
                )
                continue
            dep_at = _pick(
                locations_of(conn, k["target_identity"]),
                None,
                prefer=(k["target_locator"], k["target_path"], k["target_rev"]),
            )
            if dep_at is None:
                continue
            needs.append(dep_at["address"])
            visit(k["target_identity"], dep_at, "link" if k["relation"] == "is" else "ref")
        imp = json.loads(d["imports"])
        for s in imp.get("statements", []):
            if s not in imports:
                imports.append(s)
        stdlib.update(imp.get("stdlib", []))
        requires.update(imp.get("third_party", []))
        order.append(_node(conn, d, at, via, needs))

    for ident, at in roots:
        visit(ident, at, "root")
    return {
        "address": roots[0][1]["address"],
        "identity": f"sha256:{short(roots[0][0])}",
        "roots": [at["address"] for _, at in roots],
        "definitions": order,
        "count": len(order),
        "lines": sum(n["lines"] for n in order),
        "imports": imports,
        "stdlib": sorted(stdlib),
        "requires": sorted(requires),
        "missing": missing,
        "origin": {"order": "derived", "imports": "derived", "requires": "derived"},
    }


def _pick(locs: list[dict], t: Target | None, prefer: tuple | None = None) -> dict | None:
    """The location to show for an identity: the place (and rev) the address named, else the
    preferred place at the preferred rev, else that place at its latest, else the most recent."""
    if not locs:
        return None
    if t and t.place:
        same = [x for x in reversed(locs) if (x["repo"], x["path"], x["symbol"]) == t.place]
        if t.rev:
            for x in same:
                if x["sha"].startswith(t.rev.lower()):
                    return x
        if same:
            return same[0]
    if prefer:
        repo, path, rev = prefer
        same = [x for x in reversed(locs) if (x["repo"], x["path"]) == (repo, path)]
        for x in same:
            if rev and x["sha"].startswith(rev.lower()):
                return x
        if same:
            return same[0]
    return locs[-1]


def _node(conn, d, at: dict, via: str, needs: list[str]) -> dict:
    if at["symbol"]:
        defines = [at["symbol"].split(".")[0]]
    else:
        defines = [
            r["symbol"]
            for r in conn.execute(
                "SELECT symbol FROM locations WHERE repo = ? AND sha = ? AND path = ? "
                "AND symbol IS NOT NULL AND symbol NOT LIKE '%.%' ORDER BY span_first",
                (at["repo"], at["sha"], at["path"]),
            )
        ]
    description = at["description"]
    derived = False
    if description is None and d["signature"]:
        from cttp.closure import describe
        from cttp.resolve import Resolved

        description, derived = describe(
            Resolved.from_json(page_json(conn, d, at), at["registry"] or "")
        )
    return {
        "address": at["address"],
        "locator": at["address"],
        "identity": f"sha256:{short(d['identity'])}",
        "identity_full": d["identity"],
        "kind": d["kind"],
        "symbol": at["symbol"],
        "path": at["path"],
        "lines": d["lines"],
        "license": at["license"],
        "description": description,
        "via": via,
        "needs": needs,
        "defines": defines,
        "source": d["source"],
        "origin": {
            "description": None if description is None else "derived" if derived else "asserted",
            "via": "asserted" if via == "link" else "derived",
        },
    }


# --- search ------------------------------------------------------------------------------------


def search(conn: sqlite3.Connection, text: str, limit: int = 20) -> dict:
    """By name, symbol, signature or docstring: FTS5 with stemming, every term a prefix."""
    terms = [t.replace('"', '""') for t in text.split()]
    if not terms:
        raise IndexingError("search needs some text")
    query = " ".join(f'"{t}"*' for t in terms)
    rows = conn.execute(
        "SELECT f.identity, bm25(definitions_fts) AS score FROM definitions_fts f "
        "WHERE definitions_fts MATCH ? ORDER BY score LIMIT ?",
        (query, limit),
    ).fetchall()
    hits = []
    for r in rows:
        d = definition(conn, r["identity"])
        locs = locations_of(conn, r["identity"], current=True) or locations_of(conn, r["identity"])
        hits.append(
            {
                "identity": f"sha256:{short(d['identity'])}",
                "identity_full": d["identity"],
                "name": d["name"],
                "kind": d["kind"],
                "signature": d["signature"],
                "docstring": d["docstring"],
                "score": r["score"],
                "address": locs[-1]["address"] if locs else None,
                "locations": [
                    {
                        "address": x["address"],
                        "repo": x["repo"],
                        "path": x["path"],
                        "symbol": x["symbol"],
                        "name": x["name"],
                    }
                    for x in locs
                ],  # fmt: skip
            }
        )
    return {
        "query": text,
        "hits": hits,
        "count": len(hits),
        "origin": {"hits": "derived", "score": "derived"},
    }


# --- history -----------------------------------------------------------------------------------


def history(conn: sqlite3.Connection, text: str, registries=None) -> dict:
    """The identities seen at one place — (repo, path, symbol) — over every crawled revision of
    its repository, oldest commit first; `changed` marks a revision whose identity differs from
    the one before it, `absent` one where the place has no page."""
    t = target_of(conn, text, registries)
    if not t.place:
        raise IndexingError(f"{text!r} names no place (repository, path, symbol) the index knows")
    repo, path, symbol = t.place
    revs = conn.execute(
        "SELECT sha, committed_at, crawled_at, license FROM revisions WHERE repo = ? "
        "ORDER BY committed_at, rowid",
        (repo,),
    ).fetchall()
    out = []
    prev: str | None = None
    for v in revs:
        row = conn.execute(
            "SELECT l.identity, d.shape, d.signature FROM locations l "
            "JOIN definitions d ON d.identity = l.identity "
            "WHERE l.repo = ? AND l.sha = ? AND l.path = ? AND l.symbol IS ?",
            (repo, v["sha"], path, symbol),
        ).fetchone()
        ident = row["identity"] if row else None
        out.append(
            {
                "sha": v["sha"],
                "address": str(
                    Address("locator", locator=repo, path=path, rev=short(v["sha"]), symbol=symbol)
                ),
                "committed_at": v["committed_at"],
                "crawled_at": v["crawled_at"],
                "identity": f"sha256:{short(ident)}" if ident else None,
                "identity_full": ident,
                "shape": f"sha256:{short(row['shape'])}" if row and row["shape"] else None,
                "signature": row["signature"] if row else None,
                "absent": ident is None,
                "changed": ident != prev,
            }
        )
        prev = ident
    identities = []
    for x in out:
        if x["identity_full"] and x["identity_full"] not in identities:
            identities.append(x["identity_full"])
    return {
        "repo": repo,
        "path": path,
        "symbol": symbol,
        "revisions": out,
        "identities": [f"sha256:{short(i)}" for i in identities],
        "count": len(out),
        "origin": {"revisions": "derived", "identity": "derived"},
    }


# --- rank --------------------------------------------------------------------------------------


def rank(conn: sqlite3.Connection, limit: int = 20) -> dict:
    """Pages by how many distinct pages link to them (any relation, any crawled revision)."""
    rows = conn.execute(
        "SELECT target_identity AS identity, relation, origin, "
        "count(DISTINCT source_identity) AS n FROM links "
        "WHERE target_identity IS NOT NULL AND target_identity != source_identity "
        "GROUP BY target_identity, relation, origin"
    ).fetchall()
    totals: dict[str, dict] = {}
    for r in rows:
        t = totals.setdefault(r["identity"], {"n": 0, "by": {}})
        t["by"].setdefault(r["relation"], {})[r["origin"]] = r["n"]
    for ident, t in totals.items():
        t["n"] = conn.execute(
            "SELECT count(DISTINCT source_identity) FROM links WHERE target_identity = ? "
            "AND target_identity != source_identity",
            (ident,),
        ).fetchone()[0]
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1]["n"], kv[0]))[:limit]
    out = []
    for ident, t in ranked:
        d = definition(conn, ident)
        locs = locations_of(conn, ident, current=True) or locations_of(conn, ident)
        out.append(
            {
                "identity": f"sha256:{short(ident)}",
                "identity_full": ident,
                "name": d["name"],
                "kind": d["kind"],
                "signature": d["signature"],
                "address": locs[-1]["address"] if locs else None,
                "backlinks": t["n"],
                "by": t["by"],
            }
        )
    return {"ranked": out, "count": len(out), "origin": {"backlinks": "derived", "rank": "derived"}}
