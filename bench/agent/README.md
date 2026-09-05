# The agent benchmark

Plan Phase 8: does an agent that navigates code through cttp's tools consume less context than one
that navigates with the shell, and does it succeed as often? Two arms, the same tasks, the same
model, the same harness — only the tools differ.

## How a run works

`harness.py` runs **Claude Code headless** — `claude -p <prompt> --output-format stream-json` — as
a subprocess under the subscription login of whoever runs it. It never passes `--bare`, which
needs an API key; the login is what makes the benchmark free to run. Nothing from `~/.claude`
reaches a run: `--setting-sources ""` drops the user, project and local settings (hooks, plugins,
model preference), `--strict-mcp-config` drops the user-scope cttp MCP server, the fresh checkout
under a scratch directory has no `CLAUDE.md` and no auto memory, and `--no-session-persistence`
leaves no transcript behind.

Per run:

1. **Checkout.** The task's source — a directory of this repository, or a git repository on
   disk at a pinned commit — is committed as `main`, cloned bare as the "remote", and cloned
   again as the working copy the agent edits. The setup overlay (the bug, the visible tests) is
   committed on top. The working copy's `origin` is the bare repository, which a per-run
   `cttp.toml` maps to the task's locator through `[remotes]` — exactly how the test suite serves
   its fixtures, so `cttp index add <checkout>` and `resolve <locator>` work with no network. A
   cross-repository task's `[[deps]]` get the same treatment and land beside the working copy as
   `deps/<name>` (`../deps/rich` from the agent's directory), so both arms can reach them.
2. **Index** (links arm; both arms for an impact task, whose grader reads it). `cttp index add`
   for the checkout and every dependency clone, one `cttp index crawl`, into the run's own
   `index.db`; the MCP server is started with `CTTP_CONFIG`, `CTTP_INDEX` and `CTTP_HOME`
   pointing at the run's files.
3. **Claude Code**, from the checkout, with the arm's tools, `--permission-mode dontAsk`,
   `--permission-prompts none`, the same `--model`, `--max-turns` and `--append-system-prompt`.
   stdin is `/dev/null`; a run past `--timeout` gets SIGINT, then SIGKILL.
4. **Grade.** The grade overlay (the hidden tests) is copied over the checkout and the task's
   command runs; exit 0 is a pass. A cross-repository task then runs the **link check**, an
   impact task the **who check** (below); every check's findings are in the record under
   `grade.checks`. The agent's diff against the base commit is kept.
5. **Record** `results/<date>/<task>/<arm>/<run>.json`, with the raw stream beside it as
   `<run>.stream.jsonl` (and stderr as `<run>.stream.stderr`).

## The arms

| | `links` | `baseline` |
|---|---|---|
| cttp MCP tools (`resolve`, `who`, `closure`, `search`, `dups`, `fold`) | yes | no |
| `Read`, `Edit`, `Write` | yes | yes |
| `Bash` | the task's test command only (an impact task has none) | the test command, plus the read-only commands `dontAsk` mode auto-approves (`grep`, `find`, `ls`, `cat`, `git log`, …) |
| shell readers (`cat`, `grep`, `find`, `ls`, `sed`, `git`, … — `SHELL_READERS`) | denied by rule | allowed |

Two facts about Claude Code 2.1.261 shaped this:

- **`Edit` and `Write` refuse a file the session has not read.** The plan's first design had
  no `Read` in the links arm; in the smoke run the agent found the bug through `fold`, `search`,
  `closure`, `resolve` and `who`, then could not apply it (every `Edit` and `Write` answered
  "File has not been read yet") and burned its turns. Both arms therefore have `Read`. What the
  arms compare is how the agent *finds* code — the cttp tools against the shell — not whether it
  can read the file it edits.
- **There is no `Grep` or `Glob` tool.** Searching is `grep` and `find` through `Bash`. The
  baseline keeps them (that is ordinary Claude Code); the links arm denies them by explicit
  rules, because `dontAsk` mode auto-approves the read-only command set and would otherwise let
  them through.

- **An arm that is not told what its search is discovers it by denial.** In the first runs the
  links arm reached for `grep` or `cat` in every single run and learned of its own tools from
  the permission denial — a wasted turn per run, sometimes two, which measures the deny list
  rather than the tools. Since 2026-09-05 the appended system prompt carries **one sentence per
  arm naming that arm's search** (`SEARCH_NOTES` in `harness.py`): the six cttp tools and what
  each answers for `links`, the shell's readers for `baseline`. The treatment is symmetric —
  neither arm has to find its search by trial — and every record carries the exact text it was
  given as `system_prompt`. The report states this, because it is a change to the arms.

Every tool call of every run is in the record (`tool_calls`, `tool_counts`), so a leak — a
reader that slipped past the deny list, a cttp tool the baseline somehow reached — is visible,
and `permission_denials` counts what the rules stopped.

## What a record holds

`tokens` is the sum of the result object's `usage` — `input_tokens`, `output_tokens`,
`cache_read_input_tokens`, `cache_creation_input_tokens` — over the whole run: the tokens of
context the model consumed, cached or not. `usage` and `model_usage` (the per-model breakdown,
which also counts side requests such as the title or the classifier) are kept as Claude Code
reported them; `total_cost_usd` is Claude Code's list-price estimate, not a bill.
`stream_usage` is the input side summed again from the stream's per-response usage (one count
per message id) and `requests` the number of API responses — a cross-check of `usage`, which
is authoritative; the stream's output counts are per chunk and are not summed. Also:
`num_turns`, `duration_ms`, `wall_seconds`, `permission_denials`, `tool_calls` (name, input,
denied, error, result size), `tools_available` and `mcp_servers` from `system/init`
(`cttp_connected` says whether the server was up), the last `rate_limit` event (the five-hour
and seven-day utilization — what P8-T3's estimate reads), `final_text`, the `grade` (pass,
output, the diff), `base_sha`, the crawl's counts under `index`, and the full `argv`.

