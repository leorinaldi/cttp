"""The resolver: an address → the page it names, pinned and hashed. Spec §5.

Name form: the registries are asked in order (an HTTP registry hands back its object, a local one
does the git work). Locator form: straight to git through `[remotes]` — no registry is needed,
though a local registry that names the same target lends its name and description. Identity form
needs the object cache (P2-T2).
"""

from dataclasses import asdict, dataclass

from cttp import gitcache
from cttp.address import Address, identity, parse, short
from cttp.extract.python import extract_script
from cttp.registry import Entry, HttpRegistry, Registries, RegistryError, ref_for, split_target


class ResolveError(LookupError):
    pass


@dataclass(frozen=True)
class Resolved:
    name: str | None  # None when a locator has no entry in any local registry
    address: str  # pinned: name@<12-hex rev>, or host/owner/repo@<12-hex rev>/path
    rev: str  # full commit SHA
    identity: str  # sha256:<12 hex>
    identity_full: str
    kind: str
    language: str
    source: str
    description: str | None
    license: str | None
    target: str
    path: str
    registry: str | None  # which registry answered, or lent the name; None for a bare locator

    FIELDS = (
        "name", "address", "rev", "identity", "identity_full", "kind", "language", "source",
        "description", "license", "target", "path", "registry",
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
            "license": "derived",
            "rev": "derived",
            "description": "asserted" if self.description is not None else None,
        }
        return d


def resolve(text: str, registries: Registries) -> Resolved:
    a = parse(text)
    if a.symbol:
        raise ResolveError("symbols are not resolvable yet (P1-T3)")
    if a.form == "identity":
        raise ResolveError("identity addresses need the object cache (P2-T2)")
    if a.form == "locator":
        return resolve_locator(a, registries)

    def ask(registry):
        if isinstance(registry, HttpRegistry):
            return Resolved.from_json(registry.fetch(a.name, a.rev), registry.url)
        return resolve_entry(a, registry.lookup(a.name), registry, registries)

    return registries.first(a.name, ask)


def resolve_entry(a: Address, entry: Entry, registry, registries: Registries) -> Resolved:
    """Name → entry → locator → fetch → extract → hash, against a local registry repository."""
    locator, path = split_target(entry.target)
    if path is None:
        raise ResolveError(f"{a.name!r} names a whole repository; symbol search arrives in P2-T1")
    ref = ref_for(entry, a.rev)
    sha, page, license = _fetch_page(locator, ref, path, registries)
    ident = identity(page.source)
    return Resolved(
        name=a.name,
        address=f"{a.name}@{short(sha)}",
        rev=sha,
        identity=f"sha256:{short(ident)}",
        identity_full=ident,
        kind=page.kind,
        language=page.language,
        source=page.source,
        description=entry.description,
        license=license,
        target=entry.target,
        path=path,
        registry=registry.describe(),
    )


def resolve_locator(a: Address, registries: Registries) -> Resolved:
    """Locator → fetch → extract → hash. A local registry naming the target lends its entry."""
    sha, page, license = _fetch_page(a.locator, a.rev, a.path, registries)
    target = f"{a.locator}/{a.path}"
    found = registries.entry_for_target(target)
    entry, registry = found if found else (None, None)
    ident = identity(page.source)
    return Resolved(
        name=entry.name if entry else None,
        address=f"{a.locator}@{short(sha)}/{a.path}",
        rev=sha,
        identity=f"sha256:{short(ident)}",
        identity_full=ident,
        kind=page.kind,
        language=page.language,
        source=page.source,
        description=entry.description if entry else None,
        license=license,
        target=target,
        path=a.path,
        registry=registry.describe() if registry else None,
    )


def _fetch_page(locator: str, ref: str, path: str, registries: Registries):
    repo = gitcache.ensure_repo(locator, registries.url_for(locator), want=ref)
    try:
        sha = gitcache.rev_parse(repo, ref)
    except gitcache.GitError as e:
        raise ResolveError(f"{ref!r} is not a revision of {locator}: {e}") from e
    try:
        text_at_rev = gitcache.show(repo, sha, path)
    except gitcache.GitError as e:
        raise ResolveError(f"{path!r} is not in {locator} at {short(sha)}: {e}") from e
    return sha, extract_script(text_at_rev), gitcache.license_of(repo, sha)
