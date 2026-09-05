import pytest
from conftest import add_remote_repo, add_to_registry

from cttp.registry import RegistryError
from cttp.resolve import Mismatch, ResolveError, resolve


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
    with pytest.raises(ResolveError, match="neither the object cache nor the index"):
        resolve("sha256:" + "a" * 12, registry)


# --- P2-T1: locator resolution in full ---------------------------------------------------------


def test_a_tag_rev_pins_to_the_full_sha(registry):
    r = resolve(
        "github.com/leorinaldi/thermo@v1/src/thermo/decode.py#reg_to_millicelsius", registry
    )
    assert len(r.rev) == 40 and r.rev.isalnum()
    assert (
        r.address
        == f"github.com/leorinaldi/thermo@{r.rev[:12]}/src/thermo/decode.py#reg_to_millicelsius"
    )
    assert r.license == "MIT" and r.to_json()["origin"]["license"] == "derived"


def test_a_repository_without_a_license_file_has_none(registry, tmp_path):
    locator = add_remote_repo(tmp_path, "bare", {"a.py": "x = 1\n"})
    r = resolve(f"{locator}@v1/a.py", registry)
    assert r.license is None and r.to_json()["license"] is None


def test_a_name_without_a_path_finds_a_unique_symbol(registry, tmp_path):
    add_to_registry(tmp_path, "leo.thermo", target="github.com/leorinaldi/thermo")
    r = resolve("leo.thermo#reg_to_millicelsius", registry)
    assert r.path == "src/thermo/decode.py" and r.symbol == "reg_to_millicelsius"
    assert r.address == f"leo.thermo@{r.rev[:12]}#reg_to_millicelsius" and r.name == "leo.thermo"
    assert resolve("leo.thermo#LM75.read_temp", registry).path == "src/thermo/lm75.py"
    with pytest.raises(ResolveError, match="names the whole repository .*add a #symbol"):
        resolve("leo.thermo", registry)
    with pytest.raises(ResolveError, match="'nowhere' is not defined anywhere"):
        resolve("leo.thermo#nowhere", registry)


def test_a_name_without_a_path_stops_on_two_candidates(registry, tmp_path):
    locator = add_remote_repo(
        tmp_path,
        "twins",
        {"a.py": "def helper():\n    return 1\n", "b/c.py": "def helper():\n    return 2\n"},
    )
    add_to_registry(tmp_path, "twins", target=locator)
    with pytest.raises(ResolveError) as e:
        resolve("twins#helper", registry)
    message = str(e.value)
    assert "'helper' is defined 2 times" in message
    assert f"{locator}@" in message and "/a.py#helper" in message and "/b/c.py#helper" in message
    # the candidates it lists are locators that resolve
    candidate = message.split(": ", 2)[-1].split(", ")[0]
    assert resolve(candidate, registry).source == "def helper():\n    return 1\n"


def test_an_id_mismatch_is_reported_with_both_hashes(registry):
    r = resolve("hello-world", registry)
    assert resolve("hello-world", registry, expect=r.identity).identity == r.identity
    wrong = "sha256:" + "0" * 12
    with pytest.raises(Mismatch) as e:
        resolve(r.address, registry, expect=wrong)
    assert (
        str(e.value) == f"id mismatch: the link says {wrong} but {r.address} hashes to {r.identity}"
    )
    assert e.value.resolved.identity == r.identity and e.value.claimed == wrong
