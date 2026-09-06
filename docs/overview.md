# cttp — Orientation

**Read this in full at session start.** It is the durable map of the project: what it is, how it is
structured, where things live, the invariants, and the traps that cost real time. It is deliberately
**slow-moving** — nothing here should change more than about monthly.

It carries **no status and no next steps**. For "what is true right now / what's next", read
[`PROGRESS.md`](../PROGRESS.md). For "how to behave in this repo", read `CLAUDE.md`. For why the
project exists, [`vision.md`](vision.md); for where it is going, [`spec.md`](spec.md).

---

## 1. What this is

cttp — *code text transfer protocol* — lets code point at code. Every definition has an
**address**; a reference to one is a **link**, a comment of the form `# cttp: <address>` written
where an import would go; and a **registry** answers what a name means. The tool acts at **edit
time**: `cttp expand` resolves each link and writes the code it names directly beneath the comment,
stamping the line with the pinned revision and a content hash. The runtime, the compiler and the
reader only ever see ordinary source. A program that uses expanded code runs with cttp
uninstalled — that is the founding rule, and a test guards it.

Today the address, the link and the resolver exist in full: all three address forms resolve — a
name through a registry, a locator through git, an identity from the object cache — with a
`#symbol` selecting one Python definition of a file; a registry that is a public git repository
(`github.com/leorinaldi/cttp-registry`) or an HTTP server speaking the registry contract;
identity and shape hashes; a Python extractor that is exact (`ast`) and derives references; the
three link markers in any comment syntax, with the block beneath a link defined; a license
matcher; `resolve --latest` following a pinned address to the repository's head; the
**materializer in full** — the closure of a page, expansion with the closure beneath the link
(dependencies above, imports hoisted, each beneath its own stamp), `add`, `check --fix`,
`update`, `fold`, `run` confirming every page, and `expand --package` as the vendored fallback;
the **index** — a SQLite file crawled from repositories you name, identity the key, answering
`who`, `dups`, `closure --indexed`, `search`, `history`, `rank` and `--latest`'s rule 3; and
the **viewer** over registry and index on port 3120; and the **agent interface** — every
command's `--json` object defined once in `schemas.py` (stamped `schema_version`, validated by a
test, rendered to `docs/json-schemas.md`) and `cttp mcp`, an MCP server over stdio exposing
`resolve`, `who`, `closure`, `search`, `dups` and `fold` as tools that answer exactly what the
CLI prints; and the **read side for C** — a tree-sitter extractor driven by a per-language
query file, so `.c`/`.h` files have definitions, identities, shapes and backlinks like Python
files (no references, no write side), and the **driver corpus** reproduced under `bench/drivers/`
with spec §12's acceptance test 1 and the line-level measurement behind the vision's numbers;
and the **registry as a service** — `cttp name show | claim | verify` (proof of control: the
target's `cttp.toml` declares the name; a claim is a pull request), federation (registries in
order, first match wins), and `cttp serve --export` writing the contract as static files for
`cttp.ai`; and the **benchmark harness** (`bench/agent/`) — Claude Code run headless under a
subscription login with two arms, the cttp tools against the shell's search, each run in its own
checkout with its own index, every run a record, tasks run in parallel with `--jobs`. **The plan
is complete**: fifteen tasks over `click`, `attrs` and `rich`, ninety runs recorded, and
[`benchmark.md`](benchmark.md) carrying the table and its reading. What it found, in one line:
cttp is cheaper for cross-repository reuse and the margin grows with the closure's size (0.90
overall, 0.38 on a two-file closure), costs about twice as much on in-repository fixes while
passing slightly more often, and cost 19–40x on impact questions over a `src/`-layout project.
That last was **one defect in two halves** — `who` could not resolve a test's import into
`src/`, and an agent cannot confirm an answer it senses is incomplete. The source-root rule (§4)
closed the first: the family 16.28x → **6.65x**. **`who`'s `coverage` object** (§4) closed the
second — it states what the answer is an answer over, and `complete` says when there is no gap —
and the family fell again to **2.40x** at 14 median turns, the worst question 23.62x → 8.65x. The
two flat-layout tasks, which were never uncertain, got slightly *worse*: assurance costs on every
call and repays only where the agent would have doubted. **Collapsing the coverage object** on a
complete answer (§4) then cut it 1,373 → 479 characters at the tool's mouth and gave those two
tasks nothing back — the family read 3.26x on a fourth sweep, `im-nested-chain-click` alone
spanning 141k–569k tokens over three runs. The effect is beneath the benchmark's resolution at
three runs per arm; no ratio here should be trusted to a change of a few hundred tokens per call.
See [`benchmark.md`](benchmark.md).

## 2. Architecture

Everything is one Python package, `src/cttp/`, installed as the `cttp` command. There is no API
tier and no database. The pieces, in the order a link travels through them:

```text
link line ──parse──▶ address ──resolve──▶ registry ──entry──▶ git cache ──blob──▶ extractor
   ▲                                                                                  │
   └────────────────── expand writes stamp + source beneath the link ◀─── page + identity
```

- **Address** (`address.py`) — the grammar of spec §2: one frozen `Address` for the name,
  locator and identity forms, canonical `str()`, `parse_pinned()` for stamps.
- **Hashing** (`hashing.py`) — the **identity**: SHA-256 of the definition's own normalized
  source (dedented, LF, no trailing whitespace, one trailing newline); and the **shape**: the
  same text tokenized with identifiers as positional placeholders and literals as typed ones,
  keywords and builtins kept, comments and blank lines dropped, structure tokens kept.
  `shape(text, language)`: Python through `tokenize`, a language with a tree-sitter grammar
  through `extract.treesitter.shape_text` (its identifier and literal nodes; braces and
  semicolons are the structure), anything else `ShapeError`. `address.py` re-exports both.
- **Links** (`links.py`) — one regex finds every link line in any comment syntax (`#`, `//`,
  `--`, `;`, `/* … */`); the marker gives the relation — `cttp:` *is*, `cttp-from:` *from*,
  `cttp-see:` *see*; fields are ordered `key=value`, the description is the trailing quoted
  string, `~"…"` when derived by the tool. A link with an `id=` field is *stamped*. A malformed
  link line is a `LinkError` naming the line and the field. `find_links()` records every link's
  **block** as `start`/`end` — see §4 — so nothing downstream guesses at it.
- **Registry** (`registry.py`) — an ordered list from the config. Each is a **local registry
  repository** (`cttp.toml` + `names/<name>.toml`, each entry mapping a name to a
  `host/owner/repo/path` target and version labels to refs) or an **HTTP registry** serving
  `GET /<name>[@<version>][%23<symbol>].json` — a symbol rides the same route, percent-encoded.
  First that knows the name answers; a miss falls through. **Names** (spec §8): `declaration_at`
  reads a target's `cttp.toml` at the head of its default branch (`name = "x"`, `names = […]`);
  `check_entry` runs the registry's checks (declaration, owner, target, labels, resolves);
  `claim` writes `names/<name>.toml` — into the first local registry's working tree
  (`--no-pr`), or onto a `claim/<name>` branch made in a temporary worktree, pushed to `origin`
  and opened as a PR with `gh` — and `verify` is what the registry's CI runs. The owner is
  `host/owner` of the target, derived.
- **Git cache** (`gitcache.py`) — bare clones under `$CTTP_HOME/repos/<host>/<owner>/<repo>`,
  fetched from wherever `[remotes]` in the config points, else `https://<locator>.git`. Plain
  `git`: `rev-parse` for tags and branches, `cat-file` for blobs, `ls-tree` for a rev, the bare
  clone's HEAD for the default branch. The license is the SPDX id of the `LICENSE*`/`COPYING*`
  file at the rev, matched by phrase (nine ids; anything else is `None`).
