# PLAN — cttp

**What this is:** the executable decomposition of [`spec.md`](spec.md) into tasks a coding agent can
pick up and finish in one session. The spec says *what and why*; this says *what to build next, in
what order, and how to know it worked*.

**What this is not:** a status document. Task status lives **only** in [`PROGRESS.md`](../PROGRESS.md).
Entries below are specs — if a task turns out to be wrong, amend it here deliberately and note the
amendment in `PROGRESS.md`'s build history.

_Last updated: 2026-09-04. First draft, written against the second draft of the spec (confirmed by
Leo 2026-09-04). Amended the same day: P0-T1 became a one-session spike so hello world runs
before anything is built carefully._

---

## How to use this document

1. Read `PROGRESS.md` to find the first task not marked done (if none, start at **P0-T1**).
2. Read that task's entry here **in full**, plus its preconditions.
3. Do only that task. Stay inside its **May touch** list.
4. Run its **Accept** check. It must pass with the stated observable result — not "looks right".
5. Update `PROGRESS.md` (state + build-history entry), then commit and push.

**One task = one session = one commit.** If a task needs two commits, that is a signal it should
have been two tasks — split it here first.

**Between Phase 0 and Phase 1, write [`overview.md`](overview.md).** It is not a task here because
it is not code, but it is not optional either. (Done; the start-sequence document that asked for it
has been retired.)

## The shape of the plan

Phase 0 is a **walking skeleton**: the thinnest vertical slice through every layer that makes the
spec's hello-world acceptance test (§12, test 4) pass end to end. Its first task is a deliberate
**spike** — one session, quick and dirty, hello world running tonight — so that Leo can see the
thing in action before anything is built carefully; the rest of Phase 0 hardens what the spike
sketched. Every module the spike creates is the real module in minimal form, not a throwaway.
Phases 1–4 then deepen one layer each, in the spec's own order — address and extractor, resolver,
materializer, index — so that the tool is useful to an agent as early as Phase 3 and the three
remaining acceptance tests land in Phases 4 and 6. Phase 5 is the agent interface, Phase 6 the
language-neutral read side and the driver-corpus test, Phase 7 the registry as a public service, and
Phase 8 the benchmark — the number the vision says decides whether any of this helps.

**Decisions the spec delegated to this plan**, made here:

| Question | Decision | Where |
|---|---|---|
| Home of the first registry repository | `github.com/leorinaldi/cttp-registry`, **public** (a registry that only its owner can read is not a registry), holding the first snippets too | P0-T2 |
| Abbreviated or full SHAs in stamps | The tool **writes 12-hex abbreviations** for both rev and identity, as in the spec's examples; it **accepts** any length ≥ 12. Revisit if a real repository ever produces an ambiguous 12-hex rev | P0-T5 |
| Where the tool's configuration lives | `~/.config/cttp/config.toml` (XDG), overridable with `CTTP_CONFIG`; a project may add `cttp.toml` at its root for project-level defaults such as `track = "latest"` | P0-T3 |
| How tests reach git repositories without the network | A `[remotes]` table in the config maps a locator prefix (`github.com/leorinaldi/`) to a URL prefix; tests point it at bare repositories built in `tmp_path`. The same mechanism serves a private mirror | P2-T1 |
| Benchmark model and harness | **Claude Code headless (`claude -p`) under Leo's subscription login**, one model and effort in both arms (`--model`; Opus 5 unless Leo picks otherwise), the same harness for both arms so the only variable is the tool list (`--allowedTools` / `--disallowedTools`, `--mcp-config` for the links arm); tokens measured from the `usage` object of `--output-format json` (input, output, cache read, cache write, per model). Decided 2026-09-05 over the Anthropic SDK: the SDK bills the API per token, the login is included in the subscription, and the docs say ordinary individual use of Claude Code and the Agent SDK is what the login is for. The caveat is stated in the report: both arms run inside Claude Code's harness (its system prompt, its context management, MCP tool deferral), so the result compares tool sets inside Claude Code, not minimal agents | P8-T1 |
| Benchmark task set | Three mid-size Python repositories, five tasks per family, three runs per task; see P8-T2 | P8-T2 |
| How `cttp.ai` serves the contract at first | A **static export** of the registry contract (`cttp serve --export`) published with GitHub Pages under the domain. Every route in §8 is a file; a dynamic host is a later refinement | P7-T3 |

## Guardrails (apply to every task, no exceptions)

| Rule | Enforcement |
|---|---|
| Never commit `.env`, `.venv/`, `node_modules/`, or bulk data (`bench/drivers/corpus/`, benchmark checkouts) | `.gitignore` |
| Never invent a value — missing is "not available" / `null`, never coerced to zero or to an empty string that reads as a value | tests |
| The local site runs on port **3120** and nothing else | `cttp serve` default; tests assert it |
| **No runtime component.** Nothing under `src/cttp/` is ever imported by a user's program; expanded output never contains `import cttp`; fixture programs are run with `python3 -I` from an interpreter that has no cttp installed | test `test_no_runtime_component` in P0-T5, kept forever |
| **The tool never executes origin code.** Extraction, hashing and expansion read text; the only thing that runs user code is `cttp run`, after confirmation | code review; no `exec`/`import` of fetched source anywhere but `run` |
| **Derived and asserted are never merged.** Every fact in `--json` carries `origin`; every viewer page separates them visually | schema tests in P5-T1 |
| **No lockfile.** Nothing is written outside the user's files except caches under `~/.cache/cttp/` and the index under `~/.local/share/cttp/` | code review |
| Tests never touch the network. Every repository a test resolves is a bare repo built in `tmp_path` and reached through `[remotes]` | pytest fixture `remotes`; CI has no credentials |
| Every subcommand has `--json` with a stable schema; a change to a schema is a deliberate act noted in `PROGRESS.md` | P5-T1 schema tests |

## Pinned stack

