"""The `--json` schemas: the one definition of every command's JSON output. Plan P5-T1, spec §9.

Every subcommand prints an object that carries `schema_version`, every field the schema names
(present, `null` when not available — never invented), and `origin` on every derived or asserted
fact (spec §10). `COMMANDS` maps each command to its schema; `validate()` checks a value
strictly — a missing field, an extra field, a wrong type or an unknown enum value is an error;
`json_schema()` renders a schema as JSON Schema (what the MCP server publishes as each tool's
`outputSchema`); `markdown()` renders `docs/json-schemas.md`; `fingerprint()` is the digest a
test pins, so a change to any schema fails until `SCHEMA_VERSION` is bumped and the new digest
recorded beside it. `python -m cttp.schemas` rewrites the doc.
"""

# ruff: noqa: E501 — a definitions file: each field's meaning reads best on one line
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

SCHEMA_VERSION = 3
FINGERPRINTS = {
    1: "95c46a2dbc0766c1",
    2: "14c8b9e5c6d17b96",
    3: "cc99e1dcc837f541",
}  # schema version → fingerprint(); a schema change bumps both

# --- the schema language -----------------------------------------------------------------------


@dataclass(frozen=True)
class S:
    """One schema node. `type` is object | array | map | string | integer | number | boolean |
    enum | ref; `doc` says what the value means; `origin` documents whether it is derived by the
    tool or asserted by a person (or `None` for a fact that is neither, such as a count)."""

    type: str
    doc: str = ""
    fields: tuple[tuple[str, S], ...] = ()  # object: name → schema, in output order
    items: S | None = None  # array: the element; map: the value
    values: tuple[str, ...] = ()  # enum
    ref: str | None = None  # ref: a name in DEFS
    nullable: bool = False
    origin: str | None = None

    def null(self) -> S:
        """The same, allowing `null` — the value when the fact is not available."""
        return S(**{**self.__dict__, "nullable": True})

    def derived(self) -> S:
        return S(**{**self.__dict__, "origin": "derived"})

    def asserted(self) -> S:
        return S(**{**self.__dict__, "origin": "asserted"})

    def about(self, doc: str) -> S:
        return S(**{**self.__dict__, "doc": doc})


def obj(doc: str, fields: dict[str, S]) -> S:
    return S("object", doc, fields=tuple(fields.items()))


def arr(items: S, doc: str = "") -> S:
    return S("array", doc, items=items)


def mapping(items: S, doc: str = "") -> S:
    return S("map", doc, items=items)


def string(doc: str = "") -> S:
    return S("string", doc)


def integer(doc: str = "") -> S:
    return S("integer", doc)


def number(doc: str = "") -> S:
    return S("number", doc)


def boolean(doc: str = "") -> S:
    return S("boolean", doc)


def enum(*values: str, doc: str = "") -> S:
    return S("enum", doc, values=values)


def ref(name: str, doc: str = "") -> S:
    return S("ref", doc, ref=name)


DERIVED = enum("derived", doc="computed by the tool from the repository")
ASSERTED = enum("asserted", doc="stated by a person: a link line or a registry entry")
ORIGIN = enum("derived", "asserted", doc="which it is (spec §10)")
RELATION = enum("is", "from", "see", doc="the link's marker: `cttp:` / `cttp-from:` / `cttp-see:`")
KIND = enum(
    "function",
    "class",
    "constant",
    "type",
    "macro",
    "script",
    doc="what the page is: `type` (a C struct, union, enum or typedef) and `macro` come from the tree-sitter extractor",
)

# --- shared objects ----------------------------------------------------------------------------

DEFS: dict[str, S] = {}

DEFS["imports"] = obj(
    "the outside modules a page needs (spec §8)",
    {
        "stdlib": arr(string(), "top-level standard-library modules used").derived(),
        "third_party": arr(string(), "top-level modules that are neither stdlib nor in the repository").derived(),
        "statements": arr(string(), "the import statements that bind those names; `expand` hoists them").derived(),
    },
)  # fmt: skip

DEFS["ref"] = obj(
    "a derived reference to a file or definition in the same repository",
    {
        "address": string("a pinned locator address at the same rev").derived(),
        "name": string("the text the page reaches it by (`REG_BITS`, `decode.STEP`, `r2m`); decides whether it can be inlined (spec §7)").derived(),
        "relation": enum("ref").derived(),
        "origin": DERIVED,
    },
)  # fmt: skip

DEFS["link"] = obj(
    "a link line found in the page's own text (spec §4)",
    {
        "address": string("the address as written").asserted(),
        "relation": RELATION.asserted(),
        "fields": mapping(string(), "the `key=value` fields, in order").asserted(),
        "description": string("the trailing quoted string").null().asserted(),
        "derived": boolean("whether the description was written by the tool (`~\"…\"`)"),
        "line": integer("1-based, within the page's text"),
        "indent": string("the whitespace before the comment marker"),
        "origin": ASSERTED,
    },
)  # fmt: skip

