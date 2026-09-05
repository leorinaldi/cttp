# PROGRESS — cttp

cttp — *code text transfer protocol* — is a protocol that sits on top of existing programming languages
and lets code point at code: every definition gets an address, references are links rather than imports,
and an index answers who links where. Rationale: [`docs/vision.md`](docs/vision.md).

**Status: PHASES 0, 1 AND 2 COMPLETE. NEXT IS P3-T1 (the closure).** Phase 0 (2026-09-04): the
spike, the public registry `github.com/leorinaldi/cttp-registry` tagged `v1`, the config with an
ordered registry list and `[remotes]`, the registry as an **HTTP contract**, `run` asking before
the first run. Phase 1 (2026-09-04/05): the **full address grammar**, **identity and shape
hashing**, the **Python extractor in full** with derived references, and the **link convention in
full** — three markers, fields, `~`, stacks, any comment syntax, and the block beneath a link
recorded as `start`/`end`. Phase 2 (2026-09-05): **the resolver in full** — an SPDX license
matcher, symbol search for a name without a path, `id=` mismatch, the **object cache** so
identity addresses resolve offline, and **`resolve --latest`** rules 1 and 2. All three address
forms resolve. 205 tests green, ruff clean.

_Last updated: 2026-09-05._

> **Read [`docs/overview.md`](docs/overview.md) first** — it is the lay of the land. This file is
> only *where we are*: state, next steps, follow-ups and recent history.

## Next session — suggested next steps

**Start here: P3-T1 — the closure.** Read its entry in [`docs/plan.md`](docs/plan.md) in full.
From a page, compute the definitions it references, recursively, within the origin repository at
the pinned rev, using the extractor's derived `refs`; stdlib left as written; third-party imports
kept and reported; anything unresolvable stops the operation naming it; the 50-definition /
2,000-line budget with the `--package` suggestion. Output is an ordered list, dependencies before
dependents, that `cttp closure <address>` prints. This is what lets `expand` stop refusing pages
that link out (`ExpandError` today) and lets `reg_to_millicelsius` — which needs `REG_BITS` and
`STEP_MILLICELSIUS` — actually run after expansion (see the note in
`test_extract_python.py::test_a_symbol_link_expands_and_checks`). The plan wants a
`tests/fixtures/pyrepo/` fixture; the thermo fixture already has the sibling-reference shapes
and may serve, but check the acceptance list before deciding.

Then **P3-T2** (closure expansion beneath the link, each definition with its own stamp) and the
rest of Phase 3: `add`, `update`, `fold`.

If Leo wants to play, the demo is in **How to run** below. New since last time:
`cttp resolve sha256:75a27070015e` (from the object cache), `cttp resolve <pinned> --latest`,
`cttp resolve <address> --id sha256:…`, `cttp cache status`, and a `# cttp-see:` /
`# cttp-from:` line in a file passing `cttp check`.

## Current state — working & verified

**Code (`src/cttp/`), 2026-09-05.** Real modules; Phases 1 and 2 in full:
- `config.py` — **P0-T3/T4.** `~/.config/cttp/config.toml` (XDG; `CTTP_CONFIG` overrides the
  path): `registries` (ordered list of HTTP URLs or local paths; first match wins) and
  `[remotes]` (locator prefix → URL prefix, longest prefix wins, else `https://<locator>.git`).
  Paths take `~`; relative paths are relative to the file. **First run writes the file** with
  the defaults: `http://localhost:3120`, then `~/.local/share/cttp/registry`, no remotes.
  `--registry <entry>` or `CTTP_REGISTRY` replaces the list with that one entry (remotes kept).
  `cttp config [--json]` prints the effective result.
- `hashing.py` — **P1-T2.** `normalize()` (spec §2: dedent, LF, no trailing whitespace, one
  trailing newline), `identity()` (SHA-256 of the normalized text), `shape()` / `shape_text()`
  (the same text tokenized: identifiers → `$0`, `$1`… by first appearance, literals → `<num>`,
  `<str>`, `<fstr>`, statement and block structure → `<nl>`, `<in>`, `<out>`; keywords, builtins
  and operators kept; comments and blank lines dropped) and `short()`. `ShapeError` when the text
  is not Python. The identity of `print("hello world!")` is pinned in `tests/test_hashing.py`
  (`75a27070015e…`). `address.py` re-exports all of these.
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
  names it uses.
