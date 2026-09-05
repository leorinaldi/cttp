import pytest

from cttp.address import (
    Address,
    AddressError,
    identity,
    is_sha,
    normalize,
    parse,
    parse_pinned,
)

# The identity of `print("hello world!")` under the spec §2 normalization. Pinned so that a change
# to the normalization is loud.
HELLO_IDENTITY = "75a27070015ebce788a4dd572e5c3acffb9e0edffecb96611db6fc1da6f39acb"

SHA = "8f4c2e1d9a03"
FULL = "7f3a9c1e42b8" * 5 + "7f3a"  # 64 hex

# Every example in spec §2, verbatim. (The pinned-form example there carries `id=…` as a link
# field, which is the link line's business, not the address's.)
SPEC_EXAMPLES = [
    "cttp:hello-world",
    f"cttp:hello-world@{SHA}",
    f"cttp:github.com/leorinaldi/thermo@{SHA}/src/thermo/decode.py#reg_to_millicelsius",
    "cttp:sha256:7f3a9c1e42b8",
]


@pytest.mark.parametrize("text", SPEC_EXAMPLES)
def test_spec_examples_round_trip(text):
    a = parse(text)
    assert a.format(marker=True) == text
    assert str(a) == text.removeprefix("cttp:")
    assert parse(str(a)) == a  # the marker is optional on the way in


VALID = [
    # text, expected Address, canonical text
    ("hello-world", Address("name", name="hello-world"), "hello-world"),
    ("cttp:hello-world", Address("name", name="hello-world"), "hello-world"),
    ("leo.thermo", Address("name", name="leo.thermo"), "leo.thermo"),
    ("a1.b-2.c", Address("name", name="a1.b-2.c"), "a1.b-2.c"),
    ("leo.thermo@stable", Address("name", name="leo.thermo", rev="stable"), "leo.thermo@stable"),
    ("hello-world@1.2", Address("name", name="hello-world", rev="1.2"), "hello-world@1.2"),
    ("hello-world@v1", Address("name", name="hello-world", rev="v1"), "hello-world@v1"),
    (
        "hello-world@release/1.0",
        Address("name", name="hello-world", rev="release/1.0"),
        "hello-world@release/1.0",
    ),
    (
        f"hello-world@{SHA.upper()}",
        Address("name", name="hello-world", rev=SHA),
        f"hello-world@{SHA}",
    ),
    (
        "leo.thermo@stable#LM75.read_temp",
        Address("name", name="leo.thermo", rev="stable", symbol="LM75.read_temp"),
        "leo.thermo@stable#LM75.read_temp",
    ),
    ("x#f", Address("name", name="x", symbol="f"), "x#f"),
    (
        f"github.com/leorinaldi/thermo@{SHA}/src/thermo/decode.py",
        Address(
            "locator", locator="github.com/leorinaldi/thermo", rev=SHA, path="src/thermo/decode.py"
        ),
        f"github.com/leorinaldi/thermo@{SHA}/src/thermo/decode.py",
    ),
    (
        "github.com/leorinaldi/cttp-registry@main/snippets/hello_world.py",
        Address(
            "locator",
            locator="github.com/leorinaldi/cttp-registry",
            rev="main",
            path="snippets/hello_world.py",
        ),
        "github.com/leorinaldi/cttp-registry@main/snippets/hello_world.py",
    ),
    (
        "GitHub.COM/Leo/Thermo@v1.2/a.py",  # host lower-cased; owner and repo kept
        Address("locator", locator="github.com/Leo/Thermo", rev="v1.2", path="a.py"),
        "github.com/Leo/Thermo@v1.2/a.py",
    ),
    (
        "gitlab.example.org:8443/g/r@main/a/b.py",  # a port is part of the host
        Address("locator", locator="gitlab.example.org:8443/g/r", rev="main", path="a/b.py"),
        "gitlab.example.org:8443/g/r@main/a/b.py",
    ),
    (
        "github.com\\leo\\thermo@main\\src\\a.py\\",  # backslashes and a trailing slash normalize
        Address("locator", locator="github.com/leo/thermo", rev="main", path="src/a.py"),
        "github.com/leo/thermo@main/src/a.py",
    ),
    (
        # A '/' after '@' starts the path, so a branch like release/1.0 cannot be a locator rev.
        "github.com/leo/thermo@release/1.0/a.py",
        Address("locator", locator="github.com/leo/thermo", rev="release", path="1.0/a.py"),
        "github.com/leo/thermo@release/1.0/a.py",
    ),
    (
        "github.com/leo/thermo@main/a.py#Klass.method",
        Address(
            "locator",
            locator="github.com/leo/thermo",
            rev="main",
            path="a.py",
            symbol="Klass.method",
        ),
        "github.com/leo/thermo@main/a.py#Klass.method",
    ),
    ("sha256:7f3a9c1e42b8", Address("identity", identity="7f3a9c1e42b8"), "sha256:7f3a9c1e42b8"),
    ("sha256:7F3A9C1E42B8", Address("identity", identity="7f3a9c1e42b8"), "sha256:7f3a9c1e42b8"),
    (f"sha256:{FULL}", Address("identity", identity=FULL), f"sha256:{FULL}"),
    ("  cttp:hello-world \n", Address("name", name="hello-world"), "hello-world"),
]


