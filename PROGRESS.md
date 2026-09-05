# PROGRESS — cttp

cttp — *code text transfer protocol* — is a protocol that sits on top of existing programming languages
and lets code point at code: every definition gets an address, references are links rather than imports,
and an index answers who links where. Rationale: [`docs/vision.md`](docs/vision.md).

**Status: STAGE 1 EXITING — VISION AGREED, SPEC DRAFTED AND DISCUSSED, AWAITING LEO'S FINAL READ.**
On 2026-09-04 Leo agreed the vision, and the spec was written and then reshaped in conversation
around his hello-world picture: a program can be a single line, `# cttp: hello-world`; the tool
expands the link **in place**, once, at edit time, stamping the line with version and hash; there is
**no lockfile**; the registry is an HTTP contract served on localhost first and later at **cttp.ai**,
which Leo now owns. Nothing is built and no code exists.

_Last updated: 2026-09-04._

> **Read [`docs/overview.md`](docs/overview.md) first** — it is the lay of the land. This file is
> only *where we are*: state, next steps, follow-ups and recent history. (`overview.md` is blank
> until Stage 4 of [`docs/project-start-sequence.md`](docs/project-start-sequence.md); that is
> expected.)

## Next session — suggested next steps

**Start here: confirm the spec stands, then write [`docs/plan.md`](docs/plan.md) (Stage 2).** Leo
read the spec's substance through conversation on 2026-09-04 and said "all of this makes sense";
he has not yet read the final text line by line. Ask whether it stands as written. If yes, Stage 1
exits and the plan is next.

The plan's Phase 0 is fixed by the spec's fourth acceptance test (section 12): a `uv` project with
a `cttp` console script, `cttp serve` answering on **http://localhost:3120** with the registry
contract (`/<name>`, `/<name>.json`) over a local registry repo containing `hello-world`, and
`cttp expand` turning a file holding only `# cttp: hello-world` into the stamped line plus
`print("hello world!")`, run by plain `python`. Phase 1 onward should follow the spec's layer
order: address grammar and hashing → Python extractor → resolver and object cache → `expand`,
`check`, `fold`, `run` → index and `who`/`dups` → MCP server → tree-sitter read side and the driver
corpus test → the benchmark. Decisions the plan has to make that the spec left to it: the model and
harness for the benchmark (consult the `claude-api` skill), the task set, and where the first
registry repo lives (spec suggests `github.com/leorinaldi/cttp-registry`, holding the first
snippets too).

## Current state — working & verified

**Docs**
- `CLAUDE.md` — session procedure only. `AGENTS.md` — pointer to it.
- `docs/vision.md` — **agreed by Leo 2026-09-04.** Stage 0 exit done; the name `cttp` was
  re-confirmed by use (folder renamed, domain bought).
- `docs/spec.md` — **second draft, 556 lines, 14 sections**, written 2026-09-04 and amended the
  same day after discussion. Load-bearing decisions: people write the short form
  (`cttp:hello-world`), the tool writes the pinned form (`@rev id=sha256:…`); a link is a
  substitute for the code at that address; expansion is in place, once, at edit time, never at run
  time; expanded on disk, folded in view; no lockfile (the stamped line is the record — web
  subresource-integrity precedent, not pip/npm); pinned by default, `track=latest` opt-in; editing
  a copy is a fork recorded as `# cttp-from:`; a one-line description rides on the link line
  (asserted from the registry, or derived and marked `~`); pages are definitions or scripts;
  content-addressed object cache under `~/.cache/cttp/objects/`; registry is an HTTP contract, git
  repo of pointer files behind it, proof of control via `cttp.toml` in the target repo, localhost
  first then `cttp.ai`; `cttp run` as a launcher with first-run confirmation; vendored package only
  as the fallback for oversized closures; stack pinned (Python 3.12, uv, typer, ast, tree-sitter,
  SQLite, FastAPI + Jinja2 on 3120, MCP SDK, pytest, ruff). Section 14 lists what is deliberately
  open.
- `docs/plan.md`, `docs/overview.md` — **blank skeletons.**
  `docs/project-start-sequence.md` — the build arc; retires at Stage 5.
- The evidence behind the vision (the 736-file driver measurement) is quoted in `vision.md`; the
  scripts are not in the repo. See follow-ups.

**Environment**
- Git on `main`, remote `origin` → `github.com/leorinaldi/cttp` (**private**).
- Folder is `~/Claude/cttp` (renamed by Leo between the two 2026-09-04 sessions). The project
  kit's `PORTS.md` entry was renamed to match this session.
