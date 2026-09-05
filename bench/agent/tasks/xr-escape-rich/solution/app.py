"""Log lines for a console that understands rich-style [markup]."""

from typing import Match
from typing import Callable
import re

# cttp: github.com/Textualize/rich@9d8f9a372cc5/rich/markup.py#_ReStringMatch id=sha256:c29c262b43f3  ~"_ReStringMatch"
_ReStringMatch = Match[str]  # regex match object

# cttp: github.com/Textualize/rich@9d8f9a372cc5/rich/markup.py#_ReSubCallable id=sha256:55303fd69cbb  ~"_ReSubCallable"
_ReSubCallable = Callable[[_ReStringMatch], str]  # Callable invoked by re.sub

# cttp: github.com/Textualize/rich@9d8f9a372cc5/rich/markup.py#_EscapeSubMethod id=sha256:8c13b512c6c3  ~"_EscapeSubMethod"
_EscapeSubMethod = Callable[[_ReSubCallable, str], str]  # Sub method of a compiled re

# cttp: github.com/Textualize/rich@9d8f9a372cc5/rich/markup.py#escape id=sha256:39c29031206c  ~"def escape(markup: str, _escape: _EscapeSubMethod=re.compile('(\\\\*)(\\[[a-z#/@][^[]*?])').sub) -> str — Escapes text so that it won't be interpreted as markup."
def escape(
    markup: str,
    _escape: _EscapeSubMethod = re.compile(r"(\\*)(\[[a-z#/@][^[]*?])").sub,
) -> str:
    """Escapes text so that it won't be interpreted as markup.

    Args:
        markup (str): Content to be inserted in to markup.

    Returns:
        str: Markup with square brackets escaped.
    """

    def escape_backslashes(match: Match[str]) -> str:
        """Called by re.sub replace matches."""
        backslashes, text = match.groups()
        return f"{backslashes}{backslashes}\\{text}"

    markup = _escape(escape_backslashes, markup)
    if markup.endswith("\\") and not markup.endswith("\\\\"):
        return markup + "\\"

    return markup

def log_line(level: str, message: str) -> str:
    """A log line whose message is shown literally, however many brackets it has."""
    return f"[bold]{level}[/bold] {safe_markup(message)}"


def safe_markup(text: str) -> str:
    """`text` with anything that would read as markup escaped."""
    return escape(text)
