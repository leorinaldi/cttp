"""The resolver: an address → the page it names, pinned and hashed. Spec §5.

Name form: the registries are asked in order (an HTTP registry hands back its object, a local one
does the git work). Locator form: straight to git through `[remotes]` — no registry is needed,
though a local registry that names the same target lends its name and description. Identity form:
the object cache, then the index — every location known to carry that identity, the most recent
one as the address. A `#symbol` on either form selects one definition of the file. Every page
resolved is stored in the object cache on the way out.

`latest()` is the forward direction: from a pinned address, the same definition at the
repository's current head — same path and symbol (rule 1), else the same identity anywhere at
head (rule 2). Rule 3, across repositories through the index, is Phase 4.
"""

from dataclasses import asdict, dataclass, field, replace

from cttp import gitcache, objects
from cttp.address import Address, parse
from cttp.extract import ExtractError, Page, definitions, extract, language_of
from cttp.hashing import ShapeError, identity, shape, short
from cttp.registry import Entry, HttpRegistry, Registries, RegistryError, ref_for, split_target


class ResolveError(LookupError):
    pass


class Mismatch(ResolveError):
    """The page resolved, but its identity is not the one the link's `id=` claims."""

    def __init__(self, resolved: "Resolved", claimed: str):
        self.resolved = resolved
        self.claimed = claimed
        super().__init__(
            f"id mismatch: the link says {claimed} but {resolved.address} hashes to "
            f"{resolved.identity}"
        )


@dataclass(frozen=True)
class Resolved:
    name: str | None  # None when a locator has no entry in any local registry
    address: str  # pinned: name@<12-hex rev> or host/owner/repo@<12-hex rev>/path, [#symbol]
    rev: str  # full commit SHA
    identity: str  # sha256:<12 hex>
    identity_full: str
    shape: str | None  # sha256:<12 hex>; None when the page has no shape (not Python)
    shape_full: str | None
    kind: str
    language: str
    symbol: str | None
    signature: str | None
    docstring: str | None
    span: list[int]  # [first, last] 1-based inclusive lines in the origin file
    source: str
    description: str | None
    license: str | None
    target: str
    path: str
    registry: str | None  # which registry answered, or lent the name; None for a bare locator
    refs: list[dict]  # derived: {"address", "name", "relation": "ref", "origin": "derived"}
    imports: dict  # {"stdlib": [...], "third_party": [...], "statements": [...]} — see Page
    links: list[dict] = field(default_factory=list)  # asserted: the link lines in the page's text
    unresolved: list[str] = field(default_factory=list)  # derived: free names (see Page)
    # not part of the registry contract: set when an identity address was answered from a cache
    locations: list[dict] = field(
        default_factory=list
    )  # every place the page was seen, latest last
    via: str | None = None  # "cache" | "index" | None (the repository itself)

    FIELDS = (
        "name", "address", "rev", "identity", "identity_full", "shape", "shape_full", "kind",
        "language", "symbol", "signature", "docstring", "span", "source", "description",
        "license", "target", "path", "registry", "refs", "imports",
    )  # fmt: skip
    OPTIONAL = {"links": list, "unresolved": list}  # newer than the first contract; may be absent

    @classmethod
    def from_json(cls, d: dict, registry: str) -> "Resolved":
        """The object as an HTTP registry served it; `registry` becomes the URL that answered."""
        missing = [f for f in cls.FIELDS if f not in d]
        if missing:
            raise RegistryError(f"{registry}: resolution is missing {missing}")
        extra = {k: d.get(k) or make() for k, make in cls.OPTIONAL.items()}
        return cls(**{f: d[f] for f in cls.FIELDS if f != "registry"}, registry=registry, **extra)

    def to_json(self) -> dict:
        d = asdict(self)
        d["origin"] = {
            "identity": "derived",
            "shape": "derived",
            "license": "derived",
            "rev": "derived",
            "refs": "derived",
            "imports": "derived",
            "unresolved": "derived",
            "links": "asserted",
            "description": "asserted" if self.description is not None else None,
            "location": self.via or "repository",
        }
        return d


