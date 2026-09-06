"""The Python extractor: every addressable definition of spec §3, exact, via `ast`.

Addressable: module-level `def`, `async def`, `class` and simple assignment to one name (a
constant); class members as `Class.member`, recursively. The span runs from the first decorator
through the end of the body. Nested functions and comprehension-scoped names are not addressable.
A whole file addressed without a symbol is a script.

**Derived references.** Imports and attribute access that resolve statically to a file in the
same repository (given its file list) become `Ref`s, and the top-level modules a page needs from
outside the repository are split into stdlib (`sys.stdlib_module_names`) and third party. A
definition's references are the names it actually uses — import bindings and sibling definitions
in its own file; a script's are every import it makes.
"""

import ast
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

from cttp.extract import ExtractError, Page, Ref
from cttp.hashing import BUILTINS, normalize
from cttp.links import find_links, strip_links

# names every module has without binding them
MODULE_GLOBALS = frozenset(
    {"__name__", "__file__", "__doc__", "__spec__", "__package__", "__loader__", "__builtins__",
     "__path__", "__annotations__", "__dict__", "__debug__"}
)  # fmt: skip

# repository-root directories an absolute import is also rooted at: the src-layout convention
SOURCE_ROOTS = ("src",)

Function = ast.FunctionDef | ast.AsyncFunctionDef
Definition = Function | ast.ClassDef | ast.Assign | ast.AnnAssign


@dataclass(frozen=True)
class Binding:
    """What an import binds a local name to: `level` dots, then `module` (dotted), then `attr`."""

    level: int
    module: tuple[str, ...]
    attr: str | None = None
    stmt: str = ""  # the import statement that makes this one binding, as the tool rewrites it

    @property
    def parts(self) -> tuple[str, ...]:
        return self.module + ((self.attr,) if self.attr else ())


def extract(source: str, path: str, symbol: str | None = None, files: Iterable[str] = ()) -> Page:
    text = normalize(source)  # line numbers survive: endings, trailing space, tail blanks
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        if symbol:
            raise ExtractError(f"{path!r} is not valid Python (line {e.lineno}: {e.msg})") from e
        kept, links = strip_links(text.split("\n"))
        return Page(
            kind="script",
            source=normalize("\n".join(kept)) if links else text,
            language="python",
            span=(1, text.count("\n")),
            links=tuple(links),
            parsed=False,  # its links stand; no reference could be read (spec §6, coverage)
        )
    module = Module(tree, text, path, set(files))
    return module.definition(symbol) if symbol else module.script()


def definitions(source: str) -> list[str]:
    """Every addressable symbol of the file, in source order; none when it is not valid Python."""
    text = normalize(source)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    return list(Module(tree, text, "", set()).defs)


