"""Python extractor. Spike: a whole file as a script only (P1-T3 adds definitions)."""

from cttp.extract import Page
from cttp.hashing import normalize


def extract_script(source: str) -> Page:
    src = normalize(source)
    return Page(kind="script", source=src, language="python", span=(1, src.count("\n")))