| Concern | Choice |
|---|---|
| Language | Python 3.12+ |
| Environment | `uv` — `uv sync`, `uv run cttp …`, `uv run pytest` |
| CLI | `typer` |
| Python extraction | stdlib `ast` (and `tokenize` for the shape hash) |
| Other-language extraction | `tree-sitter` + `tree-sitter-language-pack` (official grammars) |
| Git | `git` via `subprocess` |
| Index | SQLite via stdlib `sqlite3` |
| Config and registry files | TOML — `tomllib` to read, `tomli-w` to write |
| Server | FastAPI + Jinja2, `uvicorn`, port **3120**; `httpx` as the client (also FastAPI's test client) |
| MCP server | the official Python MCP SDK (`mcp`) |
| Benchmark harness | Claude Code headless — `claude -p --output-format json` as a subprocess under Leo's login; no API key, no `anthropic` dependency |
| Tests | `pytest`; fixture repositories built in `tmp_path` |
| Lint and format | `ruff` (check + format) |
| Web port | **3120** |

## Target layout

```text
cttp/
  CLAUDE.md  AGENTS.md  PROGRESS.md
  docs/                  vision.md  spec.md  plan.md  overview.md
  pyproject.toml         the cttp distribution; `cttp` console script
  uv.lock
  src/cttp/
    __init__.py          version only
    address.py           grammar, parsing, normalization, identity and shape hashing
    extract/             __init__.py (Definition, Page)  python.py (ast)  treesitter.py  queries/<lang>.scm
    links.py             the comment convention: find, parse, write
    config.py            ~/.config/cttp/config.toml, project cttp.toml, [remotes]
    gitcache.py          ~/.cache/cttp/repos, fetch, blob at rev, ls-tree
    resolve.py           resolution by form, object cache, --latest
    index/               schema.py  crawl.py  queries.py
    expand.py            closure, in-place expansion, check, update, fold, run, --package
    registry.py          name resolution against a registry repo or an HTTP registry; claim, show
    server/              app.py  templates/  static/  export.py
    mcp.py               the MCP server
    cli.py               typer entry point; --json plumbing
    schemas.py           the JSON output schemas, one place
  tests/
    conftest.py          fixtures: tmp git repos, `remotes`, a registry repo, a running server
    fixtures/            source trees the fixtures commit
    test_*.py
  bench/
    drivers/             corpus/ (gitignored)  fetch.sh  expected.json  measure.py
    agent/               harness.py  tasks/  results/
```

---

# Phase 0 — Walking skeleton: hello world end to end

Target: spec §12 acceptance test 4. **P0-T1 is the spike** — the whole test passing in one
session, corners cut. P0-T2 to P0-T5 then replace each cut corner with the real thing, each
leaving `uv run pytest` green. The spike is the one task in this plan that is allowed to be quick
and dirty; the rule that pays for it is that it is built in the real layout under the real names,
so that hardening replaces bodies and never restructures.

### P0-T1 · The spike — hello world end to end, in one session

- **What:** Everything acceptance test 4 needs, built once, fast, in the real `src/cttp/` layout:
  `pyproject.toml` with the `cttp` console script and `pytest`/`ruff` configured; a Python block in
  `.gitignore`; `address.py` parsing only the name form and the stamped form and hashing text per
  §2; `extract/python.py` handling only a whole file as a script; `gitcache.py` cloning a repo
  into `~/.cache/cttp/repos/` and reading a blob at a ref; `registry.py` reading
  `names/<name>.toml` from a **local registry repository** (a git repo in a folder — the public one
  is P0-T2); `resolve.py` chaining them; `server/app.py` with `/<name>`, `/<name>.json` and
  `/<name>@<version>.json` on **3120**; `links.py` and `expand.py` with `expand`, `check` and
  `run` for one link with no closure; `cli.py` wiring `resolve`, `serve`, `expand`, `check`,
  `run`, all with `--json`. Tests: a handful of smoke tests over a `tmp_path` registry, not the
  acceptance suite. Corners that may be cut and must be listed in `PROGRESS.md` when the task
  closes: no config file (registry path by flag or `CTTP_REGISTRY` env var), no `[remotes]`, no
  object cache, no license detection beyond a `LICENSE` file's first line, no first-run
  confirmation in `run` (`--yes` implied), stamped SHAs of any convenient length.
- **Preconditions:** `uv` installed (done 2026-09-04).
- **May touch:** `pyproject.toml`, `uv.lock`, `.gitignore`, `src/cttp/**`, `tests/**`, a local
  registry repository created by a script at `tests/fixtures/registry/` (with
  `names/hello-world.toml` and `snippets/hello_world.py` exactly as P0-T2 will publish them).
- **Accept:** Done by hand, with Leo watching, then recorded in `PROGRESS.md`: `uv run cttp serve`
  is up and **http://localhost:3120/hello-world** shows the source in the browser; a file
  containing only `# cttp: hello-world` becomes, after `uv run cttp expand hello.py`, the stamped
  line plus `print("hello world!")`; `/usr/bin/python3 -I hello.py` prints `hello world!`;
  `uv run cttp run hello-world` prints `hello world!` with no file; `uv run cttp check hello.py`
  exits 0, and exits 1 after the print line is edited. `uv run pytest` is green. One commit.

### P0-T2 · The first registry repository

- **What:** Create the public repository `github.com/leorinaldi/cttp-registry` with the layout of
  spec §8: `cttp.toml` (`name = "cttp-registry"`), `names/hello-world.toml` (description
  `Prints 'hello world'.`, owner `github.com/leorinaldi`, target
  `github.com/leorinaldi/cttp-registry/snippets/hello_world.py`, default `latest`, versions
  `latest = "main"`), `snippets/hello_world.py` containing exactly `print("hello world!")`, a
  `LICENSE` (MIT), and a `README.md` that states what the repository is and links to the spec's
  registry section. Tag the first commit `v1` so `stable = "v1"` can be added later without
  rewriting history.
- **Preconditions:** P0-T1. `gh auth status` shows `leorinaldi`. Ask Leo before creating the
  repository — it is public and outward-facing.
- **May touch:** the new repository only. In this repository, `PROGRESS.md`.
- **Accept:** `git clone https://github.com/leorinaldi/cttp-registry` succeeds anonymously (from a
  shell with no credentials, e.g. `GIT_CONFIG_NOSYSTEM=1 HOME=$(mktemp -d)`); the four files are
  present with the stated contents; `git tag` lists `v1`.

### P0-T3 · Resolve a name, properly

- **What:** Replace the spike's resolution path with the real minimal modules. `address.py`: parse
  and format the **name** form and the pinned name form (`hello-world`, `hello-world@<rev>
  id=sha256:…`); the identity hash over normalized text (spec §2 rules) — no shape yet.
  `extract/python.py`: a whole file as a **script** page (kind `script`, source, span, no symbol) —
  no definitions yet. `gitcache.py`: clone or fetch `host/owner/repo` into `~/.cache/cttp/repos/…`,
  resolve a ref to a full SHA, read a blob at a rev. `config.py`: load `~/.config/cttp/config.toml`
  with `registries` (a list of either an HTTP URL or a local path to a registry repository) and
  `[remotes]`. `registry.py`: look a name up in a **local registry repository** (read
  `names/<name>.toml`, map the version label to a ref). `resolve.py`: name → registry → locator →
  fetch → extract → hash. `cli.py`: `cttp resolve <name> [--json]`.
- **Preconditions:** P0-T1, P0-T2.
- **May touch:** `src/cttp/{address,config,gitcache,registry,resolve,cli,schemas}.py`,
  `src/cttp/extract/{__init__,python}.py`, `tests/conftest.py` (fixtures: a bare target repo and a
  registry repo in `tmp_path`, a config pointing at them), `tests/test_{address,resolve}.py`.
- **Accept:** With the config's registry list set to a local clone of `cttp-registry`,
  `uv run cttp resolve hello-world --json` prints an object with `address` (pinned:
  `hello-world@<12 hex>`), `identity` (`sha256:<12 hex>` plus `identity_full`), `kind: "script"`,
  `language: "python"`, `source: "print(\"hello world!\")\n"`, `license: "MIT"`, and an `origin`
  field on `license` and `identity` reading `derived`. Tests reproduce the same against `tmp_path`
  repositories with no network. `cttp resolve no-such-name` exits non-zero with a message naming
  the registry that was asked.

### P0-T4 · `cttp serve` — the registry contract on 3120, properly

- **What:** Replace the spike's server. `server/app.py`: a FastAPI app with the three routes of spec
  §8 — `GET /<name>` (HTML from a Jinja2 template: name, description, pinned address, source,
  license, version labels), `GET /<name>.json` and `GET /<name>@<version>.json` (the resolver's
  schema from P0-T3) — over the local registry repository from the config. `cttp serve [--port 3120]
  [--registry <path>]` runs it with uvicorn. `registry.py` gains an **HTTP registry** backend: when
  a configured registry is a URL, name lookup is `GET <url>/<name>@<version>.json`. The default
  config written on first run lists `http://localhost:3120` first and the local registry path
  second, so `cttp resolve` works with or without the server up.
- **Preconditions:** P0-T3.
- **May touch:** `src/cttp/server/{__init__,app}.py`, `src/cttp/server/templates/{base,name}.html`,
  `src/cttp/{registry,config,cli}.py`, `tests/conftest.py` (a FastAPI test client fixture),
  `tests/test_server.py`.
- **Accept:** With `uv run cttp serve` running: `curl -s localhost:3120/hello-world.json` returns
  the P0-T3 object; `curl -s localhost:3120/hello-world@latest.json` returns the same;
  `curl -s -o /dev/null -w '%{http_code}' localhost:3120/hello-world` is `200` and the page shows
  the source and description (look at it in the browser); `/no-such-name.json` is `404` with a JSON
  body. `uv run cttp resolve hello-world --json` with the server up produces the same object as
  with it down, and `--json` output carries `registry: "http://localhost:3120"` versus the path.
  Record the bring-up in `PROGRESS.md` → *How to run*.

### P0-T5 · `expand`, `check`, `run` for a single link — acceptance test 4 as tests

- **What:** Replace the spike's link handling and make test 4 a test. `links.py`: find `# cttp:`
  lines, parse the short and stamped forms and the trailing description, write a stamped line
  (12-hex rev and identity, asserted description from the registry). `expand.py`: for each
  unexpanded link in a file, resolve, write the stamped line and the source directly beneath it
  (script or not — no closure yet; a page with references outside itself is refused with a message
  saying closure expansion arrives later); `check`: every stamped link's code beneath hashes to its
  `id=`, every link resolves, no link is unexpanded, exit 1 on any failure with a per-link report;
  `run <address|file>`: expand into `~/.cache/cttp/run/<pin>/` and run with `sys.executable`; on
  first run of an address show source, hash and license and ask, unless `--yes`. `cli.py` gains
  `expand`, `check`, `run`.
- **Preconditions:** P0-T4.
- **May touch:** `src/cttp/{links,expand,cli,schemas}.py`, `tests/test_{links,expand,check,run}.py`,
  `tests/fixtures/hello/`.
- **Accept:** The spec's test 4, verbatim, as pytest tests and once more by hand: a file containing only
  `# cttp: hello-world` becomes, after `uv run cttp expand hello.py`, the stamped line with the
  description `"Prints 'hello world'."` followed by `print("hello world!")`; `/usr/bin/python3 -I hello.py`
  prints `hello world!` (the test first asserts `/usr/bin/python3 -I -c "import cttp"` fails);
  `uv run cttp run hello-world --yes` prints `hello world!` with no file present; `uv run cttp check hello.py`
  exits 0, and exits 1 naming the link and `drift` after the print line is edited. The
  `test_no_runtime_component` test greps `src/cttp/` for `sys.meta_path` and expanded output for
  `import cttp` and finds neither.

---

# Phase 1 — The address and the Python extractor, in full

### P1-T1 · The full address grammar

- **What:** All three forms of spec §2 — name (with dotted labels, `@version|rev`, `#symbol`),
  locator (`host/owner/repo@rev/path#symbol`), identity (`sha256:` full or ≥ 12 prefix) — parsed
  into one `Address` type with `form`, `is_pinned`, normalization (lower-case host, forward
  slashes, no trailing slash), formatting back to canonical text, and a table-driven test of valid
  and invalid inputs (bad label characters, 11-hex prefix, missing rev in a locator, `@tag` in a
  stamp).
- **Preconditions:** P0-T5.
- **May touch:** `src/cttp/address.py`, `tests/test_address.py`.
- **Accept:** Every example in spec §2 parses and round-trips byte-for-byte; every invalid example
  in the test table raises `AddressError` with a message that names the offending part;
  `cttp resolve` accepts a locator (`cttp:github.com/leorinaldi/cttp-registry@main/snippets/hello_world.py`)
  and returns the same object as the name form, plus the identity form after P2-T2.

### P1-T2 · Identity and shape hashing

- **What:** `address.py` (or a new `hashing.py` if it grows): identity normalization exactly per
  §2 (dedent, LF, strip trailing whitespace, one trailing newline); the **shape** hash — the same
  text with every identifier replaced by a positional placeholder and every literal by a typed
  placeholder, using `tokenize`, keywords and builtins kept; both exposed as `identity(text)` and
  `shape(text)` with full and 12-hex forms.
- **Preconditions:** P1-T1.
- **May touch:** `src/cttp/address.py` (or `src/cttp/hashing.py` and its registration in
  `extract/__init__.py`), `tests/test_hashing.py`.
- **Accept:** Two functions that differ only in names, whitespace and literal values have the same
  shape and different identities; a function and itself with one statement reordered have different
  shapes; CRLF and LF sources hash identically; the hash of the spec's `print("hello world!")` is
  the one P0-T3 already produced (recorded as a constant so a normalization change is loud).

### P1-T3 · The Python extractor, in full

- **What:** `extract/python.py`: every addressable definition of spec §3 — module-level `def`,
  `async def`, `class`, simple constant assignment; class members as `Class.member`; the span
  from the first decorator through the end of the body; `kind` (`function`, `class`, `constant`,
  `script`); name, signature (from `ast.unparse` of the arguments and returns), first docstring
  line; a whole file as a script when no symbol is asked for. **Derived references**: imports and
  attribute access resolvable statically within the same repository, emitted as `ref` links with
  `origin: derived`, plus the set of third-party and stdlib imports each definition needs
  (`stdlib` decided with `sys.stdlib_module_names`).
- **Preconditions:** P1-T2.
- **May touch:** `src/cttp/extract/{__init__,python}.py`, `tests/test_extract_python.py`,
  `tests/fixtures/pyrepo/` (a small package with decorators, nested defs, a class with methods,
  constants, relative imports).
- **Accept:** For the fixture package, `cttp resolve <locator>#<symbol> --json` returns the exact
  span, signature and docstring for each of: a decorated function, an async function, a class, a
  method (`Class.method`), a class attribute, a constant; a nested function is reported as not
  addressable; the derived references of a function that calls a sibling module's function name
  that function's locator; the third-party import list of the fixture is exactly what it imports
  from outside the repository and the stdlib.

### P1-T4 · The link convention, in full

- **What:** `links.py` finishes spec §4: the three markers (`cttp:`, `cttp-from:`, `cttp-see:`),
  `key=value` fields (`id`, `license`, `track`, arbitrary), the description as the only quoted
  field, the `~` derived-description marker, stacked links above one statement, the block beneath a
  stamped link (from the line after the link to the end of the expanded page — delimited by the
  next link line or a blank line followed by a non-indented line, and recorded explicitly as
  `end` in the link's parsed form so `check` and `fold` never guess). One regular expression finds
  every link line in any language's comment syntax (`#`, `//`, `--`, `/* … */`, `;`).
- **Preconditions:** P1-T3.
- **May touch:** `src/cttp/links.py`, `src/cttp/expand.py` (use the block delimiter),
  `tests/test_links.py`.
- **Accept:** Parse → write round-trips every example line in spec §4 byte-for-byte; a file with
  a `# cttp:` link, a `# cttp-from:` link and a `# cttp-see:` link on a docstring line yields three
  links with the right relation; the C file `bench/drivers/corpus/drivers/hwmon/lm75.c` with a
  `// cttp-see:` line added in a test copy yields one link; a `# cttp:` line with a space inside a
  value is an error naming the field.

---

# Phase 2 — The resolver, in full

### P2-T1 · Locator resolution and the git cache

- **What:** `gitcache.py` in full: fetch with `git fetch` into the cache (bare clones), resolve
  tags and branches to SHAs, `git cat-file` for blobs, `git ls-tree` to enumerate a rev; the
  `[remotes]` config mapping locator prefixes to URL prefixes. `resolve.py`: locator form with a
  symbol (extract one definition), without a symbol (script), and name-without-path (search the
  repository at that rev for a unique symbol, else list candidates and stop); `id=` mismatch
  reported as `mismatch`, never hidden; license derived from `LICENSE*`/`COPYING*` at the rev via
  a small SPDX matcher (MIT, Apache-2.0, BSD-2/3, GPL-2.0/3.0, MPL-2.0, ISC, else `not available`).
- **Preconditions:** P1-T4.
- **May touch:** `src/cttp/{gitcache,config,resolve,cli,schemas}.py`, `tests/conftest.py`,
  `tests/test_resolve.py`, `tests/test_gitcache.py`.
- **Accept:** Against `tmp_path` bare repositories reached through `[remotes]`: a locator with a
  tag rev resolves to a pinned address carrying the full SHA; a name whose registry entry has no
  path finds a unique symbol and stops with a candidate list when there are two; a locator plus a
  wrong `id=` returns `mismatch` with both hashes; the license of a repository with an MIT
  `LICENSE` is `MIT`, origin `derived`, and of one with no license file is `null`. No test opens a
  socket (asserted with a `socket.socket` monkeypatch that raises).

### P2-T2 · The object cache and identity resolution

- **What:** Every resolved page is written to `~/.cache/cttp/objects/<sha256>` (source plus a
  sidecar of metadata and the locators it was seen at). `cttp resolve sha256:<prefix>` answers
  from the cache, then from the index once Phase 4 exists (a hook that returns "not indexed" until
  then). `cttp cache status|clear` for both caches.
- **Preconditions:** P2-T1.
- **May touch:** `src/cttp/{resolve,cli,schemas}.py`, `src/cttp/objects.py`, `tests/test_objects.py`.
- **Accept:** After resolving a locator, resolving its identity with the `[remotes]` target
  deleted still returns the source and the locators it was seen at, with `origin: cache` on the
  location; an unknown identity exits non-zero saying neither the cache nor the index knows it; an
  ambiguous prefix lists the candidates.

### P2-T3 · `resolve --latest`, rules 1 and 2

- **What:** Spec §5's forward resolution: from a pinned address, look at the repository's current
  default-branch head — same path and symbol (report whether the identity changed); else the same
  identity anywhere at head (a move within the repository). Rule 3 (across repositories, via the
  index) is P4-T3; until then the answer says so plainly when rules 1 and 2 fail. The answer
  states the rule that found it as derived metadata.
- **Preconditions:** P2-T2.
- **May touch:** `src/cttp/{resolve,cli,schemas}.py`, `tests/test_latest.py`, `tests/conftest.py`
  (fixture repository with a history: edit, then rename-and-move).
- **Accept:** On the fixture history: after an edit, `--latest` returns the new identity with
  `rule: same-path`; after a move within the repository, `rule: same-identity`; after a move to
  another repository, `found: false` with the message that rule 3 needs the index.

---

# Phase 3 — The materializer, in full

### P3-T1 · The closure

- **What:** `expand.py`: from a page, compute the set of definitions it references, recursively,
  within the origin repository at the pinned rev, using P1-T3's derived references; stdlib imports
  left as written; third-party imports kept and the package requirement reported; anything
  unresolvable stops the operation naming it; the size budget (50 definitions / 2,000 lines) with
  the `--package` suggestion. Output is an ordered list — dependencies before dependents, stable
  order for equal rank — that `cttp closure <address>` prints (this is also the index query's shape
  in P4-T2).
- **Preconditions:** P2-T3.
- **May touch:** `src/cttp/{expand,cli,schemas}.py`, `tests/test_closure.py`,
  `tests/fixtures/pyrepo/` (a function that calls two siblings, one of which calls a third; a
  function importing `requests`; a function calling a name that does not exist).
- **Accept:** `cttp closure <locator>#top --json` lists exactly the three definitions in
  dependency order, each with its pinned address and identity; the `requests` case reports
  `requires: ["requests"]` and keeps the import; the unresolvable case exits non-zero naming the
  missing name; a fixture with 51 tiny definitions is refused with the budget message.

### P3-T2 · Expansion with closure, and `add`

- **What:** `expand` writes the closure beneath the link — each dependency above its first use,
  each beneath its own stamped link, third-party imports hoisted to one place above the block —
  so the file runs top to bottom; `--write-deps` appends requirements to `pyproject.toml`
  (`[project] dependencies`) and otherwise only reports them. Descriptions: asserted from the
  registry for names, else derived (`~"…"`) from signature and docstring. `cttp add <address> [<file>]`
  writes the link (at the end of the file, or at `--at <line>`) and expands it.
- **Preconditions:** P3-T1.
- **May touch:** `src/cttp/{expand,links,cli}.py`, `tests/test_expand.py`.
- **Accept:** The spec §7 `greet`/`hello-world` example reproduces byte-for-byte from a fixture
  registry with those two names; the expanded file runs with `/usr/bin/python3 -I`; the
  `requests`-using fixture expands with the import above the block and reports the requirement,
  and `--write-deps` adds it to a fixture `pyproject.toml`; `cttp add` on an empty file produces
  the same as writing the link and running `expand`; re-running `expand` on an expanded file is a
  no-op (byte-identical).

### P3-T3 · `check --fix` and `update`

- **What:** `check` reports `unexpanded`, `drift`, `unresolvable`, and `mismatch` per link with
  file and line, `--json` included, exit 1 on any; `--fix` converts drifted `# cttp:` to
  `# cttp-from:` (keeping address and stamp) and reports each conversion. `update`: for each
  selected link (`track=latest` ones by default, named addresses, `--all`, or `--to <rev>`),
  re-resolve with `--latest`, show a unified diff of the code beneath, rewrite stamp and code on
  confirmation or `--yes`; on a `# cttp-from:` link show the upstream diff since the pinned
  version and change nothing. Project-level `track = "latest"` in `cttp.toml` is honored.
- **Preconditions:** P3-T2.
- **May touch:** `src/cttp/{expand,cli,schemas}.py`, `tests/test_check.py`, `tests/test_update.py`.
- **Accept:** A file with one clean, one drifted, one unexpanded link: `check` exits 1 listing
  exactly the two problems; `check --fix` rewrites the drifted link to `cttp-from:` and `check`
  then reports only the unexpanded one; after the fixture origin repository advances, `update`
  with `track=latest` on one link shows the diff and rewrites that link only, and `update --all`
  the rest; `update` on the `cttp-from:` link prints the upstream diff and leaves the file
  byte-identical.

### P3-T4 · `fold` and `run`, in full

- **What:** `fold [<file>…] [--open <address>]`: print the file with every stamped block collapsed
  to its link line and description, `--open` unfolding one; `--json` returns the list of links
  with line ranges (this is what the MCP `fold` tool returns). `run`: files as well as addresses;
  a file with unexpanded links is expanded into the cache copy and run from there, the file left
  untouched; first-run confirmation shows source, identity and license of every page about to run.
- **Preconditions:** P3-T3.
- **May touch:** `src/cttp/{expand,cli,schemas}.py`, `tests/test_fold.py`, `tests/test_run.py`.
- **Accept:** `fold` on the spec §7 example prints two link lines and nothing else, and with
  `--open greet` prints the `greet` block and the `hello-world` link line; the file is unchanged
  after `fold`; `run` on a file containing only `# cttp: hello-world` prints `hello world!` and
  leaves the file at one line; `run` without `--yes` on an uncached address shows the source and
  waits (tested by feeding `n` and asserting nothing ran).

### P3-T5 · `expand --package`

- **What:** The fallback of spec §7: the closure written into `cttp_vendor/<name>.py` with the
  same stamped links inside, and `from cttp_vendor.<name> import <symbol>` beneath the link in the
  user's file; `check`, `fold`, and `update` treat vendored files like any other.
- **Preconditions:** P3-T4.
- **May touch:** `src/cttp/{expand,cli}.py`, `tests/test_package.py`.
- **Accept:** The 51-definition fixture expands with `--package` into one vendored module, the
  user's file gains one import beneath the stamp, the program runs with `/usr/bin/python3 -I`, and
  `check` on the project passes and then fails when a vendored definition is edited.

---

# Phase 4 — The index

### P4-T1 · Schema and crawl

- **What:** `index/schema.py`: the five tables of spec §6 with identity as the key of
  `definitions` and a separate `locations` table (repo, sha, path, symbol) so that one identity in
  three places is one row plus three; `index/crawl.py`: `cttp index add <repo-or-path>` registers
  a repository (a locator, or a local path whose `origin` remote names it), `cttp index crawl [--rev]`
  extracts every Python file at the head (or given rev) of each registered repository, records
  definitions, derived `ref` links, and every asserted link found by `links.py` in any file;
  `cttp index status` counts. Default index `~/.local/share/cttp/index.db`, `--index <path>`.
- **Preconditions:** P3-T5.
- **May touch:** `src/cttp/index/{__init__,schema,crawl}.py`, `src/cttp/cli.py`,
  `tests/test_index_crawl.py`.
- **Accept:** Crawling the `pyrepo` fixture and a consumer fixture that links to it produces the
  expected row counts, one `definitions` row per distinct identity, and `links` rows for both the
  derived references and the consumer's asserted link, each with `origin`; crawling twice at the
  same rev changes nothing; crawling at a second rev adds a `revisions` row and only the changed
  definitions.

### P4-T2 · The queries

- **What:** `index/queries.py` and the CLI: `who <address>` (by relation and origin),
  `dups [--shape]`, `closure <address>…` (from indexed links, same output shape as P3-T1),
  `search <text>` (name, signature, docstring; SQLite FTS5), `history <address>`, `rank`. All
  with `--json`.
- **Preconditions:** P4-T1.
- **May touch:** `src/cttp/index/queries.py`, `src/cttp/{cli,schemas}.py`, `tests/test_index_queries.py`.
- **Accept:** On the crawled fixtures: `who` on the origin function lists the consumer's `is` link
  (asserted) and the sibling's `ref` (derived); `dups` groups a function duplicated verbatim in two
  fixture files as one identity with two locations and `dups --shape` adds the renamed copy;
  `search greet` finds `greet` by name and a function whose docstring mentions greeting; `history`
  on a definition edited across two crawled revs lists both identities in order; `rank` puts the
  most-linked definition first.

### P4-T3 · `--latest` rule 3, and acceptance tests 2 and 3

- **What:** Rule 3 of spec §5 through the index: a `# cttp:` or `# cttp-from:` link back to the
  original address anywhere crawled. Then the spec's acceptance tests 2 and 3 as pytest tests over
  fixture repositories A, B and a consumer, plus the identity-only variant of test 2.
- **Preconditions:** P4-T2.
- **May touch:** `src/cttp/resolve.py`, `tests/test_acceptance_move.py`,
  `tests/test_acceptance_provenance.py`, `tests/conftest.py`.
- **Accept:** Test 2: `resolve --latest` on the original address returns the definition in B with
  `rule: backlink`; with no `cttp-from` link and B crawled, `rule: same-identity` via the index.
  Test 3: after `cttp add` in the consumer and `cttp index add` of it, `who` on the original lists
  the copy as `is`, origin `asserted`, with its license field present.

### P4-T4 · The viewer

- **What:** `server/`: the pages of spec §9 — search at `/`, `/d/<identity>`,
  `/r/<host>/<owner>/<repo>`, `/dups` — over the index, and the name page gains history and
  *who links here*; derived and asserted facts visually separated on every page (two columns or
  two labelled sections, chosen once in `base.html`). Server-rendered, no client-side framework,
  one small stylesheet.
- **Preconditions:** P4-T3.
- **May touch:** `src/cttp/server/**`, `tests/test_server.py`.
- **Accept:** With the fixtures crawled into a test index and the server up on 3120, each page
  returns 200 with the expected content; the name page for `hello-world` shows the consumer copy
  under *who links here* labelled asserted and its identity labelled derived; looked at in the
  browser and confirmed readable on a phone-width window.

---

# Phase 5 — The agent interface

### P5-T1 · Stable `--json` schemas

- **What:** `schemas.py` becomes the single definition of every command's JSON output (TypedDicts
  or dataclasses), with `origin` on every derived or asserted value, `null` for unavailable, and a
  `schema_version` field; a test that runs every command against the fixtures and validates the
  output against the schema; `docs/json-schemas.md` generated from the definitions and registered
  in `CLAUDE.md`'s document map.
- **Preconditions:** P4-T4.
- **May touch:** `src/cttp/schemas.py`, `src/cttp/cli.py`, `tests/test_schemas.py`,
  `docs/json-schemas.md`, `CLAUDE.md` (document map row only).
- **Accept:** The schema test passes for every subcommand; a deliberate schema change fails it
  until `schema_version` is bumped; `docs/json-schemas.md` matches the code (a test regenerates and
  diffs it).

### P5-T2 · `cttp mcp`

- **What:** `mcp.py`: an MCP server (stdio) exposing `resolve`, `who`, `closure`, `search`,
  `dups`, `fold` as tools with the P5-T1 schemas and descriptions that say what each returns and
  when to use it; `cttp mcp` runs it; `cttp mcp install` prints (or with `--claude-code` runs)
  the `claude mcp add` line.
- **Preconditions:** P5-T1.
- **May touch:** `src/cttp/mcp.py`, `src/cttp/cli.py`, `tests/test_mcp.py`, `docs/overview.md`
  (running section: how to attach the server to Claude Code).
- **Accept:** The MCP SDK's client, in a test, lists six tools and calls each against the fixtures
  with the same result as the CLI; from Claude Code with the server added, asking *who links to
  hello-world* produces a tool call to `who` and a correct answer (done by hand, recorded in
  `PROGRESS.md`).

---

# Phase 6 — The read side for every language, and the driver corpus

### P6-T1 · The tree-sitter extractor

- **What:** `extract/treesitter.py` with a per-language query file (`queries/c.scm` first) naming
  definition node types and the name field; identity and shape for C (shape via the grammar's
  identifier and literal nodes, not `tokenize`); `cttp resolve` and `cttp index crawl` route
  non-Python files through it; `cttp-see`/`cttp:` links found in C comments by `links.py`.
- **Preconditions:** P5-T2.
- **May touch:** `src/cttp/extract/{__init__,treesitter}.py`, `src/cttp/extract/queries/c.scm`,
  `src/cttp/index/crawl.py`, `pyproject.toml` (the tree-sitter dependencies),
  `tests/test_extract_c.py`, `tests/fixtures/crepo/`.
- **Accept:** `cttp resolve <locator to bench/drivers/corpus/drivers/hwmon/lm75.c>#lm75_reg_to_mc`
  (or whatever the decoder in that file is named) returns its exact span and a `derived` signature;
  a C fixture with the same function in two files yields one identity; two functions differing only
  in identifiers yield one shape.

### P6-T2 · The driver corpus and acceptance test 1

- **What:** `bench/drivers/`: `fetch.sh` reproduces the corpus — identify the Linux commit the
  preserved corpus came from (fingerprint a handful of files against `git log -S` in a shallow
  clone, or by matching a tag), then sparse-checkout the same directories at that commit into
  `corpus/`; `expected.json` records the duplicate groups the vision names (the four temperature
  decoders by shape, the two verbatim copies by identity), derived by running the tool over the
  corpus and confirmed by reading the functions — the file says which. If the commit cannot be
  identified, `fetch.sh` says so, the preserved copy is the corpus, and the expectation is written
  from it and marked as such.
- **Preconditions:** P6-T1. The preserved corpus at `bench/drivers/corpus/` (736 `.c` files under
  `drivers/{gpio,hwmon,iio,rtc}`, copied from the measurement session's scratchpad on
  2026-09-04).
- **May touch:** `bench/drivers/{fetch.sh,expected.json,README.md}`, `tests/test_acceptance_drivers.py`
  (marked `slow`, skipped when the corpus is absent).
- **Accept:** `cttp index add bench/drivers/corpus && cttp index crawl --index /tmp/drivers.db`
  completes; `cttp dups --shape --json` contains a group whose locations are exactly the four
  decoders in `expected.json`; `cttp dups --json` contains the group of the two verbatim copies;
  neither query was given a hint.

### P6-T3 · The line-level measurement, reproduced

- **What:** `bench/drivers/measure.py`: the substantive-line measurement quoted in the vision
  (37 % shape-identical to a line in another file, 14 % verbatim), recomputed from the corpus with
  the tool's own normalization, printing a small table; the vision's numbers updated if they
  differ, with the method stated.
- **Preconditions:** P6-T2.
- **May touch:** `bench/drivers/measure.py`, `bench/drivers/README.md`, `docs/vision.md` (numbers
  and method only).
- **Accept:** `uv run python bench/drivers/measure.py` prints file count, substantive line count,
  shape-duplicate percentage and verbatim-duplicate percentage; the numbers are within a few points
  of the vision's or the vision is amended to match, and either way the method is written down.

---

# Phase 7 — The registry as a service

### P7-T1 · `name claim` and `name show`

- **What:** `registry.py`: `cttp name show <name>` prints the registry entry and its resolution;
  `cttp name claim <name> --target <locator>` verifies the target repository has a `cttp.toml`
  declaring the name at its default branch, writes `names/<name>.toml`, and opens a pull request
  against the registry repository with `gh` (or prints the file when `--no-pr`); refuses when the
  name exists with a different owner unless `--transfer`, which opens the PR for the old owner's
  approval.
- **Preconditions:** P6-T3.
- **May touch:** `src/cttp/{registry,cli}.py`, `tests/test_name.py`.
- **Accept:** Against a `tmp_path` registry repository and target: a claim with the declaration
  present writes the entry and `--no-pr` prints it; a claim without the declaration is refused
  naming the missing file; a second claim by another owner is refused; `name show hello-world`
  prints the P0-T2 entry.

### P7-T2 · Registry checks and federation

- **What:** A GitHub Actions workflow in `cttp-registry` that runs `cttp name verify` on every
  PR — the declaration at the target exists, labels are valid, the target resolves; the tool's
  `registries` list honoured in order with first-match-wins, and `cttp resolve --json` naming
  which registry answered.
- **Preconditions:** P7-T1. Ask Leo before pushing the workflow — it is outward-facing.
- **May touch:** `src/cttp/{registry,cli}.py`, `tests/test_registry_federation.py`; in
  `cttp-registry`: `.github/workflows/verify.yml`.
- **Accept:** A PR to `cttp-registry` with a bad claim fails the check and a good one passes (done
  once by hand, recorded); with two local registries configured, a name in the second only resolves
  and the answer names the second.

### P7-T3 · `cttp.ai`

- **What:** `server/export.py`: `cttp serve --export <dir>` writes every route of the contract for
  every name as static files (`<name>/index.html`, `<name>.json`, `<name>@<version>.json`, `/`),
  identical to the live responses; a workflow in `cttp-registry` publishes the export to GitHub
  Pages on every merge; the domain `cttp.ai` pointed at it; the tool's default registry list becomes
  `https://cttp.ai` then `http://localhost:3120`.
- **Preconditions:** P7-T2. Ask Leo for the DNS change and before the first public publish.
- **May touch:** `src/cttp/server/export.py`, `src/cttp/{config,cli}.py`, `tests/test_export.py`;
  in `cttp-registry`: `.github/workflows/pages.yml`.
- **Accept:** `curl -s https://cttp.ai/hello-world.json` returns the same object as
  `localhost:3120/hello-world.json`; a fresh machine with cttp installed and no config runs
  `cttp run hello-world --yes` and prints `hello world!`.

---

# Phase 8 — The benchmark

### P8-T1 · The harness

- **What:** `bench/agent/harness.py`: one driver that runs **Claude Code headless** — `claude -p
  <prompt> --output-format json` as a subprocess, under Leo's subscription login (never `--bare`,
  which needs an API key) — with two **arms** that differ only in the tool list. *links*:
  `--mcp-config` attaching the cttp MCP server (`resolve`, `who`, `closure`, `search`, `dups`,
  `fold`) with `--strict-mcp-config`, plus `Write`, `Edit` and `Bash` restricted to the task's
  test command (`Bash(<test command>)`), with `Read`, `Grep` and `Glob` disallowed; *baseline*:
  `Read`, `Grep`, `Glob` plus the same `Write`, `Edit` and `Bash`, and no MCP server. The same
  `--model` (Opus 5 unless Leo picks otherwise), the same `--append-system-prompt`, the same
  `--max-turns`, `--permission-mode dontAsk` with `--permission-prompts none`, run from a fresh
  checkout in `tmp_path` with a scratch `HOME`-independent `--settings` so nothing from `~/.claude`
  (hooks, plugins, memory, the user-scope cttp MCP server) leaks into either arm. Per run it
  records the result object's `usage` (input, output, cache read, cache write, and the per-model
  breakdown), the sum as **tokens of context consumed**, `total_cost_usd` as the estimate it is,
  `num_turns`, wall time, `permission_denials`, and pass/fail from the task's grader. Results go
  to `bench/agent/results/<date>/<task>/<arm>/<run>.json`, the raw result JSON kept beside each.
  A usage-limit failure (`rate_limit` in the result, or a non-zero exit naming the limit) is
  recorded as `limited`, not as a fail, and the driver waits for the window to reset or stops
  and says so; `--resume-run` picks up where a run stopped. Consult the Claude Code docs
  (`code.claude.com/docs/en/headless`, `cli-reference`) for the flags — not memory — and the
  `claude-api` skill only if a model or effort question comes up.
