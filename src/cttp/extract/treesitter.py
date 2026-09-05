"""The tree-sitter extractor: the read side for every language but Python. Spec §3.

A grammar (`tree_sitter_<language>`) parses the file; a per-language query file
(`queries/<language>.scm`) names the definition node types and the node carrying each one's name,
as `@definition.<kind>` and `@name` captures. That is enough for a page's kind, symbol, span, own
text, signature, the comment above it, its link lines, and — through `shape_text()` — its shape:
the grammar's identifier nodes become positional placeholders and its literal nodes typed ones,
comments are dropped, and everything else (keywords, primitive types, punctuation) stays as the
token it is. Derived references and imports are the Python extractor's alone: a C page has none.

Error recovery is the grammar's: a construct the grammar does not know (a kernel macro used as
a statement, say) becomes an `ERROR` node and the definitions around it are still found. Two
definitions of one symbol in a file — the two arms of an `#ifdef` — keep the first.
"""

import re
from bisect import bisect_right
from dataclasses import dataclass
from functools import cache, lru_cache
from importlib import import_module, resources

from tree_sitter import Language, Node, Parser, Query, QueryCursor, Tree

from cttp.extract import ExtractError, Page
from cttp.hashing import normalize
from cttp.links import LINK_RE, find_links, strip_links

GRAMMARS = {"c": "tree_sitter_c"}  # language → the pip package with its grammar

# nodes an address cannot reach into: a definition inside one is not at file scope
_INNER = frozenset(
    {"compound_statement", "field_declaration_list", "parameter_list", "enumerator_list"}
)
_TAGGED = {"struct_specifier": "struct", "union_specifier": "union", "enum_specifier": "enum"}
_DECLARATORS = frozenset(
    {
        "init_declarator",
        "pointer_declarator",
        "function_declarator",
        "array_declarator",
        "parenthesized_declarator",
        "attributed_declarator",
    }
)

# the shape: which leaves are names, which are literals, which are dropped
_IDENTIFIERS = frozenset(
    {"identifier", "type_identifier", "field_identifier", "statement_identifier"}
)
_LITERALS = {
    "number_literal": "<num>",
    "string_literal": "<str>",
    "concatenated_string": "<str>",
    "char_literal": "<str>",
    "system_lib_string": "<str>",
}
_DROPPED = frozenset({"comment"})
_RAW = frozenset({"preproc_arg", "ERROR"})  # unparsed text: tokenized by regex
_RAW_TOKEN = re.compile(
    r"""(?P<id>[A-Za-z_]\w*)|(?P<num>0[xX][0-9a-fA-F]+\w*|\d\w*(?:\.\d*)?)|"""
    r"""(?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(?P<tok>\S)"""
)
_RAW_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
C_KEYWORDS = frozenset(
    """auto break case char const continue default do double else enum extern float for goto if
    inline int long register restrict return short signed sizeof static struct switch typedef union
    unsigned void volatile while _Bool _Complex _Imaginary _Alignas _Alignof _Atomic _Generic
    _Noreturn _Static_assert _Thread_local defined""".split()
)


def has_grammar(language: str) -> bool:
    return language in GRAMMARS


@dataclass(frozen=True)
class Definition:
    symbol: str
    kind: str  # function | constant | type | macro
    node: Node
    name: Node


class Grammar:
    def __init__(self, language: str):
        self.language = Language(import_module(GRAMMARS[language]).language())
        self.parser = Parser(self.language)
        query = resources.files("cttp.extract").joinpath(f"queries/{language}.scm")
        self.query = Query(self.language, query.read_text(encoding="utf-8"))

    def parse(self, text: str) -> Tree:
        return self.parser.parse(text.encode("utf-8"))


@cache
def grammar(language: str) -> Grammar:
    if language not in GRAMMARS:
        raise ExtractError(f"no tree-sitter grammar for {language!r}")
    return Grammar(language)


