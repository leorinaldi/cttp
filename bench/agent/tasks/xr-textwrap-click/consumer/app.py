"""Help-text rendering for a small command-line tool whose output may carry colour codes."""


def render_help(name: str, description: str, width: int = 60) -> str:
    """The name on its own line, then the description wrapped beneath it, indented by two."""
    return f"{name}\n{wrap(description, width, indent='  ')}"