- `gitcache.py` — **P2-T1.** Bare clones under `$CTTP_HOME` (default `~/.cache/cttp`)
  `/repos/<locator>`, cloned from `config.url_for(locator)`; `rev_parse` (tags and branches to
  SHAs), `show` (`cat-file blob`), `ls_tree`, `default_branch` (the bare clone's HEAD).
  `license_of` finds `LICENSE*`/`COPYING*` at the rev (case-insensitive) and `spdx_of` matches
  the text: Apache-2.0, MPL-2.0, GPL-2.0, GPL-3.0 by title in the first 2,000 normalized chars
  (a preamble may come first — git's COPYING does), the GNU family told apart by which title
  comes first; MIT, ISC, BSD-2/3-Clause by their grant. Anything else is `None`; LGPL, AGPL and
  Unlicense deliberately return `None`. Verified against the twelve canonical SPDX texts. **A
  fetch is skipped when the wanted rev is a SHA already in the cache**, so `check` on an expanded
  file is offline once the repo is cached; labels always fetch.
- `registry.py` — `Registries`: the configured list, asked in order; a `RegistryError` from
  one is a miss and the next is asked; when all miss, the error names them all with each reason.
  `LocalRegistry` reads `cttp.toml` + `names/*.toml`. `HttpRegistry.fetch(name, version,
  symbol)` is `GET <url>/<name>[@<version>][%23<symbol>].json` — a symbol rides the same route
  percent-encoded — and returns the server's object (**the server resolves, the client asks**);
  404 and an unreachable server are misses, anything else is an error.
  `MissingRegistry` stands in for a configured path with nothing at it (a miss that says how to
  clone). `Registries(local_only=True)` is what the **server** uses — it must never ask an HTTP
  registry, which could be itself. `git_repo_from()` makes a git repo from a directory of files
  (branch `main`, tag `v1`); `create_local_registry()` is that for the registry fixture.
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
  name.
- `objects.py` — **P2-T2.** The object cache: `objects/<sha256>` is the normalized source,
  `objects/<sha256>.json` the sidecar — the page's metadata (kind, language, symbol, signature,
  docstring, span, shape, refs, imports) and `locations`, each a pinned locator address with
  target, path, rev, name, registry, description, license and a `seen` timestamp; a location seen
  again is refreshed, not duplicated. `lookup(prefix)` (12+ hex, with or without `sha256:`) →
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
- `expand.py` — `expand` (one link, no closure; a page that itself contains `# cttp:` lines is
  refused with `ExpandError` until P3-T1). **P1-T4:** the source goes beneath the link's whole
  stack, followed by a blank line when something non-blank follows, so the block is delimited;
  a page with no registry description gets one derived from its kind, signature and docstring
  (`def f(x) -> int — Summary.`), written `~"…"`. `check` (unexpanded / drift / **mismatch** /
  unresolvable / ok): `is` links are hashed over `link.block(lines)` and then resolved with
  `expect=` their id — `mismatch` means the block hashes to the stamp but the origin page does
  not; `from` and `see` links are resolved, never hashed. `Report` carries `relation`.
  `run` for an address (`~/.cache/cttp/run/<pin>/main.py`) or a file (copy, expand, run). **The
  first run of a pinned address asks** — source, hash, license, which registry — unless `--yes`;
  the run-cache entry's existence is the "confirmed" marker, so it is created only after a yes.
  Without a terminal and without `--yes` it prints the summary and exits **2** (`NotConfirmed`).
  `run <file>` confirms each address the copy expands; code already in the file runs as is.
- `server/app.py` — FastAPI on **3120**: `/`, `/<name>`, `/<name>.json`, `/<name>@<version>.json`,
  each optionally with `%23<symbol>` before `.json`; the slug is parsed with `address.parse()`.
  The page shows shape, signature, docstring, span and the derived references. Looked at in a
  headless browser (hello-world and a symbol page): renders correctly.
- `cli.py` — `cttp --version | config | resolve [--id …] [--latest] | serve | expand | check |
  run | cache status | cache clear [--run]`; `--json` is accepted before or after the subcommand.
  `resolve`'s text form prints the signature and docstring on a `#` line when the page is a
  definition, `# seen:` lines when an identity came from the object cache, and `from → to` with
  the rule under `--latest` (exit 1 when not found). `cache clear` removes repos and objects; the
  run cache — the confirmation record — only with `--run`.
- Tests: 205 in `tests/` — `test_{address,hashing,extract_python,config,links,gitcache,resolve,
  objects,latest,expand,check,run,server,cli}.py`. **Tests never connect a socket:** an autouse
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
- `expand` refuses a page that itself links out; a definition that references siblings
  (`reg_to_millicelsius` needs `REG_BITS`) expands but does not run alone → **P3-T1/P3-T2**
- `check --fix` (drift → `cttp-from:`), `update`, `fold`, `add` are not built → **Phase 3**
- The index hook `objects.index_lookup()` returns `None`; `--latest` rule 3 says so → **P4**
- A class attribute used as a default in a method signature (`address: int = ADDRESS`) is not a
  derived reference — bare names only match module-level definitions → **unscheduled**; trigger:
  the index (P4) needing class-scope name resolution

**Docs**
- `docs/vision.md` agreed, `docs/spec.md` confirmed as written, `docs/plan.md` agreed,
  `docs/overview.md` written — all on 2026-09-04. `docs/project-start-sequence.md` retired (deleted,
  per its own Stage 5; `git log` has it). `CLAUDE.md` now points at `docs/plan.md` for next steps.

**Environment**
- Git on `main`, remote `origin` → `github.com/leorinaldi/cttp` (**private**).
- **Registry repo:** `github.com/leorinaldi/cttp-registry` (**public**), first commit
  `d29352a4fbf1` tagged `v1`, contents identical to `tests/fixtures/registry/` (verified by
  anonymous clone, 2026-09-04). The README links to spec §8 in this private repo — a dead link
  for the public until cttp is opened.
- **On this machine (2026-09-04):** `~/.config/cttp/config.toml` is the first-run default
  (localhost first, then `~/.local/share/cttp/registry`, which is a **real clone** of the public
  repo). The spike's
  fixture-built registry was moved aside to `~/.local/share/cttp/registry.spike` (commit
  `9d12912`, exists nowhere else) and `~/.cache/cttp` was wiped — **trap:** the spike's cache
  held a clone of that fake repo under the real locator, so a pinned `9d12912…` address kept
  resolving from cache after the registry changed. A stale `hello.py` in the repo root stamped
  with `9d12912048b9` is Leo's and is now correctly reported `unresolvable`.
- `uv` 0.12.10 installed at `~/.local/bin/uv` (2026-09-04). Python 3.12.3 system interpreter at
  `/usr/bin/python3` has no cttp, which the tests rely on.
- Domain `cttp.ai` registered by Leo; nothing points at it yet.
- Driver corpus preserved at `bench/drivers/corpus/` (gitignored, 13 MB, 736 `.c` files under
  `drivers/{gpio,hwmon,iio,rtc}`), copied from the fisheye session's scratchpad. The measurement
  scripts and the Linux commit did **not** survive; P6-T2 reconstructs them. The LM75 teardown
  files are at `bench/drivers/lm75-teardown/` (gitignored).
- The server was restarted on the P2-T1 code on 2026-09-05 (`.local/serve.log`); P2-T2/T3
  touched nothing it serves.
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

- Identify the Linux commit the preserved corpus came from and write `bench/drivers/fetch.sh`;
  re-derive `expected.json` → **P6-T2**
- Name collision check on PyPI and npm before the first package is published → **unscheduled**;
  trigger: deciding to publish `cttp` to PyPI (not in the plan)
- Point `cttp.ai` at the static export → **P7-T3**
- The registry README links to spec §8 in the private `cttp` repo → **unscheduled**; trigger:
  making `cttp` public, or publishing the spec on `cttp.ai` (P7-T3), whichever first
- Editor extension that folds cttp blocks on open and shows a link's page on hover →
  **unscheduled**; trigger: first real use of expanded files by a person in an editor
- A branch containing `/` (`release/1.0`) cannot be a locator rev — the first `/` after `@`
  starts the path; only the name form reaches such refs → **unscheduled**; trigger: a real
  target whose only useful ref is a slashed branch (an escape such as `@{release/1.0}` would do)
- Starlette warns that `httpx` with its test client is deprecated in favour of `httpx2` →
  **unscheduled**; trigger: the warning becomes an error on upgrade
- The `%23<symbol>` extension of the registry contract is in the code and `overview.md` but not
  in spec §8's route table → **unscheduled**; trigger: the next spec edit, or publishing the spec
  on `cttp.ai` (P7-T3)
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
- **A renamed definition is not found by `--latest`** — its identity changed with its name; its
  shape did not, and a shape-based rule would find it → **unscheduled**; trigger: a real
  `--latest` miss on a rename (rule 3 via the index may also cover it, P4-T3)
- `--latest` on a **locator uses the bare clone's HEAD** as the default branch, which is the
  origin's default at clone time; a repository that changes its default branch later keeps the
  old one until the cache is cleared → **unscheduled**; trigger: it happens
- `latest()` resolves the pinned page and then the head page through `resolve()`, so **`--latest`
  stores both in the object cache** — intended, but it means the head page's location is
  recorded as "seen" without anyone linking to it → **standing**, revisit at P4

## Build history

Keep only the **five most recent** session entries. Older ones get deleted, not archived — `git log`
is the archive, and a bloated history taxes every future session start.

- **2026-09-05 (eleventh session) — P1-T4, P2-T1, P2-T2, P2-T3: Phases 1 and 2 done.**
  Four task commits. P1-T4 rewrote `links.py` around one regex for any comment syntax, three
  relations, ordered fields and a recorded block (`start`/`end`, beginning after the link's
  stack, ending at the next link, a blank line before a line no deeper than the link, or EOF);
  `expand` writes beneath the stack and adds a blank line before what follows, so user code after
  an expanded definition stopped reading as drift; the derived `~"…"` description arrived.
  Decisions: stacked links share one block; `check` hashes only `is` links; a page's own inner
  links still refuse expansion until the closure exists. P2-T1: `cat-file` for blobs, an SPDX
  matcher by title-in-head for versioned licenses and by grant for the rest — the GNU family
  told apart by which title comes first, because the LGPL/AGPL preambles and the GPL-2's own
  preamble all name other GNU licenses; symbol search across a repository for a name without a
  path; `Mismatch` with both hashes; a socket guard so tests provably never reach the network.
  P2-T2: `objects.py`, every resolution stored, identity addresses answered from it with all
  their locations, `cttp cache status|clear`. P2-T3: `latest()` with rules 1 and 2 and the
  plain "rule 3 needs the index" answer; a rename is a different identity (test says so). By
  hand against real repositories: itsdangerous now reads BSD-3-Clause, requests at a tag pins
  and reads Apache-2.0, git's COPYING reads GPL-2.0 (a preamble longer than the first head size
  tried — widened to 2,000 chars), the twelve canonical SPDX texts all classify as intended, and
  `--latest` followed itsdangerous from tag 2.1.2 to head. 138 → 205 tests.
