"""The resolver: an address → the page it names, pinned and hashed. Spec §5. Names only so far."""

from dataclasses import asdict, dataclass

from cttp import gitcache
from cttp.address import identity, parse_name, short
from cttp.extract.python import extract_script
from cttp.registry import Registries, ref_for, split_target


class ResolveError(LookupError):
    pass


@dataclass(frozen=True)
class Resolved:
    name: str
    address: str  # pinned: name@<12-hex rev>
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
    registry: str

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
    n = parse_name(text)
    if n.symbol:
        raise ResolveError("symbols are not resolvable yet (P1-T3)")
    entry, registry = registries.lookup(n.name)
    locator, path = split_target(entry.target)
    if path is None:
        raise ResolveError(f"{n.name!r} names a whole repository; symbol search arrives in P2-T1")
    ref = ref_for(entry, n.rev)
    repo = gitcache.ensure_repo(locator, registries.url_for(locator), want=ref)
    try:
        sha = gitcache.rev_parse(repo, ref)
    except gitcache.GitError as e:
        raise ResolveError(f"{ref!r} is not a revision of {locator}: {e}") from e
    try:
        text_at_rev = gitcache.show(repo, sha, path)
    except gitcache.GitError as e:
        raise ResolveError(f"{path!r} is not in {locator} at {short(sha)}: {e}") from e
    page = extract_script(text_at_rev)
    ident = identity(page.source)
    return Resolved(
        name=n.name,
        address=f"{n.name}@{short(sha)}",
        rev=sha,
        identity=f"sha256:{short(ident)}",
        identity_full=ident,
        kind=page.kind,
        language=page.language,
        source=page.source,
        description=entry.description,
        license=gitcache.license_of(repo, sha),
        target=entry.target,
        path=path,
        registry=registry.describe(),
    )
