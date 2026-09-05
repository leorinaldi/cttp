"""What the index answers. Spec §6, plan P4-T2.

Every query reads one SQLite file and returns plain data with `origin` on every derived or
asserted fact. "Current" means each repository's most recently crawled revision — that is what
`dups`, `rank` and `search` report over; `history` and `who` see every crawled revision.
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
            "ORDER BY crawled_at DESC, committed_at DESC LIMIT 1) "
        )
    sql += "ORDER BY v.committed_at, v.crawled_at, l.repo, l.path, l.symbol"
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