- **2026-09-04/05 (tenth session) — P1-T2 identity and shape hashing; P1-T3 the Python
  extractor in full.** `hashing.py` took `normalize`, `identity` and `short` out of `address.py`
  (re-exported) and added `shape()`: `tokenize` over the normalized text, identifiers positional,
  literals typed, structure tokens kept so a reordered statement changes the shape, comments and
  blank lines dropped. Then the extractor: `ast` over the file, every spec §3 definition kind,
  spans from the first decorator, signature from `ast.unparse`, the docstring's first paragraph
  as one line, and derived references resolved against the repository's file list. Decisions:
  a `#symbol` rides the HTTP contract as `%23` in the existing route (no new route); a
  definition's references are the names it uses while a script's are every import; a parameter
  shadows a module-level import; non-Python files are `text` script pages with `shape: null`
  rather than a tokenization error. By-hand acceptance against a real public repository
  (itsdangerous, over the network) found and fixed two bugs the fixture had not: the shadowing
  case, and a docstring summary wrapping onto a second line being cut. Both pages looked at in
  headless Chromium. 113 → 138 tests. Server restarted on the new code.
- **2026-09-04 (ninth session) — Stage 4 `overview.md`; start sequence retired; P1-T1 the full
  address grammar.** The overview was written from the code, not from memory: architecture,
  repo map, load-bearing decisions, vocabulary, invariants, the oddities not to "fix", the traps,
  how to run. Reaching Stage 5 retired `docs/project-start-sequence.md` exactly as it asked
  (two CLAUDE.md steps repointed at the plan, its row dropped from the map, the file deleted).
  Then P1-T1: one `Address` type for all three forms, canonical round-trip, `parse_pinned`,
  errors that name the part, a table of valid/invalid inputs. Decisions: a locator resolves
  through git without a registry (the contract has no locator route) and borrows name and
  description from a local entry with the same target; a `/` after `@` in a locator starts the
  path, so slashed branches are name-form only; hex and hosts are lower-cased on parse; stamps
  now carry the pinned address in any form (`format_stamped` signature changed). Acceptance
  walked by hand from `/tmp`: the plan's locator command, a locator link expanded, run under
  `python3 -I`, and checked ok. 55 → 113 tests. Server restarted on the new code.
