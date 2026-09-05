# PROGRESS — cttp

cttp — *code text transfer protocol* — is a protocol that sits on top of existing programming languages
and lets code point at code: every definition gets an address, references are links rather than imports,
and an index answers who links where. Rationale: [`docs/vision.md`](docs/vision.md).

**Status: PHASE 0 COMPLETE; `docs/overview.md` WRITTEN (Stage 4); PHASE 1 STARTED — P1-T1 DONE.
NEXT IS P1-T2 (shape hash).** All on 2026-09-04: the spike, the public registry
`github.com/leorinaldi/cttp-registry` tagged `v1`, the config with an ordered registry list and
`[remotes]`, the registry as an **HTTP contract** (`http://localhost:3120` first, the local clone
second), `run` asking before the first run, and now the **full address grammar** — name, locator
and identity forms in one `Address` type, with `cttp resolve` taking a locator straight through
git. The start-sequence document is retired; `docs/plan.md` is the only source of next steps.
113 tests green, ruff clean.

_Last updated: 2026-09-04._

> **Read [`docs/overview.md`](docs/overview.md) first** — it is the lay of the land. This file is
> only *where we are*: state, next steps, follow-ups and recent history.

## Next session — suggested next steps

**Start here: P1-T2 — identity and shape hashing.** Read its entry in
[`docs/plan.md`](docs/plan.md) in full. Identity normalization is already exact (`normalize()`
in `address.py`, the `print("hello world!")` constant pinned in `tests/test_address.py`); the
new work is the **shape** hash — the normalized text with identifiers replaced by positional
placeholders and literals by typed placeholders via `tokenize`, keywords and builtins kept —
exposed as `shape(text)` beside `identity(text)`, full and 12-hex forms. The plan allows a new
`hashing.py`; `address.py` is 190 lines and mostly grammar now, so moving `normalize`, `identity`,
`short` and the new `shape` into `hashing.py` is the reasonable call (keep re-exports so the
imports in `expand.py`, `resolve.py` and the tests keep working, or update them).

Then **P1-T3** (Python definitions via `ast`, so `#symbol` resolves) and **P1-T4** (the block
beneath a link defined properly; `cttp-from` and `cttp-see`).

If Leo wants to play, the demo is in **How to run** below; a locator link works there too now.

## Current state — working & verified

**Code (`src/cttp/`), 2026-09-04.** Real modules in minimal form:
- `config.py` — **P0-T3/T4.** `~/.config/cttp/config.toml` (XDG; `CTTP_CONFIG` overrides the
  path): `registries` (ordered list of HTTP URLs or local paths; first match wins) and
  `[remotes]` (locator prefix → URL prefix, longest prefix wins, else `https://<locator>.git`).
  Paths take `~`; relative paths are relative to the file. **First run writes the file** with
  the defaults: `http://localhost:3120`, then `~/.local/share/cttp/registry`, no remotes.
  `--registry <entry>` or `CTTP_REGISTRY` replaces the list with that one entry (remotes kept).
  `cttp config [--json]` prints the effective result.
- `address.py` — **P1-T1.** All three spec §2 forms in one frozen `Address` (`form`, `name`,
  `locator`, `path`, `rev`, `symbol`, `identity`): `parse()` accepts the optional `cttp:` marker,
  lower-cases the host and hex, turns backslashes into slashes, drops a trailing slash, rejects
  `.`/`..` segments; `str()` is the canonical text and `format(marker=True)` restores the
  marker — every spec example round-trips byte for byte. `is_pinned` = identity form or a SHA
  rev (`is_sha`, 12–40 hex; `gitcache` imports it). `parse_pinned()` rejects a tag or branch
  where a stamp needs a SHA. Errors name the offending part (label, version, symbol part, host,
  owner, rev, path segment, hex length). **In a locator, the first `/` after `@` starts the
  path**, so a branch with a slash cannot be a locator rev (name-form revs may have slashes).
  Also `normalize()` and `identity()`; the identity of `print("hello world!")` is pinned in
  `tests/test_address.py` (`75a27070015e…`). Symbols and identity addresses parse but
  `resolve` refuses them (P1-T3, P2-T2).
- `extract/python.py` — a whole file as a script page only.
- `gitcache.py` — bare clones under `$CTTP_HOME` (default `~/.cache/cttp`)`/repos/<locator>`,
  cloned from `config.url_for(locator)`; rev-parse, blob at rev, license from the first line of
  `LICENSE*`/`COPYING`. **A fetch is skipped when the wanted rev is a SHA already in the cache**,
  so `check` on an expanded file is offline once the repo is cached; labels always fetch.
- `registry.py` — `Registries`: the configured list, asked in order; a `RegistryError` from
  one is a miss and the next is asked; when all miss, the error names them all with each reason.
  `LocalRegistry` reads `cttp.toml` + `names/*.toml`. `HttpRegistry.fetch(name, version)` is
  `GET <url>/<name>[@<version>].json` and returns the server's object (**the server resolves,
  the client asks**); 404 and an unreachable server are misses, anything else is an error.
  `MissingRegistry` stands in for a configured path with nothing at it (a miss that says how to
  clone). `Registries(local_only=True)` is what the **server** uses — it must never ask an HTTP
  registry, which could be itself. `create_local_registry()` builds one from the fixture.
