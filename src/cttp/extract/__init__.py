"""Extractors: what a definition is, per language. Spec §3.

`extract(path, source, symbol, files)` picks the extractor by the file's suffix. Python has the
full one (`python.py`); any other file is a whole-file script page with no definitions, no shape
and no references (tree-sitter read-side extractors arrive in Phase 6).

A page's `source` is its **own text**. For a script page the link lines inside it — and the block
beneath any stamped `is` link, which is another page's code — are taken out and reported as the
page's `links`; what remains is what the identity hashes and what expansion writes beneath a stamp,
so an expanded block always hashes to its page. A definition's text is its span, verbatim.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

from cttp.hashing import normalize
from cttp.links import Link, strip_links

LANGUAGES = {".py": "python"}


class ExtractError(LookupError):
    """The symbol is not an addressable definition of the file, or the file is not code."""


@dataclass(frozen=True)
class Ref:
    """A derived reference from a page to a file, or a definition, in the same repository.

    `name` is the text the page reaches it by: `REG_BITS`, `decode.STEP_MILLICELSIUS`, `r2m` for
    an aliased import — what inline expansion has to bind for the page to run."""

    path: str
    symbol: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class Page:
    """What an address points at: a definition or a script."""

    kind: str  # "script" | "function" | "class" | "constant"
    source: str  # the page's own normalized text (see the module docstring)
    language: str
    span: tuple[int, int]  # 1-based inclusive line range in the origin file
    symbol: str | None = None  # the dotted name of a definition; None for a script
    signature: str | None = None  # a definition's header without its keyword
    docstring: str | None = None  # first line of the docstring
    refs: tuple[Ref, ...] = ()  # derived references within the repository, first use first
    stdlib: tuple[str, ...] = ()  # top-level standard-library modules the page imports
    third_party: tuple[str, ...] = ()  # top-level modules from outside the repository and stdlib
    imports: tuple[str, ...] = ()  # a definition's import statements for stdlib/third-party names
    unresolved: tuple[str, ...] = ()  # free names: not local, imported, defined here or builtin
    links: tuple[Link, ...] = ()  # asserted: the `# cttp…:` lines found in the page's text


def language_of(path: str) -> str:
    return LANGUAGES.get(PurePosixPath(path).suffix, "text")


def definitions(path: str, source: str) -> list[str]:
    """The addressable symbols of a file, in order; empty for a file without an extractor."""
    if language_of(path) == "python":
        from cttp.extract import python

        return python.definitions(source)
    return []


def extract(path: str, source: str, symbol: str | None = None, files: Iterable[str] = ()) -> Page:
    """The page at `path` (or its definition `symbol`); `files` lists the repository at that rev,
    for resolving references. A file without an extractor is a script page as it is."""
    if language_of(path) == "python":
        from cttp.extract import python

        return python.extract(source, path, symbol, files)
    if symbol:
        raise ExtractError(f"{path!r} is not Python; only Python files have definitions")
    full = normalize(source)
    kept, links = strip_links(full.split("\n"))
    return Page(
        kind="script",
        source=normalize("\n".join(kept)) if links else full,
        language="text",
        span=(1, full.count("\n")),
        links=tuple(links),
    )
