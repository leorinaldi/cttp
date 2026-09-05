"""Filling the index from git. Spec §6, plan P4-T1.

Crawling is explicit: `add()` registers a repository — a locator, or a local working copy whose
`origin` remote names one — and `crawl()` walks the registered list. For each repository at one
commit (its default branch's head, or the rev asked for) every file in the tree is read through
`git`: a Python file yields its whole-file page and one page per definition, each hashed and
recorded once per identity and once per place; any other file yields a page only when it carries
a link line. Every asserted link `links.py` finds is recorded against the innermost page whose
span holds its line; every derived reference against the page that made it. Target identities
are filled in afterwards from what the index knows — a stamp's `id=`, a pinned locator seen at
that rev, a name whose snapshot points at a crawled file — and left NULL otherwise; the crawl
never fetches a repository it was not given. The tool never executes what it reads.
"""

import json
import re
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from cttp import gitcache
from cttp.address import Address, AddressError, parse
from cttp.config import Config
from cttp.extract import ExtractError, Page, definitions, extract, language_of
from cttp.hashing import ShapeError, identity, normalize, shape, short
from cttp.index.schema import IndexingError, counts
from cttp.links import LINK_RE, LinkError, find_links, parse_link
from cttp.registry import LocalRegistry, Registries, split_target

MAX_FILE_BYTES = 1_000_000  # a file larger than this is not code anyone links to
LOCATOR_RE = re.compile(r"^[A-Za-z0-9.-]+/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")  # host/owner/repo


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --- add ---------------------------------------------------------------------------------------


def locator_of_url(url: str, config: Config) -> str:
    """The locator a clone URL names: through `[remotes]` backwards (a mirror, or a local path
    the tests use), else the host/owner/repo of an https, ssh or scp-style git URL."""
    url = url.strip()
    for prefix, base in sorted(config.remotes.items(), key=lambda kv: -len(kv[1])):
        if url.startswith(base):
            rest = url[len(base) :].strip("/")
            return _strip_git(prefix + rest)
    for scheme in ("https://", "http://", "ssh://git@", "ssh://", "git://"):
        if url.startswith(scheme):
            return _strip_git(url[len(scheme) :].strip("/"))
    if "@" in url and ":" in url and "://" not in url:  # git@github.com:owner/repo.git
        host, _, path = url.partition("@")[2].partition(":")
        return _strip_git(f"{host}/{path.strip('/')}")
    raise IndexingError(f"cannot tell a locator from the remote URL {url!r}")


def _strip_git(locator: str) -> str:
    locator = locator.removesuffix(".git")
    if locator.count("/") != 2:
        raise IndexingError(f"{locator!r} is not host/owner/repo")
    return locator.lower()


def _git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise IndexingError(f"git {' '.join(args)} in {cwd}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def add(conn: sqlite3.Connection, target: str, config: Config) -> dict:
    """Register a repository: `host/owner/repo`, or a local path whose `origin` names one."""
    p = Path(target).expanduser()
    local_path: str | None = None
    if p.exists():
        root = p if p.is_dir() else p.parent
        try:
            top = _git("rev-parse", "--show-toplevel", cwd=root)
            url = _git("remote", "get-url", "origin", cwd=root)
        except IndexingError as e:
            raise IndexingError(
                f"{target} is not inside a git repository with an origin: {e}"
            ) from e
        locator = locator_of_url(url, config)
        local_path = top
        try:
            branch = _git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=root)
            branch = branch.removeprefix("origin/")
        except IndexingError:
            branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=root)
    else:
        if not LOCATOR_RE.match(target.strip()):
            raise IndexingError(
                f"{target!r} is neither a local path nor host/owner/repo (a repository, not a file)"
            )
        locator = target.strip().lower()
        branch = None  # learned at the first crawl
    row = conn.execute("SELECT locator FROM repos WHERE locator = ?", (locator,)).fetchone()
    conn.execute(
        "INSERT INTO repos(locator, default_branch, local_path, added_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(locator) DO UPDATE SET "
        "local_path = COALESCE(excluded.local_path, local_path), "
        "default_branch = COALESCE(excluded.default_branch, default_branch)",
        (locator, branch, local_path, now()),
    )
    conn.commit()
    return {
        "repo": locator,
        "local_path": local_path,
        "default_branch": branch,
        "status": "already registered" if row else "added",
    }


# --- crawl -------------------------------------------------------------------------------------


@dataclass
class Crawled:
    repo: str
    sha: str
    status: str  # "crawled" | "already"
    files: int = 0
    pages: int = 0  # pages seen (locations written)
    definitions: int = 0  # identities the index had not seen before
    links: int = 0
    skipped: list[str] | None = None  # files that could not be read or parsed, with the reason

    def to_json(self) -> dict:
        return {
            "repo": self.repo,
            "sha": self.sha,
            "status": self.status,
            "files": self.files,
            "pages": self.pages,
            "definitions": self.definitions,
            "links": self.links,
            "skipped": list(self.skipped or []),
        }


