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

Today the whole of the hello-world loop exists in real form: all three address forms, with a
`#symbol` selecting one Python definition of a file; a registry that is a public git repository
(`github.com/leorinaldi/cttp-registry`) or an HTTP server speaking the registry contract;
identity and shape hashes; a Python extractor that is exact (`ast`) and derives references;
`expand`, `check` and `run` over one link at a time; and a viewer on port 3120. Identity-address
resolution, the object cache, the index, closure expansion, `fold`, `update` and the benchmark
are still ahead — [`plan.md`](plan.md) lays out the phases.

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
- **Links** (`links.py`) — one regex finds every `# cttp:` line; fields are `key=value`, the
  description is the trailing quoted string. A link with an `id=` field is *stamped*.
- **Registry** (`registry.py`) — an ordered list from the config. Each is a **local registry
  repository** (`cttp.toml` + `names/<name>.toml`, each entry mapping a name to a
  `host/owner/repo/path` target and version labels to refs) or an **HTTP registry** serving
  `GET /<name>[@<version>][%23<symbol>].json` — a symbol rides the same route, percent-encoded.
  First that knows the name answers; a miss falls through.
- **Git cache** (`gitcache.py`) — bare clones under `$CTTP_HOME/repos/<host>/<owner>/<repo>`,
  fetched from wherever `[remotes]` in the config points, else `https://<locator>.git`. Reads
  blobs at a rev and the license file at that rev.