- **Domain `cttp.ai` registered by Leo, 2026-09-04.** Nothing points at it yet.
- Web port **3120** (nothing serves it yet). No API or database tier by design.
- `uv` is **not installed** on this machine (`which uv` fails); Phase 0 needs it.

## Known follow-ups (deferred)

Every item carries a target: the phase that will close it, `→ standing`, or `→ unscheduled` with the
trigger that would schedule it.

- Install `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`) → **Phase 0**, first step
- Check the measurement scripts and the driver corpus into `bench/drivers/`, or reproduce them, so
  the numbers in `vision.md` and the expected duplicate groups for acceptance test 1 are
  reproducible; the originals live in the 2026-09-04 second session's scratchpad if it survived →
  **plan**, as the first benchmark task
- Name collision check: GitHub (`leorinaldi/cttp`) and `cttp.ai` are ours; **PyPI and npm not yet
  checked** — do so before the first package is published → **Stage 1 of the path**, first publish
- Decide the home of the first registry repo and create it (spec suggests
  `github.com/leorinaldi/cttp-registry`; a `cttp` GitHub org if free, but nothing depends on it) →
  **Phase 0**
- Point `cttp.ai` at a static render of the registry (GitHub Pages) once the registry repo and
  `cttp serve` exist → **unscheduled**; trigger: the local registry contract passes acceptance
  test 4
- Editor extension that folds cttp blocks on open and shows a link's page on hover → **unscheduled**;
  trigger: first real use of expanded files by a person in an editor

## Build history

Keep only the **five most recent** session entries. Older ones get deleted, not archived — `git log`
is the archive, and a bloated history taxes every future session start.

- **2026-09-04 (third session) — Vision agreed; spec written and reshaped around hello world.**
  Leo agreed the vision after one question: how linked code actually runs without a new compiler.
  Answer: the tool acts at edit time and the runtime only ever sees ordinary source. The spec was
  drafted (address grammar, extractors, link convention, resolver, index, materializer, registry,
  surfaces, stack, acceptance tests, benchmark, non-goals, open questions), then a long discussion
  moved it in Leo's direction. His picture: hello world is the single line `cttp:hello-world`, and
  `cttp.ai/hello-world` holds the code; links upon links give extreme sparsity, like the web.
  Decisions that came out of it, in order: (1) no `import cttp` anywhere — cttp is a developer tool
  on the PATH like `gh`, plus an MCP server for Claude Code; (2) the link expands **in place**
  beneath the comment rather than into a vendored package, which was the spec's original default;
  (3) links follow latest only on opt-in — Leo asked whether dynamic updating was right, and the
  precedent survey (pip/npm/Go/Cargo lockfiles, Deno's version-in-URL, Unison's hash-as-name, the
  web's subresource integrity) landed on the web's model: pin in the reference itself, so two
  files that read the same behave the same; (4) therefore **no lockfile**; (5) expansion happens
  once at edit time and is stored in the file, `cttp run` is a launcher with first-run
  confirmation; (6) expanded on disk, folded in view — sparsity for agents via `fold`, for humans
  via editor folding; (7) a one-line description rides on the link line so a folded file reads as
  what it does; (8) editing a copy is a fork, recorded as `cttp-from`, never overwritten by
  `update`; (9) the registry is an HTTP contract served on localhost first, `cttp.ai` later (Leo
  bought the domain during the session; a GitHub org is optional and non-load-bearing). Also
  finished the folder-rename follow-up in the kit's `PORTS.md`.
- **2026-09-04 (second session) — Direction changed; project renamed to cttp; vision rewritten.**
  Honest assessment of the fisheye vision found the read side commoditized and the experiment on
  record a warning. Working from first principles — where lines in giant codebases come from, a
  teardown of the Linux LM75 driver, a measurement across 736 driver files — landed on a protocol:
  definitions get addresses, references are links, an index computes backlinks, files remain the
  rendered form. Load-bearing: protocol over language; links over imports; identity by content,
  discovery by location; a link never means execution; derived and asserted labelled; Python write
  side first, then many languages, then the opportunity for a native language; a registry named as
  a concept with its shape left to the spec. Renamed every doc; created the private remote.
- **2026-09-04 (first session) — Project created and fisheye vision drafted.** Scaffolded from
  `~/Claude/new-project`: session procedure, document skeleton under `docs/`, web port **3120**
  allocated. The fisheye vision (level-of-detail views, typed holes, a leaf-or-composite lint) was
  superseded the same day.

## How to run

**Not built yet.** Once Phase 0 lands, `cttp serve` runs the local registry and viewer at
**http://localhost:3120**. Record the actual bring-up commands here as soon as they exist.

## Config / secrets

- `.env` — not created. Gitignored by design; never commit it.