def resolve(text: str, registries: Registries, expect: str | None = None) -> Resolved:
    """The page an address names. With `expect` (an `id=` value, `sha256:<hex>`), a page whose
    identity does not start with it is a `Mismatch` — reported, never hidden (spec §5)."""
    r = _resolve(parse(text), registries)
    if expect is not None:
        claimed = expect.removeprefix("sha256:").lower()
        if not claimed or not r.identity_full.startswith(claimed):
            raise Mismatch(r, expect)
    if r.via is None:
        objects.store(r)
    return r


def _resolve(a: Address, registries: Registries) -> Resolved:
    if a.form == "identity":
        return resolve_identity(a)
    if a.form == "locator":
        return resolve_locator(a, registries)

    def ask(registry):
        if isinstance(registry, HttpRegistry):
            return Resolved.from_json(registry.fetch(a.name, a.rev, a.symbol), registry.url)
        return resolve_entry(a, registry.lookup(a.name), registry, registries)

    return registries.first(a.name, ask)


def resolve_entry(a: Address, entry: Entry, registry, registries: Registries) -> Resolved:
    """Name → entry → locator → fetch → extract → hash, against a local registry repository.

    An entry naming a whole repository (no path) needs a `#symbol`, found by searching the
    repository at that rev; it must be unique there, else the candidates are listed and
    resolution stops (spec §5).
    """
    locator, path = split_target(entry.target)
    ref = ref_for(entry, a.rev)
    if path is None:
        if a.symbol is None:
            raise ResolveError(
                f"{a.name!r} names the whole repository {locator}; add a #symbol to say which "
                "definition"
            )
        path = find_symbol(locator, ref, a.symbol, registries)
    sha, page, license = _fetch_page(locator, ref, path, a.symbol, registries)
    return _resolved(
        replace(a, rev=short(sha)),
        sha,
        page,
        license,
        locator,
        path,
        entry,
        registry.describe(),
    )


def resolve_locator(a: Address, registries: Registries) -> Resolved:
    """Locator → fetch → extract → hash. A local registry naming the target lends its entry."""
    sha, page, license = _fetch_page(a.locator, a.rev, a.path, a.symbol, registries)
    found = registries.entry_for_target(f"{a.locator}/{a.path}")
    entry, registry = found if found else (None, None)
    return _resolved(
        replace(a, rev=short(sha)),
        sha,
        page,
        license,
        a.locator,
        a.path,
        entry,
        registry.describe() if registry else None,
    )


def resolve_identity(a: Address) -> Resolved:
    """Identity → the object cache, then the index: the page and every location it was seen at.
    The address is the location seen most recently; `via` says which cache answered."""
    try:
        stored = objects.lookup(a.identity)
    except objects.AmbiguousIdentity as e:
        raise ResolveError(str(e)) from e
    if stored is None:
        stored = objects.index_lookup(a.identity)
    if stored is None:
        raise ResolveError(
            f"sha256:{a.identity[:16]} is known to neither the object cache nor the index "
            "(the index arrives in Phase 4); resolve it by name or locator once to cache it"
        )
    at = stored.latest
    shp = stored.meta["shape_full"]
    return Resolved(
        name=at["name"],
        address=at["address"],
        rev=at["rev"],
        identity=f"sha256:{short(stored.identity)}",
        identity_full=stored.identity,
        shape=f"sha256:{short(shp)}" if shp else None,
        shape_full=shp,
        kind=stored.meta["kind"],
        language=stored.meta["language"],
        symbol=stored.meta["symbol"],
        signature=stored.meta["signature"],
        docstring=stored.meta["docstring"],
        span=stored.meta["span"],
        source=stored.source,
        description=at["description"],
        license=at["license"],
        target=at["target"],
        path=at["path"],
        registry=at["registry"],
        refs=stored.meta["refs"],
        imports=stored.meta["imports"],
        links=stored.meta.get("links") or [],
        unresolved=stored.meta.get("unresolved") or [],
        locations=[{**x, "origin": "cache"} for x in stored.locations],
        via="cache",
    )


