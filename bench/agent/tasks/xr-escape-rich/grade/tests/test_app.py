import ast
import inspect

import app
from app import safe_markup


def test_a_tag_is_escaped():
    assert safe_markup("[bold]hi[/bold]") == "\\[bold]hi\\[/bold]"


def test_plain_brackets_are_left_alone():
    assert safe_markup("[1, 2, 3]") == "[1, 2, 3]"
    assert safe_markup("no markup here") == "no markup here"


def test_existing_backslashes_are_doubled():
    assert safe_markup("\\[red]x") == "\\\\\\[red]x"


def test_a_trailing_backslash_is_escaped():
    assert safe_markup("ends with \\") == "ends with \\\\"


def test_rich_is_not_imported():
    """The library must not be imported — the point is to reuse the code, not depend
    on it. Parsed rather than grepped: a substring check also matches an attribution
    comment naming the library, which is exactly what a cttp link block carries."""
    banned = {"rich"}
    tree = ast.parse(inspect.getsource(app))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in banned, alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in banned, node.module
