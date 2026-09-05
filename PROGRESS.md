# PROGRESS — cttp

cttp — *code text transfer protocol* — is a protocol that sits on top of existing programming languages
and lets code point at code: every definition gets an address, references are links rather than imports,
and an index answers who links where. Rationale: [`docs/vision.md`](docs/vision.md).

**Status: STAGE 3 — PHASE 0 UNDER WAY. P0-T1 (THE SPIKE) IS DONE: HELLO WORLD RUNS END TO END.**
On 2026-09-04 Leo confirmed the spec and agreed the plan; the spike was built the same evening.
`cttp serve` answers on 3120, `cttp expand` turns `# cttp: hello-world` into a stamped line plus
`print("hello world!")`, plain `python3 -I` runs it, `cttp run hello-world` runs it with no file,
and `cttp check` passes and then catches drift. 21 tests green, ruff clean.

_Last updated: 2026-09-04._

> **Read [`docs/overview.md`](docs/overview.md) first** — it is the lay of the land. This file is
> only *where we are*: state, next steps, follow-ups and recent history. (`overview.md` is blank
> until Stage 4 of [`docs/project-start-sequence.md`](docs/project-start-sequence.md); that is
> expected.)

## Next session — suggested next steps

**Start here: P0-T2 — create the public registry repository `github.com/leorinaldi/cttp-registry`.**
Read its entry in [`docs/plan.md`](docs/plan.md) in full. Its contents are already written and
committed here under `tests/fixtures/registry/` (that is exactly what the spike serves locally);
the task is to publish them, tag `v1`, and verify an anonymous clone. **Ask Leo before creating
it — it is public.** After that: P0-T3 (config file, `[remotes]`, proper resolver), P0-T4 (HTTP
registry backend), P0-T5 (acceptance test 4 as a full test suite with first-run confirmation),
then **write `docs/overview.md` (Stage 4)** before Phase 1.

If Leo wants to play with the spike first, the demo is in **How to run** below.

## Current state — working & verified

**Code — the P0-T1 spike (`src/cttp/`), 2026-09-04.** Real modules in minimal form:
- `address.py` — name form only (`hello-world`, `@rev|label`, `#symbol` parsed but not resolvable);
  spec §2 normalization and SHA-256 identity. The identity of `print("hello world!")` is pinned
  in `tests/test_address.py` (`75a27070015e…`).
- `extract/python.py` — a whole file as a script page only.
- `gitcache.py` — bare clones under `$CTTP_HOME` (default `~/.cache/cttp`)`/repos/<locator>`,
  rev-parse, blob at rev, license from the first line of `LICENSE*`/`COPYING`.
- `registry.py` — a **local registry repository** (`cttp.toml` + `names/*.toml`); labels map to
  refs; `create_local_registry()` builds one from `tests/fixtures/registry/`.
- `resolve.py` — name → registry → git → extract → hash → `Resolved` with `origin` fields.
- `links.py` — parse and write `# cttp:` lines (stamp, `key=value` fields, quoted description).
- `expand.py` — `expand` (one link, no closure), `check` (unexpanded / drift / unresolvable / ok),
  `run` for an address (`~/.cache/cttp/run/<pin>/main.py`) or a file (copy, expand, run).
- `server/app.py` — FastAPI on **3120**: `/`, `/<name>`, `/<name>.json`, `/<name>@<version>.json`;
  Jinja2 templates with derived/asserted tags. Looked at in a headless browser: renders correctly.
- `cli.py` — `cttp --version | resolve | serve | expand | check | run`, all with `--json`.
- Tests: 21 in `tests/`, all against a `tmp_path` registry repo with caches redirected via
  `CTTP_HOME`; no network. `test_no_runtime_component` guards the no-runtime rule.

**Corners the spike cut (each is closed by the named task):**
- No config file; registry chosen by `--registry`, `CTTP_REGISTRY`, or the default path
  `~/.local/share/cttp/registry` → **P0-T3**
- No `[remotes]`; the only locator that resolves is the registry repo's own (declared as `repo =`
  in its `cttp.toml`), served from its local path; anything else would try `https://<locator>.git`
  → **P0-T3 / P2-T1**
- No HTTP registry backend — `cttp resolve` reads the registry repo directly, not the server →
  **P0-T4**
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
- Editor extension that folds cttp blocks on open and shows a link's page on hover →
  **unscheduled**; trigger: first real use of expanded files by a person in an editor
- Starlette warns that `httpx` with its test client is deprecated in favour of `httpx2` →
  **unscheduled**; trigger: the warning becomes an error on upgrade

## Build history

Keep only the **five most recent** session entries. Older ones get deleted, not archived — `git log`
is the archive, and a bloated history taxes every future session start.

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
- **2026-09-04 (first session) — Project created and fisheye vision drafted.** Scaffolded from
  `~/Claude/new-project`: session procedure, document skeleton under `docs/`, web port **3120**
  allocated. The fisheye vision was superseded the same day.

## How to run

```bash
export PATH="$HOME/.local/bin:$PATH"          # uv lives here
uv sync                                        # once; creates .venv
uv run pytest -q                               # 21 tests, no network
uv run ruff check . && uv run ruff format --check .

uv run python scripts/make_local_registry.py   # once: ~/.local/share/cttp/registry from tests/fixtures/registry
uv run cttp serve                              # http://localhost:3120  (Ctrl-C to stop)
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

The server was left running in the background by the fourth session (`.local/serve.log`); probe
`curl -s -o /dev/null -w '%{http_code}' http://localhost:3120/` before starting another.

## Config / secrets

- `.env` — not created. Gitignored by design; never commit it.
- `CTTP_HOME` (default `~/.cache/cttp`) and `CTTP_REGISTRY` (default `~/.local/share/cttp/registry`)
  are the only environment knobs; tests set both to `tmp_path`.