- **Extractor** (`extract/`) — `extract(path, source, symbol, files)` turns a file at a rev,
  or one definition of it, into a `Page`: kind, language, normalized source, span, and for a
  definition its symbol, signature, first docstring paragraph, **derived references** (`Ref`s
  to files and definitions in the same repository, resolved against the rev's file list) and
  the stdlib / third-party modules it needs. The Python extractor is exact, via `ast`; any other
  file is a `text` script page with no shape and no references.
- **Resolver** (`resolve.py`) — address → `Resolved`: pinned address (symbol kept), full rev,
  identity, shape, kind, symbol, signature, docstring, span, source, description, license,
  target, refs (as pinned locator addresses at the same rev, `origin: derived`), imports, and
  which registry answered. Against a local registry it does the
  git and extraction work itself; against an HTTP registry it takes the server's object as is.
  **The server resolves, the client asks** — that is the contract.
- **Materializer** (`expand.py`) — `expand` (write source beneath the link), `check` (stamped?
  hashes to its id? still resolvable?), `run` (materialize into a run cache and execute with the
  host interpreter).
- **Server** (`server/app.py`) — FastAPI on **3120**, Jinja2 templates. Serves the contract
  (`/<name>.json`, `/<name>@<version>.json`) and the human pages (`/`, `/<name>`) over the
  configured **local** registries only.
- **CLI** (`cli.py`) — Typer. `cttp --version | config | resolve | serve | expand | check | run`.
  Every subcommand takes `--json`, before or after the subcommand name.

Data an address needs lives in three places on disk, all of them derivable:

| Location | What | Env override |
|---|---|---|
| `~/.config/cttp/config.toml` | `registries` (ordered) and `[remotes]`; **written with defaults on first run** | `CTTP_CONFIG` (path), `CTTP_REGISTRY` (replace the list with one entry) |
| `~/.local/share/cttp/registry` | a clone of the public registry repo; the second default registry | (an entry in the config) |
| `~/.cache/cttp/` | `repos/<locator>` bare clones; `run/<pinned address>/main.py` and `run/file-<hash>/` run caches | `CTTP_HOME` |

## 3. Repo map

| Path | What | Status |
|---|---|---|
| `src/cttp/` | the package; see §2 | authored |
| `src/cttp/extract/` | `__init__.py` (`Page`, `Ref`, `extract()` dispatch by suffix), `python.py` (the `ast` extractor) | authored |
| `src/cttp/server/templates/` | `base.html`, `index.html`, `name.html` | authored |
| `tests/` | pytest, one file per concern (`test_address`, `_hashing`, `_extract_python`, `_config`, `_links`, `_resolve`, `_expand`, `_check`, `_run`, `_server`, `_cli`); `conftest.py` builds the offline world | authored |
| `tests/fixtures/registry/` | the registry repository's contents — **identical to the public repo at `v1`**; keep them in sync | authored |
| `tests/fixtures/hello/hello.py` | one line, `# cttp: hello-world` | authored |
| `tests/fixtures/thermo/` | a fake sensor package (`src/thermo/{__init__,decode,lm75}.py`) with every definition kind the extractor must handle; served in tests as `github.com/leorinaldi/thermo` | authored |
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
- **A definition's references are the names it uses; a script's are every import it makes.**
  Reference resolution is static and repository-local: an import or attribute chain becomes a
  `Ref` only when the longest module prefix names a file at that rev; anything else is a
  stdlib or third-party top-level module, decided by `sys.stdlib_module_names`. A parameter
  shadows a module-level import.
- **A `#symbol` travels the HTTP contract as `%23` in the existing route.** The contract grew
  no route; spec §8's table does not yet say so (a follow-up in `PROGRESS.md`).
- **No lockfile.** The document alone says what runs — web subresource-integrity, not pip. A link
  moves only when asked (`track=latest` and `cttp update` are in the plan, not yet built).
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
  **identity** (`sha256:<hex>`). Only the name form is implemented.
- **pinned** — an address whose rev is a commit SHA and which carries an `id=`.
- **stamp** — the pinned address plus identity that expansion writes onto the link line.
- **link** — a `# cttp:` comment line. Later also `# cttp-from:` (derived from) and `# cttp-see:`
  (reference only); neither is recognised yet.
- **page** — what an address resolves to: a definition (`function`, `class`, `constant`) or a
  script, with its normalized source. A definition's source is its span, dedented.
- **symbol** — the dotted name of a definition within a file: `reg_to_millicelsius`,
  `LM75.read_temp`. Module-level defs, classes, constants and class members are addressable;
  nested defs are not, and the error says which definition they are nested in.
- **shape** — the identity's structural twin: same hash over the placeholder text. Equal shapes
  with different identities mean a near-duplicate.
- **ref** — a derived reference from a page to another file or definition in its repository,
  emitted as a link with `relation: ref`, `origin: derived`.
- **block** — the lines beneath a stamped link that `check` hashes. Currently: to the next link
  line or EOF, trailing blanks dropped — so **user code after an expanded definition reads as
  drift** until the plan's P1-T4 defines the block properly.
- **entry** — a registry's record for a name: target, description, owner, default, versions.
- **locator** — `host/owner/repo`, no scheme. `split_target` splits an entry's target into
  locator and path.
- **registry contract** — the HTTP shape of spec §8: `GET /<name>[@<version>].json` returns the
  resolver's object.
- **miss** — a registry that does not know a name, is unreachable, or is a configured path with
  nothing at it (`MissingRegistry`). A miss asks the next registry; the final error names them all.
- **drift** — a stamped link whose block no longer hashes to its `id=`.
- **derived / asserted** — computed by the tool from the repository versus stated by a person.

## 6. Invariants — never violate

- **No runtime component.** Nothing cttp emits is imported, decorated or called at run time.
  Expanded files run under `/usr/bin/python3 -I` with cttp absent. `test_no_runtime_component`
  guards this.
- **The server never asks an HTTP registry.** It opens registries `local_only=True`; a config that
  lists `http://localhost:3120` first would otherwise make the server query itself.
- **Tests never touch the network.** `conftest.py` puts a registry repo, a bare "remote" and a
  config in `tmp_path`, points `CTTP_CONFIG` and `CTTP_HOME` there, and maps the
  `github.com/leorinaldi/` prefix at the bare repo through `[remotes]`. The server tests drive
  the FastAPI app in-process through the test client.
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
- **`expand` refuses a page that itself contains `# cttp:` lines.** Closure expansion is P3-T1;
  until then the refusal is correct behaviour, not a bug.
- **A non-Python file resolves with `shape: null` and `language: "text"`.** Not an error: only
  Python has an extractor today. Asking for a `#symbol` in such a file is the error.
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