def crawl(
    conn: sqlite3.Connection,
    registries: Registries,
    rev: str | None = None,
    only: list[str] | None = None,
    force: bool = False,
) -> list[Crawled]:
    """Crawl every registered repository (or `only` those) at its head, or at `rev`; snapshot the
    local registries' names; then fill in every target identity the index can now tell. A
    revision already crawled is left alone unless `force`, which crawls it again from scratch
    (its locations and links first removed; definitions are shared and stay)."""
    repos = [
        dict(r)
        for r in conn.execute("SELECT * FROM repos ORDER BY locator")
        if not only or r["locator"] in only
    ]
    if only:
        missing = sorted(set(only) - {r["locator"] for r in repos})
        if missing:
            raise IndexingError(f"not registered: {', '.join(missing)}; `cttp index add` first")
    if not repos:
        raise IndexingError("no repositories registered; `cttp index add <repo-or-path>` first")
    results = [_crawl_repo(conn, r, registries, rev, force) for r in repos]
    snapshot_names(conn, registries)
    resolve_targets(conn)
    conn.commit()
    return results


def _repo_handle(row: dict, registries: Registries, rev: str | None) -> tuple[Path, str, str]:
    """(git directory, sha to crawl, default branch) for a registered repository."""
    locator = row["locator"]
    if row["local_path"] and Path(row["local_path"]).exists():
        repo = Path(row["local_path"])
        branch = row["default_branch"] or _git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo)
        ref = rev or "HEAD"
    else:
        repo = gitcache.ensure_repo(locator, registries.url_for(locator), want=rev)
        branch = gitcache.default_branch(repo)
        ref = rev or branch
    try:
        sha = gitcache.rev_parse(repo, ref)
    except gitcache.GitError as e:
        raise IndexingError(f"{ref!r} is not a revision of {locator}: {e}") from e
    return repo, sha, branch


def _crawl_repo(
    conn, row: dict, registries: Registries, rev: str | None, force: bool = False
) -> Crawled:
    locator = row["locator"]
    repo, sha, branch = _repo_handle(row, registries, rev)
    if branch != row["default_branch"]:
        conn.execute("UPDATE repos SET default_branch = ? WHERE locator = ?", (branch, locator))
    if conn.execute(
        "SELECT 1 FROM revisions WHERE repo = ? AND sha = ?", (locator, sha)
    ).fetchone():
        if not force:
            return Crawled(locator, sha, "already")
        for table in ("links", "locations", "revisions"):
            conn.execute(f"DELETE FROM {table} WHERE repo = ? AND sha = ?", (locator, sha))
    files = gitcache.ls_tree(repo, sha)
    committed = int(_git("show", "-s", "--format=%ct", sha, cwd=repo) or 0) or None
    conn.execute(
        "INSERT INTO revisions(repo, sha, committed_at, license, crawled_at, files) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (locator, sha, committed, gitcache.license_of(repo, sha), now(), len(files)),
    )
    out = Crawled(locator, sha, "crawled", files=len(files), skipped=[])
    writer = _Writer(conn, locator, sha, out)
    py_files = [f for f in files if language_of(f) == "python"]
    for path in files:
        try:
            text = gitcache.show(repo, sha, path)
        except (gitcache.GitError, UnicodeDecodeError) as e:
            out.skipped.append(f"{path}: {e}")
            continue
        if len(text) > MAX_FILE_BYTES:
            out.skipped.append(f"{path}: larger than {MAX_FILE_BYTES} bytes")
            continue
        text, bad = neutralize_bad_links(text)
        out.skipped += [f"{path}: {b} — the line was ignored" for b in bad]
        try:
            if language_of(path) == "python":
                writer.python_file(path, text, py_files)
            else:
                writer.other_file(path, text)
        except (LinkError, ExtractError, SyntaxError) as e:
            out.skipped.append(f"{path}: {e}")
    conn.commit()
    return out


def neutralize_bad_links(text: str) -> tuple[str, list[str]]:
    """A line that looks like a link but is malformed — a `# cttp: <address> [key=value]` in
    prose, say — would stop the extractor for the whole file. It becomes a bare comment of the
    same comment syntax, so every definition of the file is still indexed and line numbers
    hold; the notes say which lines. Only the file page's own text differs from the file's."""
    lines = text.split("\n")
    notes = []
    for i, line in enumerate(lines):
        try:
            parse_link(i, line)
        except LinkError as e:
            m = LINK_RE.match(line)
            lines[i] = m["indent"] + m["comment"] + (" */" if m["comment"] == "/*" else "")
            notes.append(str(e))
    return ("\n".join(lines), notes) if notes else (text, notes)


