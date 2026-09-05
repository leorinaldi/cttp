# The agent benchmark

**What this measures:** whether an agent that can *follow links* — the cttp tools over an index —
finds and reuses code more cheaply than the same agent searching with a shell. It is a comparison
of **tool sets inside Claude Code**, on fifteen tasks over three real Python libraries.

**The short answer:** it depends on the question. Copying a definition out of another repository
is cheaper with cttp and gets cheaper the more the definition drags with it. Fixing a bug in the
repository you are already in costs about twice as much and succeeds slightly more often. Asking
what uses a definition is where cttp should have won and does not — not because the question is
wrong for it, but because `who` returns quietly incomplete answers on `src/`-layout projects and
the agent burns twenty to forty times the context failing to confirm them.

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

Ninety runs, 2026-09-05, Opus 5, Claude Code 2.1.261. Generated table and every record:
`bench/agent/results/2026-09-05-full/`.

**The answer depends entirely on the question being asked.** There is no single ratio worth
quoting; the three families point in three directions.

| family | cttp passes | shell passes | median tokens, cttp | median tokens, shell | ratio |
|---|---|---|---:|---:|---:|
| cross-repo reuse | 15/15 | 15/15 | 59,573 | 65,963 | **0.90** |
| in-repo bug fixes | 14/15 | 12/15 | 151,772 | 76,428 | 1.99 |
| impact questions | 14/15 | 12/15 strict, **15/15 folded** | 1,021,954 | 62,765 | 16.28 |
| all ninety | 43/45 | 39/45 | 112,634 | 65,963 | 1.71 |

**Cross-repository reuse is where links win outright** — cheaper *and* level on correctness. The
margin grows with the size of the thing being copied, because `closure` returns a multi-file
answer in one call where the shell has to find and read each piece:

| task | closure | cttp | shell | ratio |
|---|---|---:|---:|---:|
| `xr-join-options-click` | 2 definitions, 2 files | 56,265 | 146,224 | **0.38** |
| `xr-textwrap-click` | 5 definitions, 2 files | 119,865 | 186,774 | **0.64** |
| `xr-escape-rich` | 4 definitions | 59,573 | 65,963 | 0.90 |
| `xr-to-bool-attrs` | 1 definition | 63,275 | 57,770 | 1.10 |
| `xr-filesize-rich` | 2 definitions | 56,878 | 48,255 | 1.18 |

A one-definition copy is a wash. A five-definition closure across two files costs the shell 1.6x
what it costs cttp, and the two-file `join_options` closure costs it 2.6x. And every cttp run
wrote a full `id=` stamp; no shell run wrote one, because the identity is a SHA-256 of normalized
source that only `resolve` can hand over.

**In-repository fixes cost twice as much and pass more often.** 14/15 against 12/15, at 1.99x.
Both arms failed `ir-choice-metavar-click`, where the trap is that a `Choice` may hold integers —
the shell arm went 0/3, cttp 2/3. This is the most credible family in the set, because the grader
is the upstream project's own test file and owes nothing to cttp.

**Impact questions are where it goes wrong, and the cause is one defect.** The 16.28x is not a
property of asking "what uses this":

| repository | layout | median tokens, cttp | turns | ratio |
|---|---|---:|---:|---:|
| click (`im-color-default`) | `src/` | 2,829,962 | 57 | 39.95 |
| click (`im-nested-chain`) | `src/` | 1,583,572 | 48 | 31.06 |
| attrs (`im-obj-setattr`) | `src/` | 1,526,474 | 59 | 19.42 |
| rich (`im-pick-bool`) | flat | 115,944 | 15 | 1.93 |
| rich (`im-set-cell-size`) | flat | 89,833 | 11 | 1.43 |

The split is exactly the repository layout. Where `who` gives a complete answer — rich, whose
package sits at the top level — the cost is 1.4–1.9x and the agent stops after a dozen turns.
Where `who` silently omits results — click and attrs, whose packages sit under `src/`, so the
extractor cannot resolve a test's import into them — the agent senses the gap, has no `grep` with
which to close it, and reads the repository by hand at twenty to forty times the cost. One run
never finished. See the section below.

