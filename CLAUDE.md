# cttp — Project Guidance for Claude

cttp — *code text transfer protocol* — is a protocol that sits on top of existing programming languages
and lets code point at code: every definition gets an address, references are links rather than imports,
and an index answers who links where. See [`docs/vision.md`](docs/vision.md).

This file is the **session procedure**: how to start, how to finish, where things live, and the repo
policy. It deliberately does *not* describe the project — [`docs/overview.md`](docs/overview.md) does.

**Do not summarize the project from memory.** At the start of every session read
[`docs/overview.md`](docs/overview.md) first, then [`PROGRESS.md`](PROGRESS.md).

---

## Document map — what goes where

Each document has one job. Keeping them apart is what stops any of them from rotting.

| Document | Responsibility | Read when |
|---|---|---|
| `CLAUDE.md` | **Instructions to the agent** — session procedures, repo policy, this map. Nothing about the project itself | every session start |
| `AGENTS.md` | Pointer to this file, for agents that look for `AGENTS.md` | never (it has one line) |
| [`PROGRESS.md`](PROGRESS.md) | **Where we are** — current state, next steps, deferred follow-ups, recent build history. Everything dated | **every session start, second**; updated at session end |
| [`docs/overview.md`](docs/overview.md) | **The lay of the land** — what exists, how it is structured, where things live, invariants, traps. Conclusions, no dates | **every session start, first** |
| [`docs/vision.md`](docs/vision.md) | **Why this exists** — purpose and intent | when direction is in question |
| [`docs/spec.md`](docs/spec.md) | **The end state** — the finished product, its interface, its structure underneath, non-goals | when touching scope or the core model |
| [`docs/plan.md`](docs/plan.md) | **How we get there** — phased tasks with acceptance checks. Not a status doc | before starting any build task |

Add subsystem design docs and runbooks as `docs/*.md` when they earn their place, and **register each
one in this table** — an unregistered doc is invisible to the next session.

---

## Session start

Trigger: Leo says **"start session"**, **"begin session"**, **"where are we"**, or similar.

1. **Read the key docs — required, in this order.** Don't summarize from memory.
   - [`docs/overview.md`](docs/overview.md) **in full** — the durable map. Everything below assumes
     it. (Early on it is still blank; that is expected — see step 5.)
   - [`PROGRESS.md`](PROGRESS.md) — the header, **Current state**, **Next session**, and **Known
     follow-ups**. Skip **Build history** unless chasing a specific past decision.
   - [`docs/plan.md`](docs/plan.md) — the entry for the task about to be picked up, in full.

2. **Verify the environment against ground truth** — don't trust the docs:
   - `git status` and `git log --oneline -5`, so the summary reflects what is actually committed.
   - Dependencies present (`npm install` if `node_modules/` is missing; the `.venv` if Python).
   - `.env` present if the work needs credentials.

3. **Bring up the local site and tell Leo the URL.**
   - This project's web port is **3120** — hardcoded, allocated once at project creation.
     Never re-derive it.
   - **Probe before starting.** Leo routinely leaves the server up between sessions:
     ```bash
     curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3120/
     ```
     Anything but a connection failure means it is already running — **reuse it, do not
     double-start.**
   - If it is down, start the dev server in the background, wait for it to answer, then **state the
     URL plainly in chat**: *"The site is live — open **http://localhost:3120**."*
   - If it will not come up, say so and why. Never report success you did not verify.
   - This project has **no API tier and no database tier**. The web port serves the local cttp
     viewer only; the product itself is tooling and runs from the terminal.

4. **Identify where we are.** From `PROGRESS.md` plus the actual git and filesystem state, work out
   what is **working**, what is **in progress**, and what is **deferred**. Summarize tightly — this
   orients, it does not re-derive the whole build.

5. **Propose next steps, and let Leo choose.** Offer 2–4 concrete actions and recommend one. Take
   the recommendation from `PROGRESS.md`'s **Next session** block; if that is empty or stale, take
   the next unstarted task from [`docs/plan.md`](docs/plan.md). **Wait for Leo to pick before doing
   heavy work.**

---

## Session end