- **Object cache** (`objects.py`) — every page `resolve` returns is stored by identity under
  `$CTTP_HOME/objects/<sha256>` with a JSON sidecar of its metadata and every location it was
  seen at. An identity address is answered from here first, then from the index
  (`index_lookup` → `queries.lookup_identity`, `via: index`).
- **Extractor** (`extract/`) — `extract(path, source, symbol, files)` turns a file at a rev,
  or one definition of it, into a `Page`: kind, language, **its own text** (§4), span, and for a
  definition its symbol, signature, first docstring paragraph, **derived references** (`Ref`s
  to files and definitions in the same repository, resolved against the rev's file list, each
  with the `name` the page reaches it by), the stdlib / third-party modules it needs and the
  **import statements** that bind them, its **free names** (`unresolved`), and the **link
  lines** found in its text (`links`, asserted). The Python extractor is exact, via `ast`.
  **`python.Forwarder`** follows a derived reference through re-exports to the definition it
  means (`from click import echo` → `utils.py#echo`, not `__init__.py#echo`); it needs the
  other files' text, so `extract.forwarded(page, files, read)` is a separate step the crawl and
  the resolver take after extraction (§4). **`treesitter.py`** is every other language's read side: `queries/<language>.scm` names the
  definition node types (`@definition.<kind>`) and the name node (`@name`); the extractor keeps
  file-scope definitions, descends declarator chains for a function's or variable's name, and
  gives a page its kind (`function`, `constant`, `type`, `macro`), span, own text, signature (the
  declaration up to the body), the comment above it as docstring, and its link lines — **no
  refs, no imports, no free names**. C is the one grammar today (`GRAMMARS`; `.c` and `.h`). A
  file with no extractor is a `text` script page with no shape and no references.
- **Resolver** (`resolve.py`) — address → `Resolved`: pinned address (symbol kept), full rev,
  identity, shape, kind, symbol, signature, docstring, span, source, description, license,
  target, refs (as pinned locator addresses at the same rev, `origin: derived`), imports, and
  which registry answered. Against a local registry it does the
  git and extraction work itself; against an HTTP registry it takes the server's object as is.
  **The server resolves, the client asks** — that is the contract. A name whose entry names a
  whole repository takes a `#symbol` and searches the rev for it; several hits stop with the
  candidates. `resolve(…, expect=id)` raises `Mismatch` with both hashes when the page's identity
  is not the one a link claims. `latest()` follows a pinned address forward — rule 1 same path
  and symbol, rule 2 same identity anywhere at head, and a plain "rule 3 needs the index".
  `Resolved` also carries the page's `links`, `unresolved` names, `refs[].name` and
  `imports.statements`; `from_json` defaults the fields newer than the first contract.
- **Closure** (`closure.py`) — `closure(address)` → `Closure`: the pages a page needs to run
  inline, dependencies before dependents, root last. A depth-first walk through the page's
  inner `is` links (asserted; a stamped one is checked against its `id=`) and its derived refs,
  each resolved in its own repository at the pinned rev. It **refuses** — `ClosureError`, naming
  the page and the cause — anything it cannot inline honestly: a reference reached through a
  module or an alias (inlining binds a definition only by its own name), a module used as a
  whole, a free name nothing in the closure binds, a link nested inside a definition, two pages
  binding one name, and a closure over budget (50 definitions / 2,000 lines) with the
  `--package` suggestion. It also decides each stamp's description: the entry's (asserted) or
  one derived from signature and docstring (`~"…"`).
- **Materializer** (`expand.py`) — `expand` writes a link's closure: the import statements the
  pages need (once per file) and each dependency beneath its own stamp go **above the link's
  stack**; the root's stamp keeps the person's fields and description; the root's own text goes
  beneath, then a blank line so the block is delimited. `add` writes the link and expands.
  `check` (`is` links: stamped? block hashes to its id? origin page hashes to it too — else
  `mismatch`? `from` and `see` links: resolvable only; `--fix` turns a drifted `is` into `from`).
  `update` plans first — `--latest` or `--to <rev>`, a unified diff — and rewrites stamp, block
  and missing dependencies on confirmation; a `from` link is only shown its upstream diff.
  `fold` is a view: stamped blocks collapsed to their link lines. `run` materializes into a run
  cache after confirming the whole closure. `--package` writes the closure into
  `cttp_vendor/<module>.py`, stamps the user's link with `vendor=<path>` and puts an import
  beneath it; `check` follows `vendor=` into the module.
- **Index** (`index/`) — `schema.py`: one SQLite file (default `~/.local/share/cttp/index.db`,
  `--index`, `CTTP_INDEX`), `ADDED_COLUMNS` + `migrate()` bringing an older file forward by
  `ALTER TABLE` (writers only; a reader uses `has_column` and never takes the write lock), with
  `repos`, `revisions` (each carrying what the crawl `skipped` and the imports it left
  `unmapped`), `definitions` (**identity is the key**),
  `locations` (one row per place an identity was seen), `links` (the target address as written
  and parsed, its identity when the index can tell, relation, origin), `names` (registry
  snapshot), and an FTS5 shadow for search. `crawl.py`: `add` registers a locator or a local
  clone (its `origin` reversed through `[remotes]`, else parsed); `crawl` reads every file of a
  registered repository at one commit through `git` — a Python file is a **file page plus one
  page per definition**, another file a page only if it carries a link — records pages once per
  identity and once per place, asserted links against the page they stand for, derived refs
  against the page that made them — each forwarded through re-exports first, and the crawl
  reports how many were (`forwarded`) — then fills target identities from what the index knows.
  It never fetches a repository it was not given — a **sparse checkout is crawled as the files
  it has on disk**, since a blobless clone would fetch every other blob. `queries.py`: `target_of` (any address → the
  identities and place the index knows, resolving for real only when it must), `who`, `dups`,
  `closure`, `search`, `history`, `rank`, `forward` (rule 3), `lookup_identity`, `page_json`, and
  `coverage` — what a `who` answer is an answer over (§4), collapsed to its `summary` line
  when the answer is complete.
- **Server** (`server/app.py`) — FastAPI on **3120**, Jinja2 templates. Serves the contract
  (`/<name>.json`, `/<name>@<version>.json`, `%23<symbol>`) over the configured **local**
  registries only, and the viewer of spec §9 over the index: `/` (names, index status, `?q=`
  search), `/<name>` (with history and *who links here*), `/d/<identity>`,
  `/r/<host>/<owner>/<repo>`, `/dups[?shape=1]`. `base.html` fixes the derived/asserted layout
  once — two labelled columns, stacking on a narrow screen — and every page says when there is
  no index. Those three route prefixes are declared before `/{slug}`. **`server/export.py`**
  renders every contract route for every name through the same app and writes the bytes
  (`cttp serve --export <dir>`), so a static host — GitHub Pages behind `cttp.ai` — is a
  registry by construction; symbol routes are not exported.
- **CLI** (`cli.py`) — Typer. `cttp --version | config | resolve [--id] [--latest] | closure
  [--indexed] | serve | expand [--package] [--write-deps] | add [--at] | check [--fix] | update
  [--all] [--to] [--yes] | fold [--open] | run [--yes] | cache status | cache clear | index
  add|crawl|status | who [--coverage] | dups [--shape] | search | history | rank | mcp [install] | name
  show|claim|verify | serve --export`. Every
  subcommand takes `--json`, before or after the subcommand name; every index reader takes
  `--index`. `emit()` prints every object through `schemas.stamp()`, so `schema_version` comes
  first; `fail()` prints the `error` object. Prompts (`run`, `update`) go through
  `_interactive()`, which tests patch; without a terminal they decline and exit 2.
