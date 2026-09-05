"""The link convention in source. Spec §4.

A link is a whole-line comment, in any language's comment syntax, of the form

    # cttp: <address> [key=value …] [~]["<description>"]

with three markers for three relations: `cttp:` (*is* — the code beneath is that page),
`cttp-from:` (*from* — derived from it) and `cttp-see:` (*see* — a reference, no code claimed).
Fields are `key=value` with no spaces inside a value; the description is the last field and the only
quoted one; a leading `~` marks it as derived by the tool rather than asserted by a person.

The **block** beneath a link is the code the link stands for. It begins after the link's *stack*
(consecutive link lines share one block) and ends at the next link line, or at a blank line that is
followed by a line no more indented than the link, or at the end of the file. `find_links()` records
it as `start`/`end` on every link so `check` and `fold` never guess.
"""

import re
from dataclasses import dataclass, field

RELATIONS = {"cttp": "is", "cttp-from": "from", "cttp-see": "see"}
MARKERS = {v: k for k, v in RELATIONS.items()}

# One expression finds a link line in any comment syntax: `#`, `//`, `--`, `;`, `/* … */`.
LINK_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<comment>#|//|--|;+|/\*)[ \t]*"
    r"(?P<marker>cttp(?:-from|-see)?):[ \t]*(?P<body>.*?)[ \t]*(?P<close>\*/)?[ \t]*$"
)
DESC_RE = re.compile(r'(?:^|\s)(?P<derived>~?)"(?P<text>[^"]*)"$')
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


class LinkError(ValueError):
    """A line that is a link but does not follow the grammar; the message names the line."""


@dataclass
class Link:
    line: int  # 0-based index into the file's lines
    indent: str
    relation: str  # is | from | see
    address: str
    fields: dict[str, str] = field(default_factory=dict)
    description: str | None = None
    description_derived: bool = False
    comment: str = "#"  # the comment opener as written; `/*` closes with ` */`
    start: int = -1  # the block beneath: lines[start:end]; set by find_links()
    end: int = -1

    def __post_init__(self) -> None:
        if self.start < 0:
            self.start = self.line + 1
        if self.end < 0:
            self.end = self.start

    @property
    def stamped(self) -> bool:
        return "id" in self.fields

    @property
    def marker(self) -> str:
        return MARKERS[self.relation]

    def block(self, lines: list[str]) -> list[str]:
        return lines[self.start : self.end]

    def format(self) -> str:
        """The line, written back in the tool's canonical form (without the indent)."""
        parts = [self.comment, f"{self.marker}:", self.address]
        parts += [f"{k}={v}" for k, v in self.fields.items()]
        out = " ".join(parts)
        if self.description is not None:
            out += "  " + ("~" if self.description_derived else "") + quote(self.description)
        if self.comment == "/*":
            out += " */"
        return out


def quote(description: str) -> str:
    """A description is the one quoted field; it cannot itself carry a double quote."""
    return '"' + description.replace('"', "'") + '"'


def parse_link(index: int, line: str) -> Link | None:
    """The link on this line, `None` if the line is not a link line, `LinkError` if malformed."""
    m = LINK_RE.match(line)
    if not m:
        return None
    if (m["comment"] == "/*") != (m["close"] == "*/"):
        raise LinkError(f"line {index + 1}: a `/* cttp: … */` link must close on the same line")
    body = m["body"]
    description = None
    derived = False
    dm = DESC_RE.search(body)
    if dm:
        description, derived = dm["text"], dm["derived"] == "~"
        body = body[: dm.start()].rstrip()
    tokens = body.split()
    if not tokens:
        raise LinkError(f"line {index + 1}: `{m['marker']}:` with no address")
    address, fields = tokens[0], {}
    if '"' in address or "~" in address:
        raise LinkError(f"line {index + 1}: the description must be the last field")
    for token in tokens[1:]:
        key, eq, value = token.partition("=")
        if not eq or '"' in value:
            where = f"field `{list(fields)[-1]}`" if fields else "the address"
            raise LinkError(
                f"line {index + 1}: unexpected `{token}` after {where} — a value may not contain "
                "a space, and the description is the only quoted field"
            )
        if not KEY_RE.match(key):
            raise LinkError(f"line {index + 1}: `{key}` is not a field name")
        if key in fields:
            raise LinkError(f"line {index + 1}: field `{key}` given twice")
        fields[key] = value
    return Link(
        index,
        m["indent"],
        RELATIONS[m["marker"]],
        address,
        fields,
        description,
        derived,
        m["comment"],
    )


def find_links(lines: list[str]) -> list[Link]:
    """Every link in the file, each with its block recorded as `start`/`end`."""
    links = [link for i, line in enumerate(lines) if (link := parse_link(i, line))]
    link_lines = {k.line for k in links}
    for link in links:
        start = link.line + 1
        while start in link_lines:  # the rest of the stack
            start += 1
        link.start = start
        link.end = _block_end(lines, start, len(link.indent), link_lines)
    return links


def _block_end(lines: list[str], start: int, indent: int, link_lines: set[int]) -> int:
    end = start
    while end < len(lines):
        if end in link_lines:
            break
        if lines[end].strip() == "":
            after = end + 1
            while after < len(lines) and lines[after].strip() == "":
                after += 1
            if after >= len(lines) or _indent_of(lines[after]) <= indent:
                break
        end += 1
    return end


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def strip_links(lines: list[str]) -> tuple[list[str], list[Link]]:
    """A page's own text: the lines with every link line removed, and — for a stamped `is` link —
    the block beneath it and the one blank line that separated it, since that code is another
    page's, stamped as such. Leading blank lines go with them. Returns the remaining lines and the
    links that were taken out, each still knowing its line and indent in the original."""
    links = find_links(lines)
    if not links:
        return list(lines), []
    drop: set[int] = set()
    for link in links:
        drop.add(link.line)
        if link.relation == "is" and link.stamped:
            drop.update(range(link.start, link.end))
            if link.end < len(lines) and lines[link.end].strip() == "":
                drop.add(link.end)
    kept = [line for i, line in enumerate(lines) if i not in drop]
    while kept and kept[0].strip() == "":
        kept.pop(0)
    return kept, links


def format_stamped(
    pinned: str, id12: str, description: str | None, derived: bool = False, comment: str = "#"
) -> str:
    """The stamp: the pinned address (any form, SHA rev), the identity, then the description."""
    return Link(
        -1, "", "is", pinned, {"id": f"sha256:{id12}"}, description, derived, comment
    ).format()
