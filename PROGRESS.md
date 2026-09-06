# PROGRESS — cttp

cttp — *code text transfer protocol* — is a protocol that sits on top of existing programming languages
and lets code point at code: every definition gets an address, references are links rather than imports,
and an index answers who links where. Rationale: [`docs/vision.md`](docs/vision.md).

**Status: PHASES 0 TO 8 COMPLETE — THE PLAN IS DONE (the `cttp.ai` DNS is Leo's; localhost stands in until then). THE BENCHMARK'S HEADLINE DEFECT IS CLOSED IN BOTH HALVES AND RE-MEASURED TWICE: THE IMPACT FAMILY 16.28x → 6.65x → 2.40x. A FOURTH SWEEP READ 3.26x WITH NOTHING THAT SHOULD HAVE RAISED IT — AT THREE RUNS PER ARM THE BENCHMARK CANNOT RESOLVE A CHANGE OF THIS SIZE. `WHO` NOW FOLLOWS A RE-EXPORT TO ITS DEFINITION (2026-09-06): CLICK'S UNIDENTIFIED LINKS 1,422 → 50, `ECHO` 31 → 290 BACKLINKS AND COMPLETE; `ATTR.S` 22 → 348. AND AN ABSOLUTE IMPORT NO LONGER LETS A SIBLING MODULE SHADOW A STDLIB NAME (2026-09-06): CLICK 50 → 31, RICH 100 → 46, CTTP ITSELF 38 → 15, PURELY BY SUBTRACTION. **THE BUILD IS DONE; WHAT IS NOT DONE IS CONTACT WITH REAL FILES — THE NEXT STAGE IS LEO'S: BUILD THE PAGES.**  Phase 0
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
tool calls and grades, a `--replay` dry run, and the smoke task passing in both arms. **P8-T2 the
task set** (2026-09-05) — fifteen tasks over `click`, `attrs` and `rich` (cloned by
`bench/agent/fetch.sh`): five real merged fixes with the commit's tests as the hidden grader,
five cross-repository reuses graded by hidden tests plus a link check, five impact questions
graded exactly against `who`; `--check-graders` passes all sixteen (~2½ min). **439 fast tests
green plus 17 `slow`** (the corpus, and the graders' acceptance over the real clones), ruff clean.

_Last updated: 2026-09-06, session end (an absolute import is rooted where Python roots it — an ancestor holding an `__init__.py` is a package, not an import root; click 50 → 31 unidentified links, rich 100 → 46, cttp itself 38 → 15, nothing gained or altered. The plan is complete and the next stage is Leo's: crawl GitHub for repeated code and build the pages)._

> **Read [`docs/overview.md`](docs/overview.md) first** — it is the lay of the land. This file is
> only *where we are*: state, next steps, follow-ups and recent history.

## Next session — suggested next steps

**The plan is complete, and the build is not what is missing.** Phases 0–8 are done: the address
grammar, both extractors, the resolver, the materializer, the index, the viewer, the registry as a
service, the `--json`/MCP agent interface and the benchmark. 440 fast tests, 17 slow, four
acceptance tests, ruff clean. What has never happened is **contact with real files** — nothing
outside this repository uses cttp, `cttp.ai` is not live, and no one has written a link by hand and
lived with it. Spec §14 defers nearly every open design question with that same phrase, so the
design is waiting on use, not on more building.

### The next stage is Leo's: build the pages — the "coding internet" (stated 2026-09-06)

Leo's direction, to be planned by him before the next build session. The shape of it:

> **Crawl GitHub for highly common / repeating code, and build pages for those snippets.**

The index already answers the first half of this — `dups` is `GROUP BY identity`, `dups --shape`
finds near-duplicates, and the crawl reads a repository at a commit into identities and places. The
driver corpus proved it at scale (~34,000 pages of the kernel; 42 % of driver lines verbatim
duplicates, 92 % by shape). What does **not** exist yet:

- **A crawl that is not given its repositories.** `cttp index add` takes a locator or a local
  clone by hand, and `crawl` never fetches what it was not given (overview §4) — deliberate, and
  exactly what a GitHub-wide crawl must change. Where the repository list comes from (a language
  and star query, a package index's top N, the GH Archive) is the first design decision.
- **A judgment about which duplicate deserves a page.** `dups` returns groups; a page needs a
  *name*, a canonical origin among the copies, a description and an owner. Today a name is claimed
  by proof of control (the target's `cttp.toml`), which nobody but the target's owner can do — so
  a registry of found snippets needs either a second entry kind, or a namespace that does not
  claim to be owned.
- **A page surface for a snippet with no home.** The viewer renders `/d/<identity>` from the index
  already; a published page wants the origin, the copies, the shape-siblings and the license — and
  the export (`serve --export`) only renders the registry contract, not `/d/…`.

Nothing here is scheduled; the next session should start from Leo's plan, not from this list.

### If the direction changes, these are what remain

In priority order — all four are honest open items, none is blocking:

1. **The benchmark cannot resolve its own effects**, and that is the limiting factor on every
   question it is asked. Three runs per arm; `im-nested-chain-click` spanned 141k–569k tokens and
   the impact family's ratio moved 2.40 → 3.26 on a change that should have lowered it. Cheapest
   first: report the mean beside the median; raise `--runs` for the impact family alone; or a
   paired statistic per task. Until one lands, **no change under ~20 % should be argued from a
   ratio here.** Note that the last two real defects were both found by *looking* at what stayed
   unidentified, not by measuring.
2. **A definition row keeps the first crawl's derived metadata.** `INSERT OR IGNORE` means
   `--force` refreshes locations and links but not `imports`, `unresolved`, signature or
   docstring, so the viewer's *third party* line can show a classification the extractor no longer
   makes. This session's rule staled every existing row again — as the follow-up predicted.
   Properly, `imports`/`unresolved` are per-place and belong on `locations`.
3. **The closure keeps a function-local relative import** (`click.formatting.wrap_text` does
   `from ._textwrap import TextWrapper` in its body; `expand` inlines the definition and leaves
   the line, which fails at run time). Found in P8-T2, still open; spec §3's refusal list grows
   one line.
4. **Publish the benchmark.** Leo asked whether the results could be seen on a page. Nothing
   benchmark-related is in the viewer's index by design (each run indexes into its own throwaway
   directory), so this would be a page of its own, not a viewer route.

Still Leo's, not blocking: the **DNS for `cttp.ai`** (apex `A` records 185.199.108.153,
185.199.109.153, 185.199.110.153, 185.199.111.153, or an `ALIAS` to `leorinaldi.github.io`);
today the domain points at a parking host and `https://cttp.ai/hello-world.json` is a 404 the
tool treats as a miss. When the records exist: `gh api -X PUT
repos/leorinaldi/cttp-registry/pages -f https_enforced=true`, then compare
`curl -s https://cttp.ai/hello-world.json` with `localhost:3120/hello-world.json`. This is the one
item that blocks a real user story — until it is live the public registry is a localhost story, and
the pages above would have nowhere to be. Also pending Leo: whether
`bench/drivers/corpus-preserved/` (13 MB, reproduced byte for byte by `fetch.sh`) can be deleted,
and whether the stale `/tmp/cttp-bench-*` directories left by killed runs can go.

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
  (relative imports from the file's package; an absolute one against the file's **import roots** —
  `_import_roots`, **2026-09-06**: the ancestor directories that do not themselves hold an
  `__init__.py`, since a package's own directory is never on `sys.path`, so `from types import
  TracebackType` inside `src/click/` is the stdlib and not `src/click/types.py` — and then the
  repository's **source roots**, `SOURCE_ROOTS = ("src",)`, counted only when the repository has
  that directory and tried last, so a src-layout's `tests/` reach their package while flat layouts
  and nearer ancestors are unaffected; longest module prefix wins), plus
  sibling definitions in the same file; a parameter shadows a module-level import. A script's references are every import it makes; a definition's are the
  names it uses. **2026-09-06: `Forwarder(files, read)`** follows a reference through
  re-exports to the definition it means (`exports()` lists what a module binds at its top level
  by importing, aliases of those, star imports and a literal `__all__`; `forward(ref)` walks
  them, stops at the first file defining the symbol's head, keeps a member path, never follows
  `__getattr__` or a call, ends a cycle); `extract.forwarded(page, files, read)` applies it to a
  page's refs. The resolver calls it in `_fetch_page` and `_page_at`, the crawl per ref. **P3-T1:** `Ref.name` is the text the page reaches a reference by (`REG_BITS`,
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
  license at that rev, crawled-at, file count, `skipped` JSON and `unmapped` JSON — what the
  crawl could not read and the imports it could not map, which `who`'s coverage reports), `definitions` (**identity is the key**: shape,
  language, kind, name, signature, docstring, lines, source, imports JSON, unresolved JSON),
  `locations` (identity at (repo, sha, path, symbol) with its span — three places are three
  rows against one definition), `links` (source identity and where it was; the target address
  as written *and parsed* — form, name, locator, path, rev, symbol, `id=`; the target identity
  when the index can tell; relation `is`/`from`/`see`/`ref`; origin; description, derived flag,
  fields JSON, indent; a derived ref's `name`), `names` (registry entries snapshotted at crawl),
  plus `definitions_fts` (FTS5, porter stemming) for search. `open_index(path, create=False)`
  raises `IndexingError` for a missing file — a query never creates an empty index. **Migration:**
  `ADDED_COLUMNS` + `migrate()` bring an older file forward by `ALTER TABLE`, run by writers only;
  a reader calls `has_column()` and reports `null` rather than taking the write lock.
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
  them, **each forwarded through re-exports first** (`Forwarder` over the revision's Python
  files with a memoized `git cat-file` reader, primed with every file the crawl reads;
  `Crawled.forwarded` counts them and the CLI prints `N forwarded`). A **malformed link line** (prose like `# cttp: <address> [key=value]`) becomes a bare
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
  reference to itself does not. **`forward()`** is `--latest`'s rule 3 (P4-T3). **`coverage(conn, target)`** is what a `who`
  answer is an answer over (spec §6): `searched` (every crawled revision — current or not, its
  files, pages, links and the top-level directories that produced pages), `skipped` / `unread` /
  `ignored_links` from the revision's own record, `unresolved_targets` with
  `unresolved_matching` (those naming *this* address — the only part of the total that concerns
  the question), `unmapped_imports` read from `revisions.unmapped`, the static `WHO_CAVEATS`, and
  `complete` — true when this answer has no gap, `null` when the index predates the record.
- `schemas.py` — **P5-T1.** The one definition of every command's `--json` output: a small
  schema language (`S` nodes: object, array, map, string, integer, number, boolean, enum, ref;
  `.null()`, `.derived()`, `.asserted()`, `.about()`), shared objects in `DEFS` (`page` — the
  contract object; `location`, `ref`, `link`, `imports`, `node`, `missing`, `expand_report`,
  `check_report`, `update_report`, `fold_entry`, `backlink`, `by`, `dup_group`, `hit`,
  `revision`, `ranked`, `crawled`, `repo_status`, `closure`, and P8's `coverage`,
  `searched_revision`, `unmapped_import`), and `COMMANDS` — 24 entries
  (`version`, `config`, `resolve`, `resolve --latest`, `closure`, `expand`, `add`, `check`,
  `update`, `fold`, `run` (no object: the program's output), `cache status|clear`, `index
  add|crawl|status`, `who`, `dups`, `search`, `history`, `rank`, `mcp install`, `error`), each
  with usage, summary, *when*, notes and schema. `stamp()` puts `schema_version` (now 4) first on
  every object — `cli.emit()`, `cli.fail()` and the server's `/<name>.json` all go through it.
  `validate()` is strict (missing, extra, type, enum, null); `json_schema()` renders draft
  2020-12 (inline, or with `$defs`); `markdown()` renders `docs/json-schemas.md`;
  `fingerprint()` digests every schema and `FINGERPRINTS` pins it. **Version 2** (P6-T1,
  `14c8b9e5c6d17b96`): `language` is `python | c | text`, `kind` gained `type` and `macro`, the
  `signature`/`docstring` field notes say what they are for C. **Version 3** (P7,
  `b4d308f6b63419e7`). **Version 4** (2026-09-05, `41ec61e8a59e6c78`): `who` gained `coverage`,
  and `index crawl` gained `unmapped` beside `skipped`. **Version 5** (2026-09-06,
  `3af030a09bd6e1d9`): `coverage` gained `summary` and the eight gap fields became nullable —
  they collapse to `null` on a complete answer unless `--coverage` asks for them. **Version 6**
  (2026-09-06, `6905ca99be0e617c`): `index crawl`'s `crawled` gained `forwarded`, and
  `unresolved_targets`' note no longer blames re-exports.
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
  history and *who links here* — the backlink table (or *Nothing crawled links here*) is
  **always followed by `_macros.html`'s `coverage_note`**, which names the revisions searched and
  says Complete / Incomplete / Coverage unknown with the reason. **`base.html` chooses the
  derived/asserted layout once**: two
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
  so tests can drive the prompts. `who`'s text form prints one `searched <repo>@<rev>` line per crawled
  revision with the directories it reached — omitted when the coverage collapsed — then
  `coverage["summary"]`: `coverage complete — searched …`, `coverage incomplete — <reasons>`, or
  `coverage unknown — …`. `--coverage` keeps the whole object on a complete answer. `resolve`'s text form prints the signature and docstring on a
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
  committed. `README.md` has all of it. **P8-T2:** `tasks/` holds the fifteen real tasks —
  `ir-*` (five merged fixes of click/attrs/rich: `repo.rev` is the parent commit, the `grade`
  and `solution` overlays are paths taken from the fix commit), `xr-*` (five consumers with a
  `[[deps]]` repository checked out at `../deps/<name>` and a `[grade.link]` check: an `is` link
  in `app.py` resolving to the target's identity, any `id=` right), `im-*` (five impact questions
  with a `[grade.who]` check and no command: `impact.txt` equals `who`'s innermost definitions).
  `graders.py` grew `Repo`/`Overlay`/`LinkCheck`/`WhoCheck`, `apply_overlay`, per-dep clones
  mapped in the config, `prepare_index` over every clone (moved here from the harness; the
  harness indexes for the links arm and for any task whose grader needs it), `check_link`,
  `check_who`, `innermost`, `parse_answer`, `Grade.checks` (in the record as `grade.checks`),
  `Task.fetched`. `fetch.sh` clones the three repositories under the gitignored `repos/` and
  verifies every pinned commit; `--list` marks an unfetched task and a run refuses to start
  without the clones. `pyproject.toml`: a `bench` dependency group (hypothesis, pygments,
  markdown-it-py) installed by default; `bench/agent/tasks` and `repos` excluded from ruff.
- Tests: 439 fast + 17 `slow` in `tests/` — `test_{address,hashing,extract_python,extract_c,
  config,links,gitcache,resolve,objects,latest,closure,expand,check,update,fold,run,package,
  server,cli,index_crawl,index_queries,acceptance_move,acceptance_provenance,
  acceptance_drivers,schemas,mcp,name,registry_federation,export,bench_agent}.py`.
  `test_bench_agent.py` is the P8-T1 acceptance without the subscription: the smoke task loads
  and its grader tells the bug from the fix, the checkout and config are as described, the arms
  are what the README says, the stream parser reads init, tool calls, denials and the result,
  a replay of each committed smoke record reproduces its numbers exactly (and the links record
  shows cttp connected, the baseline none), and the report renders. **P8-T2:** the fifteen
  tasks load five per family with the shape each family needs; an impact task has no Bash rule;
  commit overlays grade a parent against its fix (a two-commit repo built in `tmp_path`); an
  unfetched repository is reported; dependencies are cloned beside the checkout and mapped in
  the config; the link check passes an unstamped or correctly stamped link to the target and
  fails a wrong stamp, another definition or no link (thermo as the dependency, `@main`);
  `innermost`/`parse_answer`; the who check crawls the checkout and compares (`LM75.read_temp`,
  not `LM75`; no file pages). The `slow` acceptance runs `check_grader` for each real task,
  skipped until `fetch.sh` has run. `pyproject.toml` sets
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
  `search greet`; `history` over two revs; `rank`; the indexed closure equal to the live one;
  and **nine `coverage` tests** — the revisions and directories named; `complete` true over a
  src-layout where every reference was attributed; a binary counted as `skipped` but not as a
  gap; an unparsable Python file counted as `unread`; a link line the crawl ignored counted as
  `ignored_links`; an import into a package under no source root reported as `unmapped`; a
  re-export making `unresolved_matching` non-zero while another address in the same index stays
  clear; an index with the record stripped answering `null`, not `0`, and refusing to collapse;
  and the collapse itself — every gap field `null` on a complete answer, the object less than half
  the size, `--coverage` buying it back, and the CLI printing no per-revision block — plus one for the
  `ALTER TABLE` migration of a `revisions` table written without the columns);
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
- ~~`prepare_index` crawls only the task's checkout; cross-repository indexing and a `who`
  grader are missing~~ — closed 2026-09-05 (P8-T2): every clone is indexed; `check_who`
- ~~The P8-T2 repositories must be on disk before a run~~ — closed 2026-09-05: `fetch.sh`,
  `Task.fetched`, `--list` marks them, a run refuses to start without them
- **The closure keeps a function-local relative import** (`click.formatting.wrap_text` does
  `from ._textwrap import TextWrapper` in its body; `expand` inlines `TextWrapper` and leaves
  the line, which fails at run time — found writing `xr-textwrap-click`, which uses
  `TextWrapper` directly instead). The closure should refuse it (a local import of a
  repository module) or drop the statement when the closure binds the name → **unscheduled**;
  trigger: the first real expansion of a definition with a local import (spec §3's refusal
  list would grow one line)
- ~~`who` misses a `src/` layout's tests~~ — closed 2026-09-05: `SOURCE_ROOTS = ("src",)` in
  `extract/python.py`, tried after the file's ancestors. `who` on click's `strip_ansi` went
  9 backlinks → 21, the twelve new ones all in `tests/`
- ~~`who` does not follow a re-export~~ — closed 2026-09-06: `python.Forwarder`, applied in the
  crawl and the resolver. Click's unidentified links 1,422 → 50, `echo` 31 → 290 backlinks and
  complete; attrs' 1,582 → 38, `attr.s` 22 → 348. The five impact answers are unchanged, so it
  was not re-measured
- ~~A sibling module shadows a stdlib name~~ — closed 2026-09-06: `_import_roots` in
  `extract/python.py`. An ancestor holding an `__init__.py` is a package, not an import root.
  Click's unidentified links 50 → 31, rich's 100 → 46, cttp's own 38 → 15; a row-level diff shows
  the change is **purely subtractive** — every row removed was a file reaching itself under a
  stdlib name, and none was added or altered. The five impact answers are unchanged
  (`--check-graders` passes), so nothing was re-measured
- **A single-target alias in an `__init__` is a constant definition** (`s = attrs` would be
  `__init__.py#s`, a page of its own, and references to `attr.s` would stop there; attrs
  happens to write `s = attributes = attrs`, which is no definition and forwards). The
  extractor's P1-T3 rule and the forwarder agree by construction — a definition is where a
  reference stops — but a package that aliases its API one name at a time keeps its users on
  the alias → **unscheduled**; trigger: a real package doing that
- **`unresolved_matching` matches by the leaf of the symbol**, so a reference that reaches a
  definition under another name (`attr.s` for `attrs`) was never counted as a possible miss —
  the rule closed the case that mattered, but a lazily bound alias would still hide → **standing**;
  the honest fix is per-module: an `__init__` with a `__getattr__` marks every reference into
  it as unidentifiable-for-any-name (`caveats` could say so)
- ~~The real index predates the re-export rule~~ — decided 2026-09-06: no `--force`. Nothing in
  it can forward (the corpus is C, the registry has no Python, cttp forwards zero); a plain
  crawl at this session's commit added the head. A `--force` becomes worth it only if a Python
  package with re-exports is ever added to the real index
- **`expand` writes hoisted imports without a blank line after preceding code** when the link
  is at the end of the file, and before whatever `--at` points at (`import os` ends up after
  the expanded function when the link is inserted above it) — valid Python, untidy →
  **unscheduled**; trigger: someone reading an expanded file and minding
- ~~The link check accepts an unstamped link~~ — closed 2026-09-05: stated in
  `docs/benchmark.md`, and the report's stamps table shows 15/15 links runs wrote one, 0/15
  baseline
- **The links arm cannot run `cttp add`/`check`** (Bash is the test command only), so a
  cross-repo task is copy-by-hand in both arms; giving both arms `cttp` in Bash would change
  what is measured → **standing**, by design; note it in the report
- ~~Decide whether ninety streams stay in git~~ — closed 2026-09-05: they do, **gzipped**
  (5.4 MB for the ninety; `harness.resolve_stream` reads plain or `.gz`, a replay from a
  gzipped stream reproduces the numbers exactly)
- ~~`who` misses a `src/` layout's tests — the benchmark's headline defect~~ — closed
  2026-09-05 and **re-measured**: the impact family fell 16.28x → 6.65x, the three `src/` tasks
  by 1.7x / 3.9x / 3.3x, the two flat rich ones unmoved (the control). Records in
  `results/2026-09-05-impact-srcroots/`
- ~~An agent cannot tell that a `who` answer is complete~~ — closed 2026-09-05 and
  **re-measured**: `who` returns `coverage` (schema version 4, collapsing since 5). The impact
  family fell 6.65x → **2.40x**, median turns 25 → 14, `im-color-default-click` 23.62 → 8.65 at
  43 → 24 turns. Records in `results/2026-09-05-who-coverage/`. A fourth sweep read 3.26x with no
  change that should have raised it, so treat the 2.40 as a wide interval, not a point
- ~~Coverage costs where it is not needed~~ — **done 2026-09-06, and the premise did not survive
  the measurement.** The object now collapses on a complete answer (schema version 5): 1,373 → 479
  characters at the tool's mouth. But re-running the same five tasks gave the two rich ones nothing
  back (162,368 → 163,368 and 122,805 → 117,401) and the family ratio read 3.26. The 1.74 → 2.06 /
  1.04 → 1.91 that motivated it was very likely noise. Records in
  `results/2026-09-06-coverage-collapse/`
- **The benchmark cannot resolve an effect smaller than its own variance**, and that is now the
  limiting factor on every question it is asked. Three runs of `im-nested-chain-click` spanned
  141,257–569,186 tokens; across two sweeps the family's ratio moved 2.40 → 3.26 on no change that
  should have raised it, and the mean fell while the median rose. Report the mean beside the
  median, raise `--runs` for one family and see where the spread settles, or pair runs per task
  instead of taking a ratio of medians → **next session**, first item; until then, no change under
  ~20 % should be argued from a ratio here
- **A definition row keeps the first crawl's derived metadata.** `INSERT OR IGNORE` on
  `definitions` means a `--force` re-crawl refreshes locations and links but not `imports`,
  `unresolved`, signature or docstring; the viewer's *third party* line shows the stale
  classification. The first `unmapped_imports` read that column and reported a gap the
  source-root rule had closed, which is how it was found; the computation moved to crawl time
  (`revisions.unmapped`). Properly, `imports` and `unresolved` are per-place and belong on
  `locations` → **next session**, second item. The trigger has now fired **twice**: the re-export
  rule and, 2026-09-06, the import-roots rule both restated what a definition needs from outside,
  so every row crawled before them carries a classification the extractor no longer makes
- **`coverage` reports the whole index, not the repository asked about.** `searched` lists every
  crawled revision and `unresolved_targets` counts index-wide, so a `who` against a large shared
  index carries a long `searched` list. `unresolved_matching` is the scoped number and the one
  that decides `complete` → **unscheduled**; trigger: a `who` over an index with many
  repositories where the list is the bulk of the answer
- **The impact grader's naming convention favours the links arm.** `who` cannot address a nested
  function, so it credits the enclosing method and the reference answers inherit that; an agent
  reading source names the nested one and is marked wrong. `report.fold_nested` prints a folded
  column (baseline 12/15 → 15/15) and `docs/benchmark.md` says the folded one is to be believed.
  The grader itself is unchanged — it was mid-sweep → **unscheduled**; trigger: the next impact
  run, where the grader can fold before comparing
- **A cross-repo "library is not imported" test was a substring search** and matched the agent's
  attribution comment, punishing what cttp encourages; now parsed with `ast` in all five tasks
  → closed 2026-09-05
- **Cost grows with the square of a run's turn count** (every turn re-reads the conversation from
  cache): 6 turns 37k tokens, 18 turns 189k, 41 turns 5M. Any future sweep wants `--stop-above`
  and `--jobs` → **standing**

## Build history

Keep only the **five most recent** session entries. Older ones get deleted, not archived — `git log`
is the archive, and a bloated history taxes every future session start.

- **2026-09-06 (twenty-fourth session) — an absolute import is rooted where Python roots it;
  and the plan is declared done.** Last session's second item, and the last of the reference
  defects. The ancestor rule tried an absolute import against **every** directory above the file,
  nearest first, so a module sitting beside the importer shadowed the stdlib: `from types import
  TracebackType` inside `src/click/` reached `src/click/types.py`, `from abc import ABC` inside
  `rich/` reached `rich/abc.py`, and — found on the way — `from mcp.types import CallToolResult`
  inside `src/cttp/` reached **`src/cttp/mcp.py`**, so cttp recorded the MCP SDK as references to
  itself. Python does none of this: a package's own directory is never on `sys.path`.
  **`_import_roots(path, files, source_roots)`** keeps only the ancestors that do *not* hold an
  `__init__.py`, then appends the source roots; it is computed once per `Module` and used for
  `level == 0` alone, so relative imports are untouched. The two rules now read as one sentence
  (overview §4): a package directory is not a root, a `src/` that is on no file's path is.
  **Measured** on fresh indexes, before against after, unidentified derived links: click
  **50 → 31** (19 × `types.py`), rich **100 → 46** (34 × `abc.py`, 11 × `logging.py`, 8 ×
  `json.py`, 3 × `traceback.py`), attrs 38 → 38 (nothing to find), cttp itself **38 → 15**
  (23 × `mcp.py`). A row-level diff of the two indexes shows rows removed and **none added or
  altered** — the change is purely subtractive, and every row it removed was a file reaching
  *itself* under a stdlib name (`rich/json.py` importing `dumps` from itself). The two removed
  rows that carried an identity were wrong in the same way. **Not re-measured:**
  `--check-graders` passes all sixteen, so none of the five impact answers moved; the benchmark
  table stands. No schema change — no field moved, `SCHEMA_VERSION` stays **6**. Verified in the
  browser against a fresh index: `build_server`'s definition page now reads *third party: `mcp`*
  with a clean references list. **440** fast tests green (1 new, covering the package case, the
  flat case, the qualified self-import, the relative import and a `tests/` that is itself a
  package), 17 slow, ruff clean. Docs: overview §4's import-rooting bullet states both rules,
  the `unresolved_matching` bullet drops the shadowing case, §8's trap is deleted — it is fixed.
  **And the honest reading of where the project is:** the plan is complete and nothing is
  half-built, but cttp has never met a file outside this repository, which is what spec §14 defers
  every remaining design question until. Both of the last two real defects were found by looking
  at what stayed unidentified, not by the benchmark. Leo's answer, and the next stage: **crawl
  GitHub for highly common / repeating code and build the pages** — the "coding internet". Noted
  under *Next session*, to be planned by him.
- **2026-09-06 (twenty-third session) — a derived reference names the definition, not the
  module that re-exports it.** Last session's second item, the largest real defect left.
  `from click import echo` resolved to `src/click/__init__.py#echo`, a file that defines no
  `echo`, so the index recorded a reference it could never identify — 1,422 of click's 3,196
  links — and `who` on the package's public API was wrong by hundreds. **`python.Forwarder`**:
  `exports(source, path, files)` lists what a module binds at its top level by importing from
  a repository file (statements under a top-level `if`/`try` included, never inside a def),
  the bare-name aliases of those that are not themselves definitions (`s = attributes = attrs`,
  attrs' way), its star imports and a literal `__all__`; `forward(ref)` walks a reference
  through them — stopping at the first file that defines the symbol's head, keeping a member
  path, refusing a private name through a star, ending a cycle where it started — and leaves a
  name bound any other way (`__getattr__`, a call) where it landed, unidentified, for coverage
  to report. **Where it runs:** the extractor sees only one file's text and the repository's
  file names, so `extract.forwarded(page, files, read)` is a separate step — the crawl applies
  it per ref with one `Forwarder` over the revision (memoized reads, primed with every file the
  crawl reads; `Crawled.forwarded`, printed as `N forwarded`), the resolver in `_fetch_page`
  and `_page_at`, so the live closure inlines the definition (a page binds `greet` by its own
  name, and the expansion runs) and `closure --indexed` agrees with it. Schema **5 → 6**
  (`6905ca99be0e617c`): `forwarded` on `crawled`; the `unresolved_targets` note reworded.
  Spec §3's derived-references paragraph states the rule. **Measured** over fresh indexes of
  the three task repositories at their commits: click forwards 1,372, unidentified 1,422 → 50,
  `echo` 31 → 290 (complete), `Context` 90 → 140, `style` 7 → 23; attrs forwards 1,549,
  1,582 → 38, `attrs` 22 → 348, `attrib` 45 → 437, `fields` 30 → 106 — and the alias rule was
  added on seeing that `attr.s` and `attr.ib` were 730 of the 768 attrs left after the import
  rule alone, with coverage counting only 3 misses for `attrs` because it matches by leaf name;
  rich (flat) forwards 15 and keeps 100, mostly `rich/abc.py` shadowing `abc`, the sibling-
  shadows-stdlib defect now second on the list. **Not re-measured:** `--check-graders` passes
  all sixteen, meaning none of the five impact targets' reference answers changed — the rule
  cannot show in the benchmark without a task whose target is reached through a public name.
  Tests: the forwarder's every branch on an in-memory repository, the live closure through a
  re-export, `who` following one (and the CLI's `3 forwarded`), and the old coverage test
  rewritten over a `__getattr__` package, which is the case the rule declines. **439** fast
  tests green (3 new), 17 slow, ruff clean, the sixteen graders pass. Docs: overview §2, §4
  (the decision, with numbers), §8 (the shadowing trap; the real index needs `--force`);
  benchmark.md and the bench README date their re-export caveat. The real index was not
  force-crawled — nothing in it can forward — and got a plain crawl at the commit.
- **2026-09-06 (twenty-second session) — the coverage object collapses; the benchmark could not
  resolve it.** Last session's first item, done and honestly reported. `who`'s `coverage` gains
  **`summary`** — one line, always present: what was searched, whether the count may be trusted,
  and what is missing when it is not (`queries._summary()`, the one definition, printed by the
  CLI, the MCP tool and the viewer alike). When `complete` is true the eight fields beneath it
  (`queries.COLLAPSED`) are **`null`**: they are evidence for a doubt the line has settled. An
  incomplete answer, or one that cannot tell, still carries the whole object. `cttp who
  --coverage`, the MCP tool's `coverage`, and `queries.who(detail=True)` keep it either way; the
  viewer always asks for it, since a person reading a page has room. Schema **4 → 5**, fingerprint
  `3af030a09bd6e1d9`, `docs/json-schemas.md` regenerated; new decision in spec §6.
  **The direct measurement holds:** over a fresh index of rich at the benchmark's own commit
  `9d8f9a372cc5`, the object goes **1,373 → 479 characters** and the three `caveats` the
  flat-layout agents were weighing are gone.
  **The benchmark's does not.** Five impact tasks, 3 runs per arm, 30 records in
  `results/2026-09-06-coverage-collapse/`. The two rich tasks the change was *for* did not move
  (162,368 → 163,368 and 122,805 → 117,401); the family ratio went 2.40 → **3.26**, driven by
  `im-nested-chain-click` 173,728 → 321,008 while `im-color-default-click` halved 635,046 →
  310,891 in the same sweep. Three runs of one task span 141,257–569,186 tokens; the mean over all
  fifteen links runs *fell* 295,180 → 260,980 while the median rose. Correctness unchanged — links
  15/15 strict, baseline 12 strict / 15 folded.
  **So the previous session's diagnosis is not confirmed**, and every doc that stated it was
  corrected: `benchmark.md` gains *Collapsing the coverage object, and what it did not move* and
  its headline now warns about n=3; `spec.md` and `overview.md` justify the collapse as an
  interface decision — evidence for a settled doubt is weight, not evidence — and say plainly that
  the saving was not measurable. **The change was kept** because it returns strictly less for the
  same information and the escape hatch exists, not because the benchmark endorsed it; reverting
  on a null result would repeat the error that produced the change, pointed the other way.
  436 fast tests green (2 new: the collapse and its CLI flag, the MCP parameter), ruff clean, the
  viewer re-checked in the browser.

- **2026-09-05 (twenty-first session) — `who` states its own coverage; the impact family
  6.65x → 2.40x.** Last session's re-run found that completeness was necessary and not
  sufficient: `who` was right and the agent could not *tell*, so on the hardest question it
  corroborated by hand for 43 turns. **The fix** is a `coverage` object on `who`'s answer (spec
  §6, a new decision there): the revisions searched and the directories each reached; `skipped`
  files, split into `unread` (a file a language extractor would have read — a real hole) and
  `ignored_links` (link lines that did not parse); `unresolved_targets` with
  **`unresolved_matching`**, those naming *this* address; `unmapped_imports`; three static
  `caveats`; and `complete`, true only when this answer has no gap and **`null`, never a cheerful
  zero**, when the index predates the record. Schema version **3 → 4**, new fingerprint,
  `docs/json-schemas.md` regenerated; surfaced in all three places — `--json`/MCP, a line of CLI
  text, and a note in the viewer directly under *who links here*, because a bare `count: 0` is
  the one number a reader must not take on trust.
  **`unresolved_matching` is what makes it usable.** Click's index holds 1,422 unidentifiable
  link targets, nearly all references into the `__init__.py` that re-exports names it does not
  define. That total is alarming and almost always irrelevant: 0 of them name `strip_ansi`, so
  that answer is complete; 259 name `utils.py#echo`, so that one is not; and
  `core.py#Group.get_command` — zero backlinks, four matching — is flagged instead of trusted.
  **Two defects found and fixed on the way.** An unparsable Python file became a script page with
  no references and said nothing about it (`Page.parsed`, now recorded as a gap). And the first
  version of `unmapped_imports` read `definitions.imports`, one row per identity written by
  `INSERT OR IGNORE` — it keeps the *first* crawl's classification, so it claimed a gap on cttp's
  own repository that the source-root rule had already closed. Moved to crawl time
  (`revisions.unmapped`, beside `revisions.skipped`), which is where a per-place fact belongs;
  the index gained `ADDED_COLUMNS` + `migrate()` for it, writers only, readers using `has_column`
  so no reader takes the write lock. The stale definition row itself is a follow-up.
  **Measured, not asserted:** the five impact tasks re-run, 30 records in
  `results/2026-09-05-who-coverage/`. Family 6.65 → **2.40**, median turns 25 → 14, links arm
  15/15 strict where it was 14/15; `im-color-default-click` 23.62 → 8.65 at 43 → 24 turns, and
  the links arm's own tokens 1,329,911 → 635,046. The two flat rich tasks — the control — got
  **worse** (1.74 → 2.06, 1.04 → 1.91): those agents were never uncertain, and assurance costs on
  every call while repaying only where the agent would have doubted. Stated plainly in
  `docs/benchmark.md` rather than buried; shrinking the object when there is nothing to warn
  about is the next session's first item. The fix landed *after* the sweep finished so every run
  saw identical code, and the five coverage verdicts were re-checked against a fresh index
  afterwards — unchanged, so the numbers stand. 424 tests green (11 new), ruff clean.

- **2026-09-05 (twentieth session) — the src-layout source-root rule, and the impact tasks
  re-run to measure it.** The benchmark's worst number was one defect: `extract/python.py`
  resolved an absolute import against the importing file's ancestor directories only, so
  `from click._compat import strip_ansi` in `tests/` never reached `src/click/_compat.py` and
  `who` answered click and attrs quietly incomplete. **The fix** is `SOURCE_ROOTS = ("src",)`
  plus `_source_roots(files)`: an absolute import is tried against the ancestors first and the
  repository's source roots **last**, and a root counts only when the repository actually has
  that directory — so a flat layout gains nothing and a nearer ancestor still wins, which is why
  no existing test moved. Two tests: the rule itself (ancestors win, a repo without `src/` gains
  no root, an unknown module is still third-party) and an end-to-end `who` over a crawled
  src-layout repo. On click at the benchmark commit, `who` on `strip_ansi` went **9 backlinks →
  21**, the twelve new ones all in `tests/`. **The measurement:** the five impact tasks re-run,
  three runs per arm, same model and commits — the family's ratio **16.28 → 6.65**, the three
  `src/` tasks falling 1.7x / 3.9x / 3.3x while the two flat rich tasks moved less than the
  run-to-run spread. That control is what makes the attribution safe. The sweep's turn-capped
  `error` is gone: all fifteen links runs scored. **Why the graders did not have to change:** the
  three `src/` impact targets have no test callers, so `cttp who` returns the same reference
  answer before and after — all sixteen `--check-graders` still pass and the re-run is directly
  comparable to P8-T3 rather than graded against a new standard. **The honest remainder:**
  `im-color-default-click` still costs 23x at 43 turns. Completeness was necessary and not
  sufficient — the agent has no way to *know* `who` is complete, so it corroborates by hand, and
  a `who` that stated its own coverage is what this now points to. `docs/benchmark.md` gains a
  before/after section and its two stale claims are amended; `docs/overview.md` §4 gains the rule
  and §8's trap now describes only the re-export case that remains.

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
bash bench/agent/fetch.sh                                  # once per machine: click, attrs, rich under bench/agent/repos/
uv run python -m bench.agent.harness --list                # the tasks (marks any whose repository is missing)
uv run python -m bench.agent.harness --check-graders       # each grader fails the unmodified checkout and passes the solution (~2½ min)
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