- **Preconditions:** P5-T2 (the tools) and P4-T2 (the queries). Leo logged in to Claude Code on
  this machine (`claude auth status`); no `.env`.
- **May touch:** `bench/agent/{harness,graders,report}.py`, `bench/agent/README.md`.
- **Accept:** A smoke task (fix a one-line bug in the `pyrepo` fixture) runs in both arms and
  writes two result files with the fields above; the links arm's `system/init` shows the cttp
  server connected and the baseline's shows none; a dry-run mode replays a recorded result JSON
  and produces identical numbers, so the report can be tested without using the subscription.

### P8-T2 · The task set

- **What:** `bench/agent/tasks/`: fifteen tasks, three families, five each, every one with a
  prompt, a setup (repository at a commit, index prepared), and a grader. **In-repository
  changes**: three mid-size Python repositories (5k–30k lines, good test suites, permissive
  license — pick from `attrs`, `click`, `tomli-w`, `rich`, `httpx`, and say why in the README),
  tasks taken from real merged commits with their tests as the hidden grader. **Cross-repository
  reuse**: "use function X from repository Y here", graded by the tests plus a correct `# cttp:`
  stamp on what was written. **Impact questions**: "what breaks if this signature changes",
  graded exactly against `who` on the index. Each task pinned to commits so it never drifts.