- **Schemas** (`schemas.py`) — the one definition of every command's JSON output, in a small
  schema language (`obj`, `arr`, `mapping`, `string`, `integer`, `number`, `boolean`, `enum`,
  `ref`; `.null()`, `.derived()`, `.asserted()`): shared objects in `DEFS` (`page`, `node`,
  `backlink`, the three report kinds, …) and `COMMANDS` mapping each command to its usage, a
  summary, *when* an agent reaches for it, notes, and its schema (`None` for `run`, which prints
  the program's output). `validate()` is strict — a missing field, an extra field, a wrong type
  or an unknown enum value is an error. `json_schema()` renders JSON Schema (draft 2020-12; the
  MCP tools' `outputSchema`), `markdown()` renders `docs/json-schemas.md`, `fingerprint()`
  digests every schema and `FINGERPRINTS[SCHEMA_VERSION]` pins it. `python -m cttp.schemas`
  rewrites the doc.
- **MCP** (`mcp.py`) — `build_server()`: an `MCPServer` (the `mcp` SDK, 2.x) with six tools,
  each a thin function calling what the CLI calls and returning a `CallToolResult` whose
  `structuredContent` is the stamped object and whose text is the same JSON; every tool is
  annotated read-only and idempotent, `resolve` and `closure` open-world (they may clone).
  Tools are built with `Tool.from_function(…, structured_output=False)` and their
  `fn_metadata.output_schema` set to the P5-T1 JSON Schema by hand. A failure is a `ToolError`
  carrying the CLI's message. `install_command()` is the `claude mcp add` line.

Data an address needs lives in three places on disk, all of them derivable:

| Location | What | Env override |
|---|---|---|
| `~/.config/cttp/config.toml` | `registries` (ordered: `https://cttp.ai`, `http://localhost:3120`, the clone) and `[remotes]`; **written with defaults on first run**, never rewritten | `CTTP_CONFIG` (path), `CTTP_REGISTRY` (replace the list with one entry) |
| `~/.local/share/cttp/registry` | a clone of the public registry repo; the second default registry | (an entry in the config) |
| `~/.cache/cttp/` | `repos/<locator>` bare clones; `objects/<sha256>` + `.json` the object cache; `run/<pinned address>/main.py` and `run/file-<hash>/` run caches | `CTTP_HOME` |
| `~/.local/share/cttp/index.db` | the index: what was crawled, by identity | `CTTP_INDEX` (path), `--index`, `XDG_DATA_HOME` |

## 3. Repo map

| Path | What | Status |
|---|---|---|
| `src/cttp/` | the package; see §2 | authored |
| `src/cttp/extract/` | `__init__.py` (`Page`, `Ref`, `extract()` dispatch by suffix), `python.py` (the `ast` extractor), `treesitter.py` + `queries/c.scm` (the C extractor; add a grammar wheel and a query file per further language) | authored |
| `src/cttp/index/` | `schema.py` (tables, `open_index`), `crawl.py` (`add`, `crawl`, `status`), `queries.py` (the six queries, `forward`, `lookup_identity`) | authored |
| `src/cttp/schemas.py`, `src/cttp/mcp.py` | the agent interface: the `--json` schemas and the MCP server; see §2 | authored |
| `src/cttp/server/export.py` | the static export of the contract (`cttp serve --export`), what `cttp-registry`'s `pages.yml` publishes to `cttp.ai` | authored |
| `src/cttp/server/templates/` | `base.html` (the one layout and stylesheet), `_macros.html` (tags, backlinks, locations, history), `index.html`, `name.html`, `definition.html`, `repo.html`, `dups.html` | authored |
| `tests/` | pytest, one file per concern (`test_address`, `_hashing`, `_extract_python`, `_extract_c`, `_config`, `_links`, `_gitcache`, `_resolve`, `_objects`, `_latest`, `_closure`, `_expand`, `_check`, `_update`, `_fold`, `_run`, `_package`, `_server`, `_cli`, `_index_crawl`, `_index_queries`, `_acceptance_move`, `_acceptance_provenance`, `_acceptance_drivers` (`slow`), `_schemas`, `_mcp`, `_name`, `_registry_federation`, `_export`, `_bench_agent`); `conftest.py` builds the offline world, forbids sockets (and non-`file` git protocols), and points `CTTP_INDEX` at `tmp_path` | authored |
| `tests/fixtures/registry/` | the registry repository's contents — **identical to the public repo's `main`** (minus its `.github/` and README); keep them in sync | authored |
| `tests/fixtures/hello/hello.py` | one line, `# cttp: hello-world` | authored |
| `tests/fixtures/thermo/` | a fake sensor package (`src/thermo/{__init__,decode,lm75}.py`) with every definition kind the extractor must handle; served in tests as `github.com/leorinaldi/thermo` | authored |
| `tests/fixtures/pyrepo/` | the closure fixture: `lib.py` (siblings in a chain, a `requests` import, a stdlib import, a missing name, mutual recursion) and `many.py` (51 tiny definitions, over budget); served as `github.com/leorinaldi/pyrepo` | authored |
| `tests/fixtures/crepo/` | the C fixture: every definition kind, a construct the grammar does not know, links in both comment syntaxes, one decoder verbatim in two files and under other names in a third; served as `github.com/leorinaldi/crepo` | authored |
| `docs/` | vision, spec, plan, this file; `json-schemas.md` is **generated** (`python -m cttp.schemas`); excluded from ruff | authored |
| `scripts/make_local_registry.py` | builds an offline registry repo from the fixture | authored |
| `bench/drivers/` | `fetch.sh` (the corpus: a sparse, blobless clone of `torvalds/linux` at **v7.3-rc1**, five directories' own files, 736 `.c`), `expected.json` (provenance, the duplicate groups of acceptance test 1, the measurement's numbers), `measure.py` (the line-level measurement), `README.md` | authored |
| `bench/agent/` | the agent benchmark (plan P8): `harness.py` (Claude Code headless, the two arms, records, `--replay`), `graders.py` (tasks from `tasks/<name>/task.toml`: a source repository at a commit, `[[deps]]`, `setup`/`grade`/`solution` overlays as directories or as paths from a commit; the per-run checkout with its dependency clones, config, index and grade — the test command, the link check, the who check), `report.py` (the table), `tasks/` (the fifteen P8-T2 tasks and the smoke task), `fetch.sh` (clones the three task repositories), `results/<date>/<task>/<arm>/<run>.json` + `.stream.jsonl` (committed), `README.md` (all of it) | authored |
| `bench/agent/repos/` | full clones of `pallets/click`, `python-attrs/attrs`, `Textualize/rich` made by `fetch.sh`; every task pins a commit in them — never committed | gitignored |
| `bench/drivers/corpus/`, `bench/drivers/corpus-preserved/`, `bench/drivers/lm75-teardown/` | the clone `fetch.sh` makes; the original raw-file copy it reproduces byte for byte; the LM75 teardown — never committed | gitignored |
| `.local/` | local scratch, e.g. `serve.log` | gitignored |
| `.venv/`, `uv.lock` | uv-managed environment; the lockfile is committed | `.venv` gitignored |
| `pyproject.toml` | hatchling build, `cttp` entry point, ruff and pytest config | authored |

Outside the repo: the public registry `github.com/leorinaldi/cttp-registry`, whose `README.md`
links to spec §8 here, and whose `.github/workflows/` hold `verify.yml` (runs
`cttp name verify --registry .` on every PR touching `names/`) and `pages.yml` (publishes
`cttp serve --export` to GitHub Pages as `cttp.ai` on every push to `main`). Both `pip install`
cttp straight from this repository, which is **public** — a fork's PR gets no secrets, so a
token would have broken claims by anyone but Leo.

## 4. The data model — load-bearing decisions

- **The pinned form is the tool's, the short form is the person's.** A person writes
  `# cttp: hello-world`. Expansion rewrites the line as
  `# cttp: hello-world@<12-hex rev> id=sha256:<12-hex identity>  "description"`. Stamps carry
  12-hex prefixes; the JSON objects carry full SHAs (`rev`, `identity_full`).
- **Identity hashes the definition's own source, nothing it references.** So an address is
  computable from one file offline, and `check` needs no network to detect drift. The shape is
  derived metadata beside it, never part of an address.
- **A page's `source` is its own text.** A link line inside a page is a reference, not code —
  and a link line always ends a block — so the extractor takes every link line out of a script
  page's text, and beneath a stamped `is` link the block and its separator too, and reports them
  as the page's asserted `links`. What remains is what the identity hashes and what `expand`
  writes beneath the stamp; that is why the spec §7 example (`# cttp: greet` above
  `print(greet("world"))`) expands to two blocks that both check clean. A definition's text is
  its span, verbatim; a definition with a link inside it cannot be expanded and the closure says
  so. Pages without links are untouched, so no identity moved.
- **Inline expansion binds a definition only by its own name.** A page may reach a dependency
  as `REG_BITS`, as a from-import of `reg_to_millicelsius`, or as `LM75.read_temp` through its
  class (the closure lifts the reference to `LM75`); reaching it as `decode.STEP_MILLICELSIUS`
  or through `as r2m` cannot be satisfied by inlining, and the closure refuses rather than write
  a file that would not run. `Ref.name` records how each reference is reached so this can be
  decided. Free names are checked the same way: whatever the page uses must be bound by a
  dependency, an import statement, a builtin or the page itself.
- **A definition's outside imports travel as statements.** The extractor keeps the module-level
  `import struct` / `from asyncio import sleep` that bind the names a definition uses;
  expansion hoists them once, above everything it writes. Scripts keep their imports in their
  own text. Third-party packages are reported as `requires` and written into `pyproject.toml`
  only with `--write-deps`.
- **A definition's references are the names it uses; a script's are every import it makes.**
  Reference resolution is static and repository-local: an import or attribute chain becomes a
  `Ref` only when the longest module prefix names a file at that rev; anything else is a
  stdlib or third-party top-level module, decided by `sys.stdlib_module_names`. A parameter
  shadows a module-level import.
- **An absolute import is rooted where Python would root it: at the file's ancestors that are
  not packages, then at the repository's source roots.** Two rules, in `extract/python.py`. A
  src-layout puts its packages under a directory that is on no importing file's path, so `from
  click._compat import strip_ansi` in `tests/` would otherwise reach nothing: `SOURCE_ROOTS` is
  `("src",)`, counts only when the repository has that directory, and is tried **last**, so a
  nearer ancestor keeps winning. And a package's own directory is never on `sys.path`, so an
  ancestor holding an `__init__.py` is **not** a root (`_import_roots`): `from types import
  TracebackType` inside `src/click/` is the stdlib, not `src/click/types.py`. A directory without
  an `__init__.py` stays a root — that is the flat layout and the `tests/` that is not a package.
  Together they are what makes `who` complete on click and attrs.
- **A `#symbol` travels the HTTP contract as `%23` in the existing route.** The contract grew
  no route; spec §8's table lists it, and the resolver's object beneath the table.
- **The block beneath a link is recorded, never guessed.** It begins after the link's *stack*
  (consecutive link lines share one block) and ends at the next link line, at a blank line
  followed by a line indented no deeper than the link, or at EOF. `find_links()` writes it onto
  every `Link` as `start`/`end`; `expand` writes a blank line after the source it inserts so the
  rule holds; `check` and, later, `fold` read it. Indentation is relative to the link, so a
  method expanded inside a class ends where the next method starts.
- **Every resolution feeds the object cache.** Nothing has to be asked for; the cache is a
  by-product of use, keyed by identity, and each entry remembers every location the page was seen
  at. That is how an identity address resolves offline and how a page survives its origin.
- **The identity includes the name.** A renamed definition is a new identity; only its shape
  survives a rename. `--latest` therefore finds edits and moves, not renames.
- **No lockfile.** The document alone says what runs — web subresource-integrity, not pip. A link
  moves only when asked: `cttp update` selects `track=latest` links (or all, under a project
  `cttp.toml` with `track = "latest"`, or named ones, or `--all`), shows the diff, and rewrites
  on confirmation. A `from` link is never rewritten.
- **`vendor=<path>` marks a link expanded with `--package`.** The block beneath it is an import;
  the page's code lives in `cttp_vendor/<module>.py` beneath the same stamped links, and `check`
  follows the field there. The module is written next to the user's file so a plain
  `python main.py` finds it.
- **Derived versus asserted.** `rev`, `identity`, `license` are derived by the tool from the
  repository; `description` is asserted by the entry's author. `to_json()` says which is which
  under `origin`, and the viewer tags them.
- **An answer states its own coverage.** An answer whose completeness cannot be judged is one its
  reader must reproduce by hand — and a reader that reproduces the answer has not been helped.
  `who` therefore returns a `coverage` object beside the backlinks: the revisions searched and the
  directories each reached; the files the crawl could not read (`skipped`) and which of those a
  language extractor would have read (`unread`); the link lines it had to ignore
  (`ignored_links`); the recorded links whose target the index cannot identify
  (`unresolved_targets`) and how many of those name **this** address (`unresolved_matching`); the
  imports that point into a repository and were never mapped to a file (`unmapped_imports`); and
  the `caveats` no count expresses. `complete` is true when this answer has none of those gaps and
  `null` — never a cheerful zero — when the index predates the record. It is a claim about the
  files that were read and nothing more; a repository never crawled is answered by `searched`. The
  CLI prints one line of it, the viewer a note under *who links here*, and neither shows a count
  without it: a bare `0` is the one number a reader must not take on trust.
- **A complete answer is the line and nothing else.** Evidence for a settled doubt is weight, not
  evidence: a reader told the answer is complete must otherwise decide to ignore the eight fields
  explaining how it could fail to be. So `coverage.summary` (always present) says in one
  line what was searched and whether the count may be trusted, and when `complete` is true the
  fields beneath it are `null`: they are evidence for a doubt the line has settled. An incomplete
  answer, or one that cannot tell, carries the whole object. `cttp who --coverage` (the MCP tool's
  `coverage`, `queries.who(detail=True)`) keeps it either way; the viewer always asks for it, since
  a person reading a page has room. `queries.COLLAPSED` is the list of fields that collapse. The
  justification is the interface, **not** a measured saving — the benchmark could not resolve the
  difference and the family's ratio moved the wrong way on noise; see [`benchmark.md`](benchmark.md).
- **A derived reference names the definition, not the module that re-exports it.** `from click
  import echo` resolves to `src/click/__init__.py#echo`, and that file defines no `echo`: it
  imports the name from `.utils`. Recording the reference where it landed made `who` on a
  package's public API wrong by hundreds (click's `echo`: 31 backlinks, 259 unidentified links
  naming it) and, worse, *quietly* wrong where the public name differs from the definition's
  (`attr.s` is `_make.py#attrs`; coverage matched by leaf name, so it counted 3 misses and
  hid 326). `Forwarder` (§2) follows the reference through what the module binds at its top
  level by importing — an explicit `from … import name [as alias]`, chained through as many
  modules as it takes; a bare-name alias of such a binding that is not itself a definition
  (`s = attributes = attrs`); the first `from … import *` whose module defines the name,
  honouring a literal `__all__` and never a private name — and stops at the first file that
  defines the head of the symbol, keeping any member path (`Context.invoke` follows `Context`).
  A name bound any other way (`__getattr__`, a call) is not followed and not guessed: the
  reference stays on the module, unidentified, and coverage says so. The rule runs in the crawl
  and in the resolver, so the live closure inlines the definition and `closure --indexed` agrees
  with it. Over fresh indexes of the benchmark's repositories: click forwards 1,372 references and
  its unidentified links fall 1,422 → 50; attrs 1,549 and 1,582 → 38; rich, a flat layout, 15.
  The package rule above then took click 50 → **31**, rich 100 → **46** and cttp itself 38 → **15**,
  purely by subtraction: every row it removed was a file reaching *itself* under a stdlib name.
- **`unresolved_matching` is what makes the total bearable.** What the two rules leave
  unidentified is small but real — a member no definition has, a lazily bound name, a package
  whose `__init__` binds by other means. The total is alarming and almost always irrelevant; the
  count of them that name the address asked about is the one that decides whether this answer may
  be trusted.
- **What the crawl could not do is recorded by the crawl, per revision.** `revisions.skipped` and
  `revisions.unmapped` are written at crawl time. They cannot be derived afterwards from
  `definitions`, which has one row per identity written by `INSERT OR IGNORE`: that row keeps the
  **first** crawl's `imports`, so after an extractor change it reports a classification that is no
  longer true. An earlier version of `coverage` read it and claimed a gap the source-root rule had
  already closed. Per-place facts belong on the revision, not on the identity.
- **In the index, identity is the key and a place is a row.** `definitions` has one row per
  identity; `locations` one per (repo, sha, path, symbol). "Two copies of one thing are one
  thing" is therefore a join, not a heuristic — `dups` is `GROUP BY identity`.
- **C definitions are addressed by name, tagged types by `struct.<tag>` / `enum.<tag>` /
  `union.<tag>`, typedefs and macros by name.** C's tags live in their own namespace, so a
  struct and a function may share a name; the dotted form keeps them apart within the symbol
  grammar. Kinds `type` and `macro` exist for them. Two definitions of one symbol in a file
  (the arms of an `#ifdef`) keep the first.
- **A C page has no derived references.** Only the Python extractor resolves names; a C page's
  `refs`, `imports` and `unresolved` are empty, so its graph is its asserted links alone. The
  write side stays Python's (spec §3); a `//` link in a `.c` file expanding a C *script* page
  is fine and tested, and a C definition is never refused by the closure — nothing asks it to.
- **A file with an extractor is a page beside its definitions.** The crawl records the whole-file page
  (what a locator without `#symbol` resolves to) and one page per definition. A file whose
  entire text is one definition shares that definition's identity; the definition's view (kind,
  name, signature) wins the `definitions` row, and `dups` never pairs a file with its own only
  definition.
- **An asserted link's source is the page it stands for.** In the index a `# cttp:` line at
  module level belongs to the definition in the block beneath it (spec §4), else to the
  innermost definition holding the line, else to the file. So a verbatim copy links back to its
  original *as itself* — same identity, another place — and `who`, `rank` and `--latest` rule 3
  all read provenance the same way.
- **The crawl never fetches what it was not given.** Target identities are filled in after the
  crawl from what the index knows — a stamp's `id=`, a pinned locator seen at that rev, a name
  whose snapshot points at a crawled file — and stay NULL otherwise. `who` matches by identity,
  and by place or name only for links whose identity the index could not tell.
- **"Current" is the most recently crawled revision of each repository.** `dups`, `rank`,
  `search` and the viewer's repository page report over it; `history` and `who` see every
  crawled revision, ordered by commit time, then crawl order (`rowid`) for ties. A `--rev` crawl
  makes that rev current, on purpose.
- **A name is claimed by proof of control, not an account.** The target repository's
  `cttp.toml` at the head of its default branch declares the name (`name = "x"`, or
  `names = […]` for a repository that is the target of several); the entry's `owner` is
  `host/owner` of the target's locator, derived by `claim` and checked by `verify`, never typed.
  The claim is a pull request; the registry's CI runs the same checks before merging.
- **Registry entries name a target, not code.** `names/<name>.toml` holds `target =
  host/owner/repo/path`, a `default` label and `[versions]` mapping labels to refs. Version
  labels are names for refs; git revisions are the versions. There is no second versioning scheme.
- **Every locator goes through `[remotes]` or https.** No special case lets a registry serve
  itself from its own path. The tests reach a bare repo in `tmp_path` through `[remotes]` exactly
  as a mirror would.
- **Every `--json` object is one schema, stamped.** `schemas.py` is the single definition;
  the CLI's `emit()` and the server's contract route both print through `stamp()`, so
  `schema_version` is the first key of every object, including the registry contract's
  (`from_json` ignores it). Every field is present, `null` when not available; nothing beyond
  the schema is printed. A schema change fails `test_schemas.py` until `SCHEMA_VERSION` is
  bumped and the new fingerprint recorded — a deliberate act, noted in `PROGRESS.md`.
- **`closure` is one object, live or indexed.** `source` says `repository` (the live walk: what
  `expand` would write; refuses what it cannot inline) or `index` (`--indexed`, or several
  addresses: the recorded links, `missing` for what the index cannot tell); `roots` lists the
  addresses asked about. The MCP `closure` tool has the same two modes (`indexed`).
- **The MCP tools answer exactly what the CLI prints.** Same functions, same objects, same
  `schema_version`; `test_mcp.py` asserts equality with `cttp … --json` per tool. A tool's
  `outputSchema` is the command's JSON Schema. `--latest`, `expand`, `add`, `check`, `update`,
  `run` and the index commands are CLI-only: they write, ask, or run.
- **The run cache is the confirmation record.** The first run of a pinned address shows source,
  identity, license and registry, and asks. `run/<pinned address>/main.py` is created only after a
  yes; its existence is what makes later runs silent.

## 5. Vocabulary

- **address** — what a link points at. Three forms in spec §2: **name** (`hello-world`,
  `leo.thermo@stable#LM75.read_temp`), **locator** (`host/owner/repo@rev/path#symbol`),
  **identity** (`sha256:<hex>`, full or a prefix of 12+). All three resolve.
- **pinned** — an address whose rev is a commit SHA and which carries an `id=`.
- **stamp** — the pinned address plus identity that expansion writes onto the link line.
- **link** — a whole-line comment carrying one of three markers: `# cttp:` (*is* — the code
  beneath is that page), `# cttp-from:` (*from* — derived from it, never hashed), `# cttp-see:`
  (*see* — a reference, no code claimed). The **relation** is `is`, `from` or `see`.
- **stack** — consecutive link lines above one statement. They share one block.
- **page** — what an address resolves to: a definition (`function`, `class`, `constant`, and
  for C `type`, `macro`) or a script, with its normalized source. A definition's source is its
  span, dedented.
- **symbol** — the dotted name of a definition within a file: `reg_to_millicelsius`,
  `LM75.read_temp`; in C `lm75_reg_to_mc`, `struct.lm75_data`, `LM75_REG_TEMP`. Module-level
  defs, classes, constants and class members are addressable; nested defs are not, and the
  error says which definition they are nested in. C: file-scope definitions only.
- **shape** — the identity's structural twin: same hash over the placeholder text. Equal shapes
  with different identities mean a near-duplicate.
- **ref** — a derived reference from a page to another file or definition in its repository,
  emitted as a link with `relation: ref`, `origin: derived`.
- **block** — the lines beneath a link's stack that the link stands for; `check` hashes it for
  an `is` link. Recorded on the parsed link as `start`/`end` (§4).
- **entry** — a registry's record for a name: target, description, owner, default, versions.
- **locator** — `host/owner/repo`, no scheme. `split_target` splits an entry's target into
  locator and path.
- **registry contract** — the HTTP shape of spec §8: `GET /<name>[@<version>].json` returns the
  resolver's object.
- **miss** — a registry that does not know a name, is unreachable, or is a configured path with
  nothing at it (`MissingRegistry`). A miss asks the next registry; the final error names them all.
- **drift** — a stamped link whose block no longer hashes to its `id=`.
- **mismatch** — a stamped link whose block hashes to its `id=` but whose origin page, resolved
  again, does not: the stamp is wrong, not the copy. `check` reports it; `resolve --id` exits 1.
- **location** — one place a page was seen: a pinned locator address plus name, registry,
  description, license and when. The object cache keeps every location per identity.
- **rule** — which of spec §5's `--latest` rules found a definition at head: `same-path`,
  `same-identity`, or none (rule 3 needs the index); `to` when `update --to <rev>` chose the
  rev. Derived metadata.
- **closure** — the pages a page needs to run inline, in dependency order, root last; each is a
  **node** with the page, its stamp description, `via` (`root` / `link` / `ref`), `needs` and
  `defines`. `cttp closure` prints it; `expand` writes it.
- **own text** — a page's source with its link lines (and stamped `is` blocks) taken out; what
  the identity hashes. **inner link** — a link line found in a page's text: an `is` one is a
  dependency, a `from`/`see` one is hoisted into the stack when the page is expanded.
- **free name** — a name a page uses that nothing in it binds: not local, not imported, not a
  sibling definition, not a builtin. Reported as `unresolved`; the closure must bind each one.
- **vendored** — expanded with `--package`: the closure in `cttp_vendor/<module>.py`, an import
  beneath the link, `vendor=` on the stamp.
- **fixed** — a drifted `is` link that `check --fix` turned into a `from` link.
- **upstream** — `update`'s answer for a `from` link: the diff between the pinned page and its
  head, shown and not applied.
- **derived / asserted** — computed by the tool from the repository versus stated by a person.
- **index** — the SQLite file of everything crawled: `repos`, `revisions`, `definitions`,
  `locations`, `links`, `names`. **crawl** — reading one repository at one commit into it.
  **current** — a repository's most recently crawled revision. **place** — (repo, path,
  symbol), what `history` follows. **backlink** — a link whose target is the address asked
  about; `who` lists them by relation and origin.

