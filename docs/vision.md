# Vision — cttp

**What this is:** why this project exists — its purpose and intent, written before anything is
designed. It informs [`spec.md`](spec.md); it does not replace it.

_Last updated: 2026-09-04. Supersedes the earlier "fisheye" vision entirely._

---

## The name

**cttp** — *code text transfer protocol*. The analogy is deliberate. HTTP did not replace any
document format; it gave every document an address and let any document point at any other. cttp
does the same for code: it does not replace any language, it gives every definition an address and
lets code point at code.

## The problem

Code is organized as trees of files, and the tree has one axis. A definition lives in exactly one
place, is referenced by importing a name from that place, and is shared only by packaging the whole
place. Every consequence of that shape shows up when you look at a large codebase closely.

We looked. Across 736 Linux driver files, about 408,000 lines, 257,000 of them substantive, **42
percent of substantive lines are identical, token for token, to a line in another file**, and 92
percent are once identifiers and literals are abstracted; over lines of at least eight tokens the
figures are still 16 and 66 percent. (Method and numbers: `bench/drivers/measure.py`, recomputed
with the tool's own tokenizer over Linux v7.3-rc1; the corpus and the groups below are
reproducible from `bench/drivers/`.) One eight-bit temperature decoder is written four times in
four drivers under three names; two other decoders are copied byte for byte between two drivers
each. A chip that is both a clock and a
thermometer gets its thermometer written inside the clock driver, because a file can only be in one
directory. A devicetree binding and the driver it describes disagree about which chips support an
interrupt, because one fact was written twice in two languages and maintained by hand.

None of this is a syntax problem, and none of it is a stupidity problem. Anything shared across
trees has no home, so it is copied. Anything copied drifts. And because references are names bound
by imports rather than links to definitions, nothing can answer the questions that matter most:
*who uses this*, *where did this come from*, *is this the same as that*.

Coding agents make the cost visible. An agent pays for every token it reads, and it navigates by
text search because that is all a file tree offers. It reads too much and still misses the caller in
another repository. When it writes code, the result carries no provenance: no link to what it copied,
adapted, or was derived from. We tested the alternative hypothesis first — that agents needed
stricter syntax — and it failed: a strict language profile tied on correctness and cost half again
as many tokens. The money is in how code is organized and referenced, not in how it is spelled.

## The idea

**Links, not imports.** A definition — a function, a type, a constant, a contract — has an address.
A reference to it is a link to *that definition*, not a name resolved through a file path and a
package manifest. The address carries where the definition can be found and at what version, and it
carries a content identity, so the same definition in two places is recognizably one thing.

Everything else follows from taking that seriously:

- **Identity is not a name.** Names are labels attached to definitions. Renaming is editing a
  label; every link still resolves. A definition moved to another file or another repository still
  resolves, because the address survives the move.
- **Backlinks come free.** Because links are explicit, an index can answer *who links here* across
  every repository it has seen. For an agent, "what is the blast radius of changing this" becomes a
  query instead of a guess.
- **Sharing happens at the definition.** You link to one function, not a package. The smallest
  unit of reuse today is a package with a manifest and a release process, which is why twenty-line
  helpers get rewritten instead of shared.
- **Provenance is built in.** A copy carries the link it came from, at the version it was taken,
  with its license. That is the answer, missing today, to *where did this generated code come from*.
- **Metadata attaches to identity.** Purpose, contract, tests, discussion, and effects can attach
  to a definition's address, and anyone can publish them. Each field is marked as either *derived*
  from the code by a tool or *asserted* by a person, so prose that can drift is never mistaken for
  fact.
- **Organization becomes a query.** When definitions have addresses and tags rather than a single
  home, a file is a view — *everything tagged thermometer and transport I2C, in this order* — and
  the one-axis problem dissolves rather than being solved.

## What it is, concretely

cttp is a **protocol that sits on top of existing languages**, plus the tooling that makes the
protocol usable. It is layered the way the web is:

