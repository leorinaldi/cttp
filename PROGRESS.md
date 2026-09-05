# PROGRESS — cttp

cttp — *code text transfer protocol* — is a protocol that sits on top of existing programming languages
and lets code point at code: every definition gets an address, references are links rather than imports,
and an index answers who links where. Rationale: [`docs/vision.md`](docs/vision.md).

**Status: PHASES 0 TO 7 COMPLETE, P8-T1 (THE HARNESS) DONE (the `cttp.ai` DNS is Leo's; localhost stands in until then). NEXT IS P8-T2 (THE TASK SET).** Phase 0
(2026-09-04): the spike, the public registry `github.com/leorinaldi/cttp-registry` tagged `v1`,
the config with an ordered registry list and `[remotes]`, the registry as an **HTTP contract**,
`run` asking before the first run. Phase 1 (2026-09-04/05): the **full address grammar**,
**identity and shape hashing**, the **Python extractor in full** with derived references, and the
**link convention in full**. Phase 2 (2026-09-05): **the resolver in full** — SPDX matcher,
symbol search, `id=` mismatch, the **object cache**, **`resolve --latest`** rules 1 and 2. Phase 3
(2026-09-05): **the materializer in full** — closure, expansion with closure, `add`, `check
--fix`, `update`, `fold`, `run`, `--write-deps`, `expand --package`. Phase 4 (2026-09-05): **the
index** — `cttp index add|crawl|status` over six SQLite tables with identity as the key; the six
queries `who`, `dups [--shape]`, `closure --indexed`, `search`, `history`, `rank`; **`--latest`
rule 3** through the index (a move across repositories, or a fork); spec §12 **acceptance tests
2 and 3** as pytest; and **the viewer over the index** (search, `/d/<identity>`,
`/r/<locator>`, `/dups`, the name page with history and *who links here*), derived and asserted
facts in two labelled columns. Phase 5 (2026-09-05): **the agent interface** — `schemas.py`,
the one definition of every command's `--json` object (`schema_version` stamped on all of them,
strict validation of every subcommand's real output, a pinned fingerprint, `docs/json-schemas.md`
generated); and `cttp mcp`, an MCP server over stdio whose six tools (`resolve`, `who`, `closure`,
`search`, `dups`, `fold`) answer exactly what the CLI prints, checked from Claude Code by hand.
Phase 6 (2026-09-05): **the read side for C and the driver corpus** — `extract/treesitter.py`
with `queries/c.scm` (functions, constants, `struct.`/`enum.`/`union.<tag>` types, typedefs,
macros; identity and shape from the grammar's nodes; links in C comments), `.c`/`.h` routed
through it everywhere (schema version **2**: `language` gains `c`, `kind` gains `type` and
`macro`); the corpus pinned to **Linux v7.3-rc1** and reproduced byte for byte by
`bench/drivers/fetch.sh` (a sparse, blobless clone, which the crawl reads as the files it has);
spec §12 **acceptance test 1** passing with the groups `expected.json` records; and the
line-level measurement recomputed by `bench/drivers/measure.py` — the vision's numbers amended
(42 % verbatim, 92 % by shape; the old 37 %/14 % could not be reproduced). Phase 7
(2026-09-05): **the registry as a service** — `cttp name show | claim | verify` (spec §8's proof
of control: the target's `cttp.toml` declares the name at its default branch, the owner is the
target's account, a claim is a pull request on a `claim/<name>` branch opened with `gh`);
federation tested (registries in order, first match wins, the answer names the registry);
`cttp serve --export <dir>` writing the contract as static files byte-identical to the live
responses; the default registry list now `https://cttp.ai`, `localhost:3120`, the clone (schema
version **3**). The registry repository's `verify` and `pages` workflows, the `hello-world`
declaration and the README are on an **unpushed `p7` branch of the registry clone** — pushing
them, the `CTTP_TOKEN` secret, enabling Pages, the DNS for `cttp.ai` and the two test pull
requests are Leo's, and are the open items of P7-T2/T3. Phase 8 (2026-09-05): **P8-T1 the
harness** — `bench/agent/` drives Claude Code headless under Leo's login with two arms (the
cttp MCP tools against the shell's search), per-run checkouts and indexes, records with usage,
tool calls and grades, a `--replay` dry run, and the smoke task passing in both arms. 344 fast
tests green plus 2 `slow` corpus tests (deselected by default), ruff clean.

_Last updated: 2026-09-05, session end (P8-T1 done: the harness, the smoke run, the arm design amended on evidence; cttp.ai DNS pending, not blocking)._

> **Read [`docs/overview.md`](docs/overview.md) first** — it is the lay of the land. This file is
> only *where we are*: state, next steps, follow-ups and recent history.

## Next session — suggested next steps

**Start here: P8-T2 — the task set.** Read its entry in [`docs/plan.md`](docs/plan.md) in full,
and `bench/agent/README.md` for how a task is shaped: `tasks/<name>/task.toml` (prompt, `repo`
source + locator, the grade command) with `setup/`, `grade/` and `solution/` overlays;
`--check-graders` is the acceptance. `graders.prepare_checkout` already takes a git repository
as `repo.source` with `repo.rev` — what the three real repositories need — but it clones the
source with `git clone`, so the repositories must be on disk (a bare clone under `bench/agent/`
or the git cache) before a run; decide where they live and how they are fetched (a
`fetch.sh` like `bench/drivers/`). **Design the tasks so that reading everything is the
expensive path**: in the smoke run, with `Read` available, the links arm read the two files and
never touched a cttp tool — on a two-file repository there is nothing to search for. The
cross-repository tasks need the second repository indexed too (`prepare_index` crawls only the
checkout today) and the impact questions need a grader that compares the agent's answer with
`who` — neither exists yet. Keep `Read` in both arms (see the P8-T1 amendment in `plan.md`).

**Before the full run (P8-T3):** the smoke numbers say a trivial task costs ~30–40k tokens and
~13 s per arm on Opus 5; the five-hour window's utilization is in every record's `rate_limit`
(the smoke runs moved it from 0.20 to about 0.25 across three runs, one of them 470k tokens).
Estimate from the P8-T2 tasks' first runs, and tell Leo before starting ninety.

Still Leo's, not blocking: the **DNS for `cttp.ai`** (apex `A` records 185.199.108.153,
185.199.109.153, 185.199.110.153, 185.199.111.153, or an `ALIAS` to `leorinaldi.github.io`);
today the domain points at a parking host and `https://cttp.ai/hello-world.json` is a 404 the
tool treats as a miss. When the records exist: `gh api -X PUT
repos/leorinaldi/cttp-registry/pages -f https_enforced=true`, then compare
`curl -s https://cttp.ai/hello-world.json` with `localhost:3120/hello-world.json`. Also pending
Leo: whether `bench/drivers/corpus-preserved/` (13 MB, reproduced byte for byte by `fetch.sh`)
can be deleted.

## Current state — working & verified

**Code (`src/cttp/`), 2026-09-05.** Real modules; Phases 1 to 7 in full (P7's publish steps pending):
- `config.py` — **P0-T3/T4.** `~/.config/cttp/config.toml` (XDG; `CTTP_CONFIG` overrides the
  path): `registries` (ordered list of HTTP URLs or local paths; first match wins) and
  `[remotes]` (locator prefix → URL prefix, longest prefix wins, else `https://<locator>.git`).
  Paths take `~`; relative paths are relative to the file. **First run writes the file** with
  the defaults: `https://cttp.ai`, `http://localhost:3120`, then `~/.local/share/cttp/registry`
  (P7-T3; localhost first before that), no remotes.
  `--registry <entry>` or `CTTP_REGISTRY` replaces the list with that one entry (remotes kept).
  `cttp config [--json]` prints the effective result.
- `hashing.py` — **P1-T2.** `normalize()` (spec §2: dedent, LF, no trailing whitespace, one
  trailing newline), `identity()` (SHA-256 of the normalized text), `shape()` / `shape_text()`
  (the same text tokenized: identifiers → `$0`, `$1`… by first appearance, literals → `<num>`,
  `<str>`, `<fstr>`, statement and block structure → `<nl>`, `<in>`, `<out>`; keywords, builtins
  and operators kept; comments and blank lines dropped) and `short()`. `ShapeError` when the text
  is not Python. The identity of `print("hello world!")` is pinned in `tests/test_hashing.py`
  (`75a27070015e…`). `address.py` re-exports all of these. **P6-T1:** `shape_text(text,
  language="python")` / `shape(text, language)` — a language other than Python goes to
  `treesitter.shape_text`; one with no grammar is a `ShapeError` (`resolve` and the crawl catch
  it: `shape: null`).
- `address.py` — **P1-T1.** All three spec §2 forms in one frozen `Address` (`form`, `name`,
  `locator`, `path`, `rev`, `symbol`, `identity`): `parse()` accepts the optional `cttp:` marker,
  lower-cases the host and hex, turns backslashes into slashes, drops a trailing slash, rejects
  `.`/`..` segments; `str()` is the canonical text and `format(marker=True)` restores the
  marker — every spec example round-trips byte for byte. `is_pinned` = identity form or a SHA
  rev (`is_sha`, 12–40 hex; `gitcache` imports it). `parse_pinned()` rejects a tag or branch
  where a stamp needs a SHA. Errors name the offending part (label, version, symbol part, host,
  owner, rev, path segment, hex length). **In a locator, the first `/` after `@` starts the
  path**, so a branch with a slash cannot be a locator rev (name-form revs may have slashes).
  Identity addresses parse but `resolve` refuses them (P2-T2).
- `extract/__init__.py` + `extract/python.py` — **P1-T3.** `extract(path, source, symbol,
  files)` dispatches by suffix: `.py` → the Python extractor, anything else → a `text` script
  page with no shape and no references. `Page` carries kind, normalized source, language, span,
  and for a definition its `symbol`, `signature`, `docstring` (first paragraph as one line),
  `refs` (`Ref(path, symbol)` within the repository) and the `stdlib` / `third_party` top-level
  modules it needs. Addressable: module-level `def`, `async def`, `class`, simple assignment to
  one name; class members as `Class.member`, recursively; span from the first decorator. A nested
  def is reported as nested inside its parent; an unknown symbol lists the definitions. Derived
  references: import bindings and attribute chains resolved against the repository's file list
  (relative imports from the file's package, absolute ones against every ancestor directory,
  longest module prefix wins), plus sibling definitions in the same file; a parameter shadows a
  module-level import. A script's references are every import it makes; a definition's are the
  names it uses. **P3-T1:** `Ref.name` is the text the page reaches a reference by (`REG_BITS`,
  `decode.STEP_MILLICELSIUS`, `r2m`); `Page.imports` is a definition's module-level import
  statements for the stdlib/third-party names it uses (`import struct`, `from asyncio import
  sleep`); `Page.unresolved` its free names (not local, imported, defined in the file or builtin;
  module globals like `__name__` excepted); `Page.links` the link lines found in its text. **A
  script page's `source` is its own text**: `links.strip_links()` removes every link line and,
  for a stamped `is` link, its block and separator blank; what remains is what the identity
  hashes and what `expand` writes. A definition's text stays its span verbatim.
- `extract/treesitter.py` + `extract/queries/c.scm` — **P6-T1.** The read side for C (and any
  language a `tree_sitter_<lang>` wheel and a query file are added for: `GRAMMARS`,
  `LANGUAGES` in `extract/__init__.py`). The query file names each definition node type as
  `@definition.<kind>` and, where the grammar has the field, its name as `@name`; the extractor
  descends declarator chains (`*name`, `name[]`, `(*name)(…)`) for the rest, keeps file-scope
  definitions only (nothing inside a body, struct, parameter or enumerator list; macros
  anywhere), and the first of two definitions of one symbol (`#ifdef` arms). Kinds: `function`,
  `constant` (a declaration with an initializer — tables included), `type` (`struct.<tag>`,
  `union.<tag>`, `enum.<tag>` with a body; a typedef by its name), `macro` (`#define`, with or
  without parameters). A page carries its span (rows computed from **byte offsets**, never from
  a node's `Point` — py-tree-sitter 0.26.0 hands those out from freed memory and segfaults on
  nodes returned by query captures; the dependency is pinned `<0.26`), its own text, a
  signature (the declaration up to the body or initializer, whitespace collapsed; a macro's
  name and parameters), the first paragraph of the comment directly above (kernel-doc summary;
  a link-line comment is not a description), and its link lines; **no refs, no imports, no
  free names** — those are the Python extractor's. `tokens()` gives `(row, category, token)`
  triples with comments gone and raw macro bodies regex-tokenized; `shape_text()` is the
  definition-level shape (identifiers `$n` by first appearance, literals `<num>`/`<str>`,
  keywords and primitive types kept). A parsed file is cached (`lru_cache`), so the crawl's one
  `extract()` per definition parses once. `.c` and `.h` are `c`; a whole C file is a `script`
  page with a shape, its link lines taken out.
- `gitcache.py` — **P2-T1.** Bare clones under `$CTTP_HOME` (default `~/.cache/cttp`)
  `/repos/<locator>`, cloned from `config.url_for(locator)`; `rev_parse` (tags and branches to
  SHAs), `show` (`cat-file blob`), `ls_tree`, `default_branch` (the bare clone's HEAD).
  `license_of` finds `LICENSE*`/`COPYING*` at the rev (case-insensitive) and `spdx_of` matches
  the text: Apache-2.0, MPL-2.0, GPL-2.0, GPL-3.0 by title in the first 2,000 normalized chars
  (a preamble may come first — git's COPYING does), the GNU family told apart by which title
  comes first; MIT, ISC, BSD-2/3-Clause by their grant. Anything else is `None`; LGPL, AGPL and
  Unlicense deliberately return `None`. Verified against the twelve canonical SPDX texts. **A
  fetch is skipped when the wanted rev is a SHA already in the cache**, so `check` on an expanded
  file is offline once the repo is cached; labels always fetch. **P8-T1:** a clone goes into a
  temporary sibling directory and is renamed into place, so two callers cloning one repository
  at once (the MCP server answering `resolve` and `closure` from one turn) both get it, and a
  crash never leaves a half clone.
- `registry.py` — `Registries`: the configured list, asked in order; a `RegistryError` from
  one is a miss and the next is asked; when all miss, the error names them all with each reason.
  `LocalRegistry` reads `cttp.toml` + `names/*.toml` (an empty `description = ""` is no
  description, so a derived one is written — P3-T2). `HttpRegistry.fetch(name, version,
  symbol)` is `GET <url>/<name>[@<version>][%23<symbol>].json` — a symbol rides the same route
  percent-encoded — and returns the server's object (**the server resolves, the client asks**);
  404 and an unreachable server are misses, anything else is an error.
  `MissingRegistry` stands in for a configured path with nothing at it (a miss that says how to
  clone). `Registries(local_only=True)` is what the **server** uses — it must never ask an HTTP
  registry, which could be itself. `git_repo_from()` makes a git repo from a directory of files
  (branch `main`, tag `v1`); `create_local_registry()` is that for the registry fixture.
  **P7-T1/T2 — names.** `declaration_at(locator)` reads the target's `cttp.toml` at the head
  of its default branch: `name = "x"` and `names = ["y", …]` are the names it is the target of
  (the list form is the one addition to spec §8). `owner_of(locator)` is `host/owner` — the
  owner is derived, never asked. `check_entry(entry)` runs the registry's checks — `declaration`,
  `owner`, `target` (the path exists), `labels` (well formed, each ref a revision, the default
  resolvable), `resolves` — as `Check(check, ok, detail)`. `claim(name, target, …)` validates
  the name (`NAME_RE`: labels namespaced by dots) and the locator, refuses a target that does not
  declare the name (naming the file, the branch and what it does declare), refuses a name another
  owner holds unless `transfer`, builds the entry (`latest = <default branch>` unless `--version`
  given), runs the checks, and either writes `names/<name>.toml` into the first local registry's
  working tree (`pr=False`) or `open_claim_pr()`: a temporary **worktree** of the clone at
  `origin/<default>`, branch `claim/<name>`, commit, `push --force -u origin`, `gh pr create`
  (`_gh()`, patched in tests), then the worktree and local branch are removed — the person's
  checkout is never touched. `verify(names)` runs `check_entry` over the given or every name of
  the first local registry. `entry_text()` writes the file with `tomli_w`; `entry_json()` is the
  `entry` schema object.
- `resolve.py` — `resolve()` for a **name** asks each registry in turn: an HTTP one yields
  `Resolved.from_json(...)` with `registry` set to the URL; a local one goes through
  `resolve_entry()`: entry → locator → git → extract → hash. For a **locator** (P1-T1)
  `resolve_locator()` goes straight to git through `[remotes]` — the contract has no locator
  route, so HTTP registries are not asked; `Registries.entry_for_target()` finds a local entry
  naming the same target and lends its `name`, `description` and `registry`, else those are
  `None`. A `#symbol` on either form (P1-T3) selects one definition; the pinned address keeps
  it (`name@<12-hex>#sym`, `host/owner/repo@<12-hex>/path#sym`). `Resolved` carries `shape` /
  `shape_full` (None for non-Python), `symbol`, `signature`, `docstring`, `span` (`[first,
  last]`), `refs` (`{address, relation: "ref", origin: "derived"}`, addresses in pinned locator
  form at the same rev) and `imports` (`{stdlib, third_party}`). `to_json()` adds `origin`.
  `gitcache.ls_tree()` supplies the file list for reference resolution (Python files only).
  **P2-T1:** an entry naming a whole repository (no path) takes a `#symbol`, found by
  `find_symbol()` over every Python file at the rev — one hit resolves, none or several stop with
  the candidates as locators. `resolve(text, registries, expect=id)` raises `Mismatch` (a
  `ResolveError` carrying `resolved` and `claimed`) when the page's identity does not start with
  the claimed hex. **P2-T2:** every resolution is `objects.store()`d on the way out; the identity
  form goes to `resolve_identity()` — the object cache, then `objects.index_lookup()` (returns
  `None` until Phase 4) — and answers with the most recently seen location as the address,
  `locations` (each with `origin: cache`) and `via="cache"`; `to_json()["origin"]["location"]`
  is `"cache"` or `"repository"`. `locations` and `via` are not part of the registry contract.
  **P2-T3:** `latest(text, registries)` → `Latest(pinned, head, found, rule, to, changed,
  message)`: a pinned name follows its entry's default ref, a pinned locator the repository's
  default branch; rule 1 `same-path` (with `changed`), rule 2 `same-identity` (a move within the
  repository; whole file for a script page; definitions with the pinned name tried first), else
  `found=False` saying rule 3 needs the index. A rename is not found — the identity includes the
  name. **P3-T1:** `Resolved` grew `links` (asserted: address, relation, fields, description,
  derived, line, indent) and `unresolved`; `refs[*]` carry `name`; `imports` carries
  `statements`. `from_json` requires the original `FIELDS` and defaults the newer ones
  (`OPTIONAL`) so a pre-Phase-3 server still answers. `to_json()["origin"]` says `links` are
  asserted, the rest derived.
- `objects.py` — **P2-T2.** The object cache: `objects/<sha256>` is the normalized source,
  `objects/<sha256>.json` the sidecar — the page's metadata (kind, language, symbol, signature,
  docstring, span, shape, refs, imports) and `locations`, each a pinned locator address with
  target, path, rev, name, registry, description, license and a `seen` timestamp; a location seen
  again is refreshed, not duplicated; `links` and `unresolved` joined the metadata (P3-T1).
  `lookup(prefix)` (12+ hex, with or without `sha256:`) →
  `Stored` or `None`; `AmbiguousIdentity` lists the candidates. `status()` and `clear(repos,
  objects, run)` cover both caches and the run cache.
- `links.py` — **P1-T4.** Spec §4 in full. One regex finds a link line in any comment syntax
  (`#`, `//`, `--`, `;`, `/* … */` closed on the same line); `cttp:` / `cttp-from:` / `cttp-see:`
  set `relation` (`is` / `from` / `see`); fields are ordered `key=value`, the description the last
  and only quoted field, `~` marking a derived one; `Link.format()` writes the canonical form
  (two spaces before the description) and every spec §4 example round-trips byte for byte. A
  malformed line is a `LinkError` naming the line and the field (a space in a value, a duplicate
  key, a quoted string that is not last). `find_links(lines)` records each link's **block** as
  `start`/`end`: it begins after the link's *stack* (consecutive link lines share one block) and
  ends at the next link line, at a blank line followed by a line indented no more than the link,
  or at EOF. `format_stamped(pinned, id12, description, derived=False, comment="#")`.
  **P3-T1:** `strip_links(lines)` → the lines without link lines (and without stamped `is`
  blocks), plus the links taken out.
- `closure.py` — **P3-T1.** `closure(text, registries, budget)` → `Closure(root, nodes, imports,
  stdlib, requires, hoisted)`: a depth-first walk from the page through its inner `is` links
  (asserted; a stamped one is resolved with `expect=` its id, so a wrong stamp is a `Mismatch`)
  and its derived refs, each dep resolved in its own repository at the pinned rev; post-order, so
  dependencies come before dependents and the root is last, stable in first-use order; keyed by
  pinned locator address; mutual recursion tolerated. `Node` carries the page, the stamp's
  description (asserted or derived — `describe()` moved here), `via` (`root`/`link`/`ref`),
  `needs`, `defines`. **Refusals, each a `ClosureError` naming the page and the cause:** a ref
  reached through a module (`decode.STEP_MILLICELSIUS`) or an alias (`as r2m`) — inlining binds a
  definition only by its own name; a module used as a whole; a free name nothing in the closure
  binds (`unresolved` minus what the deps define — the spec §7 `greet` case is satisfied by the
  inner link); a definition with link lines inside it, or a script with an indented `is` link;
  two pages binding one top-level name; over budget (`Budget(50, 2000)`; `None` lifts it, which
  `--package` and `cttp closure` use) with the `--package` suggestion. A ref to `Class.member`
  is lifted to `Class`. `cttp closure <address> [--json]` prints it.
- `expand.py` — **P3-T2..T5.** `expand_text()` → `Expansion(text, reports, closures, vendored)`:
  for each unstamped `is` link, its closure's import statements (deduped against the file) then
  each dependency beneath its own stamp go **above the link's stack**; the root's stamp keeps the
  person's fields (`track=latest`) and description, adds `id=` first, and the page's own
  `from`/`see` lines join the stack; the root's text goes beneath, then a blank line when
  something follows. A dependency already stamped above in the file is not written twice. Two
  `is` links in one stack are refused. `expand_file(path, registry, package, write_deps)` writes
  the file, vendored modules, and — with `--write-deps` — the third-party requirements into the
  nearest `pyproject.toml` (`write_dependencies`: a text edit that keeps comments and order,
  re-parsed before writing); otherwise a `deps` report says what to pass. `add_link()` is `cttp
  add <address> [<file>] [--at N]`. `check_file(path, registry, fix)`: `unexpanded` / `drift` /
  `mismatch` / `unresolvable` / `ok`, and with `--fix` a drifted `is` becomes `from` (marker
  swapped in place, comment syntax kept, reported `fixed`); a link with `vendor=` is checked
  through the vendored module (same page, same id, its own block hashing). `update_file(path,
  registry, addresses, all_, to, confirm)`: `select_links` (named addresses; else all under
  `--all` or a project `cttp.toml` with `track = "latest"`; else `track=latest` links) →
  `plan_update` (`latest()`, or `resolve` at `--to <rev>`) → `Update` with a unified diff → on
  confirmation `apply_update` rewrites stamp and block and inserts the new version's missing
  dependencies above the stack, bottom-up so line numbers hold. A `from` link gets `upstream` and
  the diff, never a rewrite; drifted and unexpanded links are reported, not touched. `fold_text()`
  collapses every stamped `is`/`from` block to its link line (the separator blank goes too when
  the next stack follows, stays before user code); `--open <address>` matches rev-agnostically;
  the JSON lists links with 1-based `start`/`end`. `run_address` / `run_file` confirm with the
  whole `Closure` — the CLI prompt shows every page's address, identity, license and source —
  and the run cache stays the confirmation marker. `--package`: the closure rendered as one file
  into `cttp_vendor/<module>.py` (`__init__.py` created), the user's link stamped with
  `vendor=cttp_vendor/<module>.py`, and `from cttp_vendor.<module> import <names>` (or `import
  cttp_vendor.<module>` for a script that defines nothing) beneath it.
- `index/schema.py` — **P4-T1.** One SQLite file, default `~/.local/share/cttp/index.db`
  (`--index <path>`, `CTTP_INDEX`; `XDG_DATA_HOME` honoured). Six tables: `repos` (locator,
  default branch, the local path it was added from), `revisions` (repo, sha, commit time,
  license at that rev, crawled-at, file count), `definitions` (**identity is the key**: shape,
  language, kind, name, signature, docstring, lines, source, imports JSON, unresolved JSON),
  `locations` (identity at (repo, sha, path, symbol) with its span — three places are three
  rows against one definition), `links` (source identity and where it was; the target address
  as written *and parsed* — form, name, locator, path, rev, symbol, `id=`; the target identity
  when the index can tell; relation `is`/`from`/`see`/`ref`; origin; description, derived flag,
  fields JSON, indent; a derived ref's `name`), `names` (registry entries snapshotted at crawl),
  plus `definitions_fts` (FTS5, porter stemming) for search. `open_index(path, create=False)`
  raises `IndexingError` for a missing file — a query never creates an empty index.
- `index/crawl.py` — **P4-T1.** `add()` registers `host/owner/repo`, or a local path whose
  `origin` remote names one — the URL is reversed through `[remotes]` first (so the tests' bare
  repositories map back to their locators), else parsed as https / ssh / scp-style. A registered
  local path is crawled **from that clone's git**, at `HEAD` or `--rev`; a locator through the
  git cache at its default branch. `crawl()` per repository at one sha: every file read through
  `git`; a Python file yields its **file page and one page per definition**, any other file a
  `text` page only when it carries a link line; each page recorded once per identity
  (`INSERT OR IGNORE`) and once per place; a file whose whole text is one definition shares its
  identity and **the definition's view wins the row** (kind, name, signature). Asserted links go
  against **the page they stand for** — the definition whose span starts at the block, else the
  innermost definition holding the line, else the file; derived refs against the page that made
  them. A **malformed link line** (prose like `# cttp: <address> [key=value]`) becomes a bare
  comment and a skip note names it — the file's definitions are still indexed. Then the local
  registries' names are snapshotted and `resolve_targets()` fills every `target_identity` it
  can: a stamp's `id=` (one match), a pinned locator seen at that rev, a name whose snapshot
  points at a crawled file (latest crawled rev). The crawl **never fetches a repository it was
  not given**. A revision already crawled is skipped (`already`); `--force` crawls it again
  (locations and links removed first). `status()` counts. **P6:** every file with an extractor
  (Python, C) goes through `code_file()`; a **sparse checkout is crawled as the files it has on
  disk** (`is_sparse()`, `git sparse-checkout list`) — a blobless clone would otherwise fetch
  every other blob of the repository; a local clone at a detached HEAD is named by its tag
  (`_checked_out()`, e.g. `v7.3-rc1`) when there is no origin HEAD.
- `index/queries.py` — **P4-T2.** `lookup_identity()` is `objects.index_lookup` (a `Stored`
  with `via="index"` and every crawled location); `page_json()` renders a definition at a
  location as the contract object. `target_of()` turns any address into what the index knows —
  identities and the place (repo, path, symbol); a label rev resolves for real when registries
  are given; an address the index never saw resolves for real to learn its identity. **`who`**:
  links whose target identity matches, or — only when the index could not tell the target's
  identity — whose target names the same place or name; one row per (source, file, relation,
  target), at the latest crawled rev; sorted `is`, `from`, `see`, `ref`, asserted before derived.
  **`dups`** over the **current** locations (each repository's most recently crawled revision;
  a file that is its one definition is not its own twin), by identity or `--shape`, largest
  groups first. **`closure`** from recorded `is`/`ref` links, several roots, the P3-T1 output
  shape plus `roots` and `missing` (targets the index cannot tell — listed, never fetched); a
  pinned rev wins over "current". **`search`**: FTS5, every term a quoted prefix, porter
  stemming (`greet` finds a "greeting" docstring). **`history`**: identities at a place over
  every revision of its repository, ordered by commit time then crawl order (`rowid` breaks
  same-second ties), `changed` and `absent` flags. **`rank`**: distinct linking pages
  (identity, repo, file) per target — a verbatim copy linking back counts; a definition's derived
  reference to itself does not. **`forward()`** is `--latest`'s rule 3 (P4-T3).
- `schemas.py` — **P5-T1.** The one definition of every command's `--json` output: a small
  schema language (`S` nodes: object, array, map, string, integer, number, boolean, enum, ref;
  `.null()`, `.derived()`, `.asserted()`, `.about()`), shared objects in `DEFS` (`page` — the
  contract object; `location`, `ref`, `link`, `imports`, `node`, `missing`, `expand_report`,
  `check_report`, `update_report`, `fold_entry`, `backlink`, `by`, `dup_group`, `hit`,
  `revision`, `ranked`, `crawled`, `repo_status`, `closure`), and `COMMANDS` — 24 entries
  (`version`, `config`, `resolve`, `resolve --latest`, `closure`, `expand`, `add`, `check`,
  `update`, `fold`, `run` (no object: the program's output), `cache status|clear`, `index
  add|crawl|status`, `who`, `dups`, `search`, `history`, `rank`, `mcp install`, `error`), each
  with usage, summary, *when*, notes and schema. `stamp()` puts `schema_version` (1) first on
  every object — `cli.emit()`, `cli.fail()` and the server's `/<name>.json` all go through it.
  `validate()` is strict (missing, extra, type, enum, null); `json_schema()` renders draft
  2020-12 (inline, or with `$defs`); `markdown()` renders `docs/json-schemas.md`;
  `fingerprint()` digests every schema and `FINGERPRINTS` pins it — **version 2 since P6-T1**
  (`14c8b9e5c6d17b96`): `language` is `python | c | text`, `kind` gained `type` and `macro`,
  the `signature`/`docstring` field notes say what they are for C.
  **Shapes frozen this session (deliberate, first version):** `expand`, `add` and `fold` wrap
  their per-file map in `files`; `index crawl` wraps its list in `crawled`; `closure` gained
  `source` (`repository` | `index`), `roots` and `missing` (empty for the live walk) so the live
  and indexed walks are one schema; `dups` groups carry `key` / `key_full` instead of
  `identity`/`shape` and `origin.by` instead of a dynamic key; `--version` and the error object
  carry `schema_version` too. `# ruff: noqa: E501` in this one file.
- `mcp.py` — **P5-T2.** `build_server()`: an `MCPServer` (the official `mcp` SDK, **2.1.1** —
  `FastMCP` was renamed) named `cttp` with instructions and six tools — `resolve(address,
  id)`, `who(address)`, `closure(addresses, indexed)`, `search(text, limit)`, `dups(shape)`,
  `fold(file, open)` — each calling the function the CLI calls and returning a `CallToolResult`
  with the stamped object as `structuredContent` and the same JSON as text; descriptions come
  from `COMMANDS` (summary + when + notes + "Same object as `cttp …`"); annotations read-only,
  idempotent, open-world for `resolve` and `closure`; `outputSchema` is `json_schema(name)`,
  set on `fn_metadata` by hand. A failure raises `ToolError` with the CLI's message (the client
  sees `isError` and the text). `cttp mcp [--registry] [--index]` runs it over stdio
  (`serve()`); `cttp mcp install [--claude-code]` prints, or runs, `claude mcp add --transport
  stdio cttp -- <.venv/bin/cttp> mcp`. `--latest`, `expand`, `add`, `check`, `update`, `run`
  and the index commands are CLI-only on purpose (they write, ask, or run).
- `server/app.py` — **P4-T4.** FastAPI on **3120**: the contract as before (`/<name>.json`,
  `/<name>@<version>.json`, `%23<symbol>`), and the viewer of spec §9 over the index: `/`
  (names, index status, `?q=` search), `/d/<identity>` (derived and asserted columns, every
  location with the current ones marked, source, who links here), `/r/<host>/<owner>/<repo>`
  (revisions crawled, pages at the current revision), `/dups[?shape=1]`, and the name page with
  history and *who links here*. **`base.html` chooses the derived/asserted layout once**: two
  labelled, tinted columns that stack under 44rem; inline facts keep their tag; tables become
  stacked cards on a phone. Every page says plainly when there is no index. Looked at in headless
  Chrome at 1200px and 390px against the real index.
- `server/export.py` — **P7-T3.** `export(directory, registries)` renders every route of the
  contract for every name through the same ASGI app (`TestClient`) and writes the bytes: `/` →
  `index.html`, `/<name>` → `<name>/index.html`, `/<name>.json`, `/<name>@<label>.json` per
  label; a non-200 stops it (`ExportError`). `routes_for()` lists them. Symbol routes are
  unbounded and not exported. `cttp serve --export <dir>` is the command; `--registry` chooses
  the registry (the env override is restored afterwards). Checked against the real registry and
  looked at in headless Chrome: identical to the live page.
- `cli.py` — `cttp --version | config | resolve [--id …] [--latest] [--index] | closure
  [--indexed] <address>… | serve | expand [--package] [--write-deps] | add [--at] [--package] |
  check [--fix] | update [--all] [--to] [--yes] | fold [--open] | run [--yes] | cache status |
  cache clear [--run] | index add <repo-or-path> | index crawl [<repo>…] [--rev] [--force] | index
  status | who <address> | dups [--shape] | search <text>… [--limit] | history <address> | rank
  [--limit] | mcp [--registry] [--index] | mcp install [--claude-code] | name show <name> | name
  claim <name> --target … [--description] [--version label=ref]… [--default] [--transfer]
  [--no-pr] | name verify [<name>…] | serve --export <dir>`; every index-reading
  command takes `--index <path>`; `--json` is accepted before or after the subcommand, and every
  object is stamped with `schema_version` (P5-T1). `closure` with several addresses, or `--indexed`, reads the index; one
  address without the flag is the live walk. `update` takes files and addresses mixed; exit 2
  when a change waited for a confirmation it did not get. `_interactive()` wraps the tty check
  so tests can drive the prompts. `resolve`'s text form prints the signature and docstring on a
  `#` line, `# seen:` lines when an identity came from a cache (`cache` or `index`), and `from →
  to` with the rule (`via index` when the index found it) under `--latest`.
- `bench/drivers/` — **P6-T2, P6-T3.** `fetch.sh` (the corpus: a sparse, blobless clone of
  `torvalds/linux` at **v7.3-rc1**, each of five directories' own files, 736 `.c`; ~60 MB;
  gitignored), `expected.json` (the corpus's provenance and how it was pinned; the duplicate
  groups acceptance test 1 checks; the measurement's numbers), `measure.py` (the line-level
  measurement, `--json`), `README.md` (all of it in prose). `corpus-preserved/` is the original
  raw-file copy, moved aside, identical to what `fetch.sh` produces.
- `bench/agent/` — **P8-T1.** `harness.py` runs **Claude Code headless** (`claude -p … --output-format
  stream-json --verbose`, never `--bare`) under Leo's login with two arms — `links`: the cttp
  MCP server through `--mcp-config` + `--strict-mcp-config`, `Read`, `Edit`, `Write`, `Bash`
  allowed for the task's test command only, the shell's readers denied by rule; `baseline`: the
  same without the server and with the read-only shell commands `dontAsk` auto-approves — and
  the same model (`--model opus`), `--max-turns 40`, `--append-system-prompt`,
  `--permission-mode dontAsk --permission-prompts none`, `--setting-sources ""`,
  `--no-session-persistence`, stdin `/dev/null`, a per-run timeout. `graders.py` loads
  `tasks/<name>/task.toml` and builds each run's world in a scratch directory: the source
  committed as `main`, a bare "remote", the working clone the agent edits (its `origin` the bare
  repo), the `setup/` overlay committed on top, a per-run `cttp.toml` mapping the task's locator
  to the bare repo through `[remotes]` — the test suite's pattern; the links arm gets its own
  `index.db` (`cttp index add` + `crawl`) and `CTTP_HOME`. The grade copies `grade/` over the
  checkout and runs the command (exit 0 = pass), keeping the agent's diff. Records under
  `results/<date>/<task>/<arm>/<run>.json` with the stream beside them: `usage` and its sum
  `tokens`, `model_usage`, `total_cost_usd`, `num_turns`, `wall_seconds`, `permission_denials`,
  every tool call (name, input, denied, error, result size), `tools_available` and
  `mcp_servers` from `system/init`, the last `rate_limit` event (window utilizations), the grade,
  `argv`. `status` is `pass | fail | limited | timeout | error`; `limited` stops the driver (or
  `--wait-for-reset` sleeps to the reset), and an existing record is skipped so the same
  command resumes. `--replay <run.json>` rebuilds a record from its stream (the dry run);
  `--check-graders` proves each grader fails the unmodified checkout and passes `solution/`;
  `--list`, `--task`, `--arm`, `--runs`, `--redo`, `--keep`. `report.py` renders the P8-T3 table
  (pass rate, median tokens, ratio, per task and family, result files listed). The smoke task
  `smoke-pyrepo` (pyrepo's `left` returns `x - 1`) and its two records from 2026-09-05 are
  committed. `README.md` has all of it.
- Tests: 344 fast + 2 `slow` in `tests/` — `test_{address,hashing,extract_python,extract_c,
  config,links,gitcache,resolve,objects,latest,closure,expand,check,update,fold,run,package,
  server,cli,index_crawl,index_queries,acceptance_move,acceptance_provenance,
  acceptance_drivers,schemas,mcp,name,registry_federation,export,bench_agent}.py`.
  `test_bench_agent.py` is the P8-T1 acceptance without the subscription: the smoke task loads
  and its grader tells the bug from the fix, the checkout and config are as described, the arms
  are what the README says, the stream parser reads init, tool calls, denials and the result,
  a replay of each committed smoke record reproduces its numbers exactly (and the links record
  shows cttp connected, the baseline none), and the report renders. `pyproject.toml` sets
  `pythonpath = ["."]` so `bench.agent` imports under pytest. `test_extract_c.py` is P6-T1's acceptance over the
  `crepo` fixture (every kind, exact spans and signatures, one identity in two files, one shape
  under other names and literals, links in both C comment syntaxes, the crawl and the five
  queries over C, `--latest` rule 2 on a moved C function) plus the corpus's `lm75_reg_to_mc`
  when the corpus is present. `test_acceptance_drivers.py` (**`-m slow`**, deselected by
  `addopts`, skipped without the clone) crawls the corpus offline (`GIT_ALLOW_PROTOCOL=none`)
  and checks `expected.json`'s groups and the measurement's numbers. `test_schemas.py` is
  the P5-T1 acceptance: every subcommand run through the CLI with `--json` against a fixture
  world (both `resolve` forms and the cache form, `--id` and its mismatch, `--latest` found and
  not found, live and indexed `closure` with a `missing` entry, `expand --write-deps` with all
  five statuses, `add`, `check` with drift/unexpanded/`--fix`, `update` not-confirmed then
  `--yes` with updated/unchanged/upstream, `fold`, `run`'s error object, both cache commands,
  the three index commands, the five queries, and the error object) validated strictly; the
  pinned fingerprint; the doc diffed against `markdown()`; the validator's own strictness; the
  JSON Schemas checked with `jsonschema` (a transitive dependency of `mcp`); the contract
  object validating as `resolve`. `test_mcp.py` is the P5-T2 acceptance: the in-memory client
  (`mcp.client.Client(server)`) lists six tools with the P5-T1 schemas and read-only hints,
  calls each and gets **exactly** the CLI's object, `closure` indexed by flag or by several
  roots, `resolve` by identity, failures as tool errors with the CLI's message, the install
  line. `test_index_crawl.py` is the P4-T1
  acceptance (row counts over `pyrepo` and a consumer, one `definitions` row per identity,
  `links` with origin, idempotence, a second rev adding one revision and only the changed
  definitions, an identity resolved from the index, a local clone added through its origin, a
  malformed link line costing the line not the file, `--force`); `test_index_queries.py` P4-T2
  (`who` on `deep` — the copy asserted, the sibling derived; `dups` and `--shape` over `twins`;
  `search greet`; `history` over two revs; `rank`; the indexed closure equal to the live one);
  `test_acceptance_move.py` spec §12 test 2 (a renamed move found by its `from` link, a plain
  move by identity once B is crawled, the no-index message, rules 1 and 2 still first);
  `test_acceptance_provenance.py` test 3 (`cttp add` in a cloned consumer, `cttp index add
  <path>`, `who` lists the copy as `is`/asserted with a license field; and by name).
  `conftest.py` gained `clone_remote(tmp_path, name)` and `commit_in(path, message, push)`, and
  **sets `CTTP_INDEX` to `tmp_path`** so no test can touch the real index. `test_server.py`
  covers the viewer pages with the fixtures crawled into a test index. `test_closure.py`
  is the P3-T1 acceptance (the four-definition order, `requires`, the unresolvable name, the
  budget) plus every refusal; `test_expand.py` P3-T2 (the spec §7 example byte for byte, running
  under `python3 -I`; imports hoisted once; `--write-deps`; `add` ≡ write + expand; re-expansion
  a no-op); `test_check.py` and `test_update.py` P3-T3 (one clean, one drifted, one unexpanded;
  `--fix`; a fixture history advanced with `commit_to_remote` and `track=latest` moving one link,
  `--all` the rest, the `from` link shown its diff and left byte-identical); `test_fold.py` and
  `test_run.py` P3-T4 (two link lines and nothing else; `--open`; `n` at the prompt runs
  nothing); `test_package.py` P3-T5 (51 definitions vendored, run, checked, then edited). The
  `config_file` fixture now also serves `tests/fixtures/pyrepo/` as `github.com/leorinaldi/pyrepo`. **Tests never connect a socket:** an autouse
  fixture in `conftest.py` patches `socket.socket.connect` to raise; `@pytest.mark.network`
  (registered in `pyproject.toml`) lifts it for the one test that talks to a closed local port.
  `test_links.py` is the P1-T4 acceptance (spec §4 lines round-trip; three relations in one
  file; the corpus C file with a `// cttp-see:` line, skipped when the corpus is absent; block
  rules; expand/check through the block). `test_gitcache.py` is the P2-T1 matcher and cache
  acceptance, `test_objects.py` the P2-T2 acceptance (identity resolves after the remote and the
  git cache are deleted), `test_latest.py` the P2-T3 acceptance over a fixture history.
  `conftest.py` also has `add_remote_repo(tmp_path, name, files)` (a repository reachable as
  `github.com/leorinaldi/<name>`) and `commit_to_remote(tmp_path, name, changes, message)`
  (advance it: write or delete files, commit, push to the bare remote). `test_address.py` is table-driven over the spec §2 examples plus
  valid/invalid inputs. `test_hashing.py` holds the plan P1-T2 acceptance (same shape / different
  identity, reordering, CRLF) and the pinned hello-world identity. `test_extract_python.py` is
  the plan P1-T3 acceptance through `cttp resolve <locator>#<symbol> --json` against
  `tests/fixtures/thermo/` (a package with decorators, an async def, a class with methods and
  attributes, constants, a nested def, relative imports, one third-party import): exact span,
  signature and docstring per definition kind, the nested-def error, sibling-module references,
  stdlib/third-party split, the name form with a symbol through a registry entry, the contract
  with `%23`, and a definition link expanding and checking.
  `test_expand.py::test_acceptance_test_4_hello_world` is spec §12 test 4 verbatim through the
  CLI. `conftest.py` builds, in `tmp_path`, a registry repo and the thermo repo, **bare clones of
  both under `remotes/github.com/leorinaldi/`**, and a config whose `[remotes]` maps the prefix
  there; `CTTP_CONFIG` and `CTTP_HOME` point at `tmp_path`; `add_to_registry(tmp_path, name,
  source=…)` adds a snippet name, `add_to_registry(tmp_path, name, target=…)` a name pointing
  at another repository; `hello` copies `tests/fixtures/hello/hello.py`. `test_server.py` drives
  the FastAPI app in-process (`via_http` fixture). No network.
  `test_no_runtime_component` guards the no-runtime rule.

**Corners still cut (each is closed by the named task):**
- Stamps use 12-hex for rev and identity (the plan's choice), full SHA returned in JSON → keep
- The index hook `objects.index_lookup()` returns `None`; `--latest` rule 3 says so → **P4**
- `expand`, `check`, `update` take files; spec §7's "or the project" (walk the tree) is not built
  → **unscheduled**; trigger: the first project with more files than one wants to name
- A class attribute used as a default in a method signature (`address: int = ADDRESS`) is not a
  derived reference; the method alone now reports it as an `unresolved` free name and its closure
  is refused (the class page is fine) → **unscheduled**; trigger: the index (P4) needing
  class-scope name resolution

**Docs**
- `docs/vision.md` agreed, `docs/spec.md` confirmed as written, `docs/plan.md` agreed,
  `docs/overview.md` written — all on 2026-09-04. `docs/project-start-sequence.md` retired (deleted,
  per its own Stage 5; `git log` has it). `CLAUDE.md` now points at `docs/plan.md` for next steps.

**Environment**
- Git on `main`, remote `origin` → `github.com/leorinaldi/cttp` (**public** since 2026-09-05;
  history scanned for secrets first — none).
- **Registry repo:** `github.com/leorinaldi/cttp-registry` (**public**), first commit
  `d29352a4fbf1` tagged `v1`; `main` is now `5125a659a10f` (2026-09-05) with
  `.github/workflows/verify.yml`, `.github/workflows/pages.yml`, `cttp.toml` declaring
  `names = ["hello-world"]` (identical to `tests/fixtures/registry/cttp.toml`) and the README's
  claiming instructions. The clone at `~/.local/share/cttp/registry` is at that commit, clean.
  **Pages** is enabled from Actions (`build_type = workflow`, `cname = cttp.ai`); the first
  `pages` run (33974576676) exported and deployed. **P7-T2 acceptance, done 2026-09-05:**
  **PR #1** (`claim/hello-world`, opened by `cttp name claim` itself — action `updated`, same
  owner) → `verify` **passed** all five checks in 17 s, `resolves` giving
  `hello-world@5125a659a10f sha256:75a27070015e` in CI; **PR #2** (`claim/bogus`, a hand-written
  entry for an undeclared name) → `verify` **failed** on `declaration` ("declares
  'cttp-registry', 'hello-world' … not 'bogus'"), the other checks ok; closed with a comment,
  branch deleted. **PR #1 merged** (`b18bf33c1cb6`, 2026-09-05; the entry is now in the tool's
  `tomli_w` format, and `tests/fixtures/registry/` mirrors it file for file). Runs 33974607931
  and 33974629545; the merge's `pages` run 33976466047 deployed. **P7-T3 acceptance, the half
  that needs no DNS (2026-09-05):** from a scratch directory with `CTTP_CONFIG` and `CTTP_HOME`
  pointing at empty paths — no config, no cache — `uv run --project ~/Claude/cttp cttp run
  hello-world --yes` printed `hello world!` in 0.8 s; the first run wrote the default config
  (`https://cttp.ai`, `http://localhost:3120`, the clone), the miss on cttp.ai fell through, and
  `resolve --json` named `http://localhost:3120`.
- **On this machine (2026-09-04):** `~/.config/cttp/config.toml` is the first-run default *as it
  was before P7-T3* (localhost first, then `~/.local/share/cttp/registry`, which is a **real
  clone** of the public repo); an existing file is never rewritten, so `https://cttp.ai` is not in
  Leo's list until he adds it. The spike's
  fixture-built registry was moved aside to `~/.local/share/cttp/registry.spike` (commit
  `9d12912`, exists nowhere else) and `~/.cache/cttp` was wiped — **trap:** the spike's cache
  held a clone of that fake repo under the real locator, so a pinned `9d12912…` address kept
  resolving from cache after the registry changed. A stale `hello.py` in the repo root stamped
  with `9d12912048b9` is Leo's and is now correctly reported `unresolvable`.
- `uv` 0.12.10 installed at `~/.local/bin/uv` (2026-09-04). Python 3.12.3 system interpreter at
  `/usr/bin/python3` has no cttp, which the tests rely on.
- Domain `cttp.ai` registered by Leo; nothing points at it yet.
- Driver corpus: `bench/drivers/corpus/` is now a **sparse, blobless clone of torvalds/linux at
  v7.3-rc1** made by `fetch.sh` (2026-09-05; gitignored). The original raw-file copy from the
  measurement session's scratchpad is at `bench/drivers/corpus-preserved/` (gitignored, 13 MB),
  byte-identical to the clone's five directories — Leo may delete it. The LM75 teardown files
  are at `bench/drivers/lm75-teardown/` (gitignored). **The real index now holds the corpus**
  (`github.com/torvalds/linux [v7.3-rc1]`, ~34,000 pages), crawled 2026-09-05.
- `tree-sitter` **0.25.2** (pinned `<0.26`) and `tree-sitter-c` 0.24.2 added to
  `pyproject.toml` (`uv.lock` updated); aarch64 wheels, no build step.
- The server was restarted on the Phase 6 code on 2026-09-05 (`.local/serve.log`); the contract
  object carries `schema_version: 2` first.
- **MCP SDK `mcp` 2.1.1** added to `pyproject.toml` (with `jsonschema`, `pydantic`,
  `sse-starlette` and friends as transitive dependencies; `uv.lock` updated). 2.x renamed
  `FastMCP` to `MCPServer` — see overview §8.
- **The MCP server was checked from Claude Code by hand (2026-09-05)** without touching Leo's
  config: `claude -p "Using the cttp MCP tools, who links to hello-world?" --mcp-config
  <scratch>/mcp.json --strict-mcp-config --allowedTools mcp__cttp__who,… --model sonnet
  --output-format stream-json` produced one call to `mcp__cttp__who` with `{"address":
  "hello-world"}` and the answer "3 links to hello-world: docs/spec.md (lines 138 and 142) and
  tests/fixtures/hello/hello.py (line 1), both in github.com/leorinaldi/cttp" — correct against
  `cttp who hello-world`. Then, on Leo's decision (2026-09-05), **the server was attached at
  user scope** — `claude mcp add -s user --transport stdio cttp --
  /home/leo/Claude/cttp/.venv/bin/cttp mcp` — so every Claude Code session on this machine has
  the six tools (`claude mcp get cttp` shows it connected; `claude mcp remove cttp -s user`
  detaches). It launches the venv's binary fresh each session, so code changes need no
  reinstall; it breaks if the venv moves. `who`, `search` and `dups` answer from the real index,
  so a new project needs `cttp index add` + `crawl` before backlinks appear.
- `~/.cache/cttp/repos/` holds four real repositories from by-hand checks (2026-09-05):
  `pallets/itsdangerous`, `psf/requests`, `leorinaldi/cttp-registry`, and **`git/git`, which is
  ~340 MB** (cloned to check the matcher on a COPYING with a long preamble). `cttp cache status`
  shows it; `rm -rf ~/.cache/cttp/repos/github.com/git` frees the space. `~/.cache/cttp/objects/`
  holds a few pages from the P2-T2 by-hand check.
- A headless Chromium exists at `~/.cache/ms-playwright/chromium-1223/chrome-linux/chrome`
  (`--headless=new --screenshot=…`); system Firefox's headless screenshot did not work.

## Known follow-ups (deferred)

Every item carries a target: the phase that will close it, `→ standing`, or `→ unscheduled` with the
trigger that would schedule it.

- Name collision check on PyPI and npm before the first package is published → **unscheduled**;
  trigger: deciding to publish `cttp` to PyPI (not in the plan)
- Point `cttp.ai` at the static export → **P7-T3**
- ~~The registry README links to spec §8 in the private `cttp` repo~~ — closed 2026-09-05:
  `cttp` is public
- Editor extension that folds cttp blocks on open and shows a link's page on hover →
  **unscheduled**; trigger: first real use of expanded files by a person in an editor
- A branch containing `/` (`release/1.0`) cannot be a locator rev — the first `/` after `@`
  starts the path; only the name form reaches such refs → **unscheduled**; trigger: a real
  target whose only useful ref is a slashed branch (an escape such as `@{release/1.0}` would do)
- Starlette warns that `httpx` with its test client is deprecated in favour of `httpx2` →
  **unscheduled**; trigger: the warning becomes an error on upgrade
- A **script page with a blank line followed by a non-indented statement** ends its block early
  under spec §4's delimiter, so `check` reports drift on it; no fixture hits this yet →
  **unscheduled**; trigger: the first real script page with an internal blank line (a fix would
  let `expand` record the block's `end` on the link, or indent-fold scripts)
- The **derived description prefixes `def` / `async def` / `class`** to the extractor's signature
  (which has no keyword, a P1-T3 choice used by the viewer and `resolve`); spec §4's example
  reads `def greet(...) — …`, so both are consistent, but the two representations of a signature
  should be reconciled once → **unscheduled**; trigger: the next change to `_signature`
- **`GPL-2.0` / `GPL-3.0` are the plan's spellings** and SPDX has deprecated them in favour of
  `-only` / `-or-later`; a license file alone cannot say which → **unscheduled**; trigger: the
  spec edit that publishes the license list (P7-T3), decide then
- **A renamed definition is not found by `--latest` unless a link points back** — its identity
  changed with its name; its shape did not, and a shape-based rule through the index would find
  it → **unscheduled**; trigger: a real `--latest` miss on a rename with no `from` link
- `--latest` on a **locator uses the bare clone's HEAD** as the default branch, which is the
  origin's default at clone time; a repository that changes its default branch later keeps the
  old one until the cache is cleared → **unscheduled**; trigger: it happens
- `latest()` resolves the pinned page and then the head page through `resolve()`, so **`--latest`
  stores both in the object cache** — intended, but it means the head page's location is
  recorded as "seen" without anyone linking to it → **standing**; the index now records
  locations independently, so this only affects the object cache
- **`update` on a vendored module does not follow through to the user's `vendor=` link**: after
  the module's root moves, `check` on the user's file reports drift ("the module holds X; the
  link says Y") and the person re-expands → **unscheduled**; trigger: the first real `--package`
  project that runs `update`
- **`python3 -I` implies `-P` since 3.11**, so a vendored `cttp_vendor` import — like any local
  package — needs the project directory on `sys.path`; plain `python main.py` provides it,
  `test_package.py` runs with `-E -s`. The plan's P3-T5 acceptance says `-I`; this is the honest
  reading → **unscheduled**; trigger: Leo deciding whether the vendored import should carry its
  own `sys.path` line
- **A script page with a top-level blank line between statements** still ends its block early
  under the block rule (the P1-T4 follow-up); the closure only ever inlines definitions and the
  root, so it bites only when the root is such a script → **unscheduled**; trigger unchanged
- **`fold` treats a `from` block as foldable** (derived code is still a block with a stamp) —
  spec §7 says "expanded code"; revisit if a person wants forks visible in the folded view →
  **unscheduled**; trigger: a complaint

- **A stamped `is` block that is a script, not a definition, is not a page of the consumer**
  (`# cttp: hello-world@… id=…` + `print(...)` in `main.py`): `who` sees the link, `dups` does
  not see the copy, since a block page would collide with the file page's `(repo, sha, path,
  NULL)` location key → **unscheduled**; trigger: wanting `dups` to find copies of script
  snippets (a block location would need its own symbol-like key, say the link's line)
- **The crawl re-parses a Python file once per definition** (`extract(path, text, symbol)` each
  time), so a file with many definitions costs O(definitions × file) → **unscheduled**; trigger:
  a crawl slow enough to notice (this repository's 64 files crawl in seconds)
- **"Current" is the most recently crawled revision of a repository**, so `cttp index crawl
  --rev <older>` makes that older rev current for `dups`, `rank`, `search` and the viewer →
  **standing**, by design; say so in the spec at P7-T3
- **The viewer's `/d/…`, `/r/…` and `/dups` routes shadow registry names `d`, `r`, `dups`** →
  **unscheduled**; trigger: someone claiming such a name (spec §8's naming rules could reserve
  them)
- **`runner = CliRunner()` is defined thirteen times across the test files** — `cttp dups`'s
  first real finding on this repository; a `conftest.py` fixture would do → **unscheduled**;
  trigger: the next time a test file is touched for another reason
- **`--latest` is not an MCP tool** (nor are the writing commands); an agent that wants to
  follow a link forward shells out to `cttp resolve --latest --json` → **unscheduled**; trigger:
  an agent task in P8 that needs it (adding a `latest` tool is one function plus its schema)
- **The viewer's `/dups` page links each location's `name` to `/<name>`** as if it were a
  registry name, but `dups` locations carry the *definition's* name (the schema now says so) —
  a dead link for every group → **unscheduled**; trigger: the next viewer session (drop the link
  or look the registry name up per location)
- **Spec §3 says a definition is "a function, class or constant"**; the C extractor adds `type`
  and `macro` kinds, and names tagged types `struct.<tag>` — the spec should say so, and §12
  test 1's wording ("four temperature decoders… two verbatim copies") should match
  `expected.json` → **P7-T3** (the spec edit that publishes)
- **`cttp resolve` on a real locator clones the whole repository into the git cache** — for
  `github.com/torvalds/linux` that is the entire kernel; the corpus is reachable only through the
  index and its local clone (`dups`, `who`, `search`, `resolve sha256:…`). A locator whose
  repository is registered with a `local_path` could resolve through that clone instead →
  **unscheduled**; trigger: wanting `resolve <corpus locator>#symbol` to work (the P6-T1
  acceptance used a small repo built from the two lm75 files)
- **A C page has no derived references and no free names**, so the closure of a C file would
  inline it beneath a `#` link happily (the write side is Python's by spec §3; a `//` link in a
  `.c` file expanding a C script page is tested and fine) → **unscheduled**; trigger: someone
  expanding a C definition into a Python file
- **Kernel constructs the grammar does not know** (`MODULE_DEVICE_TABLE(…)`, `module_init(…)`,
  `static IIO_CONST_ATTR(…)`) become `ERROR` nodes: 27 top-level ones across the 736 files, the
  definitions around them found, their own text regex-tokenized for the shape → **standing**
- **`default_branch` of a local clone at a detached HEAD** with no origin HEAD is the tag (or
  `HEAD`); `--latest` rule 3 and the viewer treat it as a branch name → **unscheduled**; trigger:
  a `--latest` against such a repository
- **The line-level shape abstracts every identifier within a line**, so `return $0 ;` and
  `$0 = $1 ( $2 ) ;` make 92 % of substantive lines "shape-identical"; the table by minimum
  tokens shows how much is short lines. A shape over windows of several lines would say more →
  **unscheduled**; trigger: wanting the vision's headline to be about copied *blocks*
- **The viewer's `/dups?shape=1` (7.6 MB) and `/r/github.com/torvalds/linux` (10 MB) pages
  render the whole kernel-scale index in one response** — under a second server-side, but a
  heavy page; paginate or cap groups when it hurts → **unscheduled**; trigger: the viewer
  becoming a daily tool over a large index
- **`open_index(create=False)` used to run the schema script and take the write lock**, so the
  viewer answered 500 for the two minutes a corpus crawl held the lock; fixed this session
  (readers skip the script; 5 s busy timeout) — a test with a concurrent writer is still missing
  → **unscheduled**; trigger: the next change to `open_index`
- **The exported site's header links to `/dups`, search and `/d/…`**, which need an index a
  static host does not have (404 on Pages), and shows the registry's path (the CI checkout's);
  the name page's *who links here* is whatever index the exporting machine had → **unscheduled**;
  trigger: cttp.ai being live and someone clicking them (an `exporting` flag on the templates
  would drop the index navigation and name the registry by URL)
- **`name claim` pushes `claim/<name>` with `--force`**, so a second claim of the same name
  replaces the branch (and the open PR's commits) rather than failing → **standing**, by
  design; a stale claim branch is never worth keeping
- **The `verify` workflow checks only the names a PR adds or changes** (`--diff-filter=AM`); a
  PR that deletes an entry, or edits `snippets/`, runs no check on it → **unscheduled**;
  trigger: the first deletion PR (a check that the deleter is the owner would need the PR
  author's identity, which `gh` can give the workflow)
- **`name show` is not an MCP tool** (nor `verify`) → **unscheduled**; trigger: an agent task
  in P8 that needs an entry's owner or labels
- **`tests/fixtures/registry/` now mirrors the public repo's `main`, not its `v1` tag** (the
  fixture's `cttp.toml` declares `hello-world`; the public `v1` commit does not). The fixture's
  own `v1` tag is on the fixture content, so `hello-world@v1` resolves the same either way →
  **standing**; overview §6 says `main`
- **A search hit's one `address` is the identity's most recently committed current place**,
  so a definition copied into another repository (the consumer's expanded `deep`) can show the
  copy's address rather than the origin's; the origin is knowable from the copy's backlink. The
  viewer test asserted the origin and flaked (about one run in five: pyrepo's and the consumer's
  commits straddling a second boundary flipped the tie-break) — fixed 2026-09-05 to assert the
  identity → **unscheduled**; trigger: wanting search to prefer the origin (follow the `is` /
  `from` backlink among the places)
- **`resolve` through the index for a file that is its one definition says `kind: function`**
  (the definition's view won the `definitions` row) where git would say `script` for the file
  address — same text, same identity → **unscheduled**; trigger: it confuses someone
- **The links arm did not reach for a cttp tool once `Read` was available** (smoke run: two
  `Read`s, one `Edit`, the test) — on a two-file repository there is nothing to search for. The
  tools must earn their keep on repositories where reading everything is the expensive path;
  if they still go unused, an arm-specific line in the prompt naming them is the next lever,
  and a confound to state in the report → **P8-T2** (task design), **P8-T3** (the caveat)
- **The links arm's deny list catches `| tail -40` and `| head`** in a pipeline with the test
  command (each subcommand is checked); the agent recovers by running the plain command, at
  the cost of a turn → **standing**; the read-only set has to stay denied
- **`prepare_index` crawls only the task's checkout**; a cross-repository task needs the second
  repository registered and crawled too, and an impact question needs a grader that compares
  the answer with `who` → **P8-T2**
- **`repo.source` as a git repository is cloned with `git clone`**, so the P8-T2 repositories
  must be on disk before a run (nothing fetches them yet) → **P8-T2**
- **`results/` is committed** (the smoke run is 76 KB with its streams); ninety runs of real
  tasks will be tens of MB of streams — decide whether streams stay in git or only the records
  → **P8-T3**

## Build history

Keep only the **five most recent** session entries. Older ones get deleted, not archived — `git log`
is the archive, and a bloated history taxes every future session start.

- **2026-09-05 (seventeenth session) — P8-T1 built: the benchmark harness, and the arm design
  amended on evidence.** The flags were checked against `code.claude.com/docs/en/headless` and
  the CLI reference and probed on Claude Code 2.1.261 with two haiku runs before writing:
  `--tools` restricts the built-ins and keeps MCP tools; `--disallowedTools "Bash(cat *)"`
  beats `dontAsk`'s read-only auto-approval; `--setting-sources ""` drops `~/.claude`'s
  settings; a `rate_limit_event` in the stream carries the five-hour and seven-day
  utilizations; the result object's `usage` is the main thread's cumulative count and
  `modelUsage` adds side requests. Decisions: **stream-json, not json**, so `system/init` (tools,
  MCP status), every tool call, denials and the rate-limit event are recorded with the result
  (the last line is the same result object); the per-run world is built the test suite's way
  (bare remote + clone + `[remotes]`) so the checkout has a locator without a network; the
  links arm gets a per-run index and cache; results are committed with their streams. **The
  smoke run changed the plan's arms:** without `Read`, the links arm found the bug through
  `fold`, `search`, `closure`, `resolve` and `who` and then could not apply it — `Edit` and
  `Write` refuse a file the session has not read — and burned 41 turns and 471k tokens; both
  arms now have `Read` and differ in how code is *found* (the cttp tools against the shell's
  `grep`/`find`/`cat`, which this Claude Code has no `Grep`/`Glob` tool for). With `Read`: links
  pass, 36,787 tokens, 6 turns; baseline pass, 29,428 tokens, 5 turns — and the links arm
  never called a cttp tool. Found and fixed on the way: two MCP calls in one turn raced to clone
  one repository into the git cache ("destination path already exists"); `gitcache._clone` now
  clones into a temporary sibling and renames. `tests/test_bench_agent.py` (10 tests, one a
  replay of each committed record) and a concurrent-clone test. `pythonpath = ["."]` in
  `pyproject.toml`. The plan's P8-T1 entry carries the amendment.

- **2026-09-05 (sixteenth session) — Phase 7 built: P7-T1 `name show` and `name claim`,
  P7-T2 `name verify` and federation, P7-T3 `serve --export` and the cttp.ai default.** Three
  commits, plus two on an unpushed `p7` branch of the registry clone. Decisions: the target's
  declaration is `name = "x"` as spec §8 says, plus `names = […]` for a repository that is the
  target of several (the registry repo itself: its own `name` is `cttp-registry`, and it hosts
  `hello-world`), written into the spec; the **owner is derived from the locator**
  (`host/owner`), never an option, because "the account that proved control of the target" is
  exactly that; a claim opens its PR from a **temporary worktree** so the registry clone's
  checkout is never dirtied and a merged PR pulls cleanly (an uncommitted `names/<name>.toml` in
  the working tree would have collided with the merge); `--no-pr` writes into the working tree
  on purpose, since `LocalRegistry` reads it and the name works at once; a same-owner re-claim
  is `updated`, not refused. The schema went to **3** once and was re-pinned as commands were
  added within the session. Found on the way: a `git fetch` subprocess in a test reached GitHub
  — the socket guard covers Python only — so `conftest.py` sets `GIT_ALLOW_PROTOCOL=file`;
  `serve --registry` leaked `CTTP_REGISTRY` into the process, invisible while `serve` ran
  forever, visible the moment `--export` returned. The export goes through the ASGI app with
  the test client so "identical to the live responses" is by construction, not by a second
  renderer; the running dev server, started last session, printed `schema_version: 2` against
  the export's 3 — restarted. The workflows first installed cttp from the private repo with a
  token secret; a fork's PR gets no secrets, which would have broken every outside claim, so
  **`cttp` was made public** (history scanned for secrets first) and the token dropped.
  `pages.yml` writes `CNAME` and `.nojekyll` itself so the export stays host-neutral.
  The outward-facing steps were done on Leo's word later the same session: the registry's
  `main` pushed, Pages enabled from Actions with the `cttp.ai` domain, and the P7-T2 acceptance
  run for real — PR #1 opened by the tool itself passed `verify` (the `resolves` check ran a real
  resolution in CI); PR #2, a hand-written undeclared name, failed on `declaration` and was
  closed, then #1 merged and the fixture re-synced (one test asserted the old aligned file
  format — fixed). The fresh-machine half of the P7-T3 acceptance ran clean with cttp.ai
  missing and localhost answering. The DNS is Leo's and blocks nothing. Last: on Leo's
  question about API cost, the **P8 harness was re-planned onto Claude Code headless (`claude
  -p --output-format json`) under his subscription login** instead of the Anthropic SDK —
  checked against the current docs, which say ordinary individual use of Claude Code and the
  Agent SDK is what the login is for; `plan.md`'s decision table, pinned stack, P8-T1 and P8-T3
  record it, with the caveat that both arms then run inside Claude Code's harness. The
  session-end run caught a flake — `test_definition_repo_dups_and_search_pages`, one run in
  about five — traced to git's one-second commit timestamps deciding which of two places a
  search hit shows; the test now asserts the identity (follow-up filed on the query).
- **2026-09-05 (fifteenth session) — Phase 6 end to end: P6-T1 the tree-sitter extractor,
  P6-T2 the corpus and acceptance test 1, P6-T3 the measurement.** Three commits. P6-T1:
  `tree-sitter` 0.26.0 segfaulted on nodes returned from query captures (a `Point` read from
  freed memory gave spans like `(9928, 9928)` before the crash); pinned `<0.26` and, belt and
  braces, every row is computed from `start_byte`/`end_byte`. Decisions: tagged types are
  addressed `struct.<tag>` / `enum.<tag>` / `union.<tag>` (C's tag namespace is separate, and the
  symbol grammar is dotted identifiers); kinds `type` and `macro` were added rather than
  stretching `class`; the C shape keeps keywords and primitive types and abstracts every
  identifier node, and a raw macro body or `ERROR` text is regex-tokenized with comments cut
  out; a comment directly above a definition is its docstring unless it is a link line; the
  first of two `#ifdef` definitions wins. `shape()` took a `language` argument instead of a
  second function, so the crawl and `resolve` stopped special-casing Python. A refusal of C
  pages in the closure was tried and reverted: `test_check.py` expands a C script page beneath a
  `//` link in a `.c` file on purpose. P6-T2: the preserved copy's `urls.txt` said `master`,
  2026-09-04; hashing every file as a git blob against the GitHub contents API showed the five
  directories unchanged on master from the rtc merge `275bc4eedf2c` (2026-08-28) through
  2026-09-05, so **v7.3-rc1** is the pin. Reproducing the original fetch exactly needed
  non-cone sparse patterns (cone mode takes `hwmon/pmbus` and the 12 files of `drivers/iio`
  itself) ordered shallowest-first so an exclusion never undoes a deeper inclusion; the result
  is byte-identical to the preserved copy (moved to `corpus-preserved/`, not deleted). The crawl
  of a blobless clone would have fetched the whole kernel blob by blob, so a sparse checkout is
  crawled as the files it has; the acceptance test runs git with `GIT_ALLOW_PROTOCOL=none` so a
  lazy fetch would fail loudly. Crawl: 799 files, 34,087 pages, 33,811 identities, 2 m 14 s,
  nothing skipped. The vision's own example groups were not recoverable; `expected.json` records
  what the tool finds (four `(s8)reg * 1000` decoders by shape, two verbatim pairs) and says so.
  A `cttp resolve github.com/torvalds/linux@v7.3-rc1/…` typed by hand started cloning the whole
  kernel into `~/.cache/cttp` — killed, cache dir removed, follow-up filed. P6-T3: the
  line-level numbers came out 92 % / 42 % under the stated method, and 89/31, 83/23, 66/16 over
  lines of ≥3, ≥5, ≥8 tokens — nowhere near 37/14 under any reading tried, so the vision was
  amended to the recomputed figures with the method named, and `expected.json` keeps the old
  numbers under `vision_before`. Slow corpus tests are deselected by default (`addopts`). The
  viewer answered 500 during the real-index crawl (`database is locked`: a read-only open ran
  the schema script); readers now skip it.
- **2026-09-05 (fourteenth session) — Phase 5 end to end: P5-T1 the `--json` schemas, P5-T2
  `cttp mcp`.** Two tasks, one commit. P5-T1: `schemas.py` was written from the code's actual
  outputs — every `to_json()` and query dict read first — as a small schema language rather than
  TypedDicts, because one definition had to do three jobs at once: validate strictly (extra
  fields are errors, so shape drift is caught the day it happens), render JSON Schema for the
  MCP tools' `outputSchema`, and render the Markdown doc. Load-bearing decisions: **every
  object is stamped** with `schema_version` at the one place the CLI prints (`emit`) and at the
  contract route, so the registry contract and `cttp resolve --json` stay byte-identical;
  **a schema change is a deliberate act** — a fingerprint of every JSON Schema is pinned per
  version and the test's failure message says what to do; **the live and indexed `closure` are
  one object** (`source`, `roots`, `missing`), which settled the spec §9 follow-up and gave the
  MCP tool one output schema; `dups` groups got a fixed `key`/`key_full` so `--shape` is the same
  schema; `expand`/`add`/`fold` wrap their per-file map in `files` and `crawl` its list in
  `crawled`, so every object is an object with a version. The schema test builds a fixture world
  and runs all 24 command shapes for real, including every report status. P5-T2: the official
  `mcp` SDK turned out to be 2.x (`MCPServer`, not `FastMCP`), so the server hands the SDK
  pre-built tools with the P5-T1 JSON Schema set as `output_schema` and returns
  `CallToolResult`s itself — the only way to keep the tool's object byte-identical to the CLI's
  (the SDK would otherwise wrap a `dict` return in `{"result": …}`). The test asserts that
  equality per tool through the SDK's in-memory client. By hand: the real stdio server listed
  six tools and answered `who hello-world` from the real index; Claude Code (Sonnet, via a
  scratch `--mcp-config`) called `mcp__cttp__who` and answered correctly. Spec §9 amended
  (schemas, `closure` in both modes); `docs/json-schemas.md` registered in `CLAUDE.md`. Server
  restarted on the new code. 275 → 295 tests.
- **2026-09-05 (thirteenth session) — spec §8 patched; Phase 4 end to end: P4-T1 the index
  schema and crawl, P4-T2 the six queries, P4-T3 `--latest` rule 3 with acceptance tests 2 and
  3, P4-T4 the viewer over the index.** Five commits. First the spec: §8 gained the
  `%23<symbol>` route and a field table for the resolver's object, checked row by row against
  the live server. Then the index. Load-bearing decisions: **identity is the key of
  `definitions` and `locations` is its own table**, so "the same code in three places" is one
  row plus three; **a Python file is a page too** (the whole-file page beside its definitions),
  which is what makes a script snippet like `hello-world` indexable — and what made a file that
  is exactly one definition share that definition's identity, so the definition's view (kind,
  name, signature) wins the row and `dups` never pairs a file with its own only definition;
  **an asserted link's source is the page it stands for** — the definition in the block beneath
  it (spec §4), not the file — so a verbatim copy links back *as itself* and `who`, `rank` and
  `--latest` all see provenance the same way; **the crawl never fetches a repository it was not
  given**, so target identities are filled in afterwards from what the index knows (a stamp's
  `id=`, a pinned locator seen at that rev, a name's snapshot) and left NULL otherwise, and
  `who` falls back to place-matching only for those; **"current" means most recently crawled**,
  with `rowid` breaking same-second ties for history order. `--latest` asks the index last: the
  same identity at another repository's current revision first (derived, exact), then an
  `is`/`from` backlink (`is` before `from`, newest commit first). Found on the way: a
  documentation line that *looks* like a malformed link (`links.py`'s own docstring, spec §4's
  grammar) made the crawler drop the whole file — now the line becomes a bare comment with a
  skip note, and `--force` exists to crawl a revision again; two commits in the same second
  need `rowid` to order; a label rev in a query address must be resolved for real; headless
  Chrome here needs `--no-sandbox`. By hand on the real index: this repository and the public
  registry crawled (670 identities, 1,093 links), `dups` finding `runner` ×13, `who hello-world`
  listing spec §7's examples, every page at 1200px and 390px. 249 → 275 tests.
## How to run

```bash
export PATH="$HOME/.local/bin:$PATH"          # uv lives here
uv sync                                        # once; creates .venv
uv run pytest -q                               # 344 tests, no network; -m slow adds the corpus tests (~2.5 min)
uv run ruff check . && uv run ruff format --check .

git clone https://github.com/leorinaldi/cttp-registry ~/.local/share/cttp/registry   # once
uv run cttp config                             # first run writes ~/.config/cttp/config.toml; shows it
uv run cttp serve                              # http://localhost:3120  (Ctrl-C to stop)
curl -s localhost:3120/hello-world.json        # the contract; /hello-world is the page
uv run cttp resolve hello-world --json         # registry: http://localhost:3120 when up, the clone when down
uv run --project ~/Claude/cttp cttp …          # from any other directory (not `uv --directory`, which changes cwd)
```

The demo (acceptance test 4), from any directory with the server up or down:

```bash
printf '# cttp: hello-world\n' > hello.py
uv run cttp expand hello.py && cat hello.py    # stamped line + print("hello world!")
/usr/bin/python3 -I hello.py                   # runs with cttp uninstalled
uv run cttp run hello-world                    # runs with no file at all; asks the first time (or --yes)
uv run cttp check hello.py                     # exit 0
sed -i 's/hello world!/goodbye/' hello.py && uv run cttp check hello.py   # drift, exit 1
uv run cttp --json resolve hello-world         # what an agent sees
uv run cttp resolve cttp:github.com/leorinaldi/cttp-registry@main/snippets/hello_world.py   # the locator form, no registry needed
uv run cttp resolve 'github.com/pallets/itsdangerous@main/src/itsdangerous/encoding.py#base64_encode' --json   # one definition of any public repo
```

Phase 3, against the `pyrepo` fixture served from a scratch directory (the tests build the same
world in `tmp_path`; `git_repo_from` + a bare clone under `remotes/github.com/leorinaldi/` and a
config whose `[remotes]` points there — see `conftest.py`):

```bash
uv run cttp closure github.com/leorinaldi/pyrepo@main/lib.py#top          # four definitions, deps first
uv run cttp add github.com/leorinaldi/pyrepo@main/lib.py#top main.py      # link + expansion in one step
printf '\nprint(top(3))\n' >> main.py && /usr/bin/python3 -I main.py         # 9
uv run cttp fold main.py                                                  # four link lines
uv run cttp check main.py && uv run cttp update main.py --all             # ok; unchanged until the origin moves
uv run cttp expand --package big.py                                       # over budget → cttp_vendor/<module>.py
uv run cttp check --fix drifted.py                                        # drift → cttp-from:
```

Phase 4, the index (the real one already holds this repository and the public registry):

```bash
uv run cttp index add github.com/leorinaldi/cttp-registry   # a locator; or a local clone's path
uv run cttp index add .                                     # this clone, through its origin remote
uv run cttp index crawl                                     # every registered repo at its head (--rev, --force)
uv run cttp index status
uv run cttp who hello-world                                 # backlinks, by relation and origin
uv run cttp dups && uv run cttp dups --shape                # the same code, or the same shape, in several places
uv run cttp search registry                                 # name, signature, docstring (FTS5)
uv run cttp history github.com/leorinaldi/cttp-registry@main/snippets/hello_world.py
uv run cttp rank --limit 10
uv run cttp closure --indexed github.com/leorinaldi/cttp@main/src/cttp/resolve.py#latest
uv run cttp resolve --latest <pinned address>               # rule 3 through the index when 1 and 2 miss
```

Phase 5, the agent interface:

```bash
uv run cttp --json who hello-world | head -3               # every object starts with "schema_version": 1
uv run cttp mcp install                                    # prints: claude mcp add --transport stdio cttp -- …/.venv/bin/cttp mcp
uv run cttp mcp install --claude-code                      # runs it (writes Claude Code's config) — Leo's call
uv run cttp mcp                                            # the server itself, over stdio; Ctrl-C
uv run python -m cttp.schemas                              # regenerate docs/json-schemas.md after a schema change

bash bench/drivers/fetch.sh                                # the corpus: Linux v7.3-rc1, five directories, ~60 MB
uv run cttp index add bench/drivers/corpus && uv run cttp index crawl github.com/torvalds/linux   # ~2 min
uv run cttp dups --shape | head                            # the four eight-bit decoders are one group
uv run python bench/drivers/measure.py                     # the line-level duplicate figures
uv run pytest -m slow tests/test_acceptance_drivers.py     # acceptance test 1 and the measurement, as tests
```

Phase 7, the registry as a service:

```bash
uv run cttp name show hello-world                          # the entry (owner, target, labels) and its resolution
uv run cttp name claim <name> --target host/owner/repo/path.py --description "…" --no-pr   # writes names/<name>.toml into the clone
uv run cttp name claim <name> --target host/owner/repo/path.py    # the same on a claim/<name> branch + `gh pr create`
uv run cttp name verify                                    # every name's checks; exit 1 on a failure (the registry's CI)
uv run cttp serve --export /tmp/site                       # the contract as static files (what pages.yml publishes)
```

Phase 8, the benchmark (uses Leo's Claude Code login; nothing else):

```bash
uv run python -m bench.agent.harness --list                # the tasks
uv run python -m bench.agent.harness --check-graders       # each grader fails the bug and passes the solution
uv run python -m bench.agent.harness --task smoke-pyrepo   # both arms once; results/<today>/smoke-pyrepo/<arm>/1.json
uv run python -m bench.agent.harness --runs 3 --wait-for-reset   # every task, both arms, three runs, sleeping through limits
uv run python -m bench.agent.harness --replay bench/agent/results/2026-09-05/smoke-pyrepo/links/1.json   # no subscription used
uv run python -m bench.agent.report bench/agent/results/2026-09-05   # the table; writes report.md there
```

`scripts/make_local_registry.py` still builds an offline registry from the fixture if needed.
The server was left running in the background (`.local/serve.log`); probe
`curl -s -o /dev/null -w '%{http_code}' http://localhost:3120/` before starting another. **It
runs the code it was started with** — after a change to `server/` it has to be restarted
(`pgrep -af 'cttp serve'`, then `kill <pids>` in a separate command).

## Config / secrets

- `.env` — not created. Gitignored by design; never commit it.
- `~/.config/cttp/config.toml` — the tool's configuration (see `config.py` above). Environment
  knobs: `CTTP_CONFIG` (config file path), `CTTP_HOME` (caches, default `~/.cache/cttp`),
  `CTTP_REGISTRY` (one registry, replacing the list), `CTTP_INDEX` (the index file, default
  `~/.local/share/cttp/index.db`). Tests set `CTTP_CONFIG`, `CTTP_HOME` and `CTTP_INDEX` to
  `tmp_path`.
