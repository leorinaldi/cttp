import pytest

from cttp.registry import RegistryError
from cttp.resolve import resolve


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