## 6. Invariants — never violate

- **No runtime component.** Nothing cttp emits is imported, decorated or called at run time.
  Expanded files run under `/usr/bin/python3 -I` with cttp absent. `test_no_runtime_component`
  guards this.
- **The server never asks an HTTP registry.** It opens registries `local_only=True`; a config that
  lists `http://localhost:3120` first would otherwise make the server query itself.
- **Tests never touch the network — and cannot.** `conftest.py` puts a registry repo, a bare
  "remote" and a config in `tmp_path`, points `CTTP_CONFIG` and `CTTP_HOME` there, and maps the
  `github.com/leorinaldi/` prefix at the bare repo through `[remotes]`. An autouse fixture
  patches `socket.socket.connect` to raise; only a test marked `network` (there is one, against
  a closed local port) escapes it. The server tests drive the FastAPI app in-process through the
  test client, whose event loop makes a socketpair — no connect, so it passes the guard. **The
  socket guard covers Python only**: a `git` subprocess can still reach the network, so the
  fixture also sets `GIT_ALLOW_PROTOCOL=file` — a fetch of `https://…` fails at once.
- **Never invent a value.** A missing license is `None` and prints `not available`; a missing
  description stays absent. Nothing is coerced to a plausible default.
- **Rows come from byte offsets, never from a tree-sitter `Point`.** py-tree-sitter 0.26.0
  returns `Point`s from freed memory for nodes that came out of query captures (garbage spans,
  then a segfault); the dependency is pinned `<0.26` *and* `treesitter.Rows` maps
  `start_byte`/`end_byte` to lines. Keep both.
