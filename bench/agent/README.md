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

1. **Checkout.** The task's source directory is committed as `main`, cloned bare as the "remote",
   and cloned again as the working copy the agent edits. The setup overlay (the bug, the visible
   tests) is committed on top. The working copy's `origin` is the bare repository, which a
   per-run `cttp.toml` maps to the task's locator through `[remotes]` — exactly how the test
   suite serves its fixtures, so `cttp index add <checkout>` and `resolve <locator>` work with no
   network.
2. **Index** (links arm only). `cttp index add` + `cttp index crawl` into the run's own
   `index.db`; the MCP server is started with `CTTP_CONFIG`, `CTTP_INDEX` and `CTTP_HOME` pointing
   at the run's files.
3. **Claude Code**, from the checkout, with the arm's tools, `--permission-mode dontAsk`,
   `--permission-prompts none`, the same `--model`, `--max-turns` and `--append-system-prompt`.
   stdin is `/dev/null`; a run past `--timeout` gets SIGINT, then SIGKILL.
4. **Grade.** The grade overlay (the hidden tests) is copied over the checkout and the task's
   command runs; exit 0 is a pass. The agent's diff against the base commit is kept.
5. **Record** `results/<date>/<task>/<arm>/<run>.json`, with the raw stream beside it as
   `<run>.stream.jsonl` (and stderr as `<run>.stream.stderr`).

## The arms

| | `links` | `baseline` |
|---|---|---|
| cttp MCP tools (`resolve`, `who`, `closure`, `search`, `dups`, `fold`) | yes | no |
| `Read`, `Edit`, `Write` | yes | yes |
| `Bash` | the task's test command only | the test command, plus the read-only commands `dontAsk` mode auto-approves (`grep`, `find`, `ls`, `cat`, `git log`, …) |
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
uv run python -m bench.agent.harness --list                 # the tasks
uv run python -m bench.agent.harness --check-graders        # each grader fails the unmodified checkout, passes the solution
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

A task is `tasks/<name>/task.toml` with a prompt, the source repository (a directory of this
repository — or, for P8-T2, a git repository and a commit) and its locator, and up to three
overlays: `setup/` (committed before the run), `grade/` (copied over after it, never seen by the
agent) and `solution/` (the reference fix, for `--check-graders`). `grade.command` is both the
grader and the one shell command the agent may run.

`smoke-pyrepo` is P8-T1's smoke task: pyrepo's `left` returns `x - 1`; the visible test says
`top(3) == 9`; the hidden test checks each link of the chain. P8-T2 adds the fifteen real tasks.

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

## Caveats for the report

Both arms run inside Claude Code's harness, so the comparison is between tool sets inside Claude
Code, under its system prompt and its agent loop — not between "with cttp" and "without" in the
abstract. The token counts are what Claude Code reports; cache reads are counted as context
consumed because the model attended to them, whatever they cost.
