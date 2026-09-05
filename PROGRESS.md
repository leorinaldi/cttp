# PROGRESS — cttp

cttp — *code text transfer protocol* — is a protocol that sits on top of existing programming languages
and lets code point at code: every definition gets an address, references are links rather than imports,
and an index answers who links where. Rationale: [`docs/vision.md`](docs/vision.md).

**Status: STAGE 3 — PHASE 0 UNDER WAY. P0-T1 TO P0-T4 ARE DONE; P0-T5 REMAINS.** On 2026-09-04
Leo confirmed the spec and agreed the plan; the spike was built the same evening; the public
registry `github.com/leorinaldi/cttp-registry` was published and tagged `v1`; the resolver runs
off `~/.config/cttp/config.toml` with an ordered registry list and `[remotes]`; and the registry
is now an **HTTP contract**: the default config lists `http://localhost:3120` first and the local
clone second, `cttp resolve` goes through the server when it is up and through the clone when it
is down, and the two answers differ only in `registry`. 41 tests green, ruff clean.

_Last updated: 2026-09-04._

> **Read [`docs/overview.md`](docs/overview.md) first** — it is the lay of the land. This file is
> only *where we are*: state, next steps, follow-ups and recent history. (`overview.md` is blank
> until Stage 4 of [`docs/project-start-sequence.md`](docs/project-start-sequence.md); that is
> expected.)

## Next session — suggested next steps

**Start here: P0-T5 — `expand`, `check`, `run` for a single link; acceptance test 4 as tests.**
Read its entry in [`docs/plan.md`](docs/plan.md) in full. Much of it already exists from the
spike (`tests/test_expand.py` walks expand → `python3 -I` → check → drift → run); what T5 adds is
the **first-run confirmation** in `cttp run` (`--yes` is currently accepted and ignored) and
whatever the plan's acceptance list still lacks. After T5, Phase 0 is complete: **write
`docs/overview.md` (Stage 4)** before starting Phase 1.

If Leo wants to play with the spike first, the demo is in **How to run** below.

## Current state — working & verified

**Code (`src/cttp/`), 2026-09-04.** Real modules in minimal form:
- `config.py` — **P0-T3/T4.** `~/.config/cttp/config.toml` (XDG; `CTTP_CONFIG` overrides the
  path): `registries` (ordered list of HTTP URLs or local paths; first match wins) and
  `[remotes]` (locator prefix → URL prefix, longest prefix wins, else `https://<locator>.git`).
  Paths take `~`; relative paths are relative to the file. **First run writes the file** with
  the defaults: `http://localhost:3120`, then `~/.local/share/cttp/registry`, no remotes.
  `--registry <entry>` or `CTTP_REGISTRY` replaces the list with that one entry (remotes kept).
  `cttp config [--json]` prints the effective result.
- `address.py` — name form only (`hello-world`, `@rev|label`, `#symbol` parsed but not resolvable);
  spec §2 normalization and SHA-256 identity. The identity of `print("hello world!")` is pinned
  in `tests/test_address.py` (`75a27070015e…`).
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
- `resolve.py` — `resolve()` asks each registry in turn: an HTTP one yields
  `Resolved.from_json(...)` with `registry` set to the URL; a local one goes through
  `resolve_entry()`: entry → locator → git → extract → hash. `to_json()` adds `origin` fields.
- `links.py` — parse and write `# cttp:` lines (stamp, `key=value` fields, quoted description).
- `expand.py` — `expand` (one link, no closure), `check` (unexpanded / drift / unresolvable / ok),
  `run` for an address (`~/.cache/cttp/run/<pin>/main.py`) or a file (copy, expand, run).
- `server/app.py` — FastAPI on **3120**: `/`, `/<name>`, `/<name>.json`, `/<name>@<version>.json`;
  Jinja2 templates with derived/asserted tags. Looked at in a headless browser: renders correctly.
- `cli.py` — `cttp --version | config | resolve | serve | expand | check | run`; `--json` is
  accepted before or after the subcommand.
- Tests: 41 in `tests/`. `conftest.py` builds, in `tmp_path`, a registry repo, a **bare clone of
  it under `remotes/github.com/leorinaldi/cttp-registry`**, and a config whose `[remotes]` maps
  the prefix there; `CTTP_CONFIG` and `CTTP_HOME` point at `tmp_path`. `test_server.py` drives
  the FastAPI app in-process and points an `HttpRegistry` at it through the test client
  (`via_http` fixture), so the HTTP path is tested without a socket. No network.
  `test_no_runtime_component` guards the no-runtime rule.