- **The corpus tests are `slow` and deselected by default** (`addopts = "-m 'not slow'"`);
  `uv run pytest -m slow` runs them, skipped when `bench/drivers/corpus/.git` is absent. They
  run git against a blobless clone with `GIT_ALLOW_PROTOCOL=none`, so a lazy blob fetch fails
  loudly instead of reaching GitHub.
- **Stamps carry commit SHAs only.** Tags and branches are for humans; they never appear in a
  stamp the tool writes.
- **`tests/fixtures/registry/` mirrors the public registry repo's `main`.** A change to one is a
  change to both, in the same session.
- **Tests never touch the real index.** `config_file` sets `CTTP_INDEX` to `tmp_path`; a test
  that needs an index opens one there. `open_index(create=False)` is what queries use, so a
  query never creates an empty index as a side effect.
- **A `who` count is never shown without its coverage.** The CLI, the MCP tool and the viewer all
  carry it; `complete` is `null` when it cannot be told, never `true` by default. Weakening this
  puts back the thrash the benchmark measured. What collapses on a complete answer is the
  *evidence*, never `coverage.summary` — that line is the coverage, and it is always printed.
- **`docs/json-schemas.md` is never edited by hand.** `test_schemas.py` diffs it against
  `markdown()`; regenerate with `python -m cttp.schemas`.
