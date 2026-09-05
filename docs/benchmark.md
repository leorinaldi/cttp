# The agent benchmark

**What this measures:** whether an agent that can *follow links* — the cttp tools over an index —
finds and reuses code more cheaply than the same agent searching with a shell. It is a comparison
of **tool sets inside Claude Code**, on fifteen tasks over three real Python libraries.

It is not a claim about cttp against "no cttp" in the abstract, and it is not a model evaluation.
Read [§What the number does not mean](#what-the-number-does-not-mean) before quoting anything here.

The method lives in `bench/agent/README.md`; this document is the result and its honest reading.
The raw records are under `bench/agent/results/<date>/`, one JSON file per run with the full
event stream beside it, and `report.md` in each date directory is generated from them by
`python -m bench.agent.report`.

---

## Method

**Two arms, one model, one harness.** Each run is Claude Code driven headless
(`claude -p … --output-format stream-json`) under a subscription login, from a fresh checkout in
a scratch directory, isolated from `~/.claude` (`--setting-sources ""`, `--strict-mcp-config`,
`--no-session-persistence`). The arms differ in **how the agent finds code**:

| | `links` | `baseline` |
|---|---|---|
| cttp MCP tools (`resolve`, `who`, `closure`, `search`, `dups`, `fold`) | yes | no |
| `Read`, `Edit`, `Write` | yes | yes |
| shell readers (`grep`, `cat`, `find`, `ls`, `sed`, `git`, …) | denied by rule | allowed |
| `Bash` | the task's test command only | the test command and the read-only commands |

`Read` is in both arms because Claude Code's `Edit` and `Write` refuse a file the session has not
read; an arm without it can find a bug and not fix it. So the arms compare *finding*, not editing.
This Claude Code has no `Grep` or `Glob` tool, so the baseline's search genuinely is `grep` and
`find` through `Bash`.

**Both arms are told what their search is** — one sentence each in the appended system prompt
(`SEARCH_NOTES` in `harness.py`), naming the six cttp tools for `links` and the shell's readers
for `baseline`. This was added after the first runs, in which the links arm reached for `grep` in
every single run and learned of its own tools from the permission denial: that measures the deny
list, not the tools. The intervention is symmetric, and every record carries the exact prompt it
was given as `system_prompt`. The shared instruction also asks for the test command unpiped,
because the links deny list catches `| tail -5` and the baseline never hits it — a second pure
artifact of the deny list.

**Fifteen tasks over three libraries** — `pallets/click` (12.7k lines, BSD-3),
`python-attrs/attrs` (6.4k, MIT) and `Textualize/rich` (26.6k, MIT) — in three families of five:

- **In-repository fixes** (`ir-*`): a real merged bug-fix commit. The checkout is the commit's
  parent, the prompt is the bug report with no file named, and the hidden grader is the commit's
  own test file. The fix is small; finding the place is the work.
- **Cross-repository reuse** (`xr-*`): a small consumer project must reuse one definition from a
  library checked out beside it, marking the copy with `# cttp:` links. Hidden tests exercise the
  behaviour a from-scratch rewrite gets wrong (ANSI widths, backslash doubling, prefix ordering)
  and assert the library is not imported.
- **Impact questions** (`im-*`): given a definition, list every definition whose code uses it.
  Graded exactly, as a set, against `cttp who` on the run's index.

Three runs per task per arm; ninety runs. A run is `pass` only if its hidden tests pass and every
check the task asks for passes. `limited`, `timeout` and `error` runs are counted in *run health*
and never enter a median or a pass rate.

**What is measured** is the tokens of context the run consumed — input, output, cache reads and
cache writes, as Claude Code reports them. Cache reads count: the model attended to them, whatever
they cost in dollars. Turns and wall time are recorded beside them.

---

## Results

<!-- TABLE -->
_The ninety runs are in progress; this section is filled from
`bench/agent/results/<date>/report.md` when they finish._

---

## What the number does not mean

Six things a reader should hold against any ratio in the table.

1. **Both arms run inside Claude Code.** The comparison is between tool sets under Claude Code's
   system prompt and agent loop, not between "an agent with cttp" and "an agent without" in
   general. A different harness could move the numbers either way.

2. **A tool's whole JSON payload is counted as context.** `resolve` and `closure` return complete
   objects — source plus metadata, 3.5–4.6k characters each — where the baseline's `grep -A 40`
   returns only the lines it asked for. The links arm pays for everything the tool knows, whether
   or not it needed it. That is a real cost of the interface as built, not a measurement error,
   and it is the single largest contributor to the ratio.

3. **The model already knows these libraries.** click, attrs and rich are widely-read public code
   with a training cutoff behind them. In the first runs the baseline went straight to the right
   file in rich without searching at all. Any search benchmark over well-known open source has
   this problem; it flatters the arm that needs no search, which is the baseline.

4. **The prompts name the search.** Both arms are told what their tools are, which removes a
   discovery artifact but is still an intervention on behaviour. Runs before that change are kept
   separately under `results/2026-09-05-first-runs/` and are not part of the ninety.

5. **The link check accepts an unstamped link.** A stamp's `id=` is a SHA-256 of normalized
   source, which only the links arm can obtain (`resolve` returns it); requiring one would grade
   tool availability rather than the work. So a correct pinned address passes in either arm, and
   how often each arm wrote a full stamp is *reported* rather than graded — see the stamps table.

6. **The impact grader is the extractor's notion of a use.** `cttp who` is the derived reference
   graph of `extract/python.py`: a use inside a nested function is attributed to the enclosing
   addressable definition, a name reached through a re-export is not a backlink, and in a `src/`
   layout the tests' absolute imports do not resolve into `src/`, so click's and attrs' tests are
   backlinks of nothing. The five targets were picked so that `grep` agrees with `who` on each,
   but the grader is still `who`: an agent that reads the code differently loses even where it is
   arguably right.

Two further asymmetries worth naming. The links arm **cannot run `cttp add` or `check`** — `Bash`
is the test command only — so a cross-repository task is copy-by-hand in both arms; giving both
arms the `cttp` CLI would change what is being measured. And on impact tasks the links arm has no
`Bash` at all, so an attempt at the shell costs it a turn; those denials are in *run health*.

---

## Reproducing

```bash
bash bench/agent/fetch.sh                       # once: the three repositories (~150 MB, gitignored)
uv run python -m bench.agent.harness --check-graders          # every task's reference solution
uv run python -m bench.agent.harness --runs 3 --wait-for-reset
uv run python -m bench.agent.report bench/agent/results/<date>
```

A run that already exists is skipped, so the command resumes after a usage limit or a Ctrl-C.
`--replay <run.json>` re-derives a record from its recorded stream and uses no subscription.
