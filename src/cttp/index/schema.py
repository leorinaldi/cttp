"""The index's tables. Spec §6, plan P4-T1.

One SQLite file per index; the default is global (`~/.local/share/cttp/index.db`, `--index <path>`
or `CTTP_INDEX` to choose another). Six tables, by grain:

- `repos` — one git remote: its locator, default branch, and the local path it was added from.
- `revisions` — one crawled commit of one repo: sha, commit time, license at that rev, crawled-at.
- `definitions` — one **identity**: shape, language, kind, name, signature, docstring, source,
  imports, free names. Identity is the key, so the same code seen in three places is one row.
- `locations` — one place an identity was seen: (repo, sha, path, symbol) and its span. Three
  places are three rows against the one `definitions` row.
- `links` — one edge from a page: the source identity and where it was (repo, sha, file, line),
  the target address as written and parsed, the target identity when the index can tell,
  relation (`is` / `from` / `see` / `ref`), origin (`asserted` / `derived`).
- `names` — one registry entry, snapshotted at crawl time.

`definitions_fts` is the FTS5 shadow of `definitions` that `search` reads.
"""

import os
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS repos (
    locator        TEXT PRIMARY KEY,   -- host/owner/repo
    default_branch TEXT,
    local_path     TEXT,               -- the working copy it was added from, if any
    added_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS revisions (
    repo         TEXT NOT NULL REFERENCES repos(locator),
    sha          TEXT NOT NULL,        -- full commit SHA
    committed_at INTEGER,              -- the commit's own timestamp (unix)
    license      TEXT,                 -- SPDX id at this rev; NULL when not available
    crawled_at   TEXT NOT NULL,
    files        INTEGER NOT NULL,     -- files looked at
    PRIMARY KEY (repo, sha)
);

CREATE TABLE IF NOT EXISTS definitions (
    identity   TEXT PRIMARY KEY,       -- full sha256 hex of the page's own text
    shape      TEXT,                   -- full sha256 hex of its shape; NULL when it has none
    language   TEXT NOT NULL,
    kind       TEXT NOT NULL,          -- function | class | constant | type | macro | script
    name       TEXT NOT NULL,          -- the last component of the symbol, or the file name
    signature  TEXT,
    docstring  TEXT,
    lines      INTEGER NOT NULL,
    source     TEXT NOT NULL,
    imports    TEXT NOT NULL,          -- JSON {stdlib, third_party, statements}
    unresolved TEXT NOT NULL           -- JSON list of free names
);

CREATE TABLE IF NOT EXISTS locations (
    identity   TEXT NOT NULL REFERENCES definitions(identity),
    repo       TEXT NOT NULL,
    sha        TEXT NOT NULL,
    path       TEXT NOT NULL,
    symbol     TEXT,                   -- NULL for a whole-file page
    span_first INTEGER NOT NULL,
    span_last  INTEGER NOT NULL,
    PRIMARY KEY (repo, sha, path, symbol),
    FOREIGN KEY (repo, sha) REFERENCES revisions(repo, sha)
);
CREATE INDEX IF NOT EXISTS locations_identity ON locations(identity);
CREATE INDEX IF NOT EXISTS locations_place ON locations(repo, path, symbol);

CREATE TABLE IF NOT EXISTS links (
    source_identity TEXT NOT NULL,
    repo            TEXT NOT NULL,
    sha             TEXT NOT NULL,
    file            TEXT NOT NULL,
    line            INTEGER NOT NULL,  -- 1-based line of the link (a derived ref: the page's first)
    relation        TEXT NOT NULL,     -- is | from | see | ref
    origin          TEXT NOT NULL,     -- asserted | derived
    target_address  TEXT NOT NULL,     -- as written
    target_form     TEXT,              -- name | locator | identity; NULL when unparsable
    target_name     TEXT,
    target_locator  TEXT,
    target_path     TEXT,
    target_rev      TEXT,
    target_symbol   TEXT,
    target_id       TEXT,              -- the link's id= (hex, maybe a prefix) or identity address
    target_identity TEXT,              -- full identity when the index can tell; else NULL
    description     TEXT,              -- an asserted link's description, as written
    derived         INTEGER,           -- 1 when that description was tool-derived (~"…")
    fields          TEXT,              -- an asserted link's key=value fields, JSON
    indent          INTEGER,           -- the link line's indentation
    name            TEXT,              -- a derived ref: the text the source reaches it by
    PRIMARY KEY (source_identity, repo, sha, file, line, relation, target_address)
);
CREATE INDEX IF NOT EXISTS links_target ON links(target_identity);
CREATE INDEX IF NOT EXISTS links_target_name ON links(target_name);
CREATE INDEX IF NOT EXISTS links_target_place ON links(target_locator, target_path);

CREATE TABLE IF NOT EXISTS names (
    name           TEXT NOT NULL,
    registry       TEXT NOT NULL,
    target         TEXT NOT NULL,
    description    TEXT,
    owner          TEXT,
    default_label  TEXT,
    versions       TEXT NOT NULL,      -- JSON {label: ref}
    snapshotted_at TEXT NOT NULL,
    PRIMARY KEY (name, registry)
);

CREATE VIRTUAL TABLE IF NOT EXISTS definitions_fts USING fts5(
    identity UNINDEXED, name, symbol, signature, docstring,
    tokenize = 'porter unicode61'
);
"""


class IndexingError(LookupError):
    """The index cannot answer; the message says why (missing, unknown address, and so on)."""


def default_index_path() -> Path:
    if env := os.environ.get("CTTP_INDEX"):
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(xdg) / "cttp" / "index.db"


def open_index(path: Path | str | None = None, create: bool = True) -> sqlite3.Connection:
    """The index at `path` (default: the global one), its tables created if absent.

    With `create=False` a missing file is an `IndexingError` rather than a new, empty index —
    what a query wants, since an empty index answers nothing."""
    p = Path(path) if path else default_index_path()
    if not create and not p.exists():
        raise IndexingError(
            f"no index at {p}; `cttp index add <repo>` and `cttp index crawl` first"
        )
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, timeout=5.0)  # wait out a writer's commit rather than fail at once
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if create:
        # a reader must not run the schema script: `CREATE TABLE IF NOT EXISTS` takes the write
        # lock, and a crawl holds it for minutes — the viewer would answer 500 the whole while
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema', ?)", (str(SCHEMA_VERSION),)
        )
        conn.commit()
    return conn


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in ("repos", "revisions", "definitions", "locations", "links", "names")
    }
