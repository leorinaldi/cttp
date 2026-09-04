# PLAN — fisheye

> **Status: not written yet.** Write this after [`spec.md`](spec.md) is settled. See
> [`project-start-sequence.md`](project-start-sequence.md) Stage 2. Delete this blockquote once
> there is real content.

**What this is:** the executable decomposition of [`spec.md`](spec.md) into tasks a coding agent can
pick up and finish in one session. The spec says *what and why*; this says *what to build next, in
what order, and how to know it worked*.

**What this is not:** a status document. Task status lives **only** in [`PROGRESS.md`](../PROGRESS.md).
Entries below are specs — if a task turns out to be wrong, amend it here deliberately and note the
amendment in `PROGRESS.md`'s build history.

_Last updated: 2026-09-04._

---

## How to use this document

1. Read `PROGRESS.md` to find the first task not marked done (if none, start at **P0-T1**).
2. Read that task's entry here **in full**, plus its preconditions.
3. Do only that task. Stay inside its **May touch** list.
4. Run its **Accept** check. It must pass with the stated observable result — not "looks right".
5. Update `PROGRESS.md` (state + build-history entry), then commit and push.

**One task = one session = one commit.** If a task needs two commits, that is a signal it should
have been two tasks — split it here first.

## Guardrails (apply to every task, no exceptions)

| Rule | Enforcement |
|---|---|
| Never commit `.env`, `.venv/`, `node_modules/`, or bulk data | `.gitignore` |
| Never invent a value — missing is "not available" / `NULL`, never coerced to zero | tests |
| The local site runs on port **3120** and nothing else | scripts + config |
| <!-- add the ones this project earns --> | |

## Pinned stack

| Concern | Choice |
|---|---|
| Language | <!-- --> |
| Framework | <!-- --> |
| Storage | <!-- --> |
| Tests | <!-- --> |
| Lint | <!-- --> |
| Web port | **3120** |

## Target layout

```text
fisheye/
  CLAUDE.md  AGENTS.md  PROGRESS.md
  docs/
    vision.md  spec.md  plan.md  overview.md
  <!-- the rest, as the spec implies -->
```

---

# Phase 0 — Scaffold

<!-- Phase 0 is always the skeleton: environment, dependencies, the dev server answering on
     http://localhost:3120, the first thing that runs. Every later phase leaves the project
     in a working state. -->

### P0-T1 · <!-- task name -->

- **What:** <!-- one or two sentences -->
- **Preconditions:** <!-- what must be true first -->
- **May touch:** <!-- the file list; stay inside it -->
- **Accept:** <!-- the observable result that proves it worked -->

---

# Phase 1 — <!-- name -->

### P1-T1 · <!-- task name -->

- **What:**
- **Preconditions:**
- **May touch:**
- **Accept:**
