# cttp — the `--json` schemas

**Generated from `src/cttp/schemas.py` — do not edit.** `python -m cttp.schemas` rewrites it; `tests/test_schemas.py` fails when it is stale.

Schema version **5**, fingerprint `3af030a09bd6e1d9`. A change to any schema is a deliberate act: the fingerprint test fails until `SCHEMA_VERSION` is bumped and the change noted in `PROGRESS.md`.

## Conventions

- Every subcommand accepts `--json`, before or after the subcommand name (`cttp --json who x` and `cttp who x --json`). The object goes to stdout.
- Every object carries `schema_version` (an integer) first.
- **Every field is present.** A fact that is not available is `null` — never a plausible-looking value, never coerced to zero or an empty string (spec §10).
- No field beyond the schema's is printed; a reader may reject unknown fields.
- **Origin.** A fact computed by the tool from the repository is *derived*; a fact stated by a person is *asserted*. Each table says which under **Origin**; objects that carry an `origin` field say it in the output too.
- Types: `string`, `integer`, `number`, `boolean`, `[T]` an array of `T`, `{string: T}` a map with arbitrary keys, `a | b` one of the listed values, `?` may be `null`, `→ name` a shared object defined under **Shared objects**.
- On failure every command prints the [error object](#error) and exits 1 (2 for a declined confirmation).
- `serve`, `mcp` run until stopped and print no JSON object; `run` prints the program's own output.

## Commands

### version

`cttp --version --json`

The tool's version.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `version` | string |  |  |

### config

`cttp config --json`

The effective configuration: the file, the ordered registry list, the remotes.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `path` | string? |  | the config file; `null` when defaults were used |
| `registries` | [string] |  | HTTP URLs or local paths, asked in order |
| `remotes` | {string: string} |  | locator prefix → URL prefix |

### resolve

`cttp resolve <address> [--id <identity>] --json`

The page an address names: its source, identity, license, references and imports.

**When:** When you need one definition's text and signature, not the file. Any address form: a name, a locator, or an identity (answered from the object cache or the index).

- This is the registry contract's object (spec §8): `GET /<name>.json` returns the same.
- `locations` and `via` are only filled when an identity address was answered from a cache.
- With `--id`, a page whose identity does not start with the given hex is an error (exit 1) naming both hashes — the stamp is wrong, not the copy.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `name` | string? | asserted | the registry name, or `null` for a bare locator |
| `address` | string | derived | the pinned address: a 12-hex rev, the `#symbol` kept |
| `rev` | string | derived | the full commit SHA |
| `identity` | string | derived | `sha256:<12 hex>` of the page's own normalized text |
| `identity_full` | string | derived | the full hex |
| `shape` | string? | derived | `sha256:<12 hex>` of the shape; `null` when the language has no extractor |
| `shape_full` | string? | derived |  |
| `kind` | `function` \| `class` \| `constant` \| `type` \| `macro` \| `script` | derived | what the page is: `type` (a C struct, union, enum or typedef) and `macro` come from the tree-sitter extractor |
| `language` | `python` \| `c` \| `text` | derived | `text` for a file with no extractor |
| `symbol` | string? | derived | for a definition: its dotted name |
| `signature` | string? | derived | for a definition: Python — the header without its keyword; C — the declaration up to the body or initializer, a macro's name and parameters |
| `docstring` | string? | derived | the first docstring paragraph as one line; for C, the first paragraph of the comment directly above |
| `span` | [integer] | derived | `[first, last]` 1-based lines in the origin file |
| `source` | string | derived | the page's own text, normalized, link lines taken out (spec §4) |
| `description` | string? | asserted | the entry's one line; `null` when the entry has none |
| `license` | string? | derived | SPDX id of the repository's license file at the rev |
| `target` | string | derived | `host/owner/repo/path` |
| `path` | string | derived | the path within the repository |
| `registry` | string? |  | which registry answered, or lent the name; `null` for a bare locator |
| `refs` | [→ [ref](#ref)] | derived |  |
| `imports` | → [imports](#imports) | derived |  |
| `links` | [→ [link](#link)] | asserted |  |
| `unresolved` | [string] | derived | free names: used, bound by nothing in the page — what a closure must bind |
| `locations` | [→ [location](#location)] |  | every place seen, latest last; empty unless answered from a cache |
| `via` | `cache` \| `index`? |  | which cache answered an identity address; `null` when the repository did |
| `origin` | object |  | which fields are derived and which asserted |
| `origin.identity` | `derived` |  | computed by the tool from the repository |
| `origin.shape` | `derived` |  | computed by the tool from the repository |
| `origin.license` | `derived` |  | computed by the tool from the repository |
| `origin.rev` | `derived` |  | computed by the tool from the repository |
| `origin.refs` | `derived` |  | computed by the tool from the repository |
| `origin.imports` | `derived` |  | computed by the tool from the repository |
| `origin.unresolved` | `derived` |  | computed by the tool from the repository |
| `origin.links` | `asserted` |  | stated by a person: a link line or a registry entry |
| `origin.description` | `asserted`? |  | `null` when there is no description |
| `origin.location` | `repository` \| `cache` \| `index` |  | what answered |

### resolve --latest

`cttp resolve <pinned address> --latest --json`

Where a pinned page is at its repository's head, and which rule found it.

**When:** Before `update`: to see what following a link forward would resolve to.

- Exit 1 when not found; the object still says why.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `from` | → [page](#page) |  | the pinned page |
| `head` | string | derived | the full SHA of the head that was searched |
| `found` | boolean |  |  |
| `rule` | `same-path` \| `same-identity` \| `backlink`? | derived | spec §5: the same path and symbol at head; the same identity elsewhere; or, through the index, a page that links back (another repository, or a fork) |
| `via` | string? | derived | `index` when the index found it |
| `to` | → [page](#page)? |  | the page at head |
| `changed` | boolean? | derived | the identity differs from the pinned one (rule 1) |
| `message` | string |  | what happened, in words |
| `origin` | object |  |  |
| `origin.rule` | `derived` |  | computed by the tool from the repository |
| `origin.head` | `derived` |  | computed by the tool from the repository |
| `origin.via` | `derived` |  | computed by the tool from the repository |

### closure

`cttp closure <address> --json | cttp closure --indexed <address>… --json`

Exactly the definitions a page needs to run inline, in dependency order, each with its address.

**When:** When a task needs a definition and what it depends on, and nothing else: context cost proportional to the task. The live walk is what `expand` would write and refuses what cannot be inlined honestly; `--indexed` reads the index's recorded links instead, takes several roots, and lists what it cannot tell under `missing`.

- A closure over budget (50 definitions / 2,000 lines) is only an error for `expand`; `closure` lifts the budget.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `address` | string | derived | the (first) root's pinned address |
| `identity` | string | derived |  |
| `source` | `repository` \| `index` |  | a live walk of the repositories, or the index's recorded links (`--indexed`) |
| `roots` | [string] |  | the addresses asked about — one, or several with `--indexed` |
| `definitions` | [→ [node](#node)] | derived |  |
| `count` | integer |  |  |
| `lines` | integer |  |  |
| `imports` | [string] | derived | import statements to hoist above the whole block, in first-need order |
| `stdlib` | [string] | derived |  |
| `requires` | [string] | derived | third-party top-level packages the closure needs |
| `missing` | [→ [missing](#missing)] |  | always empty for a live walk, which refuses instead |
| `origin` | object |  |  |
| `origin.order` | `derived` |  | computed by the tool from the repository |
| `origin.imports` | `derived` |  | computed by the tool from the repository |
| `origin.requires` | `derived` |  | computed by the tool from the repository |

### expand

`cttp expand <file>… [--package] [--write-deps] --json`

What was written beneath each unexpanded link, per file.

**When:** To materialize links in place. Prefer `add` to write a new link.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `files` | {string: [→ [expand_report](#expand_report)]} |  | file path → its reports |

### add

`cttp add <address> [<file>] [--at N] [--package] --json`

The link written into the file and expanded, as `expand` reports it.

**When:** To bring a page into a file: writes `# cttp: <address>` and expands it.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `files` | {string: [→ [expand_report](#expand_report)]} |  | the one file → its reports |

### check

`cttp check <file>… [--fix] --json`

Every link's state: stamped, block hashing to its id, resolvable.

**When:** After editing a file with links, or before trusting one.

- Exit 1 when any link failed.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `ok` | boolean |  | no link failed (`ok` or `fixed`) |
| `links` | {string: [→ [check_report](#check_report)]} |  | file path → its reports |

### update

`cttp update <file>… [<address>…] [--all] [--to <rev>] [--yes] --json`

Each selected link's proposed or applied move forward.

**When:** To follow pinned links forward; `--yes` applies without a terminal.

- Exit 2 when a change waited for a confirmation it did not get.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `ok` | boolean |  | nothing is waiting for a confirmation |
| `links` | {string: [→ [update_report](#update_report)]} |  | file path → its reports |

### fold

`cttp fold <file>… [--open <address>] --json`

Each file as links, with every expanded block's line range.

**When:** To see a file as its links, so that a file with expanded code costs no more context than its link lines. Writes nothing.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `files` | {string: [→ [fold_entry](#fold_entry)]} |  | file path → its links |

### run

`cttp run <address | file> [--yes] --json`

Runs the program; its output is the program's own, not a JSON object.

- Only an error prints the error object. Exit 2 when the first run of an address was not confirmed (pass `--yes` without a terminal); otherwise the program's exit code.

No JSON object on success.

### cache status

`cttp cache status --json`

What the caches hold.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `home` | string |  | `$CTTP_HOME` |
| `repos` | object |  | bare clones |
| `repos.count` | integer |  |  |
| `repos.bytes` | integer |  |  |
| `objects` | object |  | the object cache |
| `objects.count` | integer |  |  |
| `objects.bytes` | integer |  |  |
| `run` | object |  | run-cache entries: what was confirmed to run |
| `run.count` | integer |  |  |
| `run.bytes` | integer |  |  |

### cache clear

`cttp cache clear [--run] --json`

What was removed.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `removed` | [string] |  | paths removed; the run cache only with `--run` |

### index add

`cttp index add <host/owner/repo | path> --json`

The repository registered for crawling.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `repo` | string |  | `host/owner/repo` |
| `local_path` | string? |  | the clone it was added from |
| `default_branch` | string? |  | learned at the first crawl of a locator |
| `status` | `added` \| `already registered` |  |  |

### index crawl

`cttp index crawl [<repo>…] [--rev <rev>] [--force] --json`

Each registered repository crawled at its head (or `--rev`).

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `crawled` | [→ [crawled](#crawled)] |  |  |

### index status

`cttp index status --json`

What the index holds.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `index` | string |  | the index file |
| `counts` | object |  | rows per table |
| `counts.repos` | integer |  |  |
| `counts.revisions` | integer |  |  |
| `counts.definitions` | integer |  |  |
| `counts.locations` | integer |  |  |
| `counts.links` | integer |  |  |
| `counts.names` | integer |  |  |
| `repos` | [→ [repo_status](#repo_status)] |  |  |

### who

`cttp who <address> [--coverage] --json`

Backlinks: every indexed page linking to the address, by relation and origin.

**When:** To find who uses a definition before changing it, or where a copy came from.

- Matches by identity; by place or name only for links whose target identity the index could not tell.
- Read `coverage.summary` before trusting the count: one line saying what was searched and whether the count may be trusted. `coverage.complete` true means every reference in the files read was attributed — the answer needs no corroboration, and the rest of the object is then `null` because there is nothing to warn about; `--coverage` (the tool's `coverage`) keeps it. When `complete` is false or null the object is whole, and every field of it is a reason to look further. Coverage cannot speak for a repository that was never crawled.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `address` | string |  | as asked |
| `identities` | [string] | derived | the identities the index knows at that address |
| `name` | string? |  | the name form's name |
| `repo` | string? |  | the place the address names |
| `path` | string? |  |  |
| `symbol` | string? |  |  |
| `backlinks` | [→ [backlink](#backlink)] | derived | sorted `is`, `from`, `see`, `ref`; asserted before derived |
| `count` | integer |  |  |
| `by` | → [by](#by) |  |  |
| `coverage` | → [coverage](#coverage) |  |  |
| `origin` | object |  |  |
| `origin.backlinks` | `derived` |  | computed by the tool from the repository |
| `origin.relation` | string |  | `per link: its origin` |

### dups

`cttp dups [--shape] --json`

Groups of pages that are the same code in more than one place, at the current revisions.

**When:** To find copies worth turning into links.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `by` | `identity` \| `shape` |  | `shape`: the same structure under other names or literals |
| `groups` | [→ [dup_group](#dup_group)] | derived | largest first |
| `count` | integer |  |  |
| `origin` | object |  |  |
| `origin.groups` | `derived` |  | computed by the tool from the repository |
| `origin.by` | `derived` |  | computed by the tool from the repository |

### search

`cttp search <words>… [--limit N] --json`

Pages whose name, signature or docstring match the words.

**When:** To find a definition by what it is called or what its docstring says. Every term is a prefix; stemming applies.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `query` | string |  |  |
| `hits` | [→ [hit](#hit)] | derived | best first |
| `count` | integer |  |  |
| `origin` | object |  |  |
| `origin.hits` | `derived` |  | computed by the tool from the repository |
| `origin.score` | `derived` |  | computed by the tool from the repository |

### history

`cttp history <address> --json`

The identities seen at one place over every crawled revision of its repository.

**When:** To see how a definition changed, or when it appeared.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `repo` | string |  |  |
| `path` | string |  |  |
| `symbol` | string? |  |  |
| `revisions` | [→ [revision](#revision)] | derived | oldest commit first |
| `identities` | [string] | derived | the distinct identities, in order of appearance |
| `count` | integer |  | revisions |
| `origin` | object |  |  |
| `origin.revisions` | `derived` |  | computed by the tool from the repository |
| `origin.identity` | `derived` |  | computed by the tool from the repository |

### rank

`cttp rank [--limit N] --json`

Pages ordered by how many distinct pages link to them.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `ranked` | [→ [ranked](#ranked)] | derived | most linked first |
| `count` | integer |  |  |
| `origin` | object |  |  |
| `origin.backlinks` | `derived` |  | computed by the tool from the repository |
| `origin.rank` | `derived` |  | computed by the tool from the repository |

### name show

`cttp name show <name> --json`

A registry entry and what the name resolves to.

**When:** To see who owns a name, where it points, and its labels, before linking to it.

- An HTTP registry answers resolutions, not entries; the entry comes from a local registry repository.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `name` | string |  |  |
| `registry` | string |  | the local registry the entry came from |
| `entry` | → [entry](#entry) | asserted |  |
| `resolution` | → [page](#page) | derived | what `cttp resolve <name>` prints |
| `origin` | object |  |  |
| `origin.entry` | `asserted` |  | stated by a person: a link line or a registry entry |
| `origin.resolution` | `derived` |  | computed by the tool from the repository |

### name claim

`cttp name claim <name> --target <host/owner/repo[/path]> [--description …] [--version label=ref]… [--default label] [--transfer] [--no-pr] --json`

The entry written for the name, the checks it passed, and the pull request opened for it.

- Refused (exit 1) when the target's `cttp.toml` does not declare the name, when the name is another owner's and `--transfer` was not given, or when a label or ref is not valid.
- The pull request needs `gh` and an `origin` remote on the registry clone; `--no-pr` needs neither.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `name` | string |  |  |
| `action` | `claimed` \| `updated` \| `transferred` |  | a new name; the same owner's entry rewritten; another owner's name taken over (`--transfer`) |
| `owner` | string | derived | `host/owner` of the target |
| `previous_owner` | string? |  | the owner the entry had before, when it existed |
| `target` | string |  |  |
| `declared_at` | object | derived | where the target declared the name |
| `declared_at.file` | string |  | `cttp.toml` |
| `declared_at.branch` | string |  | the target's default branch |
| `declared_at.rev` | string |  | its head, full SHA |
| `entry` | → [entry](#entry) |  |  |
| `checks` | [→ [check](#check)] |  | the checks run before writing (`resolves` is left to `name verify`) |
| `path` | string |  | `names/<name>.toml` |
| `text` | string |  | the file's text |
| `written_to` | string? |  | the file in the registry clone's working tree (`--no-pr`); `null` when it went into a pull request |
| `branch` | string? |  | `claim/<name>`, pushed to the registry's origin; `null` with `--no-pr` |
| `pr` | string? |  | the pull request's URL; `null` with `--no-pr` |
| `registry` | string |  | the local registry repository the claim is against |
| `origin` | object |  |  |
| `origin.owner` | `derived` |  | computed by the tool from the repository |
| `origin.declaration` | `derived` |  | computed by the tool from the repository |
| `origin.description` | `asserted` |  | stated by a person: a link line or a registry entry |

### name verify

`cttp name verify [<name>…] --json`

The registry's checks on each entry (every name when none is given), and whether all passed.

- Exit 1 when any check failed. This is what the registry repository's workflow runs on a pull request, with `--registry .`.
- A name the registry does not have fails its `declaration` check with the reason.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `ok` | boolean |  | every name passed every check |
| `names` | [object] |  | in the order asked, or sorted |
| `names[].name` | string |  |  |
| `names[].ok` | boolean |  |  |
| `names[].checks` | [→ [check](#check)] |  |  |
| `count` | integer |  | names verified |

### serve --export

`cttp serve --export <dir> --json`

The static files written: every route of the contract for every name, identical to the live responses.

- Symbol routes (`%23<symbol>`) are not exported — they are unbounded; a live server answers them.
- `cttp serve` without `--export` runs until stopped and prints no JSON object.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `directory` | string |  |  |
| `names` | [string] |  | every name in the local registries, sorted |
| `files` | [object] |  | `/` → `index.html`, `/<name>` → `<name>/index.html`, `/<name>.json`, `/<name>@<label>.json` per version label |
| `files[].route` | string |  | the route as the live server serves it |
| `files[].path` | string |  | the file, relative to the directory |
| `files[].bytes` | integer |  |  |
| `count` | integer |  | files written |

### mcp install

`cttp mcp install [--claude-code] --json`

The `claude mcp add` line that attaches the MCP server to Claude Code, and whether it ran.

- `cttp mcp` itself runs the server over stdio and prints no JSON object.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `command` | [string] |  | the command line, one argument per element |
| `ran` | boolean |  | `--claude-code`: it was run |
| `output` | string? |  | what `claude mcp add` printed; `null` when not run |

### error

`any command, on failure`

What went wrong, in one line.

- Printed to stdout with `--json` (stderr otherwise); exit 1, or 2 for a declined confirmation.

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `schema_version` | integer |  |  |
| `error` | string |  | the message the text mode prints after `error:` |

## Shared objects

### imports

the outside modules a page needs (spec §8)

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `stdlib` | [string] | derived | top-level standard-library modules used |
| `third_party` | [string] | derived | top-level modules that are neither stdlib nor in the repository |
| `statements` | [string] | derived | the import statements that bind those names; `expand` hoists them |

### ref

a derived reference to a file or definition in the same repository

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `address` | string | derived | a pinned locator address at the same rev |
| `name` | string | derived | the text the page reaches it by (`REG_BITS`, `decode.STEP`, `r2m`); decides whether it can be inlined (spec §7) |
| `relation` | `ref` | derived |  |
| `origin` | `derived` |  | computed by the tool from the repository |

### link

a link line found in the page's own text (spec §4)

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `address` | string | asserted | the address as written |
| `relation` | `is` \| `from` \| `see` | asserted | the link's marker: `cttp:` / `cttp-from:` / `cttp-see:` |
| `fields` | {string: string} | asserted | the `key=value` fields, in order |
| `description` | string? | asserted | the trailing quoted string |
| `derived` | boolean |  | whether the description was written by the tool (`~"…"`) |
| `line` | integer |  | 1-based, within the page's text |
| `indent` | string |  | the whitespace before the comment marker |
| `origin` | `asserted` |  | stated by a person: a link line or a registry entry |

### location

one place a page was seen, from the object cache or the index (not part of the registry contract)

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `address` | string | derived | the pinned locator address |
| `target` | string | derived | `host/owner/repo/path` |
| `path` | string | derived |  |
| `rev` | string | derived | the full commit SHA |
| `name` | string? | asserted | the registry name that pointed here |
| `registry` | string? |  | which registry answered |
| `description` | string? | asserted | the entry's one line |
| `license` | string? | derived | SPDX id at that rev |
| `seen` | string |  | ISO-8601 UTC: when it was resolved (cache) or crawled (index) |
| `origin` | `cache` \| `index` |  | which cache the location came from |

### page

the resolver's object — what an address names; the registry contract's JSON (spec §8)

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `name` | string? | asserted | the registry name, or `null` for a bare locator |
| `address` | string | derived | the pinned address: a 12-hex rev, the `#symbol` kept |
| `rev` | string | derived | the full commit SHA |
| `identity` | string | derived | `sha256:<12 hex>` of the page's own normalized text |
| `identity_full` | string | derived | the full hex |
| `shape` | string? | derived | `sha256:<12 hex>` of the shape; `null` when the language has no extractor |
| `shape_full` | string? | derived |  |
| `kind` | `function` \| `class` \| `constant` \| `type` \| `macro` \| `script` | derived | what the page is: `type` (a C struct, union, enum or typedef) and `macro` come from the tree-sitter extractor |
| `language` | `python` \| `c` \| `text` | derived | `text` for a file with no extractor |
| `symbol` | string? | derived | for a definition: its dotted name |
| `signature` | string? | derived | for a definition: Python — the header without its keyword; C — the declaration up to the body or initializer, a macro's name and parameters |
| `docstring` | string? | derived | the first docstring paragraph as one line; for C, the first paragraph of the comment directly above |
| `span` | [integer] | derived | `[first, last]` 1-based lines in the origin file |
| `source` | string | derived | the page's own text, normalized, link lines taken out (spec §4) |
| `description` | string? | asserted | the entry's one line; `null` when the entry has none |
| `license` | string? | derived | SPDX id of the repository's license file at the rev |
| `target` | string | derived | `host/owner/repo/path` |
| `path` | string | derived | the path within the repository |
| `registry` | string? |  | which registry answered, or lent the name; `null` for a bare locator |
| `refs` | [→ [ref](#ref)] | derived |  |
| `imports` | → [imports](#imports) | derived |  |
| `links` | [→ [link](#link)] | asserted |  |
| `unresolved` | [string] | derived | free names: used, bound by nothing in the page — what a closure must bind |
| `locations` | [→ [location](#location)] |  | every place seen, latest last; empty unless answered from a cache |
| `via` | `cache` \| `index`? |  | which cache answered an identity address; `null` when the repository did |
| `origin` | object |  | which fields are derived and which asserted |
| `origin.identity` | `derived` |  | computed by the tool from the repository |
| `origin.shape` | `derived` |  | computed by the tool from the repository |
| `origin.license` | `derived` |  | computed by the tool from the repository |
| `origin.rev` | `derived` |  | computed by the tool from the repository |
| `origin.refs` | `derived` |  | computed by the tool from the repository |
| `origin.imports` | `derived` |  | computed by the tool from the repository |
| `origin.unresolved` | `derived` |  | computed by the tool from the repository |
| `origin.links` | `asserted` |  | stated by a person: a link line or a registry entry |
| `origin.description` | `asserted`? |  | `null` when there is no description |
| `origin.location` | `repository` \| `cache` \| `index` |  | what answered |

### node

one page of a closure

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `address` | string | derived | the pinned address |
| `locator` | string | derived | the pinned locator form — the closure's key |
| `identity` | string | derived |  |
| `identity_full` | string | derived |  |
| `kind` | `function` \| `class` \| `constant` \| `type` \| `macro` \| `script` | derived | what the page is: `type` (a C struct, union, enum or typedef) and `macro` come from the tree-sitter extractor |
| `symbol` | string? | derived |  |
| `path` | string | derived |  |
| `lines` | integer | derived | lines of source |
| `license` | string? | derived |  |
| `description` | string? |  | the stamp's description: the entry's, else one derived from signature and docstring |
| `via` | `root` \| `link` \| `ref` |  | how the closure reached it: the root, an inner `# cttp:` line, or a derived reference |
| `needs` | [string] | derived | pinned locator addresses this page depends on directly |
| `defines` | [string] | derived | the top-level names this page binds when inlined |
| `source` | string | derived |  |
| `origin` | object |  |  |
| `origin.description` | `derived` \| `asserted`? |  | `null` when there is no description |
| `origin.via` | `derived` \| `asserted` |  | `asserted` for a link, `derived` for a reference or the root |

### missing

a target the index cannot tell (never fetched); only `--indexed` lists these — the live walk refuses instead

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `from` | string |  | the page that links to it |
| `address` | string |  | the target as written |
| `relation` | `is` \| `ref` |  |  |

### expand_report

one link's outcome from `expand` or `add`

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `line` | integer |  | 1-based; 0 for a report about `pyproject.toml` |
| `relation` | `is` \| `from` \| `see` |  | the link's marker: `cttp:` / `cttp-from:` / `cttp-see:` |
| `address` | string |  | the link's address as written (a path for the `deps` report) |
| `status` | `expanded` \| `unchanged` \| `vendored` \| `requires` \| `deps` |  | `requires`: the closure needs third-party packages (listed in `detail`); `deps`: what `--write-deps` did, or what it would do |
| `detail` | string? |  |  |

### check_report

one link's outcome from `check`

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `line` | integer |  | 1-based; 0 for a report about `pyproject.toml` |
| `relation` | `is` \| `from` \| `see` |  | the link's marker: `cttp:` / `cttp-from:` / `cttp-see:` |
| `address` | string |  | the link's address as written (a path for the `deps` report) |
| `status` | `ok` \| `unexpanded` \| `drift` \| `mismatch` \| `unresolvable` \| `fixed` |  | spec §7: `drift` — the block no longer hashes to its `id=`; `mismatch` — the block does, the origin page does not; `fixed` — `--fix` turned a drifted `is` into `from` |
| `detail` | string? |  |  |

### update_report

one link's outcome from `update`

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `line` | integer |  | 1-based; 0 for a report about `pyproject.toml` |
| `relation` | `is` \| `from` \| `see` |  | the link's marker: `cttp:` / `cttp-from:` / `cttp-see:` |
| `address` | string |  | the link's address as written (a path for the `deps` report) |
| `status` | `updated` \| `unchanged` \| `upstream` \| `not-found` \| `drift` \| `unexpanded` \| `vendored` \| `not-confirmed` |  | `upstream`: a `from` link — the diff is shown, never applied; `not-confirmed`: the change waited for a confirmation it did not get (exit 2) |
| `detail` | string? |  |  |
| `to` | string? | derived | the address the link would move to |
| `rule` | `same-path` \| `same-identity` \| `backlink` \| `to`? | derived | which of spec §5's rules found it |
| `diff` | string | derived | a unified diff of the block, empty when there is none |

### fold_entry

one link of a file, with the block it stands for

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `line` | integer |  | 1-based line of the link |
| `relation` | `is` \| `from` \| `see` | asserted | the link's marker: `cttp:` / `cttp-from:` / `cttp-see:` |
| `address` | string | asserted |  |
| `description` | string? | asserted |  |
| `start` | integer |  | 1-based first line of the block |
| `end` | integer |  | 1-based last line, inclusive; `start - 1` when nothing is beneath |
| `lines` | integer |  |  |
| `folded` | boolean |  | whether the block was collapsed in the text output |

### backlink

one indexed link whose target is the address asked about

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `source` | object |  | the page the link belongs to (spec §4: the block's definition, else the innermost holding definition, else the file) |
| `source.identity` | string | derived |  |
| `source.identity_full` | string | derived |  |
| `source.address` | string? | derived | its pinned locator address |
| `source.repo` | string |  |  |
| `source.sha` | string |  |  |
| `source.path` | string |  |  |
| `source.symbol` | string? |  |  |
| `source.kind` | `function` \| `class` \| `constant` \| `type` \| `macro` \| `script` |  | what the page is: `type` (a C struct, union, enum or typedef) and `macro` come from the tree-sitter extractor |
| `source.name` | string |  | the definition's name, or the file name |
| `source.signature` | string? | derived |  |
| `source.license` | string? | derived |  |
| `relation` | `is` \| `from` \| `see` \| `ref` |  |  |
| `origin` | `derived` \| `asserted` |  | `asserted` for a link line, `derived` for a reference |
| `line` | integer |  | 1-based, in the file |
| `target` | string |  | the target address as written |
| `target_identity` | string? | derived | the target's identity, when the index can tell |
| `description` | string? | asserted |  |
| `name` | string? |  | a derived reference: the text it is reached by |

### by

counts by relation, then by origin: `{"is": {"asserted": 2}, "ref": {"derived": 1}}`

| Field | Type | Origin | Meaning |
|---|---|---|---|

### searched_revision

one crawled revision the answer covers

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `repo` | string |  | host/owner/repo |
| `rev` | string | derived | the commit, 12 hex |
| `sha` | string | derived | the full commit SHA |
| `current` | boolean |  | whether this is the repository's most recently crawled revision — what `dups`, `rank` and `search` report over |
| `committed_at` | integer? | derived | the commit's own unix timestamp |
| `crawled_at` | string | derived |  |
| `files` | integer | derived | files the crawl looked at |
| `pages` | integer | derived | pages recorded: every Python file and each of its definitions, plus any other file carrying a link |
| `links` | integer | derived | link and reference rows recorded from this revision |
| `paths` | {string: integer} | derived | top-level directory → files under it that produced a page (`.` for the repository root); a directory absent here holds no page, as in a sparse checkout |
| `skipped` | integer? | derived | files the crawl could not read or parse; `null` for a revision crawled before this was recorded — `cttp index crawl --force` fills it |
| `unread` | integer? | derived | of those, the files a language extractor would have read and did not — a hole anything could have been referenced through. A binary blob is skipped and is no hole |
| `ignored_links` | integer? | derived | link lines the crawl had to ignore because they did not parse — usually prose in a docstring that looks like a link, but the crawl cannot tell |
| `origin` | `derived` |  | computed by the tool from the repository |

### unmapped_import

an import naming a module the repository itself provides that the extractor could not map to a file — a layout no source root reaches, or a namespace package with no `__init__.py`

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `repo` | string |  |  |
| `rev` | string | derived | the commit, 12 hex |
| `module` | string | derived | the top-level module named |
| `files` | integer | derived | files importing it |
| `origin` | `derived` |  | computed by the tool from the repository |

### coverage

what the answer is an answer over: an agent that wants to stop reads this instead of corroborating by hand. A complete answer is `summary` and the three counts; the rest is evidence for a doubt `complete` has already settled, and it is `null` unless `cttp who --coverage` (the MCP tool's `coverage`) asks for it

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `repos` | integer |  | repositories searched |
| `revisions` | integer |  | crawled revisions searched — `who` sees every one of them |
| `files` | integer |  | files looked at across them |
| `summary` | string |  | the whole of the above in one line: what was searched, whether the count may be trusted, and what is missing when it may not. Always present — on a complete answer it is the only part that is |
| `searched` | [→ [searched_revision](#searched_revision)]? | derived | by repository, then crawl order; `null` on a collapsed complete answer — `summary` names the revisions |
| `skipped` | integer? | derived | files not read, across every revision; `null` when any revision predates the record, or on a collapsed complete answer |
| `unread` | integer? | derived | of those, the files a language extractor would have read and did not |
| `ignored_links` | integer? | derived | link lines the crawl had to ignore because they did not parse; an asserted link may be missing for each |
| `unresolved_targets` | integer? | derived | recorded links whose target identity the index cannot tell; `who` matches those by name or place only, so a match can be missed. Mostly re-exports: a reference to `click.echo` lands on the `__init__.py` that imports the name, which defines nothing |
| `unresolved_matching` | integer? | derived | of those, the ones naming *this* address — the misses this answer could have. Zero is `who` saying the total does not concern the question asked, which is what a collapsed complete answer says by being collapsed |
| `unmapped_imports` | [→ [unmapped_import](#unmapped_import)]? | derived | each one is a reference the crawl did not record, and so a backlink `who` cannot see |
| `caveats` | [string]? |  | the ways `who` is knowingly incomplete inside the files it did read; no count expresses these. `null` on a collapsed complete answer: they are standing limits of the query, not findings about this one |
| `complete` | boolean? | derived | true when this answer has no gap: no file went unread, no link line was ignored, no unidentified link names this address, no import into a repository went unmapped. The answer then needs no corroboration beyond `caveats`, and the fields above it collapse to `null` unless `--coverage` was asked for. It says nothing about a repository never crawled: `summary` and `searched` answer that. `null` when `unread` is unknown |
| `origin` | `derived` |  | computed by the tool from the repository |

### dup_group

pages that are the same code (by identity) or the same structure (by shape), in more than one place

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `key` | string | derived | `sha256:<12 hex>` — the identity or the shape the group shares |
| `key_full` | string | derived |  |
| `identities` | [string] | derived | the distinct identities in the group (one, by identity) |
| `names` | [string] | derived | the distinct definition names, sorted |
| `kind` | `function` \| `class` \| `constant` \| `type` \| `macro` \| `script` | derived | what the page is: `type` (a C struct, union, enum or typedef) and `macro` come from the tree-sitter extractor |
| `lines` | integer | derived |  |
| `count` | integer |  | places |
| `locations` | [object] |  |  |
| `locations[].address` | string | derived |  |
| `locations[].identity` | string | derived |  |
| `locations[].repo` | string |  |  |
| `locations[].path` | string |  |  |
| `locations[].symbol` | string? |  |  |
| `locations[].license` | string? | derived |  |
| `locations[].name` | string | derived | the definition's name |

### hit

one search hit

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `identity` | string | derived |  |
| `identity_full` | string | derived |  |
| `name` | string | derived |  |
| `kind` | `function` \| `class` \| `constant` \| `type` \| `macro` \| `script` | derived | what the page is: `type` (a C struct, union, enum or typedef) and `macro` come from the tree-sitter extractor |
| `signature` | string? | derived |  |
| `docstring` | string? | derived |  |
| `score` | number | derived | FTS5 bm25 rank; lower is better |
| `address` | string? |  | where it is at the current revision, else the last place seen |
| `locations` | [object] |  | current places first when there are any |
| `locations[].address` | string |  |  |
| `locations[].repo` | string |  |  |
| `locations[].path` | string |  |  |
| `locations[].symbol` | string? |  |  |
| `locations[].name` | string? | asserted | the registry name pointing at this place |

### revision

one crawled revision of the place

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `sha` | string |  |  |
| `address` | string |  | the place at that rev |
| `committed_at` | integer? | derived | the commit's own timestamp (unix) |
| `crawled_at` | string |  | ISO-8601 UTC |
| `identity` | string? | derived |  |
| `identity_full` | string? | derived |  |
| `shape` | string? | derived |  |
| `signature` | string? | derived |  |
| `absent` | boolean |  | the place has no page at this rev |
| `changed` | boolean |  | the identity differs from the revision before |

### ranked

one ranked page

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `identity` | string | derived |  |
| `identity_full` | string | derived |  |
| `name` | string | derived |  |
| `kind` | `function` \| `class` \| `constant` \| `type` \| `macro` \| `script` | derived | what the page is: `type` (a C struct, union, enum or typedef) and `macro` come from the tree-sitter extractor |
| `signature` | string? | derived |  |
| `address` | string? |  |  |
| `backlinks` | integer | derived | distinct linking pages — (identity, repo, file) |
| `by` | → [by](#by) |  |  |

### crawled

one repository crawled at one revision

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `repo` | string |  | `host/owner/repo` |
| `sha` | string |  |  |
| `status` | `crawled` \| `already` |  | `already`: skipped, crawled before (`--force` redoes it) |
| `files` | integer |  | files looked at |
| `pages` | integer |  | locations written |
| `definitions` | integer |  | identities the index had not seen before |
| `links` | integer |  |  |
| `skipped` | [string] |  | files that could not be read or parsed, with the reason |
| `unmapped` | {string: integer} | derived | module → files: an import naming a module this repository provides that no source root reached, so no reference was recorded for it; `who`'s coverage reports these |

### repo_status

one registered repository

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `repo` | string |  |  |
| `default_branch` | string? |  |  |
| `local_path` | string? |  | the clone it was added from |
| `revisions` | [object] |  |  |
| `revisions[].sha` | string |  |  |
| `revisions[].crawled_at` | string |  |  |
| `revisions[].license` | string? | derived |  |
| `revisions[].files` | integer |  |  |

### closure

the pages a page needs to run inline, dependencies before dependents, the root last

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `address` | string | derived | the (first) root's pinned address |
| `identity` | string | derived |  |
| `source` | `repository` \| `index` |  | a live walk of the repositories, or the index's recorded links (`--indexed`) |
| `roots` | [string] |  | the addresses asked about — one, or several with `--indexed` |
| `definitions` | [→ [node](#node)] | derived |  |
| `count` | integer |  |  |
| `lines` | integer |  |  |
| `imports` | [string] | derived | import statements to hoist above the whole block, in first-need order |
| `stdlib` | [string] | derived |  |
| `requires` | [string] | derived | third-party top-level packages the closure needs |
| `missing` | [→ [missing](#missing)] |  | always empty for a live walk, which refuses instead |
| `origin` | object |  |  |
| `origin.order` | `derived` |  | computed by the tool from the repository |
| `origin.imports` | `derived` |  | computed by the tool from the repository |
| `origin.requires` | `derived` |  | computed by the tool from the repository |

### entry

a registry entry: `names/<name>.toml` (spec §8) — asserted by its author, except `owner`, which `name claim` derives from the target

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `name` | string | asserted |  |
| `description` | string? | asserted | one line, copied onto link lines; `null` when the entry has none |
| `owner` | string? | derived | `host/owner`: the account that proved control of the target |
| `target` | string | asserted | `host/owner/repo[/path]` |
| `default` | string | asserted | the label the short form resolves to |
| `versions` | {string: string} | asserted | label → ref of the target repository |

### check

one of the registry's checks on an entry (spec §8, plan P7-T2)

| Field | Type | Origin | Meaning |
|---|---|---|---|
| `check` | `declaration` \| `owner` \| `target` \| `labels` \| `resolves` |  | the target's `cttp.toml` declares the name at its default branch; the owner is the target's account; the target path exists; every label is well formed and its ref is a revision; the name resolves |
| `ok` | boolean |  |  |
| `detail` | string |  | what was found, or what is wrong and what to do |