So: **cttp costs about twice as much where its answers are complete, and catastrophically more
where they are quietly incomplete.** Fixing src-layout resolution in `extract/python.py` is the
single highest-value change this benchmark points to.

### Run health and stamps

| arm | runs | scored | not scored | permission denials |
|---|---:|---:|---|---:|
| cttp tools | 45 | 44 | 1 error (turn cap) | 43 |
| shell | 45 | 45 | none | 76 |

The shell arm's denials are its own pipelines; the cttp arm's are attempts to reach a shell reader
it does not have. Stamps: 15 of 15 cttp runs wrote one, 0 of 15 shell runs.

---

## Why the impact questions cost so much

This was visible in the first two runs of the sweep — `im-color-default-click`, links arm, at
1,895,253 and 5,043,073 tokens, the second hitting the 40-turn cap. Both had the right answer
from their **first** tool call: `who` returns exactly the five definitions the reference
answer lists, and `git grep` over the clone agrees that no test uses the target.

What the agent spent its remaining eighty tool calls on was trying to establish that *nothing
else* used it — and it could not. `cttp who` omits a `src/` layout's tests by construction, and
the links arm has no `grep` to check with. So it searched, folded and read across the repository,
63 `Read` calls in the second run, until it ran out of turns.

**The tool answered the question; the agent could not tell that the answer was complete.** That
is a property of the interface, not of the harness, and it is the most useful thing this
benchmark has produced. A `who` that resolved src-layout imports would likely end the thrash. It
is a logged follow-up, and fixing it mid-sweep would make the runs incomparable, so it is
reported here rather than fixed.

Two consequences for reading the table. **Cost grows with the square of the turn count** —
every turn re-reads the whole conversation from cache, so 6 turns cost 37k tokens, 18 cost 189k
and 41 cost 5M. One non-converging run outweighs fifty short ones, so the table reports medians
and keeps per-task rows. And a run that hits the turn cap is an `error`: it enters neither the
pass rate nor the median, and shows up only under run health. A family whose links arm carries
errors should be read as *did not converge*, not as a gap in the data.

---

## What the number does not mean

Seven things a reader should hold against any ratio in the table.

1. **Both arms run inside Claude Code.** The comparison is between tool sets under Claude Code's
   system prompt and agent loop, not between "an agent with cttp" and "an agent without" in
   general. A different harness could move the numbers either way.

2. **A tool's whole JSON payload is counted as context.** `resolve` and `closure` return complete
   objects — source plus metadata, 3.5–4.6k characters each — where the baseline's `grep -A 40`
   returns only the lines it asked for. The links arm pays for everything the tool knows, whether
   or not it needed it. That is a real cost of the interface as built, not a measurement error,
   and on the tasks that converge it is the largest single contributor to the ratio.

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

6. **The impact grader's naming convention quietly favours the links arm.** The prompt asks for
   "the innermost definition containing the use". `cttp who` cannot address a nested function —
   nested definitions are outside the address grammar — so it attributes such a use to the
   *enclosing addressable* definition, and the reference answer is generated from `who`. An agent
   reading the raw source instead names the nested function, which is the more literal reading of
   the prompt and is marked wrong. The links arm sees `who`'s output and inherits the grader's
   convention for free; the baseline has to guess it. This is not hypothetical: every baseline
   impact failure recorded so far is of exactly this form, entries like `Class.method.nested`
   where the reference wanted `Class.method`, and under a folded comparison the baseline's impact
   score is clean. The report therefore prints **both** — see *Impact grading: strict and
   folded*, where folding walks an unmatched answer up its dotted name until it meets the
   expected set. The sweep was already running under the strict rule, so the grader was not
   changed mid-measurement; the folded column is the one to believe.

7. **The impact grader is the extractor's notion of a use.** `cttp who` is the derived reference
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
