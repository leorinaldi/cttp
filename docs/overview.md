# cttp — Orientation

> **Status: not written yet.** Write this once the Phase 0 scaffold exists and runs — there is
> nothing to describe before then. See [`project-start-sequence.md`](project-start-sequence.md)
> Stage 4. Delete this blockquote once there is real content.

**Read this in full at session start.** It is the durable map of the project: what it is, how it is
structured, where things live, the invariants, and the traps that cost real time. It is deliberately
**slow-moving** — nothing here should change more than about monthly.

It carries **no status and no next steps**. For "what is true right now / what's next", read
[`PROGRESS.md`](../PROGRESS.md). For "how to behave in this repo", read `CLAUDE.md`. For why the
project exists, [`vision.md`](vision.md); for where it is going, [`spec.md`](spec.md).

_Last updated: 2026-09-04._

---

## 1. What this is

<!-- The project in a paragraph, as it stands today. Conclusions, not aspirations. -->

## 2. Architecture

<!-- The tiers and the contract between them: what talks to what, who writes what. A diagram if it helps. -->

## 3. Repo map

<!-- Top-level directories, one line each, marking which are authored, derived, or gitignored. -->

## 4. The data model — load-bearing decisions

<!-- The grain, the keys, the deliberate choices that look odd until explained. -->

## 5. Vocabulary

<!-- Domain terms that appear in PROGRESS.md and the code, defined once. -->

## 6. Invariants — never violate

## 7. Do **not** "fix" these

<!-- The deliberate asymmetries that look like bugs. Each one costs a session when rediscovered. -->

## 8. Operational gotchas

<!-- The environment traps that have actually cost time. The most-read section in every project. -->

## 9. Running and testing

<!-- Bring-up commands, the test suites, the ports. Site: http://localhost:3120 -->

## 10. Which document answers which question

## 11. Maintaining this document

Update it only when something **foundational** changes — a decision settled or reversed, a new
invariant, a new top-level directory, a changed bring-up command, a new trap worth warning the next
agent about. The test: *would an agent starting fresh next week be wrong without this?* Everything
dated belongs in `PROGRESS.md` instead.