- **2026-09-04 (eighth session) — P0-T5: first-run confirmation; test 4 as tests; Phase 0 done.**
  `run` now asks before the first run of a pinned address (source, identity, license, registry)
  and exits 2 with "pass --yes" when there is no terminal; the run-cache entry is the confirmed
  marker and is only created after a yes (a declined run leaves nothing — found by a test).
  `expand` refuses a page that contains `# cttp:` lines itself (closure is P3-T1). Tests split by
  concern (`links`, `expand`, `check`, `run`), acceptance test 4 verbatim through the CLI, 41 →
  55. Walked by hand against the live server including decline/accept through a pty via
  `script(1)`. Also: `uv run --project <dir>` is the way to run cttp from another directory.
- **2026-09-04 (seventh session) — P0-T4: the registry as an HTTP contract.** `HttpRegistry`
  now fetches `GET <url>/<name>@<version>.json` and the resolver dispatches: HTTP registries hand
  back the server's object (`Resolved.from_json`, `registry` = the URL), local ones do the git
  work. Misses fall through — 404, unreachable server, or a configured path with nothing at it
  (`MissingRegistry`, no longer an error at startup) — and the final error names every registry
  with its reason. The server opens registries `local_only=True` so a config that lists it first
  cannot make it query itself. First run writes the default config (localhost first, clone
  second). Acceptance run live: the four curl checks, the page looked at in headless Chromium,
  and `cttp resolve hello-world --json` with the server up versus down identical except for
  `registry`. Trimmed history to five sessions. Added
  `config.py`; `registry.py` became `Registries` (ordered, first match wins) over `LocalRegistry`
  plus an `HttpRegistry` stub; the spike's "the registry repo serves itself from its local path"
  rule was removed — every locator now goes through `[remotes]` or https, and the tests reach a
  bare repo in `tmp_path` through `[remotes]` exactly as the plan's guardrail says. Also:
  `cttp config`, `--json` after the subcommand (the plan's acceptance form), and a fetch skipped
  when a pinned SHA is already cached. Acceptance run for real: the local registry replaced by a
  clone of the public repo, `cttp resolve hello-world --json` pins to `d29352a4fbf1` with all the
  stated fields, and acceptance test 4 walked again end to end. Two traps found and recorded
  under Environment: the spike's poisoned git cache, and `uv --directory` changing cwd (use
  `uv run --project` from another directory).

## How to run

```bash
export PATH="$HOME/.local/bin:$PATH"          # uv lives here
uv sync                                        # once; creates .venv
uv run pytest -q                               # 138 tests, no network
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

`scripts/make_local_registry.py` still builds an offline registry from the fixture if needed.
The server was left running in the background (`.local/serve.log`); probe
`curl -s -o /dev/null -w '%{http_code}' http://localhost:3120/` before starting another.

## Config / secrets

- `.env` — not created. Gitignored by design; never commit it.
- `~/.config/cttp/config.toml` — the tool's configuration (see `config.py` above). Environment
  knobs: `CTTP_CONFIG` (config file path), `CTTP_HOME` (caches, default `~/.cache/cttp`),
  `CTTP_REGISTRY` (one registry, replacing the list). Tests set the first two to `tmp_path`.
