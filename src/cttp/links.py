"""The link convention in source: `# cttp: <address> [key=value …] ["description"]`. Spec §4.

Spike: the `is` marker only; `cttp-from:` and `cttp-see:` arrive in P1-T4.
"""

import re
from dataclasses import dataclass, field

LINK_RE = re.compile(r"^(?P<indent>[ \t]*)#[ \t]*cttp:[ \t]*(?P<body>.*?)[ \t]*$")
DESC_RE = re.compile(r'(?:^|\s)(?P<derived>~?)"(?P<text>[^"]*)"$')


@dataclass
class Link:
    line: int  # 0-based index into the file's lines
    indent: str
    address: str
    fields: dict[str, str] = field(default_factory=dict)
    description: str | None = None
    description_derived: bool = False

    @property
    def stamped(self) -> bool:
        return "id" in self.fields


def parse_link(index: int, line: str) -> Link | None:
    m = LINK_RE.match(line)
    if not m:
        return None
    body = m["body"]
    description = None
    derived = False
    dm = DESC_RE.search(body)
    if dm:
        description, derived = dm["text"], dm["derived"] == "~"
        body = body[: dm.start()].rstrip()
    tokens = body.split()
    if not tokens:
        return None
    fields = dict(t.split("=", 1) for t in tokens[1:] if "=" in t)
    return Link(index, m["indent"], tokens[0], fields, description, derived)


def find_links(lines: list[str]) -> list[Link]:
    return [link for i, line in enumerate(lines) if (link := parse_link(i, line))]


def format_stamped(name: str, rev12: str, id12: str, description: str | None) -> str:
    out = f"# cttp: {name}@{rev12} id=sha256:{id12}"
    if description is not None:
        out += f'  "{description}"'
    return out
