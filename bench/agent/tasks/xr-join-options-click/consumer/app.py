"""A help table for a command-line tool: option names on the left, help text on the right."""


def help_rows(options: dict[tuple[str, ...], str]) -> list[tuple[str, str]]:
    """Each option's names joined the way a help screen shows them, with its help text."""
    return [(format_option_names(names), text) for names, text in options.items()]
