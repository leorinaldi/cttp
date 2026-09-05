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
and a viewer on port 3120. The index, the viewer over it, the MCP server, other languages and
the benchmark are still ahead — [`plan.md`](plan.md) lays out the phases.

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
  keywords and builtins kept, comments and blank lines dropped, structure tokens kept. Python
  only; `ShapeError` otherwise. `address.py` re-exports both.
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
  First that knows the name answers; a miss falls through.
- **Git cache** (`gitcache.py`) — bare clones under `$CTTP_HOME/repos/<host>/<owner>/<repo>`,
  fetched from wherever `[remotes]` in the config points, else `https://<locator>.git`. Plain
  `git`: `rev-parse` for tags and branches, `cat-file` for blobs, `ls-tree` for a rev, the bare
  clone's HEAD for the default branch. The license is the SPDX id of the `LICENSE*`/`COPYING*`
  file at the rev, matched by phrase (nine ids; anything else is `None`).
- **Object cache** (`objects.py`) — every page `resolve` returns is stored by identity under
  `$CTTP_HOME/objects/<sha256>` with a JSON sidecar of its metadata and every location it was
  seen at. An identity address is answered from here; the index (Phase 4) is the second place
  to ask, and its hook says "not indexed" until it exists.
- **Extractor** (`extract/`) — `extract(path, source, symbol, files)` turns a file at a rev,
  or one definition of it, into a `Page`: kind, language, **its own text** (§4), span, and for a
  definition its symbol, signature, first docstring paragraph, **derived references** (`Ref`s
  to files and definitions in the same repository, resolved against the rev's file list, each
  with the `name` the page reaches it by), the stdlib / third-party modules it needs and the
  **import statements** that bind them, its **free names** (`unresolved`), and the **link
  lines** found in its text (`links`, asserted). The Python extractor is exact, via `ast`; any
  other file is a `text` script page with no shape and no references.
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
- **Server** (`server/app.py`) — FastAPI on **3120**, Jinja2 templates. Serves the contract
  (`/<name>.json`, `/<name>@<version>.json`) and the human pages (`/`, `/<name>`) over the
  configured **local** registries only.
- **CLI** (`cli.py`) — Typer. `cttp --version | config | resolve [--id] [--latest] | closure |
  serve | expand [--package] [--write-deps] | add [--at] | check [--fix] | update [--all] [--to]
  [--yes] | fold [--open] | run [--yes] | cache status | cache clear`. Every subcommand takes
  `--json`, before or after the subcommand name. Prompts (`run`, `update`) go through
  `_interactive()`, which tests patch; without a terminal they decline and exit 2.

Data an address needs lives in three places on disk, all of them derivable:

| Location | What | Env override |
|---|---|---|
| `~/.config/cttp/config.toml` | `registries` (ordered) and `[remotes]`; **written with defaults on first run** | `CTTP_CONFIG` (path), `CTTP_REGISTRY` (replace the list with one entry) |
| `~/.local/share/cttp/registry` | a clone of the public registry repo; the second default registry | (an entry in the config) |
| `~/.cache/cttp/` | `repos/<locator>` bare clones; `objects/<sha256>` + `.json` the object cache; `run/<pinned address>/main.py` and `run/file-<hash>/` run caches | `CTTP_HOME` |

## 3. Repo map