DEFS["location"] = obj(
    "one place a page was seen, from the object cache or the index (not part of the registry contract)",
    {
        "address": string("the pinned locator address").derived(),
        "target": string("`host/owner/repo/path`").derived(),
        "path": string().derived(),
        "rev": string("the full commit SHA").derived(),
        "name": string("the registry name that pointed here").null().asserted(),
        "registry": string("which registry answered").null(),
        "description": string("the entry's one line").null().asserted(),
        "license": string("SPDX id at that rev").null().derived(),
        "seen": string("ISO-8601 UTC: when it was resolved (cache) or crawled (index)"),
        "origin": enum("cache", "index", doc="which cache the location came from"),
    },
)  # fmt: skip

DEFS["page"] = obj(
    "the resolver's object — what an address names; the registry contract's JSON (spec §8)",
    {
        "name": string("the registry name, or `null` for a bare locator").null().asserted(),
        "address": string("the pinned address: a 12-hex rev, the `#symbol` kept").derived(),
        "rev": string("the full commit SHA").derived(),
        "identity": string("`sha256:<12 hex>` of the page's own normalized text").derived(),
        "identity_full": string("the full hex").derived(),
        "shape": string("`sha256:<12 hex>` of the shape; `null` when the language has no extractor").null().derived(),
        "shape_full": string().null().derived(),
        "kind": KIND.derived(),
        "language": enum("python", "c", "text", doc="`text` for a file with no extractor").derived(),
        "symbol": string("for a definition: its dotted name").null().derived(),
        "signature": string("for a definition: Python — the header without its keyword; C — the declaration up to the body or initializer, a macro's name and parameters").null().derived(),
        "docstring": string("the first docstring paragraph as one line; for C, the first paragraph of the comment directly above").null().derived(),
        "span": arr(integer(), "`[first, last]` 1-based lines in the origin file").derived(),
        "source": string("the page's own text, normalized, link lines taken out (spec §4)").derived(),
        "description": string("the entry's one line; `null` when the entry has none").null().asserted(),
        "license": string("SPDX id of the repository's license file at the rev").null().derived(),
        "target": string("`host/owner/repo/path`").derived(),
        "path": string("the path within the repository").derived(),
        "registry": string("which registry answered, or lent the name; `null` for a bare locator").null(),
        "refs": arr(ref("ref")).derived(),
        "imports": ref("imports").derived(),
        "links": arr(ref("link")).asserted(),
        "unresolved": arr(string(), "free names: used, bound by nothing in the page — what a closure must bind").derived(),
        "locations": arr(ref("location"), "every place seen, latest last; empty unless answered from a cache"),
        "via": enum("cache", "index", doc="which cache answered an identity address; `null` when the repository did").null(),
        "origin": obj(
            "which fields are derived and which asserted",
            {
                "identity": DERIVED,
                "shape": DERIVED,
                "license": DERIVED,
                "rev": DERIVED,
                "refs": DERIVED,
                "imports": DERIVED,
                "unresolved": DERIVED,
                "links": ASSERTED,
                "description": ASSERTED.null().about("`null` when there is no description"),
                "location": enum("repository", "cache", "index", doc="what answered"),
            },
        ),
    },
)  # fmt: skip

DEFS["node"] = obj(
    "one page of a closure",
    {
        "address": string("the pinned address").derived(),
        "locator": string("the pinned locator form — the closure's key").derived(),
        "identity": string().derived(),
        "identity_full": string().derived(),
        "kind": KIND.derived(),
        "symbol": string().null().derived(),
        "path": string().derived(),
        "lines": integer("lines of source").derived(),
        "license": string().null().derived(),
        "description": string("the stamp's description: the entry's, else one derived from signature and docstring").null(),
        "via": enum("root", "link", "ref", doc="how the closure reached it: the root, an inner `# cttp:` line, or a derived reference"),
        "needs": arr(string(), "pinned locator addresses this page depends on directly").derived(),
        "defines": arr(string(), "the top-level names this page binds when inlined").derived(),
        "source": string().derived(),
        "origin": obj(
            "",
            {
                "description": ORIGIN.null().about("`null` when there is no description"),
                "via": ORIGIN.about("`asserted` for a link, `derived` for a reference or the root"),
            },
        ),
    },
)  # fmt: skip

DEFS["missing"] = obj(
    "a target the index cannot tell (never fetched); only `--indexed` lists these — the live walk refuses instead",
    {
        "from": string("the page that links to it"),
        "address": string("the target as written"),
        "relation": enum("is", "ref"),
    },
)  # fmt: skip

REPORT_FIELDS = {
    "line": integer("1-based; 0 for a report about `pyproject.toml`"),
    "relation": RELATION,
    "address": string("the link's address as written (a path for the `deps` report)"),
}

DEFS["expand_report"] = obj(
    "one link's outcome from `expand` or `add`",
    {
        **REPORT_FIELDS,
        "status": enum(
            "expanded", "unchanged", "vendored", "requires", "deps",
            doc="`requires`: the closure needs third-party packages (listed in `detail`); "
            "`deps`: what `--write-deps` did, or what it would do",
        ),
        "detail": string().null(),
    },
)  # fmt: skip

