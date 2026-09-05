"""The resolver: an address → the page it names, pinned and hashed. Spec §5.

Name form: the registries are asked in order (an HTTP registry hands back its object, a local one
does the git work). Locator form: straight to git through `[remotes]` — no registry is needed,
though a local registry that names the same target lends its name and description. Identity form
needs the object cache (P2-T2). A `#symbol` on either form selects one definition of the file.
"""

from dataclasses import asdict, dataclass, replace

from cttp import gitcache
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
    refs: list[dict]  # derived references: {"address", "relation": "ref", "origin": "derived"}
    imports: dict  # {"stdlib": [...], "third_party": [...]} — top-level modules the page needs

    FIELDS = (
        "name", "address", "rev", "identity", "identity_full", "shape", "shape_full", "kind",
        "language", "symbol", "signature", "docstring", "span", "source", "description",
        "license", "target", "path", "registry", "refs", "imports",
    )  # fmt: skip

    @classmethod
    def from_json(cls, d: dict, registry: str) -> "Resolved":
        """The object as an HTTP registry served it; `registry` becomes the URL that answered."""
        missing = [f for f in cls.FIELDS if f not in d]
        if missing:
            raise RegistryError(f"{registry}: resolution is missing {missing}")
        return cls(**{f: d[f] for f in cls.FIELDS if f != "registry"}, registry=registry)

    def to_json(self) -> dict:
        d = asdict(self)
        d["origin"] = {
            "identity": "derived",
            "shape": "derived",
            "license": "derived",
            "rev": "derived",
            "refs": "derived",
            "description": "asserted" if self.description is not None else None,
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
    return r


def _resolve(a: Address, registries: Registries) -> Resolved:
    if a.form == "identity":
        raise ResolveError("identity addresses need the object cache (P2-T2)")
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
                "relation": "ref",
                "origin": "derived",
            }
            for r in page.refs
        ],
        imports={"stdlib": list(page.stdlib), "third_party": list(page.third_party)},
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