`status` is `pass`, `fail`, `limited` (a usage limit: the rate-limit event says `rejected`, or
the result is an error naming the limit — never counted as a fail), `timeout` or `error`.

## Commands

```bash
bash bench/agent/fetch.sh                                   # once: clone click, attrs and rich under bench/agent/repos/
uv run python -m bench.agent.harness --list                 # the tasks (marks any whose repository is not fetched)
uv run python -m bench.agent.harness --check-graders        # each grader fails the unmodified checkout, passes the solution (~2½ min)
uv run python -m bench.agent.harness --task smoke-pyrepo    # both arms, one run each, today's date
uv run python -m bench.agent.harness --runs 3               # every task, both arms, three runs
uv run python -m bench.agent.harness --runs 3 --wait-for-reset   # sleep through usage limits
uv run python -m bench.agent.harness --replay results/<date>/<task>/<arm>/1.json   # no subscription used
uv run python -m bench.agent.report results/<date>          # the table; writes report.md beside the results
```

A run that exists is skipped, so the same command picks up where a usage limit or a Ctrl-C
stopped it; `--redo` runs it again. `--keep` leaves the scratch checkout on disk for a look.
`--model`, `--max-turns` (40) and `--timeout` (1200 s) apply to both arms.

## Tasks

A task is `tasks/<name>/task.toml` with a prompt, the source repository (`[repo]`: a directory of
this repository, or a git repository on disk with a pinned `rev`), its locator, optional
`[[deps]]` (other repositories, each with its own locator and rev), and up to three overlays:
`setup` (committed before the run), `grade` (copied over after it, never seen by the agent) and
`solution` (the reference fix, for `--check-graders`). An overlay is a directory of the task
(`overlay = "grade"`) or paths taken from a commit of the source repository (`commit = "<sha>"`,
`paths = [...]`) — the in-repository tasks carry their real fixes and tests that way, without
copying licensed code into this repository. `grade.command` is both the grader and the one shell
command the agent may run; `[grade.link]` and `[grade.who]` add the checks below.

**The repositories** (P8-T2 asked for three mid-size Python projects, 5k–30k lines, good test
suites, permissive licenses, from `attrs`, `click`, `tomli-w`, `rich`, `httpx`):

| repository | license | package lines | why |
|---|---|---:|---|
| `pallets/click` | BSD-3 | 12,700 | src layout, many small modules, a steady stream of small behavioural fixes with tests; needs only `pytest` |
| `python-attrs/attrs` | MIT | 6,400 | one 3,400-line `_make.py` that generates code — finding the right spot is the work; tests need `hypothesis` |
| `Textualize/rich` | MIT | 26,600 | flat layout, the biggest of the three, rendering fixes whose tests compare exact output; needs `pygments` and `markdown-it-py` |

`tomli-w` is a few hundred lines — too small to have anything to search for. `httpx` needs a
network stack (`httpcore`, `anyio`, `trio`, a test server) to run its tests. The three chosen run
their tests with what the `bench` dependency group installs into this project's venv
(`pyproject.toml`; `uv sync` installs it by default). `bash bench/agent/fetch.sh` clones the
three under `bench/agent/repos/` (gitignored, ~150 MB) and checks every pinned commit is present;
tasks and their `--list` line say when a repository is missing.

**In-repository changes** (`ir-*`, five): real merged bug-fix commits. The checkout is the
commit's parent; the prompt is the bug report, written from the issue and the commit without
naming the file; the hidden grader is the commit's test file (the tests it added fail on the
parent, the rest pass — verified for each); the reference solution is the commit's source file.
Chosen so that the fix is small but the place has to be found in a 700–3,400-line file.

