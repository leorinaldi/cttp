"""The closure: everything a page needs to run inline, in dependency order. Spec §7, plan P3-T1.

From a page, the definitions it references — through the `# cttp:` links written inside it
(asserted) and the references the extractor derived — recursively, within each page's own
repository at its pinned rev. The output is an ordered list, dependencies before dependents, the
root last; each entry carries its pinned address and identity. Standard-library imports are left
as the page wrote them; third-party imports are kept as statements and their packages reported as
`requires`; anything that cannot be expanded honestly stops the operation and says why. A budget
stops a link from dragging in a codebase.

What "honestly" means here — the rules, each of which is a refusal with a message:

- a page may only reach a definition **by the definition's own name** (`REG_BITS`, a from-import
  of `reg_to_millicelsius`, `LM75.read_temp` through its class); reaching it through a module
  (`decode.STEP_MILLICELSIUS`) or an alias (`as r2m`) cannot be satisfied by inlining;
- a module used as a whole is not a definition and cannot be inlined;
- a free name that no definition in the closure, no import and no builtin binds is unresolvable;
- a definition whose span contains link lines, or a script with an `is` link inside a block,
  cannot be expanded verbatim without breaking the block rule of spec §4;
- two definitions in one closure may not bind the same top-level name.
"""

from dataclasses import dataclass, replace

from cttp import gitcache
from cttp.address import AddressError, parse
from cttp.extract import definitions
from cttp.objects import locator_address
from cttp.registry import Registries, RegistryError
from cttp.resolve import Resolved, ResolveError, resolve

MAX_DEFINITIONS = 50
MAX_LINES = 2000


class ClosureError(LookupError):
    """The closure cannot be completed; the message names what stopped it."""


@dataclass(frozen=True)
class Budget:
    definitions: int = MAX_DEFINITIONS
    lines: int = MAX_LINES


DEFAULT_BUDGET = Budget()


@dataclass
class Node:
    page: Resolved
    description: str | None  # for the stamp: asserted from a registry, else derived
    derived: bool
    via: str  # "root" | "link" (an inner `# cttp:` line) | "ref" (a derived reference)
    needs: list[str]  # pinned locator addresses of the pages this one depends on directly
    defines: list[str]  # the top-level names this page binds when inlined

    @property
    def key(self) -> str:
        return locator_address(self.page)

    @property
    def lines(self) -> int:
        return self.page.source.count("\n")

    def to_json(self) -> dict:
        return {
            "address": self.page.address,
            "locator": self.key,
            "identity": self.page.identity,
            "identity_full": self.page.identity_full,
            "kind": self.page.kind,
            "symbol": self.page.symbol,
            "path": self.page.path,
            "lines": self.lines,
            "license": self.page.license,
            "description": self.description,
            "via": self.via,
            "needs": list(self.needs),
            "defines": list(self.defines),
            "source": self.page.source,
            "origin": {
                "description": (
                    None if self.description is None else "derived" if self.derived else "asserted"
                ),
                "via": "asserted" if self.via == "link" else "derived",
            },
        }


@dataclass
class Closure:
    root: Resolved
    nodes: list[Node]  # dependencies before dependents; the root last
    imports: list[str]  # import statements to hoist above the whole block, in first-need order
    stdlib: list[str]
    requires: list[str]  # third-party top-level packages the closure needs
    hoisted: list[dict]  # the root's own `from` / `see` links, to keep in the stack

    @property
    def address(self) -> str:
        return self.root.address

    @property
    def lines(self) -> int:
        return sum(n.lines for n in self.nodes)

    def to_json(self) -> dict:
        return {
            "address": self.root.address,
            "identity": self.root.identity,
            "definitions": [n.to_json() for n in self.nodes],
            "count": len(self.nodes),
            "lines": self.lines,
            "imports": list(self.imports),
            "stdlib": list(self.stdlib),
            "requires": list(self.requires),
            "origin": {"order": "derived", "imports": "derived", "requires": "derived"},
        }


def describe(r: Resolved) -> tuple[str | None, bool]:
    """The description for a stamp: the entry's, asserted; else one derived from the page."""
    if r.description is not None:
        return r.description, False
    if r.signature is None:
        return None, False
    head = r.signature
    if r.kind == "function":  # the signature reads as code: `def greet(name) -> str`
        head = (
            head.replace("async ", "async def ", 1) if head.startswith("async ") else f"def {head}"
        )
    elif r.kind == "class":
        head = f"class {head}"
    return head + (f" — {r.docstring}" if r.docstring else ""), True


def defines(r: Resolved) -> list[str]:
    """The top-level names a page binds when its text is inlined."""
    if r.symbol:
        return [r.symbol.split(".")[0]]
    return [s for s in definitions(r.path, r.source) if "." not in s]