- **Preconditions:** P8-T1.
- **May touch:** `bench/agent/tasks/**`, `bench/agent/README.md`.
- **Accept:** `uv run python -m bench.agent.harness --list` shows fifteen tasks; every grader runs
  against its own reference solution and passes, and against the unmodified repository and fails.

### P8-T3 · Run and report

- **What:** Run every task three times per arm; `report.py` writes `bench/agent/results/<date>/report.md`
  — a table with one row per task and family totals: median tokens per arm, pass rate per arm, and
  the ratio; a short `docs/benchmark.md` stating the method, the table, and the honest reading of
  it, registered in `CLAUDE.md`'s document map — including the caveat that both arms ran inside
  Claude Code's harness. From P8-T1's smoke run, estimate the tokens per run and how many of
  the ninety fit in one of the subscription's 5-hour windows, and tell Leo before starting; the
  full run may span several windows and days.
- **Preconditions:** P8-T2. Leo's go-ahead on the estimated usage and the time it will take.
- **May touch:** `bench/agent/report.py`, `bench/agent/results/<date>/**`, `docs/benchmark.md`,
  `CLAUDE.md` (document map row only), `PROGRESS.md`.
- **Accept:** The table exists with ninety runs behind it (fifteen tasks × two arms × three runs),
  every cell traceable to a result file; `docs/benchmark.md` says what the number means and what
  it does not.

---

## Deliberately not in this plan

- **Publishing `cttp` to PyPI.** The spec has no view on it; it is a follow-up in `PROGRESS.md`
  with the name check as its trigger.
- **An editor extension.** A wanted convenience (spec §13); scheduled when a person uses expanded
  files in an editor for real.
- **A dynamic `cttp.ai` host.** The static export meets the contract; a host arrives when the
  public index outgrows a static render.
- **A second write-side language.** A new spec section first (spec §13).
- **Anything in spec §14.** Those questions are answered by contact with real files, and the task
  that meets each one amends this plan when it does.
