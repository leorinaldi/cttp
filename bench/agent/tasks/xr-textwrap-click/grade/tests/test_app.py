import ast
import inspect

import app
from app import wrap

TEXT = "the quick brown fox jumps over the lazy dog and keeps on running"
BOLD, RESET = "\x1b[1m", "\x1b[0m"


def test_wrap_fills_a_paragraph():
    assert wrap(TEXT, 24) == "the quick brown fox\njumps over the lazy dog\nand keeps on running"


def test_indent_applies_to_every_line():
    assert wrap(TEXT, 30, indent="  ") == (
        "  the quick brown fox jumps\n  over the lazy dog and keeps\n  on running"
    )


def test_ansi_codes_do_not_count_toward_the_width():
    # `the` is styled: the raw string is 8 characters longer, the visible text is not
    styled = f"{BOLD}the{RESET} quick brown fox jumps over the lazy dog and keeps on running"
    assert wrap(styled, 24) == (
        f"{BOLD}the{RESET} quick brown fox\njumps over the lazy dog\nand keeps on running"
    )


def test_a_styled_word_is_never_split():
    styled = f"aaaa {BOLD}bbbbbb{RESET} cccc"
    assert wrap(styled, 6) == f"aaaa\n{BOLD}bbbbbb{RESET}\ncccc"


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