class Rows:
    """Line numbers from byte offsets. (Positions are taken from `start_byte`/`end_byte`, never
    from a node's `Point`, which py-tree-sitter 0.26 hands out from freed memory.)"""

    def __init__(self, text: str):
        data = text.encode("utf-8")
        self.starts = [0] + [i + 1 for i, b in enumerate(data) if b == 0x0A]

    def row(self, byte: int) -> int:
        """0-based row of the byte offset."""
        return bisect_right(self.starts, byte) - 1


@lru_cache(maxsize=8)
def _parsed(language: str, text: str) -> tuple[Tree, dict[str, Definition]]:
    """The tree and the file-scope definitions of `text`, in source order. Cached, so that a
    crawl asking for every definition of a file parses it once."""
    g = grammar(language)
    tree = g.parse(text)
    found: list[Definition] = []
    for _, captures in QueryCursor(g.query).matches(tree.root_node):
        capture = next(c for c in captures if c.startswith("definition."))
        node = captures[capture][0]
        kind = capture.split(".", 1)[1]
        if kind != "macro" and not _file_scope(node):
            continue
        name = captures["name"][0] if "name" in captures else _declared_name(node)
        if name is None:
            continue
        symbol = name.text.decode("utf-8")
        if node.type in _TAGGED:
            symbol = f"{_TAGGED[node.type]}.{symbol}"
        found.append(Definition(symbol, kind, node, name))
    found.sort(key=lambda d: (d.node.start_byte, d.node.end_byte))
    defs: dict[str, Definition] = {}
    for d in found:
        defs.setdefault(d.symbol, d)
    return tree, defs


def _file_scope(node: Node) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type in _INNER or parent.type == "function_definition":
            return False
        parent = parent.parent
    return True


def _declared_name(node: Node) -> Node | None:
    """The identifier at the bottom of a declarator chain: `*name`, `name[]`, `(*name)(…)`."""
    d = node.child_by_field_name("declarator")
    while d is not None:
        if d.type == "identifier":
            return d
        if d.type in _DECLARATORS:
            d = d.child_by_field_name("declarator") or next(
                (c for c in d.named_children if c.type.endswith("declarator")), None
            )
        else:
            return None
    return None


# --- pages -------------------------------------------------------------------------------------


def definitions(language: str, source: str) -> list[str]:
    """Every addressable symbol of the file, in source order."""
    _, defs = _parsed(language, normalize(source))
    return list(defs)


def extract(language: str, source: str, path: str, symbol: str | None = None) -> Page:
    text = normalize(source)  # line numbers survive: endings, trailing space, tail blanks
    lines = text.split("\n")
    if symbol is None:
        kept, links = strip_links(lines)
        return Page(
            kind="script",
            source=normalize("\n".join(kept)) if links else text,
            language=language,
            span=(1, text.count("\n")),
            links=tuple(links),
        )
    _, defs = _parsed(language, text)
    d = defs.get(symbol)
    if d is None:
        available = ", ".join(defs) or "none"
        raise ExtractError(f"{symbol!r} is not a definition in {path!r}; definitions: {available}")
    rows = Rows(text)
    start, end = rows.row(d.node.start_byte) + 1, rows.row(d.node.end_byte - 1) + 1
    own = lines[start - 1 : end]
    return Page(
        kind=d.kind,
        source=normalize("\n".join(own)),
        language=language,
        span=(start, end),
        symbol=symbol,
        signature=_signature(d),
        docstring=_comment_above(d.node, rows),
        links=tuple(find_links(own)),
    )


