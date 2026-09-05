# PROGRESS — cttp

cttp — *code text transfer protocol* — is a protocol that sits on top of existing programming languages
and lets code point at code: every definition gets an address, references are links rather than imports,
and an index answers who links where. Rationale: [`docs/vision.md`](docs/vision.md).

**Status: PHASE 0 COMPLETE; PHASE 1 THREE-QUARTERS DONE — P1-T1, P1-T2, P1-T3 DONE. NEXT IS
P1-T4 (the link convention in full).** Phase 0 (2026-09-04): the spike, the public registry
`github.com/leorinaldi/cttp-registry` tagged `v1`, the config with an ordered registry list and
`[remotes]`, the registry as an **HTTP contract** (`http://localhost:3120` first, the local clone
second), `run` asking before the first run. Phase 1 so far (2026-09-04/05): the **full address
grammar**, **identity and shape hashing** in `hashing.py`, and the **Python extractor in full** —
every definition of spec §3 addressable by `#symbol` on either address form, with signature,
docstring, span, shape and **derived references**. 138 tests green, ruff clean.

_Last updated: 2026-09-05._

> **Read [`docs/overview.md`](docs/overview.md) first** — it is the lay of the land. This file is
> only *where we are*: state, next steps, follow-ups and recent history.

## Next session — suggested next steps

**Start here: P1-T4 — the link convention in full.** Read its entry in
[`docs/plan.md`](docs/plan.md) in full. `links.py` finishes spec §4: the three markers (`cttp:`,
`cttp-from:`, `cttp-see:`), `key=value` fields, the `~` derived-description marker, stacked links,
and — the part that bites today — **the block beneath a stamped link defined properly** (to the
next link line or a blank line followed by a non-indented line, recorded as `end` on the parsed
link) so that user code after an expanded definition no longer reads as drift. `expand.py` then
uses that delimiter instead of `block_end()`'s to-EOF rule. One regex must find a link in any
comment syntax (`#`, `//`, `--`, `/* */`, `;`); the C file in `bench/drivers/corpus/` is the
acceptance case for that. `test_extract_python.py::test_a_symbol_link_expands_and_checks` is
the test to extend once the block rule exists (it deliberately puts nothing after the link).

Then **Phase 2**: P2-T1 (locator resolution in full: symbol search across a repository, `id=`
mismatch, a real license matcher) and P2-T2 (the object cache, so identity addresses resolve).

If Leo wants to play, the demo is in **How to run** below; a definition link
(`# cttp: <locator>#<symbol>`) expands there too now.

## Current state — working & verified

**Code (`src/cttp/`), 2026-09-05.** Real modules; Phase 0 minimal, Phase 1 in full:
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
- `gitcache.py` — bare clones under `$CTTP_HOME` (default `~/.cache/cttp`)`/repos/<locator>`,
  cloned from `config.url_for(locator)`; rev-parse, blob at rev, license from the first line of
  `LICENSE*`/`COPYING`. **A fetch is skipped when the wanted rev is a SHA already in the cache**,
  so `check` on an expanded file is offline once the repo is cached; labels always fetch.
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
- `links.py` — parse and write `# cttp:` lines (stamp, `key=value` fields, quoted description).
  `format_stamped(pinned_address, id12, description)` takes the pinned address in any form, so a
  locator link expands to `# cttp: host/owner/repo@<sha12>/path id=sha256:… "…"`.
- `expand.py` — `expand` (one link, no closure; a page that itself contains `# cttp:` lines is
  refused with `ExpandError` until P3-T1), `check` (unexpanded / drift / unresolvable / ok),
  `run` for an address (`~/.cache/cttp/run/<pin>/main.py`) or a file (copy, expand, run). **The
  first run of a pinned address asks** — source, hash, license, which registry — unless `--yes`;
  the run-cache entry's existence is the "confirmed" marker, so it is created only after a yes.
  Without a terminal and without `--yes` it prints the summary and exits **2** (`NotConfirmed`).
  `run <file>` confirms each address the copy expands; code already in the file runs as is.
- `server/app.py` — FastAPI on **3120**: `/`, `/<name>`, `/<name>.json`, `/<name>@<version>.json`,
  each optionally with `%23<symbol>` before `.json`; the slug is parsed with `address.parse()`.
  The page shows shape, signature, docstring, span and the derived references. Looked at in a
  headless browser (hello-world and a symbol page): renders correctly.
- `cli.py` — `cttp --version | config | resolve | serve | expand | check | run`; `--json` is
  accepted before or after the subcommand. `resolve`'s text form prints the signature and
  docstring on a `#` line when the page is a definition.
- Tests: 138 in `tests/` — `test_{address,hashing,extract_python,config,links,resolve,expand,
  check,run,server,cli}.py`. `test_address.py` is table-driven over the spec §2 examples plus
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

**Corners the spike cut (each is closed by the named task):**
- `[remotes]` exists but no mirror has been exercised outside the tests → **P2-T1**
- No object cache; identity addresses parse but do not resolve → **P2-T2**
- A name whose entry names a whole repository (no path) cannot resolve a symbol yet → **P2-T1**
- Stamps use 12-hex for rev and identity (the plan's choice), full SHA returned in JSON → keep
- The block beneath a link runs to the next link line or EOF, so **user code after an expanded
  definition reads as drift** → **P1-T4** defines it properly
- License detection is a two-entry first-line map (itsdangerous shows as "Copyright 2011
  Pallets", the first line of its BSD file) → **P2-T1**
- `# cttp-from:` and `# cttp-see:` are not recognised → **P1-T4**
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
- The server was restarted on the P1-T3 code on 2026-09-05 (`.local/serve.log`).
- `~/.cache/cttp/repos/github.com/pallets/itsdangerous` exists from the P1-T3 by-hand check (a
  real symbol resolved over the network, then again offline at its pinned rev).
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

## Build history

Keep only the **five most recent** session entries. Older ones get deleted, not archived — `git log`
is the archive, and a bloated history taxes every future session start.

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
- **2026-09-04 (fifth session) — P0-T2: the public registry repository.** Created
  `github.com/leorinaldi/cttp-registry` (public) from `tests/fixtures/registry/`, one commit
  tagged `v1`, and ran the acceptance check: anonymous clone from a credential-free shell, files
  identical to the fixture, `git tag` lists `v1`. The only content change was the README gaining
  the link to spec §8 the plan asked for; the fixture was updated to stay identical. Leo also
  asked how to see a file both expanded and folded; `cttp fold` is P3-T4 and was left there.

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
