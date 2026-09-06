"""Extractors: what a definition is, per language. Spec §3.

`extract(path, source, symbol, files)` picks the extractor by the file's suffix. Python has the
full one (`python.py`, exact, with derived references); C goes through the tree-sitter one
(`treesitter.py` and `queries/c.scm`: definitions, identity, shape, links — no references); any
other file is a whole-file script page with no definitions, no shape and no references.

A page's `source` is its **own text**. For a script page the link lines inside it — and the block
beneath any stamped `is` link, which is another page's code — are taken out and reported as the
page's `links`; what remains is what the identity hashes and what expansion writes beneath a stamp,
so an expanded block always hashes to its page. A definition's text is its span, verbatim.

A derived reference names the definition, not the module that re-exports it: `forwarded()` follows
each of a page's references through `__init__.py`-style re-exports (`python.Forwarder`), which
needs the other files' text — so it is a separate step the crawl and the resolver take.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from cttp.hashing import normalize
from cttp.links import Link, strip_links

LANGUAGES = {".py": "python", ".c": "c", ".h": "c"}


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
    parsed: bool = True  # False for a file its language's extractor could not parse: the page
    # stands (its text is its text) but no reference was read from it, which `who`'s coverage
    # counts as a hole rather than letting a quietly reference-free file pass for a complete answer


def language_of(path: str) -> str:
    return LANGUAGES.get(PurePosixPath(path).suffix, "text")


def definitions(path: str, source: str) -> list[str]:
    """The addressable symbols of a file, in order; empty for a file without an extractor."""
    language = language_of(path)
    if language == "python":
        from cttp.extract import python

        return python.definitions(source)
    if language != "text":
        from cttp.extract import treesitter

        return treesitter.definitions(language, source)
    return []


def extract(path: str, source: str, symbol: str | None = None, files: Iterable[str] = ()) -> Page:
    """The page at `path` (or its definition `symbol`); `files` lists the repository at that rev,
    for resolving references. A file without an extractor is a script page as it is."""
    language = language_of(path)
    if language == "python":
        from cttp.extract import python

        return python.extract(source, path, symbol, files)
    if language != "text":
        from cttp.extract import treesitter

        return treesitter.extract(language, source, path, symbol)
    if symbol:
        raise ExtractError(f"{path!r} has no extractor, so it has no definitions")
    full = normalize(source)
    kept, links = strip_links(full.split("\n"))
    return Page(
        kind="script",
        source=normalize("\n".join(kept)) if links else full,
        language="text",
        span=(1, full.count("\n")),
        links=tuple(links),
    )


def forwarded(page: Page, files: Iterable[str], read: Callable[[str], str | None]) -> Page:
    """`page` with each derived reference forwarded through re-exports to the definition it means
    (Python's rule; another language's page is returned as it is). `read(path)` gives a file's
    text at the same revision, or None."""
    if page.language != "python" or not page.refs:
        return page
    from cttp.extract.python import Forwarder

    forwarder = Forwarder(files, read)
    return replace(page, refs=tuple(forwarder.forward(r) for r in page.refs))