DEFS["check_report"] = obj(
    "one link's outcome from `check`",
    {
        **REPORT_FIELDS,
        "status": enum(
            "ok", "unexpanded", "drift", "mismatch", "unresolvable", "fixed",
            doc="spec §7: `drift` — the block no longer hashes to its `id=`; `mismatch` — the block "
            "does, the origin page does not; `fixed` — `--fix` turned a drifted `is` into `from`",
        ),
        "detail": string().null(),
    },
)  # fmt: skip

DEFS["update_report"] = obj(
    "one link's outcome from `update`",
    {
        **REPORT_FIELDS,
        "status": enum(
            "updated", "unchanged", "upstream", "not-found", "drift", "unexpanded", "vendored",
            "not-confirmed",
            doc="`upstream`: a `from` link — the diff is shown, never applied; "
            "`not-confirmed`: the change waited for a confirmation it did not get (exit 2)",
        ),
        "detail": string().null(),
        "to": string("the address the link would move to").null().derived(),
        "rule": enum("same-path", "same-identity", "backlink", "to", doc="which of spec §5's rules found it").null().derived(),
        "diff": string("a unified diff of the block, empty when there is none").derived(),
    },
)  # fmt: skip

DEFS["fold_entry"] = obj(
    "one link of a file, with the block it stands for",
    {
        "line": integer("1-based line of the link"),
        "relation": RELATION.asserted(),
        "address": string().asserted(),
        "description": string().null().asserted(),
        "start": integer("1-based first line of the block"),
        "end": integer("1-based last line, inclusive; `start - 1` when nothing is beneath"),
        "lines": integer(),
        "folded": boolean("whether the block was collapsed in the text output"),
    },
)  # fmt: skip

DEFS["backlink"] = obj(
    "one indexed link whose target is the address asked about",
    {
        "source": obj(
            "the page the link belongs to (spec §4: the block's definition, else the innermost holding definition, else the file)",
            {
                "identity": string().derived(),
                "identity_full": string().derived(),
                "address": string("its pinned locator address").null().derived(),
                "repo": string(),
                "sha": string(),
                "path": string(),
                "symbol": string().null(),
                "kind": KIND,
                "name": string("the definition's name, or the file name"),
                "signature": string().null().derived(),
                "license": string().null().derived(),
            },
        ),
        "relation": enum("is", "from", "see", "ref"),
        "origin": ORIGIN.about("`asserted` for a link line, `derived` for a reference"),
        "line": integer("1-based, in the file"),
        "target": string("the target address as written"),
        "target_identity": string("the target's identity, when the index can tell").null().derived(),
        "description": string().null().asserted(),
        "name": string("a derived reference: the text it is reached by").null(),
    },
)  # fmt: skip

DEFS["by"] = mapping(
    mapping(integer(), "origin → count"),
    'counts by relation, then by origin: `{"is": {"asserted": 2}, "ref": {"derived": 1}}`',
)

DEFS["dup_group"] = obj(
    "pages that are the same code (by identity) or the same structure (by shape), in more than one place",
    {
        "key": string("`sha256:<12 hex>` — the identity or the shape the group shares").derived(),
        "key_full": string().derived(),
        "identities": arr(string(), "the distinct identities in the group (one, by identity)").derived(),
        "names": arr(string(), "the distinct definition names, sorted").derived(),
        "kind": KIND.derived(),
        "lines": integer().derived(),
        "count": integer("places"),
        "locations": arr(
            obj(
                "",
                {
                    "address": string().derived(),
                    "identity": string().derived(),
                    "repo": string(),
                    "path": string(),
                    "symbol": string().null(),
                    "license": string().null().derived(),
                    "name": string("the definition's name").derived(),
                },
            )
        ),
    },
)  # fmt: skip

DEFS["hit"] = obj(
    "one search hit",
    {
        "identity": string().derived(),
        "identity_full": string().derived(),
        "name": string().derived(),
        "kind": KIND.derived(),
        "signature": string().null().derived(),
        "docstring": string().null().derived(),
        "score": number("FTS5 bm25 rank; lower is better").derived(),
        "address": string("where it is at the current revision, else the last place seen").null(),
        "locations": arr(
            obj(
                "",
                {
                    "address": string(),
                    "repo": string(),
                    "path": string(),
                    "symbol": string().null(),
                    "name": string("the registry name pointing at this place").null().asserted(),
                },
            ),
            "current places first when there are any",
        ),
    },
)  # fmt: skip

DEFS["revision"] = obj(
    "one crawled revision of the place",
    {
        "sha": string(),
        "address": string("the place at that rev"),
        "committed_at": integer("the commit's own timestamp (unix)").null().derived(),
        "crawled_at": string("ISO-8601 UTC"),
        "identity": string().null().derived(),
        "identity_full": string().null().derived(),
        "shape": string().null().derived(),
        "signature": string().null().derived(),
        "absent": boolean("the place has no page at this rev"),
        "changed": boolean("the identity differs from the revision before"),
    },
)  # fmt: skip

DEFS["ranked"] = obj(
    "one ranked page",
    {
        "identity": string().derived(),
        "identity_full": string().derived(),
        "name": string().derived(),
        "kind": KIND.derived(),
        "signature": string().null().derived(),
        "address": string().null(),
        "backlinks": integer("distinct linking pages — (identity, repo, file)").derived(),
        "by": ref("by"),
    },
)  # fmt: skip