**Corners the spike cut (each is closed by the named task):**
- `[remotes]` exists but there is no license matcher beyond the first-line map, and no mirror
  has been exercised outside the tests → **P2-T1**
- No object cache; no symbols; no locator/identity address forms → **P2-T2 / P1-T1 / P1-T3**
- `run` never asks for confirmation (`--yes` is accepted and ignored) → **P0-T5**
- Stamps use 12-hex for rev and identity (the plan's choice), full SHA returned in JSON → keep
- The block beneath a link runs to the next link line or EOF → **P1-T4** defines it properly
- License detection is a two-entry first-line map → **P2-T1**
- `# cttp-from:` and `# cttp-see:` are not recognised → **P1-T4**

**Docs**
- `docs/vision.md` agreed, `docs/spec.md` confirmed as written, `docs/plan.md` agreed — all on
  2026-09-04. `docs/overview.md` still a blank skeleton (Stage 4, after Phase 0).

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
- Starlette warns that `httpx` with its test client is deprecated in favour of `httpx2` →
  **unscheduled**; trigger: the warning becomes an error on upgrade

## Build history

Keep only the **five most recent** session entries. Older ones get deleted, not archived — `git log`
is the archive, and a bloated history taxes every future session start.

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
- **2026-09-04 (third session) — Vision agreed; spec written and reshaped around hello world.**
  Leo agreed the vision after one question: how linked code actually runs without a new compiler.
  Answer: the tool acts at edit time and the runtime only ever sees ordinary source. The spec was
  drafted, then a long discussion moved it in Leo's direction: no `import cttp` anywhere; the link
  expands in place beneath the comment; links follow latest only on opt-in (web
  subresource-integrity precedent); therefore no lockfile; expansion once at edit time, `cttp run`
  as a launcher; expanded on disk, folded in view; a one-line description rides on the link line;
  editing a copy is a fork (`cttp-from`); the registry is an HTTP contract served on localhost
  first, `cttp.ai` later (Leo bought the domain during the session).
- **2026-09-04 (second session) — Direction changed; project renamed to cttp; vision rewritten.**
  Honest assessment of the fisheye vision found the read side commoditized. Working from first
  principles — a teardown of the Linux LM75 driver, a measurement across 736 driver files — landed
  on a protocol: definitions get addresses, references are links, an index computes backlinks,
  files remain the rendered form. Renamed every doc; created the private remote.

## How to run

```bash
export PATH="$HOME/.local/bin:$PATH"          # uv lives here
uv sync                                        # once; creates .venv
uv run pytest -q                               # 21 tests, no network
uv run ruff check . && uv run ruff format --check .

git clone https://github.com/leorinaldi/cttp-registry ~/.local/share/cttp/registry   # once
uv run cttp config                             # first run writes ~/.config/cttp/config.toml; shows it
uv run cttp serve                              # http://localhost:3120  (Ctrl-C to stop)
curl -s localhost:3120/hello-world.json        # the contract; /hello-world is the page
uv run cttp resolve hello-world --json         # registry: http://localhost:3120 when up, the clone when down
```

The demo (acceptance test 4), from any directory with the server up or down:

```bash
printf '# cttp: hello-world\n' > hello.py
uv run cttp expand hello.py && cat hello.py    # stamped line + print("hello world!")
/usr/bin/python3 -I hello.py                   # runs with cttp uninstalled
uv run cttp run hello-world                    # runs with no file at all
uv run cttp check hello.py                     # exit 0
sed -i 's/hello world!/goodbye/' hello.py && uv run cttp check hello.py   # drift, exit 1
uv run cttp --json resolve hello-world         # what an agent sees
```

`scripts/make_local_registry.py` still builds an offline registry from the fixture if needed.
The server was left running in the background (`.local/serve.log`); probe
`curl -s -o /dev/null -w '%{http_code}' http://localhost:3120/` before starting another.

## Config / secrets

- `.env` — not created. Gitignored by design; never commit it.
- `~/.config/cttp/config.toml` — the tool's configuration (see `config.py` above). Environment
  knobs: `CTTP_CONFIG` (config file path), `CTTP_HOME` (caches, default `~/.cache/cttp`),
  `CTTP_REGISTRY` (one registry, replacing the list). Tests set the first two to `tmp_path`.