| Layer | Web analogue | Job |
|---|---|---|
| Address | URL | Names one definition, at one version, in any language, with a content identity |
| Resolver | HTTP GET | Fetches a definition's source, signature, and metadata |
| Extractor per language | HTML parser | Decides what a definition is and where its boundaries are |
| Link convention per language | the anchor tag | How a link is written in source without breaking the compiler |
| Index | search engine | Crawls repositories, computes backlinks, importance, and duplicates |
| Materializer | package manager, per definition | Turns a link into the host language's native plumbing, or a vendored copy with provenance |
| Registry | DNS | Maps short, memorable names to addresses, and renders the page for a definition |

The protocol proper is the first two rows plus the link convention. Everything above it — contracts,
effects, tests, discussion — is optional metadata that rides on the addresses. HTTP won by being thin
and permissive; cttp should be the same.

In the host language, a link is an annotation the tooling acts on. The compiler, the editor, the
test runner, and version control keep working on ordinary files, because files remain the rendered
form. cttp adds addresses, links, and an index; it takes nothing away.

Public code hosting is the default namespace, so that linking is an open, sharing exercise from the
first day. The address format is origin-agnostic; a public host is the resolver most people use, not
a dependency of the protocol.

**A registry sits above the addresses, the way DNS sits above IP.** People register a name for
their code for free and get a short form — `cttp:3d-objects` rather than a full location — that
resolves to the address of the code, wherever it is hosted. The registry holds pointers, not code.
It is also the natural home of the page for a definition: purpose, signature, source, license,
history, and who links to it. The long form always works without it, so the registry is a
convenience and a gathering place, never a requirement. Its exact shape — naming rules, how names
pin to versions, how it stays trustworthy as a central point, whether other domains can federate
with it — is deliberately unresolved here and belongs to the spec.

The protocol is language-neutral by construction. Which languages get the full write side, and in
what order, is a staged path — see **The path** below.

## The path

Three stages, each earning the next. The order is not negotiable: the value of links comes from how
much there is to link to, so the protocol must start where the code already is.

**Stage 1 — language-neutral read side, Python write side.** Addresses, the resolver, the index, and
backlinks are language-neutral from the first commit and crawl the public corpus in every language
an extractor can parse — the read side is cheap, and the corpus is where the network effect lives.
The write side — the link convention in source, the materializer, the typed resolver, and the
benchmark — is built to excellence in **one host language first, and that language is Python.**
Python has the largest share of agent-written code, a precise cross-repository indexer already
built on its type checker, a community that has accepted annotation-in-comments conventions, an
import system that makes the materializer nearly trivial, and a culture where copying a function is
already normal and package overhead is most resented. Stage 1 ends when the benchmark number exists:
an agent with links against an agent with search, on real tasks, in Python.

**Stage 2 — many existing languages.** With the write side proven once, add host languages one at a
time, each with its own link convention and materializer, in order of agent usage and extractor
quality. TypeScript is the likely second. This is where cttp becomes what its name says — a protocol
that sits on top of languages rather than a Python tool — and where the cross-language graph,
reference without invocation, becomes the thing no other tool has.

**Stage 3 — the opportunity for a cttp-native language.** Once definitions have addresses and the
graph is populated, a language whose *only* module system is the protocol becomes viable: no
imports, no packages, links as the sole mechanism of reference, and the store rather than the file
as the unit of organization. Two things make this plausible now that were not before. The
ecosystem problem becomes a translation problem, and agents make translation cheap — existing code
can be ported into the native language at scale, safely, because the addresses and provenance from
Stages 1 and 2 already exist. And a native language can be a *dialect* of a host language rather
than a fresh syntax, so most of the training prior survives. This stage is an opportunity, not a
commitment. It is taken only if Stages 1 and 2 have produced users, and never before, because a
language with nothing to link to has the network effect working against it.

## Who this is for