DEFS["crawled"] = obj(
    "one repository crawled at one revision",
    {
        "repo": string("`host/owner/repo`"),
        "sha": string(),
        "status": enum("crawled", "already", doc="`already`: skipped, crawled before (`--force` redoes it)"),
        "files": integer("files looked at"),
        "pages": integer("locations written"),
        "definitions": integer("identities the index had not seen before"),
        "links": integer(),
        "skipped": arr(string(), "files that could not be read or parsed, with the reason"),
    },
)  # fmt: skip

DEFS["repo_status"] = obj(
    "one registered repository",
    {
        "repo": string(),
        "default_branch": string().null(),
        "local_path": string("the clone it was added from").null(),
        "revisions": arr(
            obj(
                "most recently crawled first",
                {
                    "sha": string(),
                    "crawled_at": string(),
                    "license": string().null().derived(),
                    "files": integer(),
                },
            )
        ),
    },
)  # fmt: skip

DEFS["closure"] = obj(
    "the pages a page needs to run inline, dependencies before dependents, the root last",
    {
        "address": string("the (first) root's pinned address").derived(),
        "identity": string().derived(),
        "source": enum("repository", "index", doc="a live walk of the repositories, or the index's recorded links (`--indexed`)"),
        "roots": arr(string(), "the addresses asked about — one, or several with `--indexed`"),
        "definitions": arr(ref("node")).derived(),
        "count": integer(),
        "lines": integer(),
        "imports": arr(string(), "import statements to hoist above the whole block, in first-need order").derived(),
        "stdlib": arr(string()).derived(),
        "requires": arr(string(), "third-party top-level packages the closure needs").derived(),
        "missing": arr(ref("missing"), "always empty for a live walk, which refuses instead"),
        "origin": obj("", {"order": DERIVED, "imports": DERIVED, "requires": DERIVED}),
    },
)  # fmt: skip

DEFS["entry"] = obj(
    "a registry entry: `names/<name>.toml` (spec §8) — asserted by its author, except `owner`, which `name claim` derives from the target",
    {
        "name": string().asserted(),
        "description": string("one line, copied onto link lines; `null` when the entry has none").null().asserted(),
        "owner": string("`host/owner`: the account that proved control of the target").null().derived(),
        "target": string("`host/owner/repo[/path]`").asserted(),
        "default": string("the label the short form resolves to").asserted(),
        "versions": mapping(string(), "label → ref of the target repository").asserted(),
    },
)  # fmt: skip

DEFS["check"] = obj(
    "one of the registry's checks on an entry (spec §8, plan P7-T2)",
    {
        "check": enum(
            "declaration", "owner", "target", "labels", "resolves",
            doc="the target's `cttp.toml` declares the name at its default branch; the owner is the target's account; the target path exists; every label is well formed and its ref is a revision; the name resolves",
        ),
        "ok": boolean(),
        "detail": string("what was found, or what is wrong and what to do"),
    },
)  # fmt: skip

# --- the commands ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Command:
    usage: str  # how it is invoked
    summary: str  # one line: what it returns
    schema: S | None  # None: the command prints no JSON object on success
    when: str = ""  # when an agent should reach for it
    notes: tuple[str, ...] = field(default_factory=tuple)  # exit codes and caveats