| task | commit | what |
|---|---|---|
| `ir-write-usage-click` | click `0551bf5` (#3360) | `HelpFormatter.write_usage` with no args writes a blank line |
| `ir-choice-metavar-click` | click `1a4d8c1` (#2356) | `Choice` with `show_choices=False` still lists the values in `--help` |
| `ir-slots-getattr-attrs` | attrs `88e2896` (#1230) | the generated `__getattr__` of a slotted class swallows a property's `AttributeError` |
| `ir-table-highlight-rich` | rich `16b3830` (#3517) | columns `add_row` creates do not inherit `highlight` |
| `ir-pretty-dataclass-rich` | rich `6055e2d` (#3417) | pretty-printing a dataclass with an unset `init=False` field raises |

**Cross-repository reuse** (`xr-*`, five): the checkout is a small consumer project of the task
(`consumer/`: `app.py` with a function that calls the one to be written, one visible test); one
dependency repository at a pinned commit is checked out at `../deps/<name>` and indexed. The
prompt names the function to write, the library, the repository, the commit and the definition
to reuse — not its file — and asks for the copied code to be marked with `# cttp:` links. The
hidden tests exercise the behaviour (including what a from-scratch rewrite would get wrong: ANSI
widths, backslash doubling, prefix ordering) and assert the library is not imported. The
reference `app.py` was written with `cttp add`, so it carries real stamps.

| task | definition | closure |
|---|---|---|
| `xr-textwrap-click` | click `_textwrap.py#TextWrapper` | 5 definitions, 181 lines, across `_textwrap.py` and `_compat.py` |
| `xr-join-options-click` | click `formatting.py#join_options` | 2 definitions (`_split_opt` from `parser.py`) |
| `xr-filesize-rich` | rich `filesize.py#decimal` | 2 definitions, 60 lines |
| `xr-escape-rich` | rich `markup.py#escape` | 4 definitions (three type aliases) |
| `xr-to-bool-attrs` | attrs `converters.py#to_bool` | 1 definition |

**The link check** (`graders.check_link`): `app.py` must hold an `is` link (`# cttp: …`) whose
address resolves — through the run's config, so the dependency's bare clone answers — to the
same identity as the task's target definition; a link stamped with an `id=` that is not its
page's identity fails. An *unstamped* link passes: a correct pinned address is what both arms can
write, while the identity hash is something only the links arm can obtain (`resolve` returns
it; the baseline has no way to compute a SHA-256 of normalized source). Whether the link was
stamped is recorded (`stamped`) for the report, not required. The plan's "correct `# cttp:`
stamp" is read this way on purpose; the report should say so.

**Impact questions** (`im-*`, five): the checkout is one of the three repositories at a pinned
commit; the prompt names a definition and asks for every definition whose code uses it, written
to `impact.txt` as `path#name` lines (a method as `Class.method`, not its class; modules that
merely import it excluded). There is no command to run. Targets were chosen with `who` answers
of 2 to 12 definitions spread over several files, verified against `grep` by hand, and — for the
two src-layout repositories — not referenced from their tests (see the caveat).

| task | target | definitions |
|---|---|---:|
| `im-color-default-click` | click `globals.py#resolve_color_default` | 5 in 3 files |
| `im-nested-chain-click` | click `core.py#_check_nested_chain` | 2 |
| `im-obj-setattr-attrs` | attrs `_make.py#_OBJ_SETATTR` (a constant) | 12 in 2 files |
| `im-set-cell-size-rich` | rich `cells.py#set_cell_size` | 6 in 4 files, two of them tests |
| `im-pick-bool-rich` | rich `_pick.py#pick_bool` | 5 in 4 files, one a test |

**The who check** (`graders.check_who`): the answer must equal, as a set, the *innermost
definitions* among `cttp who <target>`'s backlinks on the run's index: a class whose member is
also listed is dropped (the class page's references include everything its methods reference —
`who` lists `Text` and `Text.wrap` for one use in `wrap`), and file pages (a module that
imports the target) are left out. Pass is exact equality; `missing` and `extra` are recorded so
the report can show how close a failing answer was. The reference `impact.txt` files were
generated from `who` the same way; `--check-graders` confirms they still match.

Two caveats the report must carry. `who` is the derived reference graph of the Python extractor:
a use inside a nested function is attributed to the enclosing addressable definition, a name
reached through a re-export (`attr.fields`) is not a backlink of the definition, and **in a
`src/` layout the tests' absolute imports (`from click._compat import …`) do not resolve to
`src/click/`**, so tests are not backlinks of anything in click or attrs. The five targets were
chosen so that none of this changes the answer (grep agrees with `who` for each), but the
grader is `who`, so an agent that reads the code differently from the extractor loses even when
it is arguably right. And the prompt's format rules are what make exact grading possible; both
arms get the same rules.

`smoke-pyrepo` is P8-T1's smoke task: pyrepo's `left` returns `x - 1`; the visible test says
`top(3) == 9`; the hidden test checks each link of the chain.

**Acceptance** (`--check-graders`, or `uv run pytest -m slow tests/test_bench_agent.py`): every
grader fails the unmodified checkout and passes the reference solution. For the in-repository
tasks that is the commit's own tests against its parent and against itself, under this venv's
Python 3.12 and pytest; for the others, the hidden tests plus the link or who check.

## The smoke run (2026-09-05, Opus 5)

| arm | status | tokens | turns | wall |
|---|---|---:|---:|---:|
| links (first design, no `Read`) | fail — found the bug, could not edit | 471,255 | 41 | 205 s |
| baseline | pass | 29,428 | 5 | 12 s |
| links (with `Read`) | pass | 36,787 | 6 | 14 s |

With `Read` available the links arm read the two files and never touched a cttp tool: on a
two-file repository there is nothing to search for. The tools earn their keep, if they do, on
the P8-T2 repositories. The rerun (`--redo`) overwrote the first links run's record; its numbers
survive in this table and in `PROGRESS.md`.

## The first runs of the task set (2026-09-05, Opus 5)

One task per family, both arms, one run each — the shape check before P8-T3, not data:

| task | arm | status | tokens | turns | wall | tools |
|---|---|---|---:|---:|---:|---|
| `ir-table-highlight-rich` | links | pass | 77,293 | 8 | 23 s | 2 denied `grep`, `search`, 2 `resolve`, `Edit` |
| `ir-table-highlight-rich` | baseline | pass | 33,105 | 5 | 9 s | 2 `grep`, `Edit` |
| `xr-filesize-rich` | links | pass (stamped) | 71,059 | 9 | 42 s | denied `cat`, `search`, `closure`, 2 `Read`, `Write` |
| `xr-filesize-rich` | baseline | pass (unstamped) | 45,520 | 6 | 26 s | `ls`+`cat`, `Read` of `../deps/rich/rich/filesize.py`, `Edit` |
| `im-pick-bool-rich` | links | pass (exact) | 189,171 | 18 | 83 s | denied `grep`, 2 `who`, `search`, 9 `Read`, `Write` |
| `im-pick-bool-rich` | baseline | pass (exact) | 67,732 | 10 | 32 s | `grep -rn`, 4 `Read`, `grep ^class`, `Write` |

Every run passed, and the links arm consumed **more** context in every family (1.6×, 2.3×,
2.8×). What the streams show: the links arm reaches for `grep`/`cat` first in every run and
learns it has the cttp tools from the denial — one wasted turn each, and a second one when it
tries a reader again later; `who`'s first call used a bare path (`rich/_pick.py#pick_bool`) and
had to be repeated with a full address after a `search`; the `closure` and `resolve` results are
whole JSON objects (3.5–4.6k characters each, source plus metadata) where the baseline's `grep -A
40` returned the lines it needed; and on the impact task the links arm did not trust `who` — it
read every listed definition (nine `Read`s) before writing the same five lines the baseline
found with one `grep` and four `Read`s. On the plus side the links arm wrote full stamps
(`id=sha256:<64 hex>`) from `resolve`, which the baseline cannot. The baseline also knew where
`decimal` lives in rich without searching — the model knows these libraries, which a search
benchmark on well-known code cannot avoid; say so in the report. The five-hour window went from
about 0.25 to 0.41 over these six runs (~480k tokens), which puts ninety runs at roughly two
windows.

**The lever was pulled before the full run** (2026-09-05): both arms are now told what their
search is, one sentence each (`SEARCH_NOTES`; see §The arms). These six runs therefore predate
the arms as they now stand and are **not** part of P8-T3's ninety — they are kept as the record
of why the note exists. The other reading stands whatever the prompt says: a tool's JSON payload
is counted as context whatever the agent needed out of it, and the report says so.

## Caveats for the report

Both arms run inside Claude Code's harness, so the comparison is between tool sets inside Claude
Code, under its system prompt and its agent loop — not between "with cttp" and "without" in the
abstract. The token counts are what Claude Code reports; cache reads are counted as context
consumed because the model attended to them, whatever they cost.

Each arm is told in one sentence what its search is, so neither discovers its tool set from a
permission denial; the two notes are in `SEARCH_NOTES` and in every record's `system_prompt`.
That is a deliberate intervention on both arms, and the report names it.