- **The identity of `print("hello world!")` is `75a27070015e…`**, pinned in `test_address.py`.
  If it changes, the normalization changed, and every stamp in the world would drift.

## 7. Do **not** "fix" these

- **`--json` is accepted in two positions** (`cttp --json resolve x` and `cttp resolve x --json`).
  Both are deliberate: the first is the plan's agent-facing form, the second the natural one.
- **A fetch is skipped when the wanted rev is a SHA already in the cache.** Pinned addresses never
  move, so `check` on an expanded file is offline once the repo is cached. Labels always fetch.
- **`HttpRegistry.lookup()` raises and `names()` returns empty.** The contract has no entry or
  listing route; an HTTP registry only answers `fetch()`. `Registries.lookup()` skips HTTP
  registries on purpose.
- **A declined `run` leaves nothing in the run cache.** The cache entry is the confirmation marker.
- **The closure refuses rather than guesses.** A reference through a module or an alias, a
  whole-module use, a free name nothing binds, a link inside a definition, a name clash, an
  over-budget closure — each stops `expand` with a message saying what to do. Writing a file
  that would not run is the bug; the refusal is the feature.
- **Two `is` links in one stack are refused.** They would share one block, which can hold one
  page. Separate them with a blank line.
- **A dependency already stamped above in the file is not written again.** Expanding a second
  link that needs `deep` when `deep` is already expanded above reuses it (by identity).
- **`update` never rewrites a `from` link, and skips drifted and unexpanded ones.** It shows the
  upstream diff, or says `check --fix` / `expand` first.
