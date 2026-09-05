from app import safe_markup


def test_a_tag_is_escaped():
    assert safe_markup("[bold]hi[/bold]") == "\\[bold]hi\\[/bold]"