COMMANDS: dict[str, Command] = {
    "version": Command(
        "cttp --version --json",
        "The tool's version.",
        obj("", {"version": string()}),
    ),
    "config": Command(
        "cttp config --json",
        "The effective configuration: the file, the ordered registry list, the remotes.",
        obj(
            "",
            {
                "path": string("the config file; `null` when defaults were used").null(),
                "registries": arr(string(), "HTTP URLs or local paths, asked in order"),
                "remotes": mapping(string(), "locator prefix → URL prefix"),
            },
        ),
    ),
    "resolve": Command(
        "cttp resolve <address> [--id <identity>] --json",
        "The page an address names: its source, identity, license, references and imports.",
        ref("page"),
        "When you need one definition's text and signature, not the file. Any address form: a "
        "name, a locator, or an identity (answered from the object cache or the index).",
        (
            "This is the registry contract's object (spec §8): `GET /<name>.json` returns the same.",
            "`locations` and `via` are only filled when an identity address was answered from a cache.",
            "With `--id`, a page whose identity does not start with the given hex is an error "
            "(exit 1) naming both hashes — the stamp is wrong, not the copy.",
        ),
    ),
    "resolve --latest": Command(
        "cttp resolve <pinned address> --latest --json",
        "Where a pinned page is at its repository's head, and which rule found it.",
        obj(
            "",
            {
                "from": ref("page", "the pinned page"),
                "head": string("the full SHA of the head that was searched").derived(),
                "found": boolean(),
                "rule": enum(
                    "same-path",
                    "same-identity",
                    "backlink",
                    doc="spec §5: the same path and symbol at head; the same identity elsewhere; "
                    "or, through the index, a page that links back (another repository, or a fork)",
                )
                .null()
                .derived(),
                "via": string("`index` when the index found it").null().derived(),
                "to": ref("page", "the page at head").null(),
                "changed": boolean("the identity differs from the pinned one (rule 1)")
                .null()
                .derived(),
                "message": string("what happened, in words"),
                "origin": obj("", {"rule": DERIVED, "head": DERIVED, "via": DERIVED}),
            },
        ),  # fmt: skip
        "Before `update`: to see what following a link forward would resolve to.",
        ("Exit 1 when not found; the object still says why.",),
    ),
    "closure": Command(
        "cttp closure <address> --json | cttp closure --indexed <address>… --json",
        "Exactly the definitions a page needs to run inline, in dependency order, each with its address.",
        ref("closure"),
        "When a task needs a definition and what it depends on, and nothing else: context cost "
        "proportional to the task. The live walk is what `expand` would write and refuses what "
        "cannot be inlined honestly; `--indexed` reads the index's recorded links instead, takes "
        "several roots, and lists what it cannot tell under `missing`.",
        (
            "A closure over budget (50 definitions / 2,000 lines) is only an error for `expand`; "
            "`closure` lifts the budget.",
        ),
    ),
    "expand": Command(
        "cttp expand <file>… [--package] [--write-deps] --json",
        "What was written beneath each unexpanded link, per file.",
        obj("", {"files": mapping(arr(ref("expand_report")), "file path → its reports")}),
        "To materialize links in place. Prefer `add` to write a new link.",
    ),
    "add": Command(
        "cttp add <address> [<file>] [--at N] [--package] --json",
        "The link written into the file and expanded, as `expand` reports it.",
        obj("", {"files": mapping(arr(ref("expand_report")), "the one file → its reports")}),
        "To bring a page into a file: writes `# cttp: <address>` and expands it.",
    ),
    "check": Command(
        "cttp check <file>… [--fix] --json",
        "Every link's state: stamped, block hashing to its id, resolvable.",
        obj(
            "",
            {
                "ok": boolean("no link failed (`ok` or `fixed`)"),
                "links": mapping(arr(ref("check_report")), "file path → its reports"),
            },
        ),
        "After editing a file with links, or before trusting one.",
        ("Exit 1 when any link failed.",),
    ),
    "update": Command(
        "cttp update <file>… [<address>…] [--all] [--to <rev>] [--yes] --json",
        "Each selected link's proposed or applied move forward.",
        obj(
            "",
            {
                "ok": boolean("nothing is waiting for a confirmation"),
                "links": mapping(arr(ref("update_report")), "file path → its reports"),
            },
        ),
        "To follow pinned links forward; `--yes` applies without a terminal.",
        ("Exit 2 when a change waited for a confirmation it did not get.",),
    ),
    "fold": Command(
        "cttp fold <file>… [--open <address>] --json",
        "Each file as links, with every expanded block's line range.",
        obj("", {"files": mapping(arr(ref("fold_entry")), "file path → its links")}),
        "To see a file as its links, so that a file with expanded code costs no more context "
        "than its link lines. Writes nothing.",
    ),
    "run": Command(
        "cttp run <address | file> [--yes] --json",
        "Runs the program; its output is the program's own, not a JSON object.",
        None,
        "",
        (
            "Only an error prints the error object. Exit 2 when the first run of an address was "
            "not confirmed (pass `--yes` without a terminal); otherwise the program's exit code.",
        ),
    ),
    "cache status": Command(
        "cttp cache status --json",
        "What the caches hold.",
        obj(
            "",
            {
                "home": string("`$CTTP_HOME`"),
                "repos": obj("bare clones", {"count": integer(), "bytes": integer()}),
                "objects": obj("the object cache", {"count": integer(), "bytes": integer()}),
                "run": obj(
                    "run-cache entries: what was confirmed to run",
                    {"count": integer(), "bytes": integer()},
                ),
            },
        ),  # fmt: skip
    ),
    "cache clear": Command(
        "cttp cache clear [--run] --json",
        "What was removed.",
        obj("", {"removed": arr(string(), "paths removed; the run cache only with `--run`")}),
    ),
    "index add": Command(
        "cttp index add <host/owner/repo | path> --json",
        "The repository registered for crawling.",
        obj(
            "",
            {
                "repo": string("`host/owner/repo`"),
                "local_path": string("the clone it was added from").null(),
                "default_branch": string("learned at the first crawl of a locator").null(),
                "status": enum("added", "already registered"),
            },
        ),
    ),
    "index crawl": Command(
        "cttp index crawl [<repo>…] [--rev <rev>] [--force] --json",
        "Each registered repository crawled at its head (or `--rev`).",
        obj("", {"crawled": arr(ref("crawled"))}),
    ),
    "index status": Command(
        "cttp index status --json",
        "What the index holds.",
        obj(
            "",
            {
                "index": string("the index file"),
                "counts": obj(
                    "rows per table",
                    {
                        "repos": integer(),
                        "revisions": integer(),
                        "definitions": integer(),
                        "locations": integer(),
                        "links": integer(),
                        "names": integer(),
                    },
                ),
                "repos": arr(ref("repo_status")),
            },
        ),
    ),
    "who": Command(
        "cttp who <address> --json",
        "Backlinks: every indexed page linking to the address, by relation and origin.",
        obj(
            "",
            {
                "address": string("as asked"),
                "identities": arr(
                    string(), "the identities the index knows at that address"
                ).derived(),
                "name": string("the name form's name").null(),
                "repo": string("the place the address names").null(),
                "path": string().null(),
                "symbol": string().null(),
                "backlinks": arr(
                    ref("backlink"), "sorted `is`, `from`, `see`, `ref`; asserted before derived"
                ).derived(),
                "count": integer(),
                "by": ref("by"),
                "origin": obj(
                    "", {"backlinks": DERIVED, "relation": string("`per link: its origin`")}
                ),
            },
        ),  # fmt: skip
        "To find who uses a definition before changing it, or where a copy came from.",
        (
            "Matches by identity; by place or name only for links whose target identity the index "
            "could not tell.",
        ),
    ),
    "dups": Command(
        "cttp dups [--shape] --json",
        "Groups of pages that are the same code in more than one place, at the current revisions.",
        obj(
            "",
            {
                "by": enum(
                    "identity",
                    "shape",
                    doc="`shape`: the same structure under other names or literals",
                ),
                "groups": arr(ref("dup_group"), "largest first").derived(),
                "count": integer(),
                "origin": obj("", {"groups": DERIVED, "by": DERIVED}),
            },
        ),
        "To find copies worth turning into links.",
    ),
    "search": Command(
        "cttp search <words>… [--limit N] --json",
        "Pages whose name, signature or docstring match the words.",
        obj(
            "",
            {
                "query": string(),
                "hits": arr(ref("hit"), "best first").derived(),
                "count": integer(),
                "origin": obj("", {"hits": DERIVED, "score": DERIVED}),
            },
        ),
        "To find a definition by what it is called or what its docstring says. Every term is a "
        "prefix; stemming applies.",
    ),
    "history": Command(
        "cttp history <address> --json",
        "The identities seen at one place over every crawled revision of its repository.",
        obj(
            "",
            {
                "repo": string(),
                "path": string(),
                "symbol": string().null(),
                "revisions": arr(ref("revision"), "oldest commit first").derived(),
                "identities": arr(
                    string(), "the distinct identities, in order of appearance"
                ).derived(),
                "count": integer("revisions"),
                "origin": obj("", {"revisions": DERIVED, "identity": DERIVED}),
            },
        ),
        "To see how a definition changed, or when it appeared.",
    ),
    "rank": Command(
        "cttp rank [--limit N] --json",
        "Pages ordered by how many distinct pages link to them.",
        obj(
            "",
            {
                "ranked": arr(ref("ranked"), "most linked first").derived(),
                "count": integer(),
                "origin": obj("", {"backlinks": DERIVED, "rank": DERIVED}),
            },
        ),
    ),
    "name show": Command(
        "cttp name show <name> --json",
        "A registry entry and what the name resolves to.",
        obj(
            "",
            {
                "name": string(),
                "registry": string("the local registry the entry came from"),
                "entry": ref("entry").asserted(),
                "resolution": ref("page", "what `cttp resolve <name>` prints").derived(),
                "origin": obj("", {"entry": ASSERTED, "resolution": DERIVED}),
            },
        ),
        "To see who owns a name, where it points, and its labels, before linking to it.",
        (
            "An HTTP registry answers resolutions, not entries; the entry comes from a local registry repository.",
        ),
    ),
    "name claim": Command(
        "cttp name claim <name> --target <host/owner/repo[/path]> [--description …] [--version label=ref]… [--default label] [--transfer] [--no-pr] --json",
        "The entry written for the name, the checks it passed, and the pull request opened for it.",
        obj(
            "",
            {
                "name": string(),
                "action": enum(
                    "claimed",
                    "updated",
                    "transferred",
                    doc="a new name; the same owner's entry rewritten; another owner's name taken over (`--transfer`)",
                ),
                "owner": string("`host/owner` of the target").derived(),
                "previous_owner": string("the owner the entry had before, when it existed").null(),
                "target": string(),
                "declared_at": obj(
                    "where the target declared the name",
                    {
                        "file": string("`cttp.toml`"),
                        "branch": string("the target's default branch"),
                        "rev": string("its head, full SHA"),
                    },
                ).derived(),
                "entry": ref("entry"),
                "checks": arr(
                    ref("check"),
                    "the checks run before writing (`resolves` is left to `name verify`)",
                ),
                "path": string("`names/<name>.toml`"),
                "text": string("the file's text"),
                "written_to": string(
                    "the file in the registry clone's working tree (`--no-pr`); `null` when it went into a pull request"
                ).null(),
                "branch": string(
                    "`claim/<name>`, pushed to the registry's origin; `null` with `--no-pr`"
                ).null(),
                "pr": string("the pull request's URL; `null` with `--no-pr`").null(),
                "registry": string("the local registry repository the claim is against"),
                "origin": obj(
                    "", {"owner": DERIVED, "declaration": DERIVED, "description": ASSERTED}
                ),
            },
        ),  # fmt: skip
        "",
        (
            "Refused (exit 1) when the target's `cttp.toml` does not declare the name, when the name is another owner's and `--transfer` was not given, or when a label or ref is not valid.",
            "The pull request needs `gh` and an `origin` remote on the registry clone; `--no-pr` needs neither.",
        ),
    ),
    "mcp install": Command(
        "cttp mcp install [--claude-code] --json",
        "The `claude mcp add` line that attaches the MCP server to Claude Code, and whether it ran.",
        obj(
            "",
            {
                "command": arr(string(), "the command line, one argument per element"),
                "ran": boolean("`--claude-code`: it was run"),
                "output": string("what `claude mcp add` printed; `null` when not run").null(),
            },
        ),
        "",
        ("`cttp mcp` itself runs the server over stdio and prints no JSON object.",),
    ),
    "error": Command(
        "any command, on failure",
        "What went wrong, in one line.",
        obj("", {"error": string("the message the text mode prints after `error:`")}),
        "",
        (
            "Printed to stdout with `--json` (stderr otherwise); exit 1, or 2 for a declined "
            "confirmation.",
        ),
    ),
}