- `resolve.py` — `resolve()` for a **name** asks each registry in turn: an HTTP one yields
  `Resolved.from_json(...)` with `registry` set to the URL; a local one goes through
  `resolve_entry()`: entry → locator → git → extract → hash. For a **locator** (P1-T1)
  `resolve_locator()` goes straight to git through `[remotes]` — the contract has no locator
  route, so HTTP registries are not asked; `Registries.entry_for_target()` finds a local entry
  naming the same target and lends its `name`, `description` and `registry`, else those are
  `None` (`Resolved.name` and `.registry` are now `str | None`). The pinned address of a locator
  is `host/owner/repo@<12-hex>/path`. `to_json()` adds `origin` fields.
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
- `server/app.py` — FastAPI on **3120**: `/`, `/<name>`, `/<name>.json`, `/<name>@<version>.json`;
  Jinja2 templates with derived/asserted tags. Looked at in a headless browser: renders correctly.
- `cli.py` — `cttp --version | config | resolve | serve | expand | check | run`; `--json` is
  accepted before or after the subcommand.
- Tests: 113 in `tests/` — `test_{address,config,links,resolve,expand,check,run,server,cli}.py`.
  `test_address.py` is table-driven: the spec §2 examples round-trip, ~22 valid and ~30 invalid
  inputs with the message fragment each must carry. Locator coverage: `test_resolve.py` (same
  page as the name, README with no entry, errors), `test_cli.py` (the plan's acceptance command
  returns the same object as the name form except `address`), `test_check.py` (a locator link
  expands, pins a SHA, checks ok).
  `test_expand.py::test_acceptance_test_4_hello_world` is spec §12 test 4 verbatim through the
  CLI. `conftest.py` builds, in `tmp_path`, a registry repo, a **bare clone of it under
  `remotes/github.com/leorinaldi/cttp-registry`**, and a config whose `[remotes]` maps the prefix
  there; `CTTP_CONFIG` and `CTTP_HOME` point at `tmp_path`; `add_to_registry()` adds a name to
  both for a test; `hello` copies `tests/fixtures/hello/hello.py`. `test_server.py` drives
  the FastAPI app in-process and points an `HttpRegistry` at it through the test client
  (`via_http` fixture), so the HTTP path is tested without a socket. No network.
  `test_no_runtime_component` guards the no-runtime rule.

**Corners the spike cut (each is closed by the named task):**
- `[remotes]` exists but there is no license matcher beyond the first-line map, and no mirror
  has been exercised outside the tests → **P2-T1**
- No object cache; no symbols; identity addresses parse but do not resolve → **P2-T2 / P1-T3**
- Stamps use 12-hex for rev and identity (the plan's choice), full SHA returned in JSON → keep
- The block beneath a link runs to the next link line or EOF → **P1-T4** defines it properly
- License detection is a two-entry first-line map → **P2-T1**
- `# cttp-from:` and `# cttp-see:` are not recognised → **P1-T4**

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
- The server was restarted on the P1-T1 code on 2026-09-04 (`.local/serve.log`).
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

## Build history

Keep only the **five most recent** session entries. Older ones get deleted, not archived — `git log`
is the archive, and a bloated history taxes every future session start.

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
- **2026-09-04 (fourth session) — Spec confirmed; plan written and agreed; P0-T1 spike built.**
  Leo confirmed the spec as written. The plan was drafted (nine phases, 32 tasks, decisions the
  spec delegated: public registry repo at `leorinaldi/cttp-registry`, 12-hex stamps, XDG config
  with `[remotes]`, benchmark on `claude-opus-5` through the SDK tool runner, `cttp.ai` as a
  static export). Leo asked for a quick-and-dirty working version before going further, so the
  plan was amended: **P0-T1 became a one-session spike** and P0-T2..T5 became its hardening. The
  spike was then built in one go — real modules, minimal bodies — and acceptance test 4 walked
  by hand: serve on 3120, expand, `python3 -I`, `cttp run hello-world`, check pass then drift.
  Load-bearing choices in the spike: the registry repo declares its own locator (`repo =` in
  `cttp.toml`) so the spike can serve it from a local path without a remotes table; `check`
  hashes the block beneath a link up to the next link line; `run` caches by pinned address. Also:
  the driver corpus was rescued from the old scratchpad into `bench/drivers/corpus/`; `uv`
  installed; `ruff format` was found to reformat code blocks in `docs/*.md` and `docs/` is now
  excluded in `pyproject.toml`.

## How to run

```bash
export PATH="$HOME/.local/bin:$PATH"          # uv lives here
uv sync                                        # once; creates .venv
uv run pytest -q                               # 113 tests, no network
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
```

`scripts/make_local_registry.py` still builds an offline registry from the fixture if needed.
The server was left running in the background (`.local/serve.log`); probe
`curl -s -o /dev/null -w '%{http_code}' http://localhost:3120/` before starting another.

## Config / secrets

- `.env` — not created. Gitignored by design; never commit it.
- `~/.config/cttp/config.toml` — the tool's configuration (see `config.py` above). Environment
  knobs: `CTTP_CONFIG` (config file path), `CTTP_HOME` (caches, default `~/.cache/cttp`),
  `CTTP_REGISTRY` (one registry, replacing the list). Tests set the first two to `tmp_path`.
