# SPEC — cttp

**What this is:** the end state — the finished product, what its users see and do, and how it is
structured underneath. It makes the load-bearing decisions the vision left open. It describes the
destination, not the journey: no phases, no tasks, no dates. The journey is [`plan.md`](plan.md).

**What it assumes:** [`vision.md`](vision.md), agreed on 2026-09-04. Where this document and the
vision disagree, the vision is wrong and should be amended, or this document is wrong and should be
amended; they are never allowed to drift apart silently.

_Last updated: 2026-09-04. Second draft, after the materialization discussion with Leo: links expand
in place, the stamp lives in the file, there is no lockfile, and the registry is an HTTP contract
served locally first. Decisions marked **Decision** are open to amendment. Section 14 lists what is
deliberately still unresolved._

---

## 1. The product in one paragraph

cttp is a command-line tool, `cttp`, plus a small local web server, that gives every definition in
any git-hosted codebase an **address**, lets Python source **link** to a definition by address in an
ordinary comment, **resolves** a link to the definition's source and metadata, **indexes** any set of
repositories to answer *who links here* and *what is duplicated*, and **expands** a link in place
into a pinned, hashed copy of the code that the Python runtime loads like any other lines in the
file. The runtime never learns cttp exists; a clone of a project runs with cttp uninstalled. A
program can be nothing but a link, and `cttp run` runs it. An agent uses the same tool through
`--json` output and an MCP server. A **registry** maps short names such as `hello-world` to
addresses and serves a page per name; it is an HTTP contract that `cttp serve` provides on
localhost and that `cttp.ai` provides publicly. The protocol is the address grammar, the resolver's
contract, the link convention, and the registry contract; everything else is tooling on top.

## 2. The address

An address names **one definition, at one version, with a content identity**. It has a locator
half (where to look) and an identity half (what it is). Either half alone is a valid address; the
pair is a **pinned** address.

**Decision — people write the short form; the tool writes the pinned form.** A person or an agent
types `cttp:hello-world` and nothing more. Version and identity are facts the tool records when it
expands the link, never something a person is asked to supply. The grammar below therefore has a
short form that is complete for writing and a full form that is complete for reproducing.

**Decision — grammar.** Every address begins with the marker `cttp:` followed by one of three forms:

```text
name      := label ("." label)* [ "@" (version | rev) ] [ "#" symbol ]   ; resolved by the registry
locator   := host "/" owner "/" repo "@" rev "/" path [ "#" symbol ]
identity  := "sha256:" hex               ; 64 hex digits, or a unique prefix of at least 12
```

- `label` is `[a-z0-9]+(-[a-z0-9]+)*`; dots namespace (`leo.thermo`).
- `version` is a label the registry maps to a ref of the target repository (`1.2`, `stable`).
- `host/owner/repo` is a git remote in the form the host uses for URLs, with no scheme:
  `github.com/leorinaldi/thermo`. Any git host works; nothing in the grammar is GitHub-specific.
- `rev` is a commit SHA (full, or an abbreviation of at least 12 hex digits), a tag, or a branch.
  Only a commit SHA makes an address immutable; tags and branches are conveniences for humans and
  never appear in a stamp the tool writes.
- `path` is the file path from the repository root, forward slashes.
- `symbol` is the dotted path to the definition within the file: `reg_to_millicelsius`,
  `LM75.read_temp`. Omitting it addresses the whole file.

In a link line the identity accompanies the address as a field, `id=sha256:…`, rather than being
spliced into it (section 4). An address is *pinned* when its rev is a commit SHA and it carries an
identity. Examples:

```text
cttp:hello-world                                     short form, written by a person
cttp:hello-world@8f4c2e1d9a03 id=sha256:7f3a9c1e42b8   pinned form, written by the tool
cttp:github.com/leorinaldi/thermo@8f4c2e1d9a03/src/thermo/decode.py#reg_to_millicelsius
cttp:sha256:7f3a9c1e42b8
```