NO_JSON = ("serve", "mcp")  # long-running; they print nothing but a banner


# --- stamping and validation -------------------------------------------------------------------


def stamp(data: dict) -> dict:
    """The object as printed: `schema_version` first, then the command's fields."""
    return {"schema_version": SCHEMA_VERSION, **data}


def top(schema: S) -> S:
    """A command's schema as printed: with `schema_version` in front."""
    return S("object", schema.doc, fields=(("schema_version", integer()), *_fields_of(schema)))


def _fields_of(schema: S) -> tuple[tuple[str, S], ...]:
    while schema.type == "ref":
        schema = DEFS[schema.ref]
    return schema.fields


def validate(command: str, value: object) -> list[str]:
    """Every way `value` departs from the command's printed schema; empty when it conforms."""
    cmd = COMMANDS[command]
    if cmd.schema is None:
        return [f"{command} has no JSON schema"]
    return _check(top(cmd.schema), value, "$")


def _check(s: S, v: object, path: str) -> list[str]:
    if v is None:
        return [] if s.nullable else [f"{path}: null is not allowed"]
    t = s.type
    if t == "ref":
        return _check(S(**{**DEFS[s.ref].__dict__, "nullable": s.nullable}), v, path)
    if t == "object":
        if not isinstance(v, dict):
            return [f"{path}: expected an object, got {type(v).__name__}"]
        errors = []
        names = [n for n, _ in s.fields]
        for n in names:
            if n not in v:
                errors.append(f"{path}.{n}: missing")
        for n in v:
            if n not in names:
                errors.append(f"{path}.{n}: not in the schema")
        for n, fs in s.fields:
            if n in v:
                errors += _check(fs, v[n], f"{path}.{n}")
        return errors
    if t == "array":
        if not isinstance(v, list):
            return [f"{path}: expected an array, got {type(v).__name__}"]
        return [e for i, x in enumerate(v) for e in _check(s.items, x, f"{path}[{i}]")]
    if t == "map":
        if not isinstance(v, dict):
            return [f"{path}: expected an object, got {type(v).__name__}"]
        return [e for k, x in v.items() for e in _check(s.items, x, f"{path}.{k}")]
    if t == "string":
        return [] if isinstance(v, str) else [f"{path}: expected a string, got {type(v).__name__}"]
    if t == "integer":
        ok = isinstance(v, int) and not isinstance(v, bool)
        return [] if ok else [f"{path}: expected an integer, got {v!r}"]
    if t == "number":
        ok = isinstance(v, int | float) and not isinstance(v, bool)
        return [] if ok else [f"{path}: expected a number, got {v!r}"]
    if t == "boolean":
        return [] if isinstance(v, bool) else [f"{path}: expected a boolean, got {v!r}"]
    if t == "enum":
        return [] if v in s.values else [f"{path}: {v!r} is not one of {list(s.values)}"]
    raise ValueError(t)  # pragma: no cover