def _resolved(
    pinned: Address,
    sha: str,
    page: Page,
    license: str | None,
    locator: str,
    path: str,
    entry: Entry | None,
    registry: str | None,
) -> Resolved:
    ident = identity(page.source)
    shp = _shape_of(page)
    rev12 = short(sha)
    return Resolved(
        name=entry.name if entry else None,
        address=str(pinned),
        rev=sha,
        identity=f"sha256:{short(ident)}",
        identity_full=ident,
        shape=f"sha256:{short(shp)}" if shp else None,
        shape_full=shp,
        kind=page.kind,
        language=page.language,
        symbol=page.symbol,
        signature=page.signature,
        docstring=page.docstring,
        span=list(page.span),
        source=page.source,
        description=entry.description if entry else None,
        license=license,
        target=f"{locator}/{path}",
        path=path,
        registry=registry,
        refs=[
            {
                "address": str(
                    Address("locator", locator=locator, path=r.path, rev=rev12, symbol=r.symbol)
                ),
                "name": r.name,
                "relation": "ref",
                "origin": "derived",
            }
            for r in page.refs
        ],
        imports={
            "stdlib": list(page.stdlib),
            "third_party": list(page.third_party),
            "statements": list(page.imports),
        },
        links=[
            {
                "address": k.address,
                "relation": k.relation,
                "fields": dict(k.fields),
                "description": k.description,
                "derived": k.description_derived,
                "line": k.line + 1,
                "indent": k.indent,
                "origin": "asserted",
            }
            for k in page.links
        ],
        unresolved=list(page.unresolved),
    )


def _shape_of(page: Page) -> str | None:
    if page.language != "python":
        return None
    try:
        return shape(page.source)
    except ShapeError:
        return None


def find_symbol(locator: str, ref: str, symbol: str, registries: Registries) -> str:
    """The one file at `ref` that defines `symbol`; every file with an extractor is searched."""
    repo, sha = _repo_at(locator, ref, registries)
    found = [
        path
        for path in gitcache.ls_tree(repo, sha)
        if language_of(path) != "text"
        and symbol in definitions(path, gitcache.show(repo, sha, path))
    ]
    if len(found) == 1:
        return found[0]
    if not found:
        raise ResolveError(f"{symbol!r} is not defined anywhere in {locator} at {short(sha)}")
    raise ResolveError(
        f"{symbol!r} is defined {len(found)} times in {locator} at {short(sha)}; say which with a "
        "locator: " + ", ".join(f"{locator}@{short(sha)}/{p}#{symbol}" for p in found)
    )


def _repo_at(locator: str, ref: str, registries: Registries) -> tuple:
    repo = gitcache.ensure_repo(locator, registries.url_for(locator), want=ref)
    try:
        return repo, gitcache.rev_parse(repo, ref)
    except gitcache.GitError as e:
        raise ResolveError(f"{ref!r} is not a revision of {locator}: {e}") from e


def _fetch_page(locator: str, ref: str, path: str, symbol: str | None, registries: Registries):
    repo, sha = _repo_at(locator, ref, registries)
    try:
        text_at_rev = gitcache.show(repo, sha, path)
    except gitcache.GitError as e:
        raise ResolveError(f"{path!r} is not in {locator} at {short(sha)}: {e}") from e
    files = gitcache.ls_tree(repo, sha) if language_of(path) == "python" else ()
    try:
        page = extract(path, text_at_rev, symbol, files)
    except ExtractError as e:
        raise ResolveError(f"{locator}@{short(sha)}: {e}") from e
    return sha, page, gitcache.license_of(repo, sha)


# --- forward: `resolve --latest` --------------------------------------------------------------


@dataclass(frozen=True)
class Latest:
    """Where a pinned definition is at the repository's head, and which rule found it."""

    pinned: Resolved
    head: str  # the full SHA of the head that was searched
    found: bool
    rule: str | None  # "same-path" | "same-identity" | None — derived
    to: Resolved | None
    changed: bool | None  # the identity differs from the pinned one (rule 1 only)
    message: str

    def to_json(self) -> dict:
        return {
            "from": self.pinned.to_json(),
            "head": self.head,
            "found": self.found,
            "rule": self.rule,
            "to": self.to.to_json() if self.to else None,
            "changed": self.changed,
            "message": self.message,
            "origin": {"rule": "derived", "head": "derived"},
        }


