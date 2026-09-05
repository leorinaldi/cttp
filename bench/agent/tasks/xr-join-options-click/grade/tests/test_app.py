import ast
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
    """The library must not be imported — the point is to reuse the code, not depend
    on it. Parsed rather than grepped: a substring check also matches an attribution
    comment naming the library, which is exactly what a cttp link block carries."""
    banned = {"click"}
    tree = ast.parse(inspect.getsource(app))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in banned, alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in banned, node.module