# --- JSON Schema -------------------------------------------------------------------------------


def json_schema(command: str, inline: bool = True) -> dict:
    """The command's printed schema as JSON Schema (draft 2020-12). With `inline`, shared
    objects are expanded in place — one self-contained document, as a tool's `outputSchema`."""
    cmd = COMMANDS[command]
    if cmd.schema is None:
        raise ValueError(f"{command} prints no JSON object")
    out = _js(top(cmd.schema), inline)
    out["title"] = command
    if not inline:
        out["$defs"] = {name: _js(s, False) for name, s in DEFS.items()}
    return out


def _js(s: S, inline: bool) -> dict:
    t = s.type
    if t == "ref":
        if inline:
            d = _js(S(**{**DEFS[s.ref].__dict__, "nullable": False}), True)
            if s.doc:
                d["description"] = s.doc
        else:
            d = {"$ref": f"#/$defs/{s.ref}"}
        return _nullable({"anyOf": [d, {"type": "null"}]} if s.nullable else d, s, wrapped=True)
    if t == "object":
        d = {
            "type": "object",
            "properties": {n: _js(fs, inline) for n, fs in s.fields},
            "required": [n for n, _ in s.fields],
            "additionalProperties": False,
        }
    elif t == "array":
        d = {"type": "array", "items": _js(s.items, inline)}
    elif t == "map":
        d = {"type": "object", "additionalProperties": _js(s.items, inline)}
    elif t == "enum":
        d = {"enum": list(s.values) + ([None] if s.nullable else [])}
    else:
        d = {"type": t}
    return _nullable(d, s)


