"""A help table for a command-line tool: option names on the left, help text on the right."""

import collections.abc as cabc

# cttp: github.com/pallets/click@36baa15ff831/src/click/parser.py#_split_opt id=sha256:6e7039f727e6  ~"def _split_opt(opt: str) -> tuple[str, str]"
def _split_opt(opt: str) -> tuple[str, str]:
    first = opt[:1]
    if first.isalnum():
        return "", opt
    if opt[1:2] == first:
        return opt[:2], opt[2:]
    return first, opt[1:]

# cttp: github.com/pallets/click@36baa15ff831/src/click/formatting.py#join_options id=sha256:afcd9060f37f  ~"def join_options(options: cabc.Iterable[str]) -> tuple[str, bool] — Given a list of option strings this joins them in the most appropriate way and returns them in the form ``(formatted_string, any_prefix_is_slash)`` where the second item in the tuple is a flag that indicates if any of the option prefixes was a slash."
def join_options(options: cabc.Iterable[str]) -> tuple[str, bool]:
    """Given a list of option strings this joins them in the most appropriate
    way and returns them in the form ``(formatted_string,
    any_prefix_is_slash)`` where the second item in the tuple is a flag that
    indicates if any of the option prefixes was a slash.
    """
    rv = []
    any_prefix_is_slash = False

    for opt in options:
        prefix = _split_opt(opt)[0]

        if prefix == "/":
            any_prefix_is_slash = True

        rv.append((len(prefix), opt))

    rv.sort(key=lambda x: x[0])
    return ", ".join(x[1] for x in rv), any_prefix_is_slash

def help_rows(options: dict[tuple[str, ...], str]) -> list[tuple[str, str]]:
    """Each option's names joined the way a help screen shows them, with its help text."""
    return [(format_option_names(names), text) for names, text in options.items()]


def format_option_names(names) -> str:
    """The option names joined the way a help screen shows them: shortest prefix first."""
    return join_options(names)[0]


def uses_slash_prefix(names) -> bool:
    """Whether any of the names is a `/`-style (Windows) option."""
    return join_options(names)[1]