class Module:
    def __init__(self, tree: ast.Module, text: str, path: str, files: set[str]):
        self.tree = tree
        self.lines = text.split("\n")
        self.text = text
        self.path = path
        self.files = files
        self.source_roots = _source_roots(files)
        self.defs: dict[str, Definition] = {}
        self.nested: dict[str, str] = {}  # a nested def → the definition it is nested in
        self._collect(tree.body, prefix="")
        self.bindings = _direct_bindings(tree)

    # -- what is addressable -------------------------------------------------------------------

    def _collect(self, body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, Function | ast.ClassDef):
                sym = prefix + node.name
                self.defs[sym] = node
                if isinstance(node, ast.ClassDef):
                    self._collect(node.body, sym + ".")
                else:
                    for inner in ast.walk(node):
                        if inner is not node and isinstance(inner, Function | ast.ClassDef):
                            self.nested.setdefault(inner.name, sym)
            elif name := _assigned_name(node):
                self.defs.setdefault(prefix + name, node)

    # -- pages -------------------------------------------------------------------------------

    def script(self) -> Page:
        refs: list[Ref] = []
        stdlib: list[str] = []
        third: list[str] = []
        bindings = _all_bindings(self.tree)
        for name, b in bindings.items():
            self._classify(b, b.parts, name, refs, stdlib, third)
        bound = _bound_names(self.tree) | set(bindings)
        free = [c[0] for c in _chains(self.tree) if c[0] not in bound]
        kept, links = strip_links(self.lines)
        return Page(
            kind="script",
            source=normalize("\n".join(kept)) if links else self.text,
            language="python",
            span=(1, self.text.count("\n")),
            refs=tuple(_dedupe(refs)),
            stdlib=tuple(sorted(set(stdlib))),
            third_party=tuple(sorted(set(third))),
            unresolved=tuple(_free(free)),
            links=tuple(links),
        )

    def definition(self, symbol: str) -> Page:
        node = self.defs.get(symbol)
        if node is None:
            raise ExtractError(self._not_found(symbol))
        decorators = getattr(node, "decorator_list", None)
        start = decorators[0].lineno if decorators else node.lineno
        end = node.end_lineno or start
        refs, stdlib, third, stmts, free = self._references(node, symbol)
        own = self.lines[start - 1 : end]
        return Page(
            kind=_kind(node),
            source=normalize("\n".join(own)),
            language="python",
            span=(start, end),
            symbol=symbol,
            signature=_signature(node),
            docstring=_docstring(node),
            refs=tuple(refs),
            stdlib=tuple(sorted(set(stdlib))),
            third_party=tuple(sorted(set(third))),
            imports=tuple(stmts),
            unresolved=tuple(free),
            links=tuple(find_links(own)),
        )

    def _not_found(self, symbol: str) -> str:
        head = symbol.split(".")[-1]
        within = self.nested.get(symbol) or self.nested.get(head)
        if within:
            return (
                f"{symbol!r} in {self.path!r} is nested inside {within!r} and is not addressable; "
                "only module-level definitions and class members have addresses"
            )
        available = ", ".join(sorted(self.defs)) or "none"
        return f"{symbol!r} is not a definition in {self.path!r}; definitions: {available}"

    # -- references --------------------------------------------------------------------------

    def _references(self, node: ast.AST, symbol: str):
        """What a definition needs from outside its own text: references into the repository,
        the stdlib and third-party modules it uses (with the module-level import statements that
        bind them), and the free names nothing accounts for."""
        inner = _all_bindings(node)
        bindings = self.bindings | inner
        local = _bound_names(node) - set(inner)  # a parameter shadows a module-level import
        refs: list[Ref] = []
        stdlib: list[str] = []
        third: list[str] = []
        stmts: list[str] = []
        free: list[str] = []
        for chain in _chains(node):
            root = chain[0]
            if root in local:
                continue
            if root in bindings:
                b = bindings[root]
                outside = self._classify(
                    b, b.parts + tuple(chain[1:]), ".".join(chain), refs, stdlib, third
                )
                if outside and root not in inner and b.stmt not in stmts:
                    stmts.append(b.stmt)
            elif root in self.defs:
                sibling = root
                if len(chain) > 1 and f"{root}.{chain[1]}" in self.defs:
                    sibling = f"{root}.{chain[1]}"
                if sibling != symbol:
                    refs.append(Ref(self.path, sibling, sibling))
            else:
                free.append(root)
        return _dedupe(refs), stdlib, third, stmts, _free(free)

    def _classify(self, b: Binding, parts: tuple[str, ...], name: str, refs, stdlib, third) -> bool:
        """File a binding as a repository reference or an outside module; True when outside."""
        found = self._module_file(b.level, parts)
        if found:
            file, rest = found
            refs.append(Ref(file, ".".join(rest) or None, name))
            return False
        if b.level == 0 and parts:
            (stdlib if parts[0] in sys.stdlib_module_names else third).append(parts[0])
            return True
        return False

    def _module_file(self, level: int, parts: tuple[str, ...]) -> tuple[str, list[str]] | None:
        """The repository file for the longest module prefix of `parts`, and what is left over.

        A relative import starts at the file's package (`level` dots up); an absolute one is
        tried against every ancestor directory of the file, nearest first, then the root, then
        the repository's source roots — the `src/` a src-layout puts its packages under, which is
        on no importing file's path.
        """
        here = PurePosixPath(self.path).parent
        if level == 0:
            bases = [here, *here.parents]
            bases += [root for root in self.source_roots if root not in bases]
        elif level == 1:
            bases = [here]
        elif level - 2 < len(here.parents):
            bases = [here.parents[level - 2]]
        else:
            return None
        for k in range(len(parts), 0, -1):
            for base in bases:
                stem = _join(base, parts[:k])
                for candidate in (f"{stem}.py", f"{stem}/__init__.py"):
                    if candidate in self.files:
                        return candidate, list(parts[k:])
        if level and not parts:  # `from . import x` where x is not a module: the package itself
            init = _join(bases[0], ("__init__",)) + ".py"
            if init in self.files:
                return init, []
        return None


# -- helpers -----------------------------------------------------------------------------------


def _source_roots(files: set[str]) -> tuple[PurePosixPath, ...]:
    """The directories an absolute import may be rooted at besides the file's own ancestors.

    A src-layout puts its packages under a directory that is on no importing file's path:
    `tests/test_compat.py` says `from click._compat import strip_ansi` and means
    `src/click/_compat.py`. Only a repository-root directory of one of `SOURCE_ROOTS` counts, and
    only when the repository has one — so a flat layout is unaffected.
    """
    return tuple(
        PurePosixPath(name) for name in SOURCE_ROOTS if any(f.startswith(f"{name}/") for f in files)
    )