def _nullable(d: dict, s: S, wrapped: bool = False) -> dict:
    if s.nullable and not wrapped and "type" in d:
        d = {**d, "type": [d["type"], "null"]}
    if s.doc and "description" not in d:
        d["description"] = s.doc
    if s.origin:
        d["x-origin"] = s.origin
    return d


def fingerprint() -> str:
    """A digest of every command's JSON Schema — the same input, the same digest."""
    text = json.dumps(
        {name: json_schema(name) for name, c in COMMANDS.items() if c.schema is not None},
        sort_keys=True,
    )
    return hashlib.sha256(text.encode()).hexdigest()[:16]


# --- Markdown ----------------------------------------------------------------------------------


def markdown() -> str:
    """`docs/json-schemas.md`, generated from the definitions above."""
    out = [
        "# cttp — the `--json` schemas",
        "",
        "**Generated from `src/cttp/schemas.py` — do not edit.** `python -m cttp.schemas` rewrites "
        "it; `tests/test_schemas.py` fails when it is stale.",
        "",
        f"Schema version **{SCHEMA_VERSION}**, fingerprint `{fingerprint()}`. A change to any "
        "schema is a deliberate act: the fingerprint test fails until `SCHEMA_VERSION` is bumped "
        "and the change noted in `PROGRESS.md`.",
        "",
        "## Conventions",
        "",
        "- Every subcommand accepts `--json`, before or after the subcommand name "
        "(`cttp --json who x` and `cttp who x --json`). The object goes to stdout.",
        "- Every object carries `schema_version` (an integer) first.",
        "- **Every field is present.** A fact that is not available is `null` — never a "
        "plausible-looking value, never coerced to zero or an empty string (spec §10).",
        "- No field beyond the schema's is printed; a reader may reject unknown fields.",
        "- **Origin.** A fact computed by the tool from the repository is *derived*; a fact "
        "stated by a person is *asserted*. Each table says which under **Origin**; objects that "
        "carry an `origin` field say it in the output too.",
        "- Types: `string`, `integer`, `number`, `boolean`, `[T]` an array of `T`, "
        "`{string: T}` a map with arbitrary keys, `a | b` one of the listed values, `?` may "
        "be `null`, `→ name` a shared object defined under **Shared objects**.",
        "- On failure every command prints the [error object](#error) and exits 1 "
        "(2 for a declined confirmation).",
        "- `" + "`, `".join(NO_JSON) + "` run until stopped and print no JSON object; "
        "`run` prints the program's own output.",
        "",
        "## Commands",
        "",
    ]
    for name, cmd in COMMANDS.items():
        out += [f"### {name}", "", f"`{cmd.usage}`", "", cmd.summary, ""]
        if cmd.when:
            out += [f"**When:** {cmd.when}", ""]
        for note in cmd.notes:
            out += [f"- {note}"]
        if cmd.notes:
            out.append("")
        if cmd.schema is None:
            out += ["No JSON object on success.", ""]
        else:
            out += _table(top(cmd.schema)) + [""]
    out += ["## Shared objects", ""]
    for name, s in DEFS.items():
        out += [f"### {name}", ""]
        if s.doc:
            out += [s.doc, ""]
        out += _table(s) + [""]
    return "\n".join(out).rstrip("\n") + "\n"


def _table(s: S) -> list[str]:
    rows = ["| Field | Type | Origin | Meaning |", "|---|---|---|---|"]
    for path, fs in _walk(s, ""):
        rows.append(f"| `{path}` | {_type(fs)} | {fs.origin or ''} | {_cell(fs.doc)} |")
    return rows


def _walk(s: S, prefix: str):
    if s.type == "ref":
        return
    if s.type == "object":
        for n, fs in s.fields:
            path = f"{prefix}.{n}" if prefix else n
            yield path, fs
            yield from _walk(fs, path)
    elif s.type == "array":
        yield from _walk(s.items, prefix + "[]")
    elif s.type == "map":
        yield from _walk(s.items, prefix + ".*")


def _type(s: S) -> str:
    t = s.type
    if t == "ref":
        text = f"→ [{s.ref}](#{s.ref})"
    elif t == "array":
        text = f"[{_type(S(**{**s.items.__dict__, 'nullable': False}))}" + (
            "?]" if s.items.nullable else "]"
        )
    elif t == "map":
        text = f"{{string: {_type(s.items)}}}"
    elif t == "enum":
        text = " \\| ".join(f"`{v}`" for v in s.values)
    elif t == "object":
        text = "object"
    else:
        text = t
    return text + ("?" if s.nullable else "")


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":  # pragma: no cover
    import sys
    from pathlib import Path

    target = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/json-schemas.md")
    target.write_text(markdown(), encoding="utf-8")
    print(f"wrote {target}  (schema version {SCHEMA_VERSION}, fingerprint {fingerprint()})")
