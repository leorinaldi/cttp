import inspect

import app
from app import format_option_names, uses_slash_prefix


def test_short_before_long():
    assert format_option_names(["--verbose", "-v"]) == "-v, --verbose"


def test_order_is_by_prefix_length_and_stable():
    assert format_option_names(["--all", "--list", "-l", "-a"]) == "-l, -a, --all, --list"


def test_slash_options():
    # `/` and `-` are both one-character prefixes: the given order is kept
    assert format_option_names(["/debug", "-d"]) == "/debug, -d"
    assert format_option_names(["--debug", "/d"]) == "/d, --debug"
    assert uses_slash_prefix(["/debug", "-d"]) is True
    assert uses_slash_prefix(["--debug", "-d"]) is False


def test_plus_and_bare_names():
    assert format_option_names(["+w", "--warn"]) == "+w, --warn"


def test_click_is_not_imported():
    source = inspect.getsource(app)
    assert "import click" not in source and "from click" not in source
