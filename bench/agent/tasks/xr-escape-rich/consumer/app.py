"""Log lines for a console that understands rich-style [markup]."""


def log_line(level: str, message: str) -> str:
    """A log line whose message is shown literally, however many brackets it has."""
    return f"[bold]{level}[/bold] {safe_markup(message)}"
