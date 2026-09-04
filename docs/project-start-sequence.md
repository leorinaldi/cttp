# The build arc — cttp

**What this is:** the stage ladder from blank sheet to working product, and the rule for what comes
next at each stage. Consulted at **session end**, when writing `PROGRESS.md`'s *Next session* block,
and at **session start** if that block is empty or stale.

**This document is scaffolding, and it retires.** Once the project reaches Stage 5 — the plan is
written and being executed — it has nothing left to say, and Stage 5 tells you how to remove it.

---

## Where are we?

Work down this list and stop at the first "no". That is the current stage.

| # | Question | If no → |
|---|---|---|
| 0 | Does `docs/vision.md` have real content? | **Stage 0** |
| 1 | Does `docs/spec.md` have real content? | **Stage 1** |
| 2 | Does `docs/plan.md` have real content? | **Stage 2** |
| 3 | Is the Phase 0 scaffold built and running? | **Stage 3** |
| 4 | Does `docs/overview.md` have real content? | **Stage 4** |
| — | All yes | **Stage 5** — execute the plan; retire this document |

---

## Stage 0 — Write `docs/vision.md`

Nothing else comes first. Iterate with Leo on **what this project is for and what it should do** —
purpose, intent, who it is for, what "good" looks like. It is allowed to be ambitious and short on
detail; it is not allowed to be vague about intent.

Do not design the interface here, and do not choose a stack. That is the spec's job.

**Exit:** Leo agrees the vision is right. Then, immediately:

> **Re-check the folder name.** Projects sharpen between the idea and the vision, and the name
> chosen at creation was explicitly provisional. Ask Leo whether `cttp` still fits. If it
> does not, rename now, while it is nearly free — the folder, the `origin` remote
> (`gh repo rename <new-name>`), the `cttp` references in `CLAUDE.md`, `PROGRESS.md` and
> these docs. Later it stops being free.

## Stage 1 — Write `docs/spec.md`

The **end state**: a clear picture of the finished product. What the user sees and does — the
interface, the flows, the surfaces — and how it is structured and organized underneath. Make the
load-bearing decisions here (stack, data model, storage, deployment shape) and write down the
**non-goals**, which are as load-bearing as the goals.

The spec describes the destination, not the journey. No phases, no tasks, no dates.

**Exit:** Leo agrees the spec describes the thing he wants to end up with.

## Stage 2 — Write `docs/plan.md`

The **phased sequence of tasks** that builds the spec from a blank sheet. Phase 0 is always the
scaffold: the skeleton, the environment, the dev server on port **3120**, the first thing
that runs. Later phases build outward, each one leaving the project in a working state.

Each task carries: an **ID** (`P1-T3`), what it is, its **preconditions**, the files it **may
touch**, and an **acceptance check** — an observable result, not "looks right". Aim for one task =
one session = one commit.

`plan.md` is a spec, not a status board. **Status lives only in `PROGRESS.md`.** If a task turns out
to be wrong, amend it here deliberately and note the amendment in `PROGRESS.md`'s build history.

**Exit:** Leo agrees the phases and the ordering.

## Stage 3 — Build the Phase 0 scaffold

Execute Phase 0 from `docs/plan.md`. When it is done there is a real skeleton on disk and something
that actually comes up at **http://localhost:3120** — even if all it renders is a title.

**Exit:** Phase 0's acceptance checks pass, and the dev server serves the page.

## Stage 4 — Write `docs/overview.md`

Now that something exists, describe it. `overview.md` is the **lay of the land for an agent who has
never seen this repo**: what the project is, how it is structured, where things live, the
invariants, the things not to "fix", the environment traps. Conclusions only — no dates, no status,
no next steps.

It could not have been written earlier, because until Stage 3 there was nothing to describe.

**Exit:** an agent could read `overview.md` alone and know its way around.

## Stage 5 — Execute the plan, and retire this document

From here the loop is just: **pick the next task in `docs/plan.md` → build it → check it → record it
in `PROGRESS.md` → commit and push.** Session end additionally asks whether the session changed
something foundational enough to belong in `docs/overview.md` — most sessions do not.

This document has no more advice to give. **Retire it in the session that reaches Stage 5:**

1. In `CLAUDE.md`, **session start step 5**: replace "if that is empty or stale, derive it from
   `docs/project-start-sequence.md`" with *"if that is empty or stale, take the next unstarted task
   from `docs/plan.md`."*
2. In `CLAUDE.md`, **session end step 2**: replace the sentence pointing at this file with *"take
   the next step from `docs/plan.md` — the next unstarted task, or the next phase if this one is
   done."*
3. Delete this file's row from `CLAUDE.md`'s **document map**.
4. `git rm docs/project-start-sequence.md`, and note the retirement in `PROGRESS.md`'s build history.

A scaffolding doc left standing after its job is done is just another file the next session has to
read and discard.