- **`fold` folds `from` blocks too.** Any stamped block collapses; `--open` shows one.
- **An empty `description = ""` in a registry entry is no description.** A derived `~"…"` one is
  written instead; the stamp never carries `""`.
- **A script page without a signature gets no derived description.** `# cttp: hello-world@… id=…`
  with nothing after it is complete — that is what spec §7's example shows.
- **A non-Python file resolves with `shape: null` and `language: "text"`.** Not an error: only
  Python has an extractor today. Asking for a `#symbol` in such a file is the error.
- **LGPL, AGPL and Unlicense files give `license: null`.** The matcher knows nine ids (the
  plan's list) and refuses to guess; "not available" is the honest answer for the rest.
- **`cttp cache clear` leaves the run cache.** It is the record of what the user confirmed to
  run; `--run` removes it deliberately.
- **`--latest` does not find a rename.** The identity changed with the name (§4). The test in
  `test_latest.py` says so on purpose.
- **A `from` or `see` link with an unresolvable address is `unresolvable`, not ignored.** Spec
  §7: every link resolves. `see` links to things that are not cttp addresses are not supported.
- **The docstring is the first paragraph, joined into one line.** Not the first physical line —
  a summary that wraps would be cut mid-sentence.
- **The first run of `cttp` writes `~/.config/cttp/config.toml`.** That is the designed first-run
  experience, not a side effect to suppress.
- **`run <file>` runs a copy, never the file.** The user's file is untouched; only `expand` writes
  in place.
- **`docs/` is excluded from ruff.** `ruff format` reformats code blocks inside Markdown.
- **A malformed link line costs the line, not the file.** The crawl turns prose that looks like
  a link (`# cttp: <address> [key=value]` in a docstring) into a bare comment and notes it under
  `skipped`; the file's definitions are still indexed. `resolve` on such a file still raises —
  that is the link grammar being strict where it should be.
- **`cttp index crawl` skips a revision it has crawled; `--force` is the way to redo one.** The
  skip is what makes crawling idempotent.
- **`closure --indexed` lists what it cannot tell under `missing` instead of refusing.** It is
  context for an agent, not a materialization; the live `closure` still refuses.
- **`schemas.py` carries `# ruff: noqa: E501`.** Each field's meaning is one string beside its
  type; wrapping them would make the definitions unreadable. Nowhere else.
- **`dups` groups carry `key` / `key_full`, not `identity` / `shape`.** One schema for both
  modes; `by` says which the key is, and `identities` lists the group's identities either way.
- **The MCP tools set `output_schema` by hand and return `CallToolResult` themselves.** The SDK
  would otherwise synthesize a schema from the return annotation (wrapping a `dict` in
  `{"result": …}`); building the result keeps the object byte-identical to the CLI's.
- **`open_index(create=False)` does not run the schema script.** `CREATE TABLE IF NOT EXISTS`
  takes SQLite's write lock, and a corpus crawl holds it for minutes; a reader that ran the
  script answered `database is locked` (the viewer's 500). Readers open with a 5 s busy timeout
  and touch nothing.
- **A sparse clone is crawled as the files it has, and a detached HEAD is named by its tag.**
  `fetch.sh`'s corpus is both; the crawl of a blobless clone would otherwise fetch the whole
  kernel one blob at a time, and `index status` would say `[HEAD]`.
- **`name claim` commits in a worktree, not in the registry clone's checkout.** An uncommitted
  `names/<name>.toml` in the working tree would collide with the merged PR on the next pull; the
  worktree and the local `claim/<name>` branch are removed afterwards. `--no-pr` writes into the
  working tree on purpose — `LocalRegistry` reads it, so the name works at once.
- **`serve --export` renders through the ASGI app, not the templates directly.** "Identical to
  the live responses" is then true by construction. Symbol routes are not exported: unbounded.
- **`rank` counts a copy that links back to its original.** Distinct linking *pages* are
  (identity, repo, file), so the same identity elsewhere counts; only a derived self-reference
  (recursion) is excluded.

## 8. Operational gotchas

- **The git cache can be poisoned.** `~/.cache/cttp/repos/<locator>` is keyed by locator, not by
  where it was cloned from. A repo built locally and cached under a real locator keeps answering
  for that locator after the real registry changes. A pinned address that "still resolves" after
  the registry moved is this. Cure: `rm -rf ~/.cache/cttp`.
- **`uv --directory` changes the working directory.** To run cttp against files elsewhere use
  `uv run --project ~/Claude/cttp cttp …` from that directory.
- **`pkill -f 'cttp serve'` matches its own shell, and so does `kill $(pgrep -f …)` inside one
  command.** Run `pgrep -af 'cttp serve'` first, read the pids, and kill them in a separate
  command — otherwise the shell dies (exit 144) and the server survives.
- **Port 3120 is usually already up.** Leo leaves the server running between sessions. Probe
  before starting; a second `cttp serve` fails to bind.
- **Code appended right after an expanded block without a blank line becomes part of the
  block.** `echo 'print(top(3))' >> main.py` after `cttp add` makes `check` report drift on
  `top` — correctly, by the block rule. Leave a blank line (or use `add --at`).
- **`python3 -I` implies `-P` since 3.11**: the script's directory is not on `sys.path`, so a
  `cttp_vendor` import — like any local package — fails under it. `-E -s` still runs with no
  environment and no user site; `test_package.py` uses that. Plain `python main.py` works.
- **The system `python3` has no cttp**, and the tests rely on that: `/usr/bin/python3 -I` is how
  the no-runtime rule is checked. Do not install cttp system-wide.
- **`uv` is at `~/.local/bin/uv`**, not on the default `PATH`; export it first.
- **The `bench` dependency group is installed by default** (`[tool.uv] default-groups`): the
  task repositories' test-time needs (`hypothesis`, `pygments`, `markdown-it-py`). `click` and
  `attrs` are importable in the venv for other reasons (`typer`, `hypothesis`); the cross-repo
  hidden tests check the agent did not import them.
- **The real index shows the re-export rule only after a `--force` re-crawl.** A derived
  reference is recorded at crawl time; an index crawled before the rule keeps the old rows, and
  `who` over it still answers `complete: false` with the old counts.
- **The closure keeps a function-local relative import.** `click.formatting.wrap_text` does
  `from ._textwrap import TextWrapper` inside its body; `expand` inlines `TextWrapper` and leaves
  the import line, which fails at run time. Pick definitions without local imports until this is
  fixed (a follow-up in `PROGRESS.md`).
- **Confirmation needs a terminal.** `cttp run <address>` with stdin not a tty prints the summary
  and exits 2. Scripts and tests pass `--yes`. To test the prompt by hand, use `script(1)` for a
  pty.
- **Headless screenshots:** `~/.cache/ms-playwright/chromium-*/chrome-linux/chrome --headless=new
  --screenshot=…`. System Firefox's headless screenshot does not work here.
- **The stale `hello.py` in the repo root is Leo's**, untracked, and stamped with a rev that no
  longer exists anywhere. `check` correctly reports it `unresolvable`. Leave it.
- **Headless Chrome needs `--no-sandbox` here** (with `--disable-gpu --disable-dev-shm-usage`);
  without it the process aborts with a core dump before writing the screenshot.
- **The running server serves the code it was started with.** `cttp serve` has no reload; after
  a change under `server/` restart it (`pgrep -af 'cttp serve'`, then `kill <pids>` in a
  separate command) or the browser shows the old pages.
- **The `mcp` SDK is 2.x: `from mcp.server.mcpserver import MCPServer`**, not `FastMCP` (a
  `ModuleNotFoundError` with a migration link if you try); the in-memory client for tests is
  `mcp.client.Client(server)`. Tool functions must not name a parameter `id`-style with a
  leading underscore; `open` needs `# noqa: A002`.
- **Checking the MCP server from Claude Code without touching Leo's config:** `claude -p "…"
  --mcp-config <file.json> --strict-mcp-config --allowedTools mcp__cttp__who --output-format
  stream-json --verbose` from a scratch directory; the `tool_use` blocks in the stream show the
  call. `cttp mcp install --claude-code` is the persistent attach (writes Leo's Claude Code
  config) — offer it, don't run it unasked.
- **A `--force` re-crawl refreshes locations and links but not a definition row.** `INSERT OR
  IGNORE` keeps the identity's existing `imports`, `unresolved`, signature and docstring, so the
  viewer's *third party* line can show a stale classification after an extractor change. The links
  and the backlinks are correct; the definition row's derived metadata is the first crawl's.
- **A `--force` crawl fills `skipped`/`unmapped` for each repository's *head* only**, so any
  older revision the index already held keeps NULLs and `who`'s `coverage.complete` stays `null`
  over that index — correct, since `who` searches every crawled revision. The real index is in
  that state and will stay there: `--rev <older>` would fill it but makes that rev *current* for
  `dups`, `rank`, `search` and the viewer, which is worse. A fresh index (what every benchmark run
  builds) reports `true`.
- **The real index is `~/.local/share/cttp/index.db`.** It holds whatever was crawled by hand —
  including the driver corpus (`github.com/torvalds/linux [v7.3-rc1]`, ~34,000 pages), so
  `dups` and `search` answer at kernel scale; the tests never see it. `cttp index status` says
  what is in it; deleting the file is the reset.
- **`cttp resolve <real locator>` clones the whole repository into `~/.cache/cttp/repos`.** For
  `github.com/torvalds/linux` that is the entire kernel — do not type it; the corpus is reachable
  through the index (`dups`, `who`, `search`, `resolve sha256:…`) and its local clone. If it
  happens: kill it, `rm -rf ~/.cache/cttp/repos/github.com/torvalds`.
- **The corpus clone is blobless.** Anything outside the sparse checkout (`git show HEAD:MAINTAINERS`
  is fine, root files are in; `git show HEAD:kernel/fork.c` is not) fetches from GitHub on demand.
  `GIT_ALLOW_PROTOCOL=none` in the environment turns that into an error.
- **Claude Code's `Edit` and `Write` refuse a file the session has not `Read`.** An agent arm
  without `Read` cannot change a file, whatever else it can see; the benchmark's links arm
  learned this the expensive way. Both arms have `Read`.
- **Claude Code 2.1.261 has no `Grep` or `Glob` tool**; searching is `grep`/`find` through
  `Bash`, and `--permission-mode dontAsk` auto-approves the read-only command set. To keep the
  shell's readers out of an arm, deny them by rule (`--disallowedTools "Bash(cat *)" …`);
  `--tools` restricts the built-in tools and leaves MCP tools alone.
- **A headless run is isolated from `~/.claude` with `--setting-sources ""`,
  `--strict-mcp-config` and `--no-session-persistence`**, not with `--bare`: bare mode reads no
  OAuth credentials and needs an API key. Give it `< /dev/null`, or it waits on stdin.
- **Two MCP calls in one turn can hit the git cache at once.** `gitcache._clone` clones into a
  temporary sibling directory and renames it into place for that reason; keep it that way.

## 9. Running and testing

```bash
export PATH="$HOME/.local/bin:$PATH"
uv sync                                        # once; creates .venv
uv run pytest -q                               # no network
uv run ruff check . && uv run ruff format --check .

git clone https://github.com/leorinaldi/cttp-registry ~/.local/share/cttp/registry   # once
uv run cttp config                             # writes the default config on first run; shows it
uv run cttp serve                              # http://localhost:3120
curl -s localhost:3120/hello-world.json        # the contract; /hello-world is the page
uv run cttp resolve hello-world --json
uv run cttp resolve sha256:75a27070015e   # from the object cache, once resolved by name
uv run cttp cache status                  # what ~/.cache/cttp holds
uv run cttp closure <address>             # what expand would write, dependencies first
uv run cttp add <address> main.py         # link + expansion; then fold / check / update main.py
uv run cttp index add <repo-or-path> && uv run cttp index crawl   # the index; status / --rev / --force
uv run cttp who <address>                 # backlinks; also dups [--shape], search, history, rank
uv run cttp closure --indexed <address>…  # from the index's recorded links, several roots
uv run cttp mcp install                   # the `claude mcp add` line; --claude-code runs it
uv run cttp mcp                           # the MCP server over stdio (what Claude Code launches)
uv run cttp name show <name>              # a registry entry and its resolution
uv run cttp name claim <name> --target host/owner/repo/path [--no-pr]   # proof of control → names/<name>.toml, PR via gh
uv run cttp name verify [<name>…]         # the registry's checks (what cttp-registry's CI runs)
uv run cttp serve --export <dir>          # the contract as static files (what cttp.ai serves)
uv run python -m cttp.schemas             # regenerate docs/json-schemas.md after a schema change

bash bench/drivers/fetch.sh               # the corpus (~60 MB); then index add bench/drivers/corpus && index crawl (~2 min)
uv run pytest -m slow                     # acceptance test 1 and the measurement over the corpus (~2.5 min)
uv run python bench/drivers/measure.py    # the vision's duplicate-line figures, recomputed

bash bench/agent/fetch.sh                  # once: the three task repositories under bench/agent/repos/
uv run python -m bench.agent.harness --list | --check-graders | --task <name> --runs N   # the benchmark, under the Claude Code login
uv run python -m bench.agent.harness --runs 3 --jobs 3 --wait-for-reset   # the full sweep; --jobs runs whole tasks in parallel
uv run python -m bench.agent.harness --replay bench/agent/results/<date>/<task>/<arm>/1.json   # a record from its stream, no login used
gzip -9 bench/agent/results/<date>/*/*/*.stream.jsonl        # committed streams are gzipped; --replay reads either
uv run python -m bench.agent.report bench/agent/results/<date>    # the table
```

Site: **http://localhost:3120** — the viewer and the registry contract, nothing else. The product
runs from the terminal. The acceptance demo (spec §12 test 4) is spelled out under **How to run**
in `PROGRESS.md`.

## 10. Which document answers which question

| Question | Document |
|---|---|
| Why does this exist? | [`vision.md`](vision.md) |
| What does the finished thing look like? What is the grammar, the contract, the index? | [`spec.md`](spec.md) |
| What is the next task, and what counts as done? | [`plan.md`](plan.md) |
| What is built and verified right now? What was decided last session? | [`PROGRESS.md`](../PROGRESS.md) |
| What exactly does `cttp … --json` (or an MCP tool) return? | [`json-schemas.md`](json-schemas.md), generated from `schemas.py` |
| Does any of this actually help an agent? What does the number mean? | [`benchmark.md`](benchmark.md) |
| How do I find my way around, and what will bite me? | this file |
| How should I run a session in this repo? | `CLAUDE.md` |

## 11. Maintaining this document

Update it only when something **foundational** changes — a decision settled or reversed, a new
invariant, a new top-level directory, a changed bring-up command, a new trap worth warning the next
agent about. The test: *would an agent starting fresh next week be wrong without this?* Everything
dated belongs in `PROGRESS.md` instead.
