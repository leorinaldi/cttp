# PROGRESS — fisheye

Fisheye is a TypeScript toolchain that makes a codebase cheap for coding agents to navigate and safe for them to
extend: level-of-detail views around a focus, contracts at every public boundary, and outline-first authoring
with typed holes. Product shape and rationale: [`docs/vision.md`](docs/vision.md).

**Status: STAGE 0, VISION DRAFTED.** The scaffold exists and `docs/vision.md` has a full first draft
written from the 2026-09-04 brainstorm. It is not yet agreed by Leo. Nothing is built and no code has
been written.

_Last updated: 2026-09-04 (project created)._

> **Read [`docs/overview.md`](docs/overview.md) first** — it is the lay of the land. This file is
> only *where we are*: state, next steps, follow-ups and recent history. (`overview.md` is blank
> until Stage 4 of [`docs/project-start-sequence.md`](docs/project-start-sequence.md); that is
> expected.)

## Next session — suggested next steps

**Start here: review [`docs/vision.md`](docs/vision.md) with Leo.** The project is at **Stage 0** of
[`docs/project-start-sequence.md`](docs/project-start-sequence.md); the vision is drafted, not agreed.
Walk through it section by section, amend, then apply the Stage 0 exit: re-check whether `fisheye` is
still the right folder name (the name fits the read-side view; the product's core is the write side,
so it deserves a deliberate yes). Then the spec.

Once vision is settled the arc continues: `spec.md` → `plan.md` → Phase 0 scaffold → `overview.md` →
execute the plan.

## Current state — working & verified

**Docs**
- `CLAUDE.md` — session procedure only. `AGENTS.md` — pointer to it.
- `docs/vision.md` — **drafted 2026-09-04**, awaiting Leo's review. `spec.md`, `plan.md`,
  `overview.md` — **blank skeletons**. `docs/project-start-sequence.md` — the build arc, filled in;
  retires at Stage 5.
- The brainstorm and the throwaway experiment that led here (a strict Python "profile" plus checker,
  tested with headless Claude Code on Haiku: correctness tied at 100 percent, cost up about half) live
  only in the 2026-09-04 chat session and its scratchpad; the conclusions are folded into `vision.md`.

**Environment**
- Local git on `main`. **No remote yet** — Leo has not yet said whether to create
  `github.com/leorinaldi/fisheye`.
- Web port allocated: **3120** (nothing serves it yet). No API or database tier by design.

## Known follow-ups (deferred)

Every item carries a target: the phase that will close it, `→ standing`, or `→ unscheduled` with the
trigger that would schedule it.

- Re-check the folder name `fisheye` once `docs/vision.md` is settled → **Stage 0 exit**
- Create the private GitHub repo `leorinaldi/fisheye` if it does not exist yet → **unscheduled**,
  trigger: Leo asks, or the first session that produces work worth pushing

## Build history

Keep only the **five most recent** session entries. Older ones get deleted, not archived — `git log`
is the archive, and a bloated history taxes every future session start.

- **2026-09-04 — Project created and vision drafted.** Scaffolded from `~/Claude/new-project`:
  session procedure, document skeleton under `docs/`, web port **3120** allocated (web only) and
  recorded in the kit's `PORTS.md`. `docs/vision.md` written in the same session from a long
  brainstorm on agent-legible code organization. Load-bearing decisions in it: no new language,
  TypeScript only; oracles over instructions; write side (outline plus holes) before read side; the
  benchmark comes first. Next: Leo reviews the vision.

## How to run

**Not built yet.** Once Phase 0 lands, the local site runs at **http://localhost:3120**.
Record the actual bring-up commands here as soon as they exist.

## Config / secrets

- `.env` — not created. Gitignored by design; never commit it.
