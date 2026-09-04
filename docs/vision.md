# Vision — fisheye

**What this is:** why this project exists — its purpose and intent, written before anything is
designed. It informs [`spec.md`](spec.md); it does not replace it.

_Last updated: 2026-09-04._

---

## The problem

Coding agents pay for every token they read, and the unit they are given to read is the file. The
file is the wrong unit. It conflates five jobs that a database keeps apart: storage, reading,
editing, naming scope, and review. A page is the right size for none of them. When files are long,
an agent spends most of its context on code irrelevant to the change. When files are short, the
change ripples across many of them and the agent cannot see the whole. Either way, most of what
reaches the model's context is waste, and the fraction gets worse as the codebase grows.

The failures that follow are organizational, not syntactic. A capable model does not mistype a
bracket. It edits a function without seeing a caller three files away, decides at the level of a
summary that turns out to be wrong at the level of the body, or rewrites something that already
existed under another name. We tested the syntactic hypothesis directly on 2026-09-04: a strict
Python profile with a repair-instruction checker, run through a headless agent on eighteen small
tasks, tied the plain version on correctness and cost about half again as many tokens. Syntax is not
where the money is. Where the code is, and how much of it must be read to change it, is.

The tools built to help all sit on top of the problem rather than inside it. Repo maps, code graphs,
and hierarchical summaries are indexes over text: derived, read-only, and stale the moment the text
changes. They help an agent navigate a mess. They do nothing about the mess, because writes never go
through them. And the levels they offer are either bare signatures or unverified prose, so an agent
that reasons at the summary level is reasoning over something nothing has checked.

## Who this is for

Two users, and the second matters more than the first.

**The developer running agents on a TypeScript codebase**, alone or on a small team, who wants the
agent to do more of the work at lower cost and with fewer regressions. They reach for fisheye when
a codebase has grown past what an agent can hold in one read, or when they are starting something
new and want it to stay legible to agents as it grows. They read the outline as the spec and rarely
open a body.

**The agent itself.** It orients with a budgeted view instead of reading files. It writes the plan
as compiling code before any body exists. It receives, for each piece of work, a packet containing
only what that piece needs. Fisheye's interface is designed for this user first, because the
developer's leverage is entirely a function of how well the agent works.

## What it does

Fisheye is a toolchain, not a language and not a set of instructions. It makes an ordinary
TypeScript codebase cheap to navigate and safe to extend by giving it level of detail, a focus, and
holes.

**Level of detail.** Every definition has four derived levels: a purpose line; the signature with
its contract, declared effects, errors, and test coverage; the body as an outline of named steps
with expressions elided; and the full body. Every level is derived from the code by the TypeScript
compiler API and regenerated when the definition changes. Nothing at any level is hand-written prose
that can drift.

**Focus.** A view is built around the symbols a task touches, inside a token budget, using a
degree-of-interest rule: intrinsic importance minus distance from the focus, over the call graph and
containment. Definitions near the focus appear in full; distant ones as a line. Furnas described the
rule in 1986. Nobody has applied it to filling an agent's context window.

**Holes.** A typed placeholder that compiles, carries a contract and a purpose, and throws if it is
reached at runtime. With holes an agent can write the composite functions first, prove the skeleton
type-checks and the contracts compose, and only then fill the leaves. Each hole lists its expected
type, its contract, and the interfaces of everything it may call. That listing is a complete, minimal
work packet, and the packets are independent, so leaves can be filled in parallel by cheaper models.

**The discipline that makes the levels exact.** A lint enforces that a function is either a leaf
under a size limit or a composite that only sequences named steps, and that every public boundary
carries a contract. This is Wirth's stepwise refinement, enforced by tooling rather than taste. It
is what turns the outline level from an approximation into the code itself.

The product ships as four layers. The primitives, in plain TypeScript, so there is no new syntax and
no lost training prior. The command line, which is the product: `view`, `short`, `outline`, `holes`,
`check`, and `fill`. A forkable scaffold that makes the discipline the default for one common app
shape first. And an MCP server plus a skill, so any agent uses `view` instead of reading files and
`fill` instead of writing bodies. The skill is the manual. The command line is the oracle. Only one
of those is hard to copy.

## What "good" looks like

**The north star: tokens of context per completed task, at equal pass rate, against an agent
working on the same codebase with plain read and edit.** If fisheye does not cut that number by a
large factor on a codebase too big to read whole, it has failed regardless of how elegant it is.

The demo that proves it: one cheap model builds a real application from an outline written by a
capable one, every hole filled in parallel and verified against its contract, with the token count
shown next to the baseline. The outline is short enough that a person who does not write code can
read it and say whether it is what they meant.

## Principles

- **Oracles over instructions.** Agents follow checkers, not prose. Every rule fisheye cares about
  has a tool that enforces it and prints a repair instruction with a location. A convention without
  a checker is not part of the product.
- **Derived, never authored.** Every view is computed from the code by the compiler. If a level can
  drift from the body, it is not a level, it is documentation, and it is out.
- **No new language.** TypeScript, unchanged. The compiler is the type oracle, the compiler API is
  the view engine, and the training prior is on our side. The moment a design needs new syntax it
  has to justify itself against everything that prior buys.
- **Value in the artifact, not the tool.** Frontier labs will keep improving retrieval inside their
  agents, and that erodes any read-only helper. They do not own how a codebase is written. Every
  feature is judged by whether it changes the code that gets left behind.
- **Write side first.** Reading better is commoditized. Writing the plan as compiling code, and
  filling it in parallel with verification, is not. Build that before polishing the view.
- **Measure before building.** The benchmark exists before the scaffold does. A structural idea that
  pays off on small code and not on large code is overhead; we have already seen one.
- **Honest levels.** A summary that might be wrong is worse than no summary. Levels carry only what
  the compiler, the lint, and the tests can vouch for.

## What this is not

- **Not a new programming language.** We considered one and ruled it out: the training-data
  penalty is paid by every user and the store never gets a fair trial. Unison is the cautionary
  example.
- **Not a context engine or code index competing with agent vendors.** Cursor, Claude Code, and
  Augment all have retrieval. The fisheye view exists because when the structure is native it costs
  a few hundred lines; it is not the product.
- **Not a code graph over stale text.** Fisheye is not another read-only index. If it is not
  derived from the compiler and enforced at write time, it is not fisheye.
- **Not a store with files as views, yet.** The write-through store, definitions as rows and files
  as generated projections, is the long-term direction. It is deferred until the toolchain has
  earned it, because it is the Unison-shaped risk.
- **Not Python first.** Python's dynamic features hide the structure the compiler API exposes in
  TypeScript. Other languages follow only if the TypeScript result justifies them.
- **Not a hosted service.** Local, open, and forkable from the start. Anything hosted comes later
  and only if the local tool has users.
