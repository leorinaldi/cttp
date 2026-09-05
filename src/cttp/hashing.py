"""Identity and shape hashing. Spec §2.

The **identity** is SHA-256 over the definition's own normalized source: dedented to column zero,
LF line endings, trailing whitespace stripped, exactly one trailing newline. It hashes nothing the
definition references, so it is computable from one file, offline.

The **shape** is SHA-256 over the same text with every identifier replaced by a positional
placeholder and every literal by a typed placeholder, via `tokenize`; keywords and builtins are
kept, comments and blank lines dropped. Two definitions that differ only in names, whitespace,
comments and literal values have the same shape. It is derived metadata for near-duplicate
detection and is never part of an address. Python only.
"""

import builtins
import hashlib
import io
import keyword
import textwrap
import tokenize

SHORT = 12

BUILTINS = frozenset(dir(builtins))
_LITERALS = {tokenize.NUMBER: "<num>", tokenize.STRING: "<str>"}
_STRUCTURE = {
    tokenize.NEWLINE: "<nl>",
    tokenize.INDENT: "<in>",
    tokenize.DEDENT: "<out>",
}
_DROPPED = {
    tokenize.COMMENT,
    tokenize.NL,
    tokenize.ENCODING,
    tokenize.ENDMARKER,
    tokenize.TYPE_COMMENT,
    tokenize.FSTRING_MIDDLE,
    tokenize.FSTRING_END,
}


class ShapeError(ValueError):
    """The text does not tokenize as Python, so it has no shape."""


def normalize(text: str) -> str:
    """Spec §2: dedent to column zero, LF endings, no trailing whitespace, one trailing newline."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = textwrap.dedent(text)
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def identity(text: str) -> str:
    """Full SHA-256 hex of the normalized text."""
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def shape_text(text: str) -> str:
    """The normalized text with identifiers and literals replaced by placeholders, one token per
    word: `$0`, `$1`, … for identifiers in order of first appearance, `<num>`, `<str>`, `<fstr>`
    for literals, `<nl>`, `<in>`, `<out>` for statement and block structure. Keywords, builtins
    and operators stay as they are."""
    names: dict[str, str] = {}
    words: list[str] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(normalize(text)).readline):
            if tok.type in _DROPPED:
                continue
            if tok.type == tokenize.NAME:
                if keyword.iskeyword(tok.string) or tok.string in BUILTINS:
                    words.append(tok.string)
                else:
                    words.append(names.setdefault(tok.string, f"${len(names)}"))
            elif tok.type in _LITERALS:
                words.append(_LITERALS[tok.type])
            elif tok.type == tokenize.FSTRING_START:
                words.append("<fstr>")
            elif tok.type in _STRUCTURE:
                words.append(_STRUCTURE[tok.type])
            else:
                words.append(tok.string)
    except (tokenize.TokenError, SyntaxError) as e:
        raise ShapeError(f"not tokenizable as Python: {e}") from e
    return " ".join(words)


def shape(text: str) -> str:
    """Full SHA-256 hex of the shape text."""
    return hashlib.sha256(shape_text(text).encode("utf-8")).hexdigest()


def short(hexdigest: str, n: int = SHORT) -> str:
    return hexdigest[:n]