class _Writer:
    """Writes one revision's pages and links."""

    def __init__(self, conn, repo: str, sha: str, out: Crawled):
        self.conn, self.repo, self.sha, self.out = conn, repo, sha, out
        self.rev12 = short(sha)

    def python_file(self, path: str, text: str, files: list[str]) -> None:
        whole = extract(path, text, None, files)
        defs: list[tuple[str, Page]] = []
        for sym in definitions(path, text):
            try:
                defs.append((sym, extract(path, text, sym, files)))
            except ExtractError as e:
                self.out.skipped.append(f"{path}#{sym}: {e}")
        ids = {None: self.page(path, None, whole)}
        for sym, page in defs:
            ids[sym] = self.page(path, sym, page)
        # every asserted link in the file: its source is the definition its block is (the
        # block begins right after the link's stack — spec §4), else the innermost definition
        # holding the link line, else the file itself
        spans = sorted((p.span[1] - p.span[0], p.span[0], p.span[1], s) for s, p in defs)
        starts = {p.span[0]: s for s, p in defs}
        for k in whole.links:
            line = k.line + 1
            owner = starts.get(k.start + 1)
            if owner is None:
                owner = next((s for _, a, b, s in spans if a <= line <= b), None)
            self.link(ids[owner], path, line, k)
        for sym, page in ((None, whole), *defs):
            for r in page.refs:
                self.ref(ids[sym], path, page.span[0], r)

    def other_file(self, path: str, text: str) -> None:
        links = find_links(normalize(text).split("\n"))
        if not links:
            return
        page = extract(path, text)
        ident = self.page(path, None, page)
        for k in links:
            self.link(ident, path, k.line + 1, k)

    def page(self, path: str, symbol: str | None, page: Page) -> str:
        ident = identity(page.source)
        try:
            shp = shape(page.source) if page.language == "python" else None
        except ShapeError:
            shp = None
        name = symbol.split(".")[-1] if symbol else PurePosixPath(path).name
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO definitions(identity, shape, language, kind, name, signature, "
            "docstring, lines, source, imports, unresolved) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                ident, shp, page.language, page.kind, name, page.signature, page.docstring,
                page.source.count("\n"), page.source,
                json.dumps({
                    "stdlib": list(page.stdlib),
                    "third_party": list(page.third_party),
                    "statements": list(page.imports),
                }),
                json.dumps(list(page.unresolved)),
            ),
        )  # fmt: skip
        if cur.rowcount:
            self.out.definitions += 1
        elif page.kind != "script":
            # a file whose whole text is one definition shares its identity; the definition's
            # view (kind, name, signature, docstring) is the richer one and wins the row
            self.conn.execute(
                "UPDATE definitions SET kind = ?, name = ?, signature = ?, docstring = ? "
                "WHERE identity = ? AND kind = 'script'",
                (page.kind, name, page.signature, page.docstring, ident),
            )
        if not self.conn.execute(
            "SELECT 1 FROM definitions_fts WHERE identity = ? AND name = ? AND symbol = ?",
            (ident, name, symbol or ""),
        ).fetchone():
            self.conn.execute(
                "INSERT INTO definitions_fts(identity, name, symbol, signature, docstring) "
                "VALUES (?,?,?,?,?)",
                (ident, name, symbol or "", page.signature or "", page.docstring or ""),
            )
        self.conn.execute(
            "INSERT OR REPLACE INTO locations(identity, repo, sha, path, symbol, span_first, "
            "span_last) VALUES (?,?,?,?,?,?,?)",
            (ident, self.repo, self.sha, path, symbol, page.span[0], page.span[1]),
        )
        self.out.pages += 1
        return ident

    def link(self, source: str, path: str, line: int, k) -> None:
        target = k.address
        try:
            a: Address | None = parse(target)
        except AddressError:
            a = None
        tid = k.fields.get("id")
        if tid:
            tid = tid.removeprefix("sha256:").lower()
        elif a and a.form == "identity":
            tid = a.identity
        self._insert(
            source, path, line, k.relation, "asserted", target, a, tid,
            description=k.description, derived=int(k.description_derived),
            fields=json.dumps(dict(k.fields)), indent=len(k.indent),
        )  # fmt: skip

    def ref(self, source: str, path: str, line: int, r) -> None:
        a = Address("locator", locator=self.repo, path=r.path, rev=self.rev12, symbol=r.symbol)
        self._insert(source, path, line, "ref", "derived", str(a), a, None, name=r.name)

    def _insert(
        self, source, path, line, relation, origin, target, a, tid,
        description=None, derived=None, fields=None, indent=None, name=None,
    ):  # fmt: skip
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO links(source_identity, repo, sha, file, line, relation, origin, "
            "target_address, target_form, target_name, target_locator, target_path, target_rev, "
            "target_symbol, target_id, description, derived, fields, indent, name) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                source, self.repo, self.sha, path, line, relation, origin, target,
                a.form if a else None,
                a.name if a else None,
                a.locator if a else None,
                a.path if a else None,
                a.rev if a else None,
                a.symbol if a else None,
                tid, description, derived, fields, indent, name,
            ),
        )  # fmt: skip
        self.out.links += cur.rowcount