def latest(text: str, registries: Registries) -> Latest:
    """Spec §5's `--latest`: follow a pinned address forward to the repository's current head.

    A name goes to the ref its registry entry calls default; a locator to the repository's
    default branch. Rule 1: the same path and symbol still exist there (the identity may have
    changed — a normal edit). Rule 2: the same identity is somewhere else at head (a move within
    the repository). Neither: rule 3 needs the index.
    """
    a = parse(text)
    if not a.is_pinned or a.form == "identity":
        raise ResolveError(
            f"--latest follows a pinned name or locator address forward; {text!r} is not one"
        )
    pinned = resolve(text, registries)
    locator, path = split_target(pinned.target)
    path = pinned.path
    if a.form == "name":
        entry, _ = registries.lookup(a.name)
        ref = ref_for(entry)
    else:
        ref = gitcache.default_branch(gitcache.ensure_repo(locator, registries.url_for(locator)))
    repo, head = _repo_at(locator, ref, registries)
    at = Address("locator", locator=locator, path=path, rev=short(head), symbol=a.symbol)
    to_address = replace(a, rev=short(head)) if a.form == "name" else at

    # rule 1: the same path and symbol at head
    try:
        page = _page_at(repo, head, locator, path, a.symbol)
    except ResolveError:
        page = None
    if page is not None:
        to = resolve(str(to_address), registries)
        changed = to.identity_full != pinned.identity_full
        return Latest(
            pinned, head, True, "same-path", to, changed,
            f"{'the identity changed' if changed else 'unchanged'} at the same path and symbol",
        )  # fmt: skip

    # rule 2: the same identity anywhere at head
    for found_path, found_symbol in _same_identity_at(repo, head, locator, pinned):
        to = resolve(
            str(
                Address(
                    "locator",
                    locator=locator,
                    path=found_path,
                    rev=short(head),
                    symbol=found_symbol,
                )
            ),
            registries,
        )
        return Latest(
            pinned, head, True, "same-identity", to, False,
            f"moved within {locator}: {path}{'#' + a.symbol if a.symbol else ''} → "
            f"{found_path}{'#' + found_symbol if found_symbol else ''}",
        )  # fmt: skip

    return Latest(
        pinned, head, False, None, None, None,
        f"{path}{'#' + a.symbol if a.symbol else ''} is not at {locator}@{short(head)} by path "
        "or by identity; rule 3 (a move across repositories, or a fork) needs the index, which "
        "arrives in Phase 4",
    )  # fmt: skip


def _page_at(repo, sha: str, locator: str, path: str, symbol: str | None) -> Page:
    try:
        text_at_rev = gitcache.show(repo, sha, path)
    except gitcache.GitError as e:
        raise ResolveError(f"{path!r} is not in {locator} at {short(sha)}") from e
    files = gitcache.ls_tree(repo, sha) if language_of(path) == "python" else ()
    try:
        return extract(path, text_at_rev, symbol, files)
    except ExtractError as e:
        raise ResolveError(str(e)) from e


def _same_identity_at(repo, sha: str, locator: str, pinned: Resolved):
    """Every (path, symbol) at `sha` whose page has the pinned identity; definitions with the
    pinned symbol's own name are tried first, since a move usually keeps the name."""
    files = gitcache.ls_tree(repo, sha)
    want = pinned.identity_full
    name = pinned.symbol.split(".")[-1] if pinned.symbol else None
    candidates: list[tuple[str, str | None]] = []
    for path in files:
        if pinned.symbol is None:
            candidates.append((path, None))
            continue
        if language_of(path) != "python":
            continue
        symbols = definitions(path, gitcache.show(repo, sha, path))
        first = [s for s in symbols if s.split(".")[-1] == name]
        candidates += [(path, s) for s in first] + [(path, s) for s in symbols if s not in first]
    candidates.sort(key=lambda c: 0 if c[1] and c[1].split(".")[-1] == name else 1)
    for path, symbol in candidates:
        try:
            page = _page_at(repo, sha, locator, path, symbol)
        except ResolveError:
            continue
        if identity(page.source) == want:
            yield path, symbol