Trigger: Leo says **"end session"**, **"wrap up"**, **"done for today"**, or similar.

1. **Validate the work.** Run the test suite and the typecheck/build. If behavior changed, verify it
   **in the browser** — for anything visual, actually look at it; that keeps catching what no check
   can. Report results honestly: failing tests stay reported, not hidden.

2. **Update [`PROGRESS.md`](PROGRESS.md).** This is the doc the *next* session reads for state —
   make it accurate:
   - Refresh **Current state — working & verified**, tightly.
   - Rewrite **Next session — suggested next steps**. Take the next step from
     [`docs/plan.md`](docs/plan.md) — the next unstarted task, or the next phase if this one is
     done.
   - Add a **Build history** entry: what changed and *why*, including the load-bearing decisions.
     **Then trim the history to the five most recent sessions** — older entries get deleted, not
     archived. `git log` is the archive; a bloated `PROGRESS.md` taxes every future session start.
   - Curate **Known follow-ups (deferred)**: mark items done, add what this session found. **Every
     item carries a target** — the phase that will close it, `standing`, or `unscheduled` *with the
     trigger that would schedule it*.
   - Convert relative dates to **absolute**; update `_Last updated:_`.

3. **Update [`docs/overview.md`](docs/overview.md) — only if this session changed something
   foundational.** Most sessions do not. Ask: *would an agent starting fresh next week be wrong
   without this?* If yes it goes there, stripped of dates. Triggers: a new or renamed top-level
   directory, a change to how a subsystem works, a new invariant, a new environment trap that cost
   time today, changed bring-up or test commands, a new doc worth registering. **Not** for status,
   bug fixes, or next steps — those are `PROGRESS.md`'s job. If you edit it, say so in the wrap-up
   so Leo can review the diff.

4. **Update `CLAUDE.md` only if the session procedure itself changed** — a new step, a new document
   in the map, a changed policy. Most sessions do not. Project facts never belong here.

5. **Commit and push to `main`. This is the default** — do it unless Leo says otherwise.
   ```bash
   git add -A
   git commit -m "<clear message>"      # author Leo <leorinaldi@gmail.com>, keep the Co-Authored-By: Claude trailer
   git push origin main
   ```
   No branches, no PRs. Never stage `.env`, `.venv/`, `node_modules/`, or bulk data. If there is no
   remote yet, offer to create one — see **Repository** below.

6. **Offer to stop the dev server — ask, don't assume.** If Leo says no or doesn't answer, leave it
   running so his browser tab keeps working, and so the next session's probe finds it.

7. **Leave a clean handoff.** Surface what the next session needs: unfinished work, blockers, a
   pending decision.

---

## Repository

- **`main` only.** No feature branches, no PRs — commit straight to `main`.
- **Remote:** `origin` → `https://github.com/leorinaldi/cttp.git` (**private**, GitHub account
  `leorinaldi`).
- **If there is no remote yet**, offer to create one — don't do it unasked:
  ```bash
  gh auth status                        # confirm the leorinaldi account first
  gh repo create leorinaldi/cttp --private --source=. --remote=origin --push
  ```
  That creates the private repo, wires up `origin`, and pushes `main` in one step. Afterwards
  `git push origin main` is all any session needs. If `gh` is not authenticated, ask Leo to run
  `! gh auth login` himself.
- **Commit identity:** author **Leo <leorinaldi@gmail.com>**; keep the `Co-Authored-By: Claude`
  trailer when Claude co-authored the work.
- **Never commit secrets.** `.env` is gitignored by design, as are `.venv/`, `node_modules/`, build
  output, and anything under `data/raw/`.
- `PROGRESS.md` and everything in `docs/` are authored and versioned in git.

---

## Working conventions

- **Honesty over convenience.** Never invent a value — missing data is "not available" or `NULL`,
  never a plausible-looking number and never coerced to zero.
- **Verify against reality, not the doc** — a live probe, a real query, `git status`.
- **Actually look at it.** For anything visual, open it in the browser.
- When the work involves **Claude/Anthropic models or the API**, consult the `claude-api` skill —
  don't answer from memory.