def closure(text: str, registries: Registries, budget: Budget | None = DEFAULT_BUDGET) -> Closure:
    """The closure of the page at `text` (any address form). `budget=None` lifts the limits."""
    walk = _Walk(registries, budget)
    root = walk._resolve(text, None, what="the address")
    walk.visit(root, "root")
    walk.check_names()
    return Closure(
        root=root,
        nodes=walk.order,
        imports=walk.imports,
        stdlib=sorted({m for n in walk.order for m in n.page.imports["stdlib"]}),
        requires=sorted({m for n in walk.order for m in n.page.imports["third_party"]}),
        hoisted=[k for k in root.links if k["relation"] != "is"],
    )


class _Walk:
    def __init__(self, registries: Registries, budget: Budget | None):
        self.registries = registries
        self.budget = budget
        self.order: list[Node] = []
        self.done: dict[str, Node] = {}
        self.visiting: set[str] = set()
        self.imports: list[str] = []

    def visit(self, page: Resolved, via: str) -> Node | None:
        key = locator_address(page)
        if key in self.done:
            return self.done[key]
        if key in self.visiting:  # mutual recursion between definitions: legal, once inlined
            return None
        self.visiting.add(key)
        deps = self._dependencies(page)
        needs: list[str] = []
        provided: set[str] = set()
        for dep, how in deps:
            node = self.visit(dep, how)
            needs.append(locator_address(dep))
            provided.update(defines(dep))
        missing = [n for n in page.unresolved if n not in provided]
        if missing:
            raise ClosureError(
                f"{page.address} uses {_names(missing)}, which nothing defines, imports or "
                f"links to{' in ' + page.path if page.kind != 'script' else ''}; the closure "
                "cannot be completed"
            )
        for stmt in page.imports.get("statements", []):
            if stmt not in self.imports:
                self.imports.append(stmt)
        description, derived = describe(page)
        node = Node(page, description, derived, via, needs, defines(page))
        self.visiting.discard(key)
        self.done[key] = node
        self.order.append(node)
        self._within_budget()
        return node

    def _dependencies(self, page: Resolved) -> list[tuple[Resolved, str]]:
        """The pages `page` depends on directly: its inner `is` links, then its derived refs."""
        if page.symbol and page.links:
            first = page.links[0]
            raise ClosureError(
                f"{page.address} contains a `{first['relation']}` link at line {first['line']} "
                f"of its own text ({first['address']}); a definition with links inside it cannot "
                "be expanded verbatim — link to the pieces separately"
            )
        deps: list[tuple[Resolved, str]] = []
        for link in page.links:
            if link["relation"] != "is":
                continue  # `from` and `see` lines are hoisted into the stack by expand
            if link["indent"]:
                raise ClosureError(
                    f"{page.address} has `# cttp: {link['address']}` inside a block at line "
                    f"{link['line']}; only a top-level link can be hoisted above the page"
                )
            dep = self._resolve(
                link["address"],
                link["fields"].get("id"),
                what=f"the link at line {link['line']} of {page.address}",
            )
            deps.append((dep, "link"))
        for ref in page.refs:
            a = parse(ref["address"])
            used = ref.get("name") or ""
            if a.symbol is None:
                raise ClosureError(
                    f"{page.address} uses the module {a.path} as a whole (`{used}`); a module is "
                    "not a definition and cannot be inlined — link to the definitions it uses"
                )
            top = a.symbol.split(".")[0]
            if ref.get("name") is not None and used.split(".")[0] != top:
                # an object from a registry older than this rule has no `name`: not checked
                raise ClosureError(
                    f"{page.address} reaches {a.path}#{a.symbol} as `{used}`; inline expansion "
                    f"binds a definition by its own name, so the page must use `{top}` directly "
                    f"(`from … import {top}`)"
                )
            dep = self._resolve(
                str(replace(a, symbol=top)), None, what=f"a reference of {page.address}"
            )
            deps.append((dep, "ref"))
        return deps

    def _resolve(self, address: str, expect: str | None, what: str) -> Resolved:
        try:
            return resolve(address, self.registries, expect)
        except (ResolveError, RegistryError, AddressError, gitcache.GitError) as e:
            raise ClosureError(f"{what} does not resolve: {e}") from e

    def _within_budget(self) -> None:
        if self.budget is None:
            return
        count = len(self.order)
        lines = sum(n.lines for n in self.order)
        if count > self.budget.definitions or lines > self.budget.lines:
            raise ClosureError(
                f"the closure is over budget: {count} definitions, {lines} lines (limits "
                f"{self.budget.definitions} and {self.budget.lines}); expand with --package to "
                "vendor it as a module, or link to a narrower symbol"
            )

    def check_names(self) -> None:
        """Two pages may not bind the same top-level name once inlined into one file."""
        seen: dict[str, Node] = {}
        for node in self.order:
            for name in node.defines:
                other = seen.get(name)
                if other is not None:
                    raise ClosureError(
                        f"`{name}` is defined twice in the closure: {other.page.address} and "
                        f"{node.page.address}; inlined into one file, one would shadow the other"
                    )
                seen[name] = node


def _names(names: list[str]) -> str:
    return ", ".join(f"`{n}`" for n in names)
