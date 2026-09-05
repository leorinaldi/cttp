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
    source = inspect.getsource(app)
    assert "import rich" not in source and "from rich" not in source