# --- names and target identities --------------------------------------------------------------


def snapshot_names(conn: sqlite3.Connection, registries: Registries) -> int:
    """Copy every local registry's entries into `names`; HTTP registries have no listing."""
    n = 0
    for r in registries.items:
        if not isinstance(r, LocalRegistry):
            continue
        for name in r.names():
            e = r.lookup(name)
            conn.execute(
                "INSERT OR REPLACE INTO names(name, registry, target, description, owner, "
                "default_label, versions, snapshotted_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    e.name, r.describe(), e.target, e.description, e.owner, e.default,
                    json.dumps(e.versions), now(),
                ),
            )  # fmt: skip
            n += 1
    return n


def resolve_targets(conn: sqlite3.Connection) -> int:
    """Fill `target_identity` where the index can tell: from a stamp's `id=` (one definition
    with that prefix), from a pinned locator seen at that rev, or from a name whose snapshot
    points at a crawled file (the latest crawled rev of that repository). Never a guess: two
    candidates leave it NULL."""
    filled = 0
    rows = conn.execute("SELECT rowid, * FROM links WHERE target_identity IS NULL").fetchall()
    for r in rows:
        found = _target_identity(conn, r)
        if found:
            conn.execute(
                "UPDATE links SET target_identity = ? WHERE rowid = ?", (found, r["rowid"])
            )
            filled += 1
    return filled


def _target_identity(conn, r) -> str | None:
    if r["target_id"]:
        hits = conn.execute(
            "SELECT identity FROM definitions WHERE identity LIKE ? LIMIT 2",
            (r["target_id"] + "%",),
        ).fetchall()
        return hits[0]["identity"] if len(hits) == 1 else None
    if r["target_form"] == "locator" and r["target_path"]:
        return _identity_at(
            conn, r["target_locator"], r["target_rev"], r["target_path"], r["target_symbol"]
        )
    if r["target_form"] == "name":
        entry = conn.execute(
            "SELECT target, versions, default_label FROM names WHERE name = ?", (r["target_name"],)
        ).fetchone()
        if not entry:
            return None
        locator, path = split_target(entry["target"])
        rev = r["target_rev"]
        if rev and not _is_sha(rev):
            rev = json.loads(entry["versions"]).get(rev)  # a label → a ref; only SHAs help here
            rev = rev if rev and _is_sha(rev) else None
        if path is None:
            return None  # an entry naming a whole repository needs the symbol search of resolve()
        return _identity_at(conn, locator, rev, path, r["target_symbol"])
    return None


def _is_sha(text: str | None) -> bool:
    from cttp.address import is_sha

    return bool(text) and is_sha(text)


def _identity_at(conn, locator, rev, path, symbol) -> str | None:
    """The identity at (repo, path, symbol): at the rev when it is a SHA prefix, else at the
    repository's most recently crawled revision."""
    if rev and _is_sha(rev):
        row = conn.execute(
            "SELECT identity FROM locations WHERE repo = ? AND path = ? AND symbol IS ? "
            "AND sha LIKE ?",
            (locator, path, symbol, rev.lower() + "%"),
        ).fetchone()
        return row["identity"] if row else None
    row = conn.execute(
        "SELECT l.identity FROM locations l JOIN revisions v ON v.repo = l.repo AND v.sha = l.sha "
        "WHERE l.repo = ? AND l.path = ? AND l.symbol IS ? "
        "ORDER BY v.rowid DESC LIMIT 1",
        (locator, path, symbol),
    ).fetchone()
    return row["identity"] if row else None


# --- status ------------------------------------------------------------------------------------


def status(conn: sqlite3.Connection, path: Path) -> dict:
    repos = []
    for r in conn.execute("SELECT * FROM repos ORDER BY locator"):
        revs = conn.execute(
            "SELECT sha, crawled_at, license, files FROM revisions WHERE repo = ? "
            "ORDER BY rowid DESC",
            (r["locator"],),
        ).fetchall()
        repos.append(
            {
                "repo": r["locator"],
                "default_branch": r["default_branch"],
                "local_path": r["local_path"],
                "revisions": [dict(v) for v in revs],
            }
        )
    return {"index": str(path), "counts": counts(conn), "repos": repos}
