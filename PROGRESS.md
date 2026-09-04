# PROGRESS — cttp

cttp — *code text transfer protocol* — is a protocol that sits on top of existing programming languages
and lets code point at code: every definition gets an address, references are links rather than imports,
and an index answers who links where. Rationale: [`docs/vision.md`](docs/vision.md).

**Status: STAGE 0, VISION REWRITTEN AND PUSHED.** The project was renamed from `fisheye` to `cttp`
on 2026-09-04 and `docs/vision.md` was rewritten from scratch around the protocol idea: links not
imports, a language-neutral read side, a three-stage path (Python first, then many languages, then
the opportunity for a native language), and a registry whose shape is left open. Leo chose the
direction, the name, the path, and the registry concept in conversation; the written text is a first
draft of those choices and still awaits his line-by-line read. Nothing is built and no code exists.

_Last updated: 2026-09-04._

> **Read [`docs/overview.md`](docs/overview.md) first** — it is the lay of the land. This file is
> only *where we are*: state, next steps, follow-ups and recent history. (`overview.md` is blank
> until Stage 4 of [`docs/project-start-sequence.md`](docs/project-start-sequence.md); that is
> expected.)

## Next session — suggested next steps

**Start here: Leo reads the rewritten [`docs/vision.md`](docs/vision.md) and amends it.** The
project is at **Stage 0** of [`docs/project-start-sequence.md`](docs/project-start-sequence.md). The
direction is chosen; the text is a first draft of that direction. Once agreed, apply the Stage 0
exit — the folder name (see follow-ups) — and move to the spec.

The vision now fixes the path: Stage 1 is a language-neutral read side plus a **Python** write
side, Stage 2 adds existing languages (TypeScript likely second), Stage 3 is the opportunity for a
cttp-native language, taken only if earned. The spec's first decisions, in the order they bind
everything else: the address format (location + version + content identity), the link convention in
Python source, the materializer's behaviour (native import versus vendored copy with provenance),
what the Stage 1 benchmark measures, and the shape of the registry (naming rules, version pinning,
trust as a central point, federation) — the vision names the registry as a concept and leaves its
shape open on purpose. The vision names three acceptance tests for the idea; the
spec should make them concrete.

## Current state — working & verified

**Docs**
- `CLAUDE.md` — session procedure only, renamed to cttp. `AGENTS.md` — pointer to it.
- `docs/vision.md` — **rewritten 2026-09-04** around the protocol; awaiting Leo's read-through.
  `spec.md`, `plan.md`, `overview.md` — **blank skeletons**, headers renamed.
  `docs/project-start-sequence.md` — the build arc, filled in; retires at Stage 5.
- The evidence behind the vision — a teardown of one Linux driver, then a measurement across 736
  driver files in five directories (37 percent of substantive lines shared across files after
  identifier abstraction; one decoder written four times across three subsystems; a binding that
  disagrees with its driver) — lives in the 2026-09-04 chat session and its scratchpad. The numbers
  are quoted in `vision.md`; the scripts that produced them are not yet in the repo.

**Environment**
- Git on `main`, remote `origin` → `github.com/leorinaldi/cttp` (**private**, created 2026-09-04).
- **Folder on disk is still `~/Claude/fisheye`.** See follow-ups.
- Web port allocated: **3120** (nothing serves it yet). No API or database tier by design.

## Known follow-ups (deferred)

Every item carries a target: the phase that will close it, `→ standing`, or `→ unscheduled` with the
trigger that would schedule it.

- **Rename the folder** `~/Claude/fisheye` → `~/Claude/cttp` between sessions
  (`mv ~/Claude/fisheye ~/Claude/cttp`), and update the entry in the project kit's `PORTS.md`
  under `~/Claude/new-project`. Not done in-session because moving the live working directory
  breaks the running session → **Stage 0 exit**, Leo runs it
- Check the measurement scripts and the downloaded driver corpus into the repo, or reproduce them
  under `bench/`, so the numbers in `vision.md` are reproducible → **Stage 2 (plan)**, as the first
  benchmark task
- Name collision check for `cttp`: GitHub confirmed free (`leorinaldi/cttp` created); one web
  search found no project of that name; **PyPI and npm not yet checked directly** — do so before
  the first package is published → **Stage 1**, first publish

## Build history

Keep only the **five most recent** session entries. Older ones get deleted, not archived — `git log`
is the archive, and a bloated history taxes every future session start.

- **2026-09-04 (second session) — Direction changed; project renamed to cttp; vision rewritten.**
  Leo asked for an honest assessment of the fisheye vision and whether it could yield a step change.
  Assessment: the read side was commoditized, typed holes were nearly free in TypeScript already,
  the lint discipline was the riskiest piece, and the one experiment on record was a warning not a
  confirmation. The conversation then worked from first principles — where the lines in giant
  codebases come from (decisions versus hand-derived consequences), a teardown of the Linux LM75
  driver, a measurement across 736 driver files, and what is fundamental versus mere refactoring —
  and landed on a protocol rather than a language or a toolchain: definitions get addresses,
  references are links, an index computes backlinks, files remain the rendered form. Load-bearing
  decisions in the new vision: protocol over language; links over imports; identity by content,
  discovery by location; a link never means execution; derived and asserted metadata are labelled;
  a three-stage path — Python write side first, then many existing languages, then the
  opportunity for a native language — chosen because the value of links comes from how much there
  is to link to; and a registry (DNS over the addresses, short names, pointers not code, the home
  of a definition's page) named as a concept with its shape deliberately unresolved. Renamed every
  doc; created the private remote and pushed; folder rename left to Leo.
- **2026-09-04 (first session) — Project created and fisheye vision drafted.** Scaffolded from
  `~/Claude/new-project`: session procedure, document skeleton under `docs/`, web port **3120**
  allocated and recorded in the kit's `PORTS.md`. The fisheye vision (level-of-detail views, typed
  holes, a leaf-or-composite lint) was drafted from a brainstorm and superseded the same day.

## How to run

**Not built yet.** Once Phase 0 lands, the local site runs at **http://localhost:3120**.
Record the actual bring-up commands here as soon as they exist.

## Config / secrets

- `.env` — not created. Gitignored by design; never commit it.