**Decision — what the identity hashes.** The identity is SHA-256 over the definition's *own*
normalized source: the extractor's span for that definition (decorators, signature, docstring and
body), dedented to column zero, line endings normalized to LF, trailing whitespace stripped, exactly
one trailing newline. It does **not** include the definitions it references — the closure identity
(Unison's choice) is computed by the index as derived metadata, not baked into the address. Reason:
an address must be computable from one file with no resolution, so that a link can be written and
checked offline.

A second hash, the **shape**, is the same normalization with identifiers and literals replaced by
placeholders. It is derived metadata in the index, used for near-duplicate detection, and is never
part of an address.

**Decision — a definition's history is derived, not declared.** The sequence of identities observed
at the same `(repo, path, symbol)` across revisions is the definition's version history. Nothing
declares a version number; git revisions are the versions. Registry version labels are names for
refs, not a second versioning scheme.

**Precedent.** This is the web's subresource-integrity model — a URL, a version in it, and a hash
in the tag — rather than the lockfile model of pip, npm and Cargo. The document alone determines
what runs; two files that read the same behave the same.

## 3. Definitions and extractors

An **extractor** decides, per language, what a definition is and where its boundaries are. The
read side accepts any language with an extractor; the write side (links, expansion) exists only
for Python in the end state described here, with the design leaving room for others.

**Decision — a page is a definition or a script.** What an address points at is one of two kinds.
A **definition** — a function, class or constant — is composed by other code by calling it. A
**script** — a sequence of statements, possibly including links — is run. `hello-world` may be
either: `print("hello world!")` as a script, or `def hello(): …` as a definition. The kind is
derived by the extractor, never declared, and both expand the same way (section 7).

**Decision — Python definitions.** Addressable definitions are module-level `def`, `async def`,
`class`, and simple assignments to a name (constants); class bodies expose methods and class
attributes as `Class.member`. Nested functions and comprehension-scoped names are not addressable.
The span of a definition runs from its first decorator (or the name for assignments) through the
end of its body. A whole file addressed without a symbol is a script. Extraction uses the standard
library `ast` with source positions; it is exact, not heuristic.

**Decision — every other language is read-only and tree-sitter based.** The language-neutral read
side extracts definitions with tree-sitter grammars and a small per-language query that names the
definition node types and the field that carries the name. This is enough for identity, shape,
backlinks from `cttp:` comments, and duplicate detection, and it is how the index crawls the
Linux driver corpus (C) that the vision's numbers come from. A language gets a write side only when
it gets a precise extractor and a link convention of its own.

**Derived references.** The Python extractor also records ordinary references — imports and
attribute access it can resolve statically within the repository — as *derived* links, so that an
un-annotated repository still yields a usable graph. Precision beyond the standard library
(resolution through a type checker) is welcome later and is not required by this spec.

## 4. The link convention in Python source

A link is a comment the compiler ignores, of the form:

```python
# cttp: <address> [id=sha256:…] [license=<SPDX id>] [track=latest] [key=value …] ["<description>"]
```

A link is a **substitute for the code at that address.** Written by a person it is the short form
alone. After expansion (section 7) the code stands directly beneath it and the line carries the
stamp — the pinned address and the identity — that says exactly which code that is:

```python
# cttp: hello-world
```

```python
# cttp: hello-world@8f4c2e1d9a03 id=sha256:7f3a9c1e42b8  "Prints 'hello world'."
print("hello world!")
```

**Decision — the description rides on the line.** The registry entry for a name carries a one-line
`description` written by its author (asserted). Expansion copies it onto the link line as the
trailing quoted string, so what the code does is visible wherever the line is: in an editor, a
diff, `git blame`, the folded view, and whatever an agent reads — with no hover and no tooling.
When a link has no registry description, expansion derives one from the signature and the first
line of the docstring and marks it so: `~"def greet(name: str) -> str — Return a greeting."`. The
leading `~` is the derived label; a plain quoted string is asserted.

**Decision — three relations, three markers.**

| Marker | Meaning | Placed above |
|---|---|---|
| `# cttp:` | *is* — the code beneath **is** that definition or script, verbatim | the expanded code; or alone, awaiting expansion |
| `# cttp-from:` | *from* — the code beneath was **derived from** that address and may differ | a `def`, `class`, or assignment |
| `# cttp-see:` | *see* — a reference with no code relationship claimed: cross-language, docs, "same idea" | anything, including a module docstring line |

Rules:

- One link per line; several links may stack above one statement.
- Fields after the address are `key=value`, whitespace-separated, no spaces inside values. The
  description, if present, is last and is the only quoted, space-bearing field.
- A `# cttp:` line with no stamp is **unexpanded**. A stamped `# cttp:` line whose code beneath does
  not hash to its `id=` is a **drift error**. `cttp check` reports both. `# cttp-from:` is never
  checked for identity.
- `track=latest` on a link says `cttp update` may move its pin without being named explicitly; a
  project-level default may set the same. Without it a link stays where it was pinned until asked.
- **Editing the copy is allowed and makes it a fork.** The lines beneath a link are the user's to
  change. Doing so breaks the `is` claim, and `cttp check` reports drift until the line is changed
  to `# cttp-from:`, which keeps the origin address and version but claims only derivation.
  `cttp check --fix` makes that conversion. A `from` link is never overwritten by `update`; instead
  `update` shows what changed upstream since the fork, for the user to merge by hand. The index
  still lists the fork as a backlink of the original, labelled `from`.
- Links are **asserted** metadata: written by a person, or by the tool completing what a person
  wrote. The index labels them so.
- Anything a human or agent writes by hand uses the same grammar the tool writes. There is no
  privileged form.
- No decorator, import, or runtime form exists. A program that uses expanded code must run with
  cttp uninstalled.

The convention is grep-friendly by design: one regular expression finds every link in any file,
which is what makes the read side language-neutral for the *link* layer even where extraction is
not.

## 5. The resolver

`cttp resolve <address>` returns the definition or script: its pinned address, source text,
language, kind, name, signature, docstring, license (from the repository's license file, derived),
the span, the identity and shape hashes, its derived references and imports, the link lines it
asserts, and its free names. Section 8 lists the fields; the registry contract serves the same
object.

**Decision — the resolver is git, locally, behind a content-addressed cache.** Resolution fetches
the repository into a local cache (`~/.cache/cttp/repos/<host>/<owner>/<repo>`) with plain `git`,
reads the blob at the rev, and runs the extractor. Every definition resolved is also stored by
identity under `~/.cache/cttp/objects/<sha256>`, so an identity-only address resolves from the
cache without a network, and so a definition whose origin has vanished survives wherever it was
ever fetched. No hosting API is required; a host API may be used as an accelerator for single-file
fetches when available. This is what makes the address origin-agnostic in practice.

**Three places the code as-it-was lives,** strongest first: in the expanded file itself, committed
with the project; in the origin repository's git history at the pinned rev; in the object cache of
anyone who resolved it. The first is the source of truth; the other two are how it is found again.

**Resolution by form:**

1. **Name** → registry lookup (section 8) → a repository, optionally a path and symbol, at a ref →
   continue as a locator. If the name gives no path, the symbol is looked up across the repository
   at that rev and must be unique; otherwise the resolver lists the candidates and stops. A short
   form with no `@` resolves to the registry's default ref for that name — `latest` unless the
   name's entry says otherwise.
2. **Locator** → fetch, extract, hash. If the link carried `id=` and the hash differs, the result is
   a mismatch, reported, not hidden.
3. **Identity** → object cache, then index → every locator known to carry that identity.

**Decision — "survives a move" is a resolver mode, `--latest`.** A pinned address never breaks:
the rev is immutable. What a move breaks is following the definition forward. `cttp resolve --latest`
takes a pinned address and finds the same definition at the repository's current head, in order:
same path and symbol (identity equal or changed — a normal edit); else the identity anywhere at head
(a move within the repository); else, via the index, any definition anywhere that carries a
`# cttp:` or `# cttp-from:` link back to this address (a move across repositories, or a fork). The
answer states which rule found it, as derived metadata, and states plainly when nothing did.

## 6. The index

The index is a local SQLite database that answers questions over any set of repositories it has
crawled. It is buildable by anyone from public code; nothing about it requires a service.

**Decision — one SQLite file per index; the default is global.** `~/.local/share/cttp/index.db`,
overridable with `--index <path>` so a project or a benchmark can have its own.

**Tables, by grain:**

| Table | Grain | Load-bearing columns |
|---|---|---|
| `repos` | one git remote | locator, default branch |
| `revisions` | one crawled commit of one repo | sha, crawled-at |
| `definitions` | one definition at one revision | identity, shape, repo, sha, path, symbol, language, kind, name, signature, span, license |
| `links` | one edge from a definition | source identity, target address as written, target identity when resolvable, relation (`is`/`from`/`see`/`ref`), origin (`asserted`/`derived`), file, line |
| `names` | one registry entry, snapshotted | name, target, version map, registry |

Identity is the key of `definitions`; the same identity seen in three places is one row of
identity and three rows of location. That is what makes "two copies of one thing are one thing" a
query rather than a heuristic.

**Queries the index must answer,** each a CLI command and an MCP tool:

- `who <address>` — backlinks: every definition linking here, by relation and origin, across every
  crawled repository, **with the coverage of that answer beside it**.
- `dups [--shape]` — groups of definitions sharing an identity, or a shape, with their locations.
- `closure <address>…` — the transitive set of definitions the given ones reference, in dependency
  order, for handing to an agent as the context of a task.
- `search <text>` — by name, signature, or docstring.
- `history <address>` — the identities seen at that `(repo, path, symbol)` over revisions.
- `rank` — definitions ordered by backlink count; anything smarter is a later refinement.

**Decision — crawling is explicit.** `cttp index add <repo-or-path>` and `cttp index crawl` walk a
list you gave it. There is no background daemon and nothing crawls the world by default. A public
index that has crawled a large corpus is a service someone may run, using this same code.

**Decision — `who` states its own coverage.** An answer whose completeness cannot be judged is one
its reader must reproduce by hand, and a reader that reproduces the answer has not been helped.
So `who` returns, beside the backlinks, what the answer is an answer *over*: the revisions
searched and the directories each reached; the files the crawl could not read, and which of those
could have held a reference at all; the recorded links whose target the index cannot identify, and
how many of those name *this* address; the imports that point into a repository and were never
mapped to a file; and the ways `who` is knowingly incomplete that no count expresses. `complete` is
true when this answer has none of those gaps — the reader may stop. It is a claim about the files
that were read and nothing more: a repository never crawled is answered by the list of those that
were. The same duty falls on any later query whose zero could be mistaken for an absence.

## 7. The materializer

The materializer — the verb is **expand** — turns a link into code the host runtime can run. It is
the only part of cttp that writes code into a project, and it is where the supply-chain rule — *a
link never means execution* — becomes mechanical: expansion happens once, at edit time, by a
deliberate command, and the result is ordinary lines in an ordinary file.

**Decision — expansion is in place, and the file is the only record.** The code stands directly
beneath its link, the link line carries the stamp, and nothing else is written anywhere. There is
**no lockfile**: every fact a lockfile would hold is already on the link line, and a second copy of
the same facts is a second thing to drift. `cttp check` reads the files.

**When expansion happens.** Once, when `cttp expand` (or `cttp add`) is run after a link is
written — by the agent that wrote it, by a pre-commit hook, or by an editor on save. Never when the
program starts. Again only on `cttp update`, deliberately. Between those moments the file is plain
Python, committed to git, and runs anywhere.

**What expansion writes.** For a definition: the definition's source, verbatim, beneath the link.
For a script: its statements. For either, the **closure** — the definitions it references — is
expanded too, each beneath its own stamped link, placed above the first use so the file reads and
runs top to bottom. The links within the expanded code are themselves stamped, so links upon links
expand to a file in which every line has a provenance and a hash.

```python
# cttp: greet@3a1f…  id=sha256:…
def greet(name: str) -> str:
    return f"hello {name}!"

# cttp: hello-world@8f4c…  id=sha256:…
print(greet("world"))
```

**Decision — the closure is computed statically and refused when incomplete.**

| Reference target | Handling |
|---|---|
| Another definition in the origin repository | expanded alongside, recursively, each with its own stamp |
| Standard library | left as written |
| A third-party import | kept as an import; the package requirement is reported, and written into `pyproject.toml` only with `--write-deps` |
| Anything unresolvable | the operation stops and says what it could not resolve |

A size budget (default: 50 definitions or 2,000 lines) stops a link from dragging in a whole
codebase; over budget, the tool suggests `--package` or a narrower symbol. The materializer never
imports or executes origin code; it reads text.

**Decision — the vendored package is the fallback, not the default.** `cttp expand --package`
writes the closure into a `cttp_vendor/` package in the project and leaves an import beneath the
link instead of the code. It exists for closures too large to read in place; every file it writes
carries the same stamped links, so `check`, `who` and provenance work identically.

**Commands:**

- `cttp expand [<file>…]` — expand every unexpanded `# cttp:` link in the given files, or the
  project. This is the agent's path: write links, expand once.
- `cttp add <address> [<file>]` — write the link and expand it in one step.
- `cttp check [--fix]` — every stamped link's code hashes to its `id=`; every link resolves; no
  link is unexpanded. Exit non-zero on any failure. Suitable for CI. `--fix` converts drifted
  `# cttp:` links to `# cttp-from:` and reports what it changed.
- `cttp update [<address>…] [--to <rev>] [--all]` — re-resolve (default: `--latest` per section 5),
  show the source diff, rewrite the stamp and the code beneath only on confirmation (`--yes` for
  automation). With no arguments, updates links marked `track=latest`; `--all` updates everything.
  On a `# cttp-from:` link it never rewrites the code; it shows the upstream diff since the pinned
  version and leaves the merge to the user.
- `cttp fold [<file>…]` — a **view**: print the file with expanded code collapsed to its link lines,
  each with its description, so a folded file reads as a list of what it does. It writes nothing;
  the on-disk form is always expanded. `--open <address>` unfolds one block.
- `cttp run <address | file>` — for an address, expand into `~/.cache/cttp/run/<pin>/` once and run
  it with the host runtime; for a file, expand any unexpanded links into the cache copy and run
  that, leaving the file untouched. On the first run of an address not yet cached, show what is
  about to run — source, hash, license — and ask, unless `--yes`.

**Decision — expanded on disk, folded in view.** Sparsity is delivered by `fold`, by the viewer,
and by the MCP tools, all of which present links rather than code. In an editor the block beneath a
stamped link is a foldable region; a small editor extension that folds cttp blocks on open, and
shows a link's page on hover, is wanted (section 13) but nothing depends on it. What is committed is the
expanded form, so that anyone can clone and run with nothing installed. The alternative — links
only on disk, expansion into a cache at run time — would make `cttp run` mandatory for every user
and is rejected here.

## 8. The registry

The registry maps short names to addresses, the way DNS maps names to hosts, and serves a page per
name. It holds pointers, never code, and the long form always works without it.

**Decision — the registry is an HTTP contract, served on localhost first.** A registry is anything
that answers, for a name:

| Route | Returns |
|---|---|
| `GET /<name>` | the page: source, language, kind, license, the pinned address it currently resolves to, version labels, history, who links here |
| `GET /<name>.json` | the same as JSON, in the resolver's schema |
| `GET /<name>@<version>.json` | the resolution for one version label or ref |
| `GET /<name>[@<version>]%23<symbol>.json` | the resolution for one definition of the target: the `#symbol` of section 2, percent-encoded, on the same route |

There is no locator route and no identity route: the contract answers names only. A locator goes
straight to git and an identity to the object cache and the index (section 5), neither needing a
registry. There is no listing route either; a registry is asked about a name, never enumerated.

**The resolver's object.** The JSON the contract returns is what `cttp resolve --json` prints —
**the server resolves, the client asks.** Every field is present, `null` when not available:

| Field | Meaning |
|---|---|
| `name`, `address` | the registry name, or `null` for a bare locator; the pinned address (section 2: a 12-hex rev, the `#symbol` kept) |
| `rev` | the full commit SHA |
| `identity`, `identity_full` | `sha256:<12 hex>` and the full hex of the identity hash |
| `shape`, `shape_full` | the same for the shape hash; `null` when the language has no extractor |
| `kind`, `language` | `function`, `class`, `constant` or `script`; `python`, or `text` for a file with no extractor |
| `symbol`, `signature`, `docstring`, `span` | for a definition: its dotted name, its signature without the keyword, the first docstring paragraph as one line, `[first, last]` lines in the origin file |
| `source` | the page's own text, normalized (section 2), with its link lines taken out (section 4) |
| `description` | the entry's one line, asserted; `null` when the entry has none |
| `license` | the SPDX id of the repository's license file at the rev, or `null` |
| `target`, `path`, `registry` | the entry's `host/owner/repo/path`, the path within it, and which registry answered |
| `refs` | derived references to files and definitions in the same repository: `{address, name, relation: "ref", origin: "derived"}`, the address a pinned locator at the same rev, `name` the text the page reaches it by (`REG_BITS`, `decode.STEP`, `r2m`) — what decides whether it can be inlined (section 7) |
| `imports` | `{stdlib, third_party, statements}`: the outside modules a definition needs, split by `sys.stdlib_module_names`, and the import statements that bind them |
| `links` | the link lines found in the page's text, asserted: `{address, relation, fields, description, derived, line, indent, origin: "asserted"}` |
| `unresolved` | the page's free names: used, bound by nothing in it — what a closure must bind |
| `origin` | which fields are derived and which asserted (section 10), and `location`: `repository` or `cache` |

`links` and `unresolved` may be absent from an older server; a client treats a missing one as
empty. The object the tool prints for an identity address adds `locations` and `via`; those
describe the cache that answered and are not part of the contract.

`cttp serve` provides this contract at **http://localhost:3120** from a local registry repository
and the local index, and the tool's default registry is that URL until changed. **`cttp.ai`**,
which Leo owns, provides the same contract publicly and becomes the default once it is up. Moving
from one to the other is a configuration change, not a protocol change; the two are
interchangeable by construction.

**Decision — the registry's data is a git repository.** One file per name:

```toml
# names/hello-world.toml
name        = "hello-world"
description = "Prints 'hello world'."        # one line, asserted by the author; copied onto link lines
owner       = "github.com/leorinaldi"       # the account that proved control of the target
target  = "github.com/leorinaldi/cttp-registry/snippets/hello_world.py"
default = "latest"                          # what the short form resolves to
[versions]
latest  = "main"
stable  = "v1"                               # labels are refs in the target repository
```

The first registry repository is also the home of the first snippets — the pointer-not-code rule
holds in the protocol, and the registry repository happens to be a target too.

**Naming rules.** Labels are `[a-z0-9]+(-[a-z0-9]+)*`, dots namespace, first come first served,
free. A name may point at a repository, a file (a script), or a single definition.

**Decision — proof of control, not accounts.** To claim a name, the target repository must contain
a `cttp.toml` at its root declaring `name = "hello-world"`, the way a DNS TXT record proves domain
ownership. The declaration is read at the head of the repository's default branch; a repository
that is the target of several names lists the others under `names = ["…", "…"]` beside its own
`name`. The claim is a pull request against the registry repository (`cttp name claim <name>
--target <host/owner/repo[/path]>` opens it with `gh`, or writes the file for you with `--no-pr`);
the entry's `owner` is the target's account, `host/owner` of its locator, derived and never
asked for. The registry's own checks (`cttp name verify`) verify the declaration at the target,
the owner, the target path, every label and its ref, and the resolution before merging. A name
that exists with another owner is refused unless `--transfer`, which opens the same pull request
for the old owner's approval. `cttp name show <name>` prints an entry and its resolution. No
accounts, no passwords.

**Trust as a central point.** Because every expansion writes a pinned address into the file, a
hijacked or repointed name cannot change code that is already expanded; it can only affect the
next `add` or `update`, both of which show what they resolved to. Every change to the registry is
a commit with an author, so the history is the audit log.

**Federation.** Any git repository with this layout, served by anything meeting the contract, is a
registry. The tool's configuration lists registries in order, and the first match wins. The syntax
for naming a specific registry inside an address is left open (section 14).

## 9. Surfaces

**The CLI, `cttp`.** Everything is a subcommand; every subcommand accepts `--json` and emits a stable
schema. The families are: `resolve`, `who`, `dups`, `closure`, `search`, `history`, `rank`;
`index add|crawl|status`; `expand`, `add`, `check`, `update`, `fold`, `run`; `name claim|show`;
`serve`; `mcp`.

**The agent interface.** The agent is the first user, and its interface is the CLI with `--json`
plus `cttp mcp`, an MCP server exposing `resolve`, `who`, `closure`, `search`, `dups` and `fold` as
tools with the same schemas, each published as the tool's output schema. The schemas are one
definition in `schemas.py`, rendered to `docs/json-schemas.md`; every object carries
`schema_version`, and a change to any schema bumps it. The design rule for these outputs: return
the definition, not the file. `resolve` returns one definition's text and signature; `closure`
returns exactly the definitions a task needs, in order, each with its address — one object whether
it comes from a live walk of the repositories (what `expand` would write; it refuses what cannot be
inlined) or, with `--indexed` and any number of roots, from the index's recorded links (which lists
what it cannot tell under `missing`); `fold` returns a file as links, so that context cost is
proportional to the task and not to the repository.

**The local server, `cttp serve`.** A server-rendered site at **http://localhost:3120**, read-only
over the local registry and index. It is both the local registry (section 8's contract) and the
viewer. Pages: search (`/`), a name (`/<name>`), a definition by identity (`/d/<identity>`), a
repository (`/r/<host>/<owner>/<repo>`), duplicates (`/dups`). No build step and no client-side
framework; HTML from templates. It exists so that a person can look at what the tool knows, and so
that `cttp.ai` can be the same code over a public index.

## 10. Derived and asserted

Every piece of metadata carries its origin, and the two are never merged into one field:

- **Derived** — computed by a tool from code: identity, shape, signature, span, license from the
  repository's license file, import-derived references, history, rank, `--latest` resolutions.
- **Asserted** — written by a person or by a tool on a person's explicit instruction: `# cttp:`,
  `# cttp-from:`, `# cttp-see:` links and their fields, registry entries, and any purpose or
  contract prose attached to an address.

Every output that shows a fact shows which it is. A viewer page separates the two visually; JSON
carries an `origin` field on every such value.

## 11. Stack and repository layout

**Decision — pinned stack.**

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.12+ | the first write side is Python; one language for the whole tool |
| Environment | `uv` | fast, lockfile, no global state |
| CLI | `typer` | subcommands, `--json` by convention, minimal ceremony |
| Python extraction | stdlib `ast` | exact spans and no dependency |
| Other-language extraction | `tree-sitter` with the official language packs | one mechanism for every read-only language |
| Git | `git` via subprocess | origin-agnostic; nothing to reimplement |
| Index | SQLite via stdlib `sqlite3` | one file, zero setup, buildable by anyone |
| Config and registry files | TOML (`tomllib`, `tomli-w`) | readable, diffable, stdlib reader |
| Server | FastAPI + Jinja2, served by `uvicorn` on **3120** | registry contract and viewer, server-rendered, no JS toolchain |
| MCP server | the official Python MCP SDK | the agent interface without inventing one |
| Tests | `pytest` | fixture repositories under `tests/fixtures/` |
| Lint and format | `ruff` | one tool |

**Target layout:**

```text
cttp/
  CLAUDE.md  AGENTS.md  PROGRESS.md
  docs/                  vision.md  spec.md  plan.md  overview.md
  pyproject.toml         the cttp distribution; `cttp` console script
  src/cttp/
    address.py           grammar, parsing, normalization, identity and shape hashing
    extract/             python.py (ast); treesitter.py plus per-language queries
    links.py             the comment convention: find, parse, write
    resolve.py           git cache, resolution by form, --latest
    index/               schema, crawl, queries
    expand.py            closure, in-place expansion, check, update, fold, run
    registry.py          name resolution, claim, the registry contract
    server/              FastAPI app and templates: registry routes and viewer pages
    mcp.py               the MCP server
    cli.py               typer entry point
  tests/                 unit tests and fixture repositories
  bench/
    drivers/             the Linux driver measurement, reproducible
    agent/               the links-versus-search benchmark harness and tasks
```

## 12. Acceptance tests and the benchmark

The vision names three tests of the idea. Concretely:

1. **The index rediscovers the duplicates.** `cttp index add` the Linux tree at the commit the
   measurement used, restricted to the same five driver directories; `cttp dups --shape` lists the
   four temperature decoders as one group, and `cttp dups` lists the two verbatim copies as one
   group, with no hint from the operator. The expected groups are recorded in
   `bench/drivers/expected.json` (to be recovered from the measurement session's scratchpad or
   re-derived; if neither is possible the expectation is written fresh from the corpus and said so).
2. **A link survives a move.** A fixture repository A defines a function; a consumer links to it,
   pinned. A is edited to rename the function and move it to fixture repository B, with a
   `# cttp-from:` link left on the moved definition. `cttp resolve --latest` on the original address
   returns the definition in B and states which rule found it. A second variant with no `cttp-from`
   link is found by identity alone when B has been crawled.
3. **Provenance is visible.** `cttp add` in a consumer expands the definition in place beneath a
   stamped link carrying address, identity and license; after `cttp index add` of the consumer,
   `cttp who` on the original lists the copy as an `is` backlink with origin `asserted`; and the
   page for the original shows it.
4. **Hello world.** With `cttp serve` running against the local registry, a file containing only
   `# cttp: hello-world` is expanded by `cttp expand` into that line, stamped, plus
   `print("hello world!")`; `python` runs it with cttp uninstalled; `cttp run hello-world` runs it
   with no file at all; and `cttp check` passes before and fails after the print line is edited.

**The Stage 1 benchmark** is the number that decides whether the protocol helps. Two arms with the
same model, same harness, same tasks; the only difference is the tools: one arm has `resolve`,
`who`, `closure` and `search`; the other has read and grep. Measured per task: **tokens of context
consumed** and **pass** against hidden tests or ground truth. Three task families:

- **In-repository changes** on a handful of mid-size Python repositories, graded by tests.
- **Cross-repository reuse** — "use this function from that repository" — graded by tests plus
  the presence of correct provenance on what was written.
- **Impact questions** — "what breaks if this signature changes" — graded exactly against the
  index.

The result is a table, not a sentence. The harness, the model choice, and the task set are the
plan's business, not this document's.

## 13. Non-goals

Inherited from the vision and made specific here:

- **No new syntax, no new compiler, no runtime component.** No import hook, no decorator, nothing
  on `sys.meta_path`. A program that uses cttp-expanded code runs with cttp uninstalled.
- **No fetching at import time**, even as an option, in the product described here. `cttp run` is
  a launcher that expands before running; the running program never resolves anything.
- **No lockfile.** The stamped link line is the record. A tool that needs a lockfile has misplaced
  a fact that belongs in the file.
- **No dynamic linking by default.** A link follows the latest version only when marked
  `track=latest` and only when `cttp update` runs.
- **No cross-language invocation.** `cttp-see` is the whole of cross-language support.
- **No hosted service in the protocol.** The default public registry at `cttp.ai` is a hosted
  service and the protocol works without it: the tool serves the same contract locally, and the
  long form of every address bypasses names entirely.
- **No package publishing.** cttp neither builds nor uploads distributions.
- **No editor plugin as a requirement.** A folding-and-hover extension is a wanted convenience;
  everything works from the CLI, plain editors, and plain `python`. No CI integration beyond
  `cttp check`'s exit code, no accounts, no auth.
- **No languages beyond Python on the write side** in this spec. The read side takes any language
  with a tree-sitter grammar; a second write side is a new spec section when it is earned.
- **No Stage 3 language.** Nothing here reserves syntax or structure for it; if it comes, it comes
  from what exists.

## 14. Deliberately unresolved

Named here so no one mistakes silence for a decision:

- **Registry syntax for a specific registry** inside an address, when more than one is configured.
- **One name, several languages.** Whether `hello-world` may carry renditions in more than one
  language, so that the same short form means the right thing in a TypeScript file, or whether
  each rendition is its own name. Deferred until there is a second write side.
- **Per-name version policy** beyond `default` and labelled refs — for instance a registry-wide
  rule that the short form means `stable` when the name has one.
- **Closure identity** as a second, optional identity in the address grammar — deferred until the
  index has shown whether the definition-only hash is enough in practice.
- **Attaching purpose, contract, and test metadata to an address** beyond links — the storage
  shape (in-repo sidecar file versus registry versus index) is open; the derived/asserted rule
  already governs whatever it becomes.
- **A precise cross-repository reference resolver for Python** (type-checker backed) — welcome when
  derived links from `ast` alone prove too coarse for `closure` and `who`.
- **Abbreviated versus full SHAs in stamps** — the grammar allows twelve or more; whether the tool
  writes full SHAs by default is a taste decision to make on first contact with real files.