@pytest.mark.parametrize("text,expected,canonical", VALID, ids=[v[0] for v in VALID])
def test_valid(text, expected, canonical):
    a = parse(text)
    assert a == expected
    assert str(a) == canonical
    assert parse(canonical) == a


INVALID = [
    # text, a fragment the error message must contain (it names the offending part)
    ("", "empty address"),
    ("cttp:", "empty address"),
    ("Hello", "'Hello'"),
    ("hello_world", "'hello_world'"),
    ("-x", "'-x'"),
    ("a..b", "''"),
    ("a.B", "'B'"),
    ("hello-world@", "empty version"),
    ("hello-world@a b", "'a b'"),
    ("hello-world#", "empty symbol"),
    ("hello-world#1abc", "'1abc'"),
    ("hello-world#a.", "''"),
    ("hello-world#a-b", "'a-b'"),
    ("github.com/x", "missing rev"),
    ("github.com/leo/thermo/src/a.py", "missing rev"),  # a target, not an address
    ("github.com/leo/thermo@main", "missing path"),
    ("github.com/leo/thermo@main/", "missing path"),
    ("github.com/leo/thermo@", "empty rev"),
    ("github.com/leo@main/a.py", "'github.com/leo'"),
    ("github.com/leo/thermo/extra@main/a.py", "'github.com/leo/thermo/extra'"),
    ("github.com/leo/thermo@main/../a.py", "'..'"),
    ("github.com/leo/thermo@main/a//b.py", "empty"),
    ("-bad-host/leo/thermo@main/a.py", "host '-bad-host'"),
    ("github.com/le o/thermo@main/a.py", "owner 'le o'"),
    ("sha256:", "not hexadecimal"),
    ("sha256:xyz", "'xyz'"),
    ("sha256:7f3a9c1e42b", "11 hex digits"),
    (f"sha256:{FULL}0", "65 hex digits"),
    ("sha256:7f3a9c1e42b8#f", "not hexadecimal"),
]


@pytest.mark.parametrize("text,fragment", INVALID, ids=[v[0] or "<empty>" for v in INVALID])
def test_invalid(text, fragment):
    with pytest.raises(AddressError) as e:
        parse(text)
    assert fragment in str(e.value), str(e.value)


def test_is_pinned():
    assert not parse("hello-world").is_pinned
    assert not parse("hello-world@stable").is_pinned
    assert not parse("github.com/leo/thermo@main/a.py").is_pinned
    assert parse(f"hello-world@{SHA}").is_pinned
    assert parse(f"hello-world@{'a' * 40}").is_pinned
    assert parse(f"github.com/leo/thermo@{SHA}/a.py").is_pinned
    assert parse("sha256:7f3a9c1e42b8").is_pinned


def test_parse_pinned_rejects_a_tag_in_a_stamp():
    assert parse_pinned(f"hello-world@{SHA}").rev == SHA
    with pytest.raises(AddressError, match="'v1' .* not a commit SHA"):
        parse_pinned("hello-world@v1")
    with pytest.raises(AddressError, match="'main' .* not a commit SHA"):
        parse_pinned("github.com/leo/thermo@main/a.py")


def test_is_sha():
    assert is_sha(SHA) and is_sha("A" * 40)
    assert (
        not is_sha(None) and not is_sha("") and not is_sha("8f4c2e1d9a0") and not is_sha("g" * 12)
    )
    assert not is_sha("a" * 41)


def test_normalize():
    assert normalize("  x\r\n  y  \r\n\n\n") == "x\ny\n"
    assert normalize("    def f():\n        pass") == "def f():\n    pass\n"


def test_identity_is_stable():
    assert identity('print("hello world!")') == HELLO_IDENTITY
    assert identity('  print("hello world!")\r\n\n') == HELLO_IDENTITY