| Path | What | Status |
|---|---|---|
| `src/cttp/` | the package; see §2 | authored |
| `src/cttp/extract/` | `__init__.py` (`Page`, `Ref`, `extract()` dispatch by suffix), `python.py` (the `ast` extractor) | authored |
| `src/cttp/server/templates/` | `base.html`, `index.html`, `name.html` | authored |
| `tests/` | pytest, one file per concern (`test_address`, `_hashing`, `_extract_python`, `_config`, `_links`, `_gitcache`, `_resolve`, `_objects`, `_latest`, `_closure`, `_expand`, `_check`, `_update`, `_fold`, `_run`, `_package`, `_server`, `_cli`); `conftest.py` builds the offline world and forbids sockets | authored |
| `tests/fixtures/registry/` | the registry repository's contents — **identical to the public repo at `v1`**; keep them in sync | authored |
| `tests/fixtures/hello/hello.py` | one line, `# cttp: hello-world` | authored |
| `tests/fixtures/thermo/` | a fake sensor package (`src/thermo/{__init__,decode,lm75}.py`) with every definition kind the extractor must handle; served in tests as `github.com/leorinaldi/thermo` | authored |
| `tests/fixtures/pyrepo/` | the closure fixture: `lib.py` (siblings in a chain, a `requests` import, a stdlib import, a missing name, mutual recursion) and `many.py` (51 tiny definitions, over budget); served as `github.com/leorinaldi/pyrepo` | authored |
| `docs/` | vision, spec, plan, this file; excluded from ruff | authored |
| `scripts/make_local_registry.py` | builds an offline registry repo from the fixture | authored |
| `bench/drivers/corpus/`, `bench/drivers/lm75-teardown/` | the benchmark corpus (736 Linux driver `.c` files) and the LM75 teardown; fetched by script, never committed | gitignored |
| `.local/` | local scratch, e.g. `serve.log` | gitignored |
| `.venv/`, `uv.lock` | uv-managed environment; the lockfile is committed | `.venv` gitignored |
| `pyproject.toml` | hatchling build, `cttp` entry point, ruff and pytest config | authored |

Outside the repo: the public registry `github.com/leorinaldi/cttp-registry`, whose `README.md`
links to spec §8 in this private repo.

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
- **A `#symbol` travels the HTTP contract as `%23` in the existing route.** The contract grew
  no route; spec §8's table does not yet say so (a follow-up in `PROGRESS.md`).
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
- **Registry entries name a target, not code.** `names/<name>.toml` holds `target =
  host/owner/repo/path`, a `default` label and `[versions]` mapping labels to refs. Version
  labels are names for refs; git revisions are the versions. There is no second versioning scheme.
- **Every locator goes through `[remotes]` or https.** No special case lets a registry serve
  itself from its own path. The tests reach a bare repo in `tmp_path` through `[remotes]` exactly
  as a mirror would.
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
- **page** — what an address resolves to: a definition (`function`, `class`, `constant`) or a
  script, with its normalized source. A definition's source is its span, dedented.
- **symbol** — the dotted name of a definition within a file: `reg_to_millicelsius`,
  `LM75.read_temp`. Module-level defs, classes, constants and class members are addressable;
  nested defs are not, and the error says which definition they are nested in.
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
  test client, whose event loop makes a socketpair — no connect, so it passes the guard.
- **Never invent a value.** A missing license is `None` and prints `not available`; a missing
  description stays absent. Nothing is coerced to a plausible default.
- **Stamps carry commit SHAs only.** Tags and branches are for humans; they never appear in a
  stamp the tool writes.
- **`tests/fixtures/registry/` mirrors the public registry repo.** A change to one is a change to
  both, in the same session.
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
- **Confirmation needs a terminal.** `cttp run <address>` with stdin not a tty prints the summary
  and exits 2. Scripts and tests pass `--yes`. To test the prompt by hand, use `script(1)` for a
  pty.
- **Headless screenshots:** `~/.cache/ms-playwright/chromium-*/chrome-linux/chrome --headless=new
  --screenshot=…`. System Firefox's headless screenshot does not work here.
- **The stale `hello.py` in the repo root is Leo's**, untracked, and stamped with a rev that no
  longer exists anywhere. `check` correctly reports it `unresolvable`. Leave it.

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
| How do I find my way around, and what will bite me? | this file |
| How should I run a session in this repo? | `CLAUDE.md` |

## 11. Maintaining this document

Update it only when something **foundational** changes — a decision settled or reversed, a new
invariant, a new top-level directory, a changed bring-up command, a new trap worth warning the next
agent about. The test: *would an agent starting fresh next week be wrong without this?* Everything
dated belongs in `PROGRESS.md` instead.
