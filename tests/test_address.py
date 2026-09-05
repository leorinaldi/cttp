import pytest

from cttp.address import AddressError, identity, normalize, parse_name

# The identity of `print("hello world!")` under the spec §2 normalization. Pinned so that a change
# to the normalization is loud.
HELLO_IDENTITY = "75a27070015ebce788a4dd572e5c3acffb9e0edffecb96611db6fc1da6f39acb"


def test_parse_name_forms():
    assert parse_name("hello-world").name == "hello-world"
    assert parse_name("cttp:hello-world@8f4c2e1d9a03").rev == "8f4c2e1d9a03"
    n = parse_name("leo.thermo@stable#LM75.read_temp")
    assert (n.name, n.rev, n.symbol) == ("leo.thermo", "stable", "LM75.read_temp")


@pytest.mark.parametrize("bad", ["Hello", "hello_world", "", "-x", "a..b", "github.com/x"])
def test_parse_name_rejects(bad):
    with pytest.raises(AddressError):
        parse_name(bad)


def test_normalize():
    assert normalize("  x\r\n  y  \r\n\n\n") == "x\ny\n"
    assert normalize("    def f():\n        pass") == "def f():\n    pass\n"


def test_identity_is_stable():
    assert identity('print("hello world!")') == HELLO_IDENTITY
    assert identity('  print("hello world!")\r\n\n') == HELLO_IDENTITY