def _signature(d: Definition) -> str:
    """The definition's header, whitespace collapsed: a function's declaration up to its body, a
    variable's up to its initializer, a type's up to its body, a macro's name and parameters."""
    node = d.node
    if d.kind == "macro":
        params = node.child_by_field_name("parameters")
        return d.name.text.decode("utf-8") + (_collapse(params.text) if params is not None else "")
    text = node.text
    if d.kind == "constant":
        init = node.child_by_field_name("declarator")
        value = init.child_by_field_name("value") if init is not None else None
        if value is not None:
            text = text[: value.start_byte - node.start_byte]
        head = _collapse(text).rstrip(" =;")
        return head
    body = node.child_by_field_name("body")
    if body is not None:
        text = text[: body.start_byte - node.start_byte]
    elif node.type == "type_definition":
        brace = text.find(b"{")
        text = text[:brace] if brace >= 0 else text
    return _collapse(text).rstrip(" ;")


def _collapse(text: bytes) -> str:
    return " ".join(text.decode("utf-8").split())


def _comment_above(node: Node, rows: Rows) -> str | None:
    """The first paragraph of the comment ending on the line above the definition, as one line —
    for kernel-doc, the summary before the `@param` lines."""
    prev = node.prev_sibling
    if prev is None or prev.type != "comment":
        return None
    if rows.row(prev.end_byte - 1) != rows.row(node.start_byte) - 1:
        return None
    text = prev.text.decode("utf-8")
    if LINK_RE.match(text):  # a link line is a reference, not a description
        return None
    if text.startswith("/*"):
        text = text[2:].removesuffix("*/")
    out: list[str] = []
    for raw in text.split("\n"):
        line = raw.strip().removeprefix("//").strip()
        line = line.lstrip("*").strip() if not raw.strip().startswith("//") else line
        if line.startswith("@") or (not line and out):
            break
        if line:
            out.append(line)
    return " ".join(out) or None


# --- the shape ---------------------------------------------------------------------------------


def tokens(language: str, text: str) -> list[tuple[int, str, str]]:
    """The text as `(row, category, token)` triples in source order, comments dropped: category
    `id` for an identifier, `lit` for a literal (the token is its placeholder), `tok` for anything
    else (keywords, primitive types, punctuation, kept verbatim). `row` is 0-based."""
    tree = grammar(language).parse(text)
    rows = Rows(text)
    out: list[tuple[int, str, str]] = []
    stack = [tree.root_node]
    while stack:
        n = stack.pop()
        if n.type in _DROPPED or n.is_missing:
            continue
        if n.type in _LITERALS:
            out.append((rows.row(n.start_byte), "lit", _LITERALS[n.type]))
        elif n.type in _IDENTIFIERS:
            out.append((rows.row(n.start_byte), "id", n.text.decode("utf-8")))
        elif n.child_count == 0 or n.type in _RAW and not n.named_children:
            _raw_tokens(n, rows, out)
        else:
            stack.extend(reversed(n.children))
    return out


def _raw_tokens(n: Node, rows: Rows, out: list[tuple[int, str, str]]) -> None:
    text = n.text.decode("utf-8")
    if n.type not in _RAW:
        if text.strip():
            out.append((rows.row(n.start_byte), "tok", text.strip()))
        return
    row = rows.row(n.start_byte)
    text = _RAW_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text)  # rows survive
    for m in _RAW_TOKEN.finditer(text):
        r = row + text.count("\n", 0, m.start())
        if m["id"]:
            out.append((r, "tok" if m["id"] in C_KEYWORDS else "id", m["id"]))
        elif m["num"]:
            out.append((r, "lit", "<num>"))
        elif m["str"]:
            out.append((r, "lit", "<str>"))
        else:
            out.append((r, "tok", m["tok"]))


def shape_words(toks: list[tuple[int, str, str]]) -> list[str]:
    """Identifiers as `$0`, `$1`, … by first appearance; literals and other tokens as they are."""
    names: dict[str, str] = {}
    return [names.setdefault(t, f"${len(names)}") if cat == "id" else t for _, cat, t in toks]


def shape_text(language: str, text: str) -> str:
    return " ".join(shape_words(tokens(language, normalize(text))))