**The agent.** It resolves a link instead of reading a file. It asks *who uses this* and gets an
exact answer across repositories. It receives, for a task, the closure of definitions the task
touches, computed rather than searched. It leaves provenance on everything it writes. cttp's
interface is designed for this user first, because every other user's leverage is a function of how
well the agent works.

**The developer running agents.** Alone or on a small team, on a codebase that has grown past what
an agent can hold in one read, or starting something new and wanting it to stay legible as it
grows. They adopt cttp without rewriting anything, because the read side works on code that has
done nothing to opt in.

**The open-source author.** Who wants to share one good function without publishing a package, and
who wants to know who depends on it.

## What "good" looks like

The north star is the same as before, because the goal is the same: **tokens of context per
completed task, at equal or better pass rate, against an agent working on the same codebase with
plain read and search.** The first measurable claim is narrow and testable within weeks: an agent
with a resolver and backlinks completes tasks at higher pass rate or lower cost than one with grep.

Three concrete acceptance tests for the idea itself:

- **The index rediscovers the duplicates.** Crawled over the 736 driver files we measured, it finds
  the four temperature decoders and the two identical ones, unaided.
- **A link survives a move.** A definition renamed and moved to another repository still resolves
  from a link written before the move.
- **Provenance is visible.** A function an agent copied from another repository carries its source
  link, version, and license, and the index shows the copy as a backlink of the original.

The demo that proves it: point at a function in someone else's repository, use it, and ask who else
uses it — with the token count next to the baseline.

## Principles

- **Protocol over language.** No new syntax, no new compiler, no lost training prior. Every host
  language keeps its tools. The moment a design needs a new language it has to justify itself
  against everything that prior buys.
- **Links over imports.** A reference is to a definition, not to a name in a place.
- **Identity by content, discovery by location.** The address says where to look; the content
  identity says what it is. Two copies of one thing are one thing.
- **A link never means execution.** Linking is a reference. Materializing is a deliberate, pinned,
  reviewed act. This is the supply-chain rule, and it is not negotiable.
- **Derived and asserted are labelled.** Tooling-derived facts and human-asserted prose are both
  welcome and never confused.
- **Thin and permissive.** Fewer rules, more adoption. Anything that can be optional metadata is.
- **Measure before building.** The benchmark exists before the resolver does. An idea that helps on
  small code and not on large code is overhead; we have already seen one.
- **Open by default.** The address space is public code hosting. The index is buildable by anyone.

## What this is not

- **Not a programming language first.** A cttp-native language is Stage 3 of the path and is taken
  only if the protocol has earned it. Unison is the proof that the underlying mechanism works and the
  proof of what a new language costs in ecosystem and prior when it comes first.
- **Not a package manager,** though it may reduce the need for one. Packages remain the way to ship
  releases; cttp is the way to point.
- **Not a runtime or an FFI.** Cross-language *reference* works everywhere and is worth a great
  deal. Cross-language *invocation* still needs the host languages' own mechanisms, and the protocol
  does not pretend otherwise. cttp gives a global graph, not a global runtime.
- **Not a read-only code index.** Sourcegraph, Kythe, and every agent vendor have those. cttp is
  different because links are written in source: the write side goes through it.
- **Not a Python tool.** Python is where the write side is built first, not what cttp is. The
  read side is language-neutral from day one and Stage 2 is the point.
- **Not tied to one host.** GitHub is the default namespace and the first resolver, not a dependency.
- **Not a hosted service.** The protocol and the tooling are local and open. A public index is a
  service someone can run, and the protocol works without it.

## The horizon

Beyond the path lie the things a link-structured codebase makes possible and a file tree does not:
definitions computed from other definitions and regenerated when their inputs change; contracts and
tests as the oracle that makes cheap models safe; a codebase organized like a wiki, where files are
queries and a definition's page carries its purpose, contract, callers, tests, history, and the
discussion of why it is the way it is. Most of these belong naturally to Stage 3, where the store
rather than the file is the unit. None are in scope until the protocol has earned them. The protocol
is the part that has to exist first, and the part that is hardest to copy.