def _join(base: PurePosixPath, parts: tuple[str, ...]) -> str:
    return str(base.joinpath(*parts)).removeprefix("./")


def _assigned_name(node: ast.stmt) -> str | None:
    """A simple assignment to one name — a constant — else None."""
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        target = node.target
    else:
        return None
    return target.id if isinstance(target, ast.Name) else None


def _kind(node: Definition) -> str:
    if isinstance(node, Function):
        return "function"
    if isinstance(node, ast.ClassDef):
        return "class"
    return "constant"


def _signature(node: Definition) -> str | None:
    if isinstance(node, Function):
        sig = f"{node.name}({ast.unparse(node.args)})"
        if node.returns is not None:
            sig += f" -> {ast.unparse(node.returns)}"
        return ("async " if isinstance(node, ast.AsyncFunctionDef) else "") + sig
    if isinstance(node, ast.ClassDef):
        args = [ast.unparse(b) for b in node.bases] + [ast.unparse(k) for k in node.keywords]
        return node.name + (f"({', '.join(args)})" if args else "")
    if isinstance(node, ast.AnnAssign):
        return f"{node.target.id}: {ast.unparse(node.annotation)}"
    return node.targets[0].id


def _docstring(node: Definition) -> str | None:
    """The docstring's first paragraph as one line (a summary often wraps onto a second line)."""
    if not isinstance(node, Function | ast.ClassDef):
        return None
    doc = ast.get_docstring(node)
    if not doc:
        return None
    first = doc.strip().split("\n\n", 1)[0]
    return " ".join(line.strip() for line in first.split("\n"))


def _import_bindings(node: ast.AST) -> dict[str, Binding]:
    out: dict[str, Binding] = {}
    if isinstance(node, ast.Import):
        for alias in node.names:
            stmt = f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else "")
            if alias.asname:
                out[alias.asname] = Binding(0, tuple(alias.name.split(".")), stmt=stmt)
            else:  # `import a.b.c` binds `a`; the rest is reached by attribute access
                top = alias.name.split(".")[0]
                out[top] = Binding(0, (top,), stmt=stmt)
    elif isinstance(node, ast.ImportFrom):
        module = tuple(node.module.split(".")) if node.module else ()
        head = "." * node.level + (node.module or "")
        for alias in node.names:
            if alias.name != "*":
                stmt = f"from {head} import {alias.name}"
                stmt += f" as {alias.asname}" if alias.asname else ""
                out[alias.asname or alias.name] = Binding(node.level, module, alias.name, stmt)
    return out


def _direct_bindings(scope: ast.AST) -> dict[str, Binding]:
    """Import bindings made directly in `scope`'s body, not inside nested definitions."""
    out: dict[str, Binding] = {}
    for node in getattr(scope, "body", []):
        out.update(_import_bindings(node))
    return out


def _all_bindings(tree: ast.AST) -> dict[str, Binding]:
    out: dict[str, Binding] = {}
    for node in ast.walk(tree):
        out.update(_import_bindings(node))
    return out


def _bound_names(node: ast.AST) -> set[str]:
    """Every name bound anywhere inside `node`: parameters, assignment targets, nested defs."""
    names: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.arg):
            names.add(n.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store | ast.Del):
            names.add(n.id)
        elif isinstance(n, Function | ast.ClassDef) and n is not node:
            names.add(n.name)
        elif isinstance(n, ast.ExceptHandler | ast.MatchAs | ast.MatchStar) and n.name:
            names.add(n.name)
    return names


def _chains(node: ast.AST) -> list[list[str]]:
    """Every loaded name or attribute chain rooted at a name (`a`, `a.b.c`), in source order."""
    out: list[list[str]] = []

    class Chains(ast.NodeVisitor):
        def visit_Attribute(self, n: ast.Attribute) -> None:
            chain = _flatten(n)
            if chain:
                out.append(chain)
            else:
                self.generic_visit(n)

        def visit_Name(self, n: ast.Name) -> None:
            if isinstance(n.ctx, ast.Load):
                out.append([n.id])

    Chains().visit(node)
    return out


def _flatten(n: ast.expr) -> list[str] | None:
    if isinstance(n, ast.Name):
        return [n.id] if isinstance(n.ctx, ast.Load) else None
    if isinstance(n, ast.Attribute):
        base = _flatten(n.value)
        return base + [n.attr] if base else None
    return None


def _free(names: list[str]) -> list[str]:
    """Free names in first-use order, builtins and module globals excepted."""
    out: list[str] = []
    for n in names:
        if n not in BUILTINS and n not in MODULE_GLOBALS and n not in out:
            out.append(n)
    return out


def _dedupe(refs: list[Ref]) -> list[Ref]:
    seen: set[Ref] = set()
    return [r for r in refs if not (r in seen or seen.add(r))]
