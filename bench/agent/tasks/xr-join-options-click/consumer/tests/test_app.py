from app import format_option_names


def test_short_before_long():
    assert format_option_names(["--verbose", "-v"]) == "-v, --verbose"
