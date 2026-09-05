import pytest

from cttp.registry import RegistryError
from cttp.resolve import ResolveError, resolve


def test_resolve_hello_world(registry):
    r = resolve("hello-world", registry)
    assert r.source == 'print("hello world!")\n'
    assert r.kind == "script" and r.language == "python"
    assert r.address == f"hello-world@{r.rev[:12]}" and len(r.rev) == 40
    assert r.identity == "sha256:" + r.identity_full[:12]
    assert r.license == "MIT"
    assert r.description == "Prints 'hello world'."
    j = r.to_json()
    assert j["origin"]["license"] == "derived" and j["origin"]["description"] == "asserted"


def test_resolve_by_label_and_rev(registry):
    r = resolve("hello-world", registry)
    assert resolve("hello-world@latest", registry).rev == r.rev
    assert resolve("hello-world@v1", registry).rev == r.rev
    assert resolve(r.address, registry).rev == r.rev


def test_unknown_name_names_the_registry(registry):
    with pytest.raises(RegistryError, match="no-such-name.*registry"):
        resolve("no-such-name", registry)


LOCATOR = "github.com/leorinaldi/cttp-registry@main/snippets/hello_world.py"


def test_resolve_locator_is_the_same_page_as_the_name(registry):
    by_name = resolve("hello-world", registry)
    by_locator = resolve("cttp:" + LOCATOR, registry)
    for f in ("rev", "identity", "identity_full", "kind", "language", "source", "license"):
        assert getattr(by_locator, f) == getattr(by_name, f), f
    assert by_locator.target == by_name.target and by_locator.path == by_name.path
    assert (
        by_locator.address
        == f"github.com/leorinaldi/cttp-registry@{by_name.rev[:12]}/snippets/hello_world.py"
    )
    # the local registry names this target, so it lends its name and description
    assert by_locator.name == "hello-world" and by_locator.description == by_name.description
    assert by_locator.registry == by_name.registry
    # the pinned locator resolves again to the same rev, offline
    assert resolve(by_locator.address, registry).rev == by_name.rev


def test_resolve_locator_without_an_entry(registry):
    r = resolve("github.com/leorinaldi/cttp-registry@v1/README.md", registry)
    assert r.name is None and r.description is None and r.registry is None
    assert r.path == "README.md" and r.to_json()["origin"]["description"] is None


def test_resolve_locator_errors_name_the_part(registry):
    with pytest.raises(ResolveError, match="'nope' is not a revision"):
        resolve("github.com/leorinaldi/cttp-registry@nope/snippets/hello_world.py", registry)
    with pytest.raises(ResolveError, match="'missing.py' is not in"):
        resolve("github.com/leorinaldi/cttp-registry@main/missing.py", registry)
    with pytest.raises(ResolveError, match="identity"):
        resolve("sha256:" + "a" * 12, registry)
