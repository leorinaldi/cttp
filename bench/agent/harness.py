"""The agent benchmark harness (plan P8-T1).

One driver runs Claude Code headless — `claude -p <prompt> --output-format stream-json` as a
subprocess, under the subscription login of whoever runs it (never `--bare`, which needs an API
key) — with two **arms** that differ only in the tools the agent has:

- `links`: the cttp MCP server (`resolve`, `who`, `closure`, `search`, `dups`, `fold`) attached
  with `--mcp-config` and `--strict-mcp-config`, plus `Read`, `Write`, `Edit` and `Bash`
  restricted to the task's test command. The shell's readers (`cat`, `grep`, `find`, `ls`, …)
  are denied, since `dontAsk` mode would otherwise wave the read-only ones through.
- `baseline`: the same `Read`, `Write`, `Edit` and `Bash`, no MCP server, and the read-only
  shell commands that `dontAsk` allows — what ordinary Claude Code has. (This Claude Code version
  has no `Grep` or `Glob` tool; searching *is* `grep` and `find` through Bash.)

`Read` is in both arms because `Edit` and `Write` refuse a file the session has not read; see
`ARMS`. The arms differ in how the agent finds code, not in whether it can read what it edits.

The appended system prompt is shared but for one sentence per arm naming that arm's search — the
cttp tools for `links`, the shell for `baseline` (`SEARCH_NOTES`). Without it the links arm spent
a turn per run discovering its tool set from a permission denial, which measures the deny list
and not the tools; the note is symmetric so neither arm has to find its search by trial. Each
run records the exact text it was given as `system_prompt`.

Same model, same `--max-turns`, `--permission-mode dontAsk` with
`--permission-prompts none`, run from a fresh checkout under a scratch directory with
`--setting-sources ""` and `--no-session-persistence`, so nothing in `~/.claude` (hooks, plugins,
memory, the user-scope cttp MCP server) reaches either arm.

Per run the harness records the result object's `usage` (input, output, cache read, cache
write, and the per-model breakdown), their sum as the tokens of context consumed,
`total_cost_usd` as the estimate it is, `num_turns`, wall time, `permission_denials`, every tool
call, the `system/init` message, the last rate-limit event, and pass/fail from the task's grader.
Results go to `bench/agent/results/<date>/<task>/<arm>/<run>.json`, the raw stream kept beside
each as `<run>.stream.jsonl`. A usage-limit failure is recorded as `limited`, not as a fail, and
the driver waits for the window to reset (`--wait-for-reset`) or stops and says so; running the
same date again picks up where it stopped. `--replay <run.json>` re-derives a record from its
recorded stream without touching the subscription.

    uv run python -m bench.agent.harness --list
    uv run python -m bench.agent.harness --check-graders
    uv run python -m bench.agent.harness --task smoke-pyrepo --runs 1
    uv run python -m bench.agent.harness --replay bench/agent/results/<date>/<task>/<arm>/1.json
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import gzip
import json
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from bench.agent.graders import (
    Checkout,
    Task,
    TaskError,
    check_grader,
    cttp_env,
    grade,
    load_tasks,
    prepare_checkout,
    prepare_index,
    venv_env,
    write_config,
)

RESULTS = Path(__file__).resolve().parent / "results"
CTTP = Path(sys.executable).parent / "cttp"
MCP_TOOLS = ["resolve", "who", "closure", "search", "dups", "fold"]
MCP_TOOL_NAMES = [f"mcp__cttp__{t}" for t in MCP_TOOLS]

# Shell commands that read files or list directories. `dontAsk` mode auto-approves the read-only
# command set, so the links arm denies these explicitly; the baseline keeps them — they are its
# search tools.
SHELL_READERS = [
    "cat", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "rg", "ag", "find", "ls",
    "tree", "sed", "awk", "wc", "stat", "file", "diff", "git", "od", "xxd", "strings", "nl",
    "cut", "sort", "uniq", "tac", "rev", "column", "paste", "fold", "pr", "fmt", "look",
    "locate", "which", "type", "printf", "echo",
]  # fmt: skip

APPEND_SYSTEM_PROMPT = (
    "You are working in a checkout of a repository; the working directory is its root. "
    "Nobody can answer questions, so do not ask any: complete the task with the tools you have, "
    "run the test command named in the task once when you are done (if it names one), exactly as "
    "the task writes it and without piping it into anything else, and then "
    "stop with a short summary of what you did."
)

# Each arm is told what its search is. Without this the links arm learned of its tools from a
# denial — it reached for `grep` first in every one of the P8-T2 first runs, spending a turn to
# discover its own tool set, which measures the deny list rather than the tools. The note is
# given to *both* arms so the treatment is symmetric: neither has to find its search by trial.
# Stated in `docs/benchmark.md`; the exact text of each run is recorded as `system_prompt`.
SEARCH_NOTES = {
    "links": (
        "Your search is the cttp MCP tools, not the shell: `search` finds a definition by name "
        "or docstring, `resolve` returns one definition's text by address, `who` lists what "
        "links to a definition, `closure` what a definition needs to run, `fold` reads a file "
        "as its links, `dups` finds copies. The shell's file readers (grep, cat, find, ls, sed) "
        "are denied; `Read` reads a file whose path you already know."
    ),
    "baseline": (
        "Your search is the shell through Bash: grep, find, ls, cat, sed and the other usual "
        "readers; `Read` reads a file whose path you already know."
    ),
}


def system_prompt_for(arm: Arm) -> str:
    """The shared instruction plus the arm's search note (see `SEARCH_NOTES`)."""
    return f"{APPEND_SYSTEM_PROMPT} {SEARCH_NOTES[arm.name]}"


@dataclass(frozen=True)
class Arm:
    name: str
    tools: tuple[str, ...]  # `--tools`: the built-in tools available at all
    mcp: bool  # attach the cttp MCP server
    deny_shell_readers: bool

    def allowed(self, command: str | None) -> list[str]:
        """The permission rules: the built-in tools, the test command (when the task has one —
        an impact task has nothing to run), and the MCP tools for the links arm."""
        rules = ["Edit", "Write"]
        if command:
            rules += [f"Bash({command})", f"Bash({command} *)"]
        if "Read" in self.tools:
            rules.insert(0, "Read")
        if self.mcp:
            rules = MCP_TOOL_NAMES + rules
        return rules

    def disallowed(self) -> list[str]:
        if not self.deny_shell_readers:
            return []
        rules: list[str] = []
        for cmd in SHELL_READERS:
            rules += [f"Bash({cmd})", f"Bash({cmd} *)"]
        return rules


ARMS = {
    # `Read` is in both arms: `Edit` and `Write` refuse a file the session has not read, so an
    # arm without `Read` cannot change a file (the P8-T1 smoke run proved it: the agent found
    # the bug through the cttp tools and could not apply the fix). The arms therefore differ in
    # how the agent *finds* code — the cttp tools against the shell's search — not in whether
    # it can read the file it edits.
    "links": Arm("links", ("Read", "Edit", "Write", "Bash"), mcp=True, deny_shell_readers=True),
    "baseline": Arm(
        "baseline", ("Read", "Edit", "Write", "Bash"), mcp=False, deny_shell_readers=False
    ),
}


class HarnessError(Exception):
    pass


# --- one run -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Settings:
    model: str
    max_turns: int
    timeout: int  # seconds per run
    registries: list[str]


def effective_registries() -> list[str]:
    """The registries of whoever runs the benchmark, so names resolve as they do for them."""
    proc = subprocess.run(
        [str(CTTP), "config", "--json"], capture_output=True, text=True, env=venv_env()
    )
    if proc.returncode != 0:
        raise HarnessError(f"cttp config failed: {proc.stderr.strip()}")
    return list(json.loads(proc.stdout)["registries"])


def write_mcp_config(work: Path, env: dict[str, str]) -> Path:
    path = work / "mcp.json"
    path.write_text(
        json.dumps(
            {"mcpServers": {"cttp": {"command": str(CTTP), "args": ["mcp"], "env": env}}},
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def claude_argv(task: Task, arm: Arm, settings: Settings, mcp_config: Path | None) -> list[str]:
    argv = [
        "claude", "-p", task.prompt,
        "--output-format", "stream-json", "--verbose",
        "--model", settings.model,
        "--max-turns", str(settings.max_turns),
        "--permission-mode", "dontAsk",
        "--permission-prompts", "none",
        "--setting-sources", "",
        "--no-session-persistence",
        "--strict-mcp-config",
        "--append-system-prompt", system_prompt_for(arm),
        "--tools", *arm.tools,
        "--allowedTools", *arm.allowed(task.test_command),
    ]  # fmt: skip
    disallowed = arm.disallowed()
    if disallowed:
        argv += ["--disallowedTools", *disallowed]
    if arm.mcp:
        if mcp_config is None:
            raise HarnessError("the links arm needs an MCP config")
        argv += ["--mcp-config", str(mcp_config)]
    return argv


def run_claude(
    argv: list[str], cwd: Path, env: dict[str, str], timeout: int, stream_path: Path
) -> dict[str, object]:
    """Run Claude Code, streaming stdout to `stream_path`. Returns exit code, wall time, stderr
    and whether the run timed out (SIGINT, then SIGKILL after a grace period)."""
    started = time.monotonic()
    timed_out = False
    with open(stream_path, "wb") as out, open(stream_path.with_suffix(".stderr"), "wb") as err:
        proc = subprocess.Popen(
            argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    wall = time.monotonic() - started
    stderr = stream_path.with_suffix(".stderr").read_text(encoding="utf-8", errors="replace")
    return {
        "returncode": proc.returncode,
        "wall_seconds": round(wall, 3),
        "timed_out": timed_out,
        "stderr": stderr[-4000:],
    }


# --- the stream --------------------------------------------------------------------------------


def parse_stream(lines: list[str]) -> dict[str, object]:
    """What the harness keeps from a `stream-json` run: the init message, every tool call with
    its outcome, the per-request usage summed, the last rate-limit event, and the result."""
    init: dict | None = None
    result: dict | None = None
    rate_limit: dict | None = None
    calls: list[dict] = []
    by_id: dict[str, dict] = {}
    requests = 0
    seen_messages: set[str | None] = set()
    summed = {
        "input_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            init = event
        elif kind == "system" and event.get("subtype") == "permission_denied":
            call = by_id.get(event.get("tool_use_id", ""))
            if call is not None:
                call["denied"] = True
        elif kind == "rate_limit_event":
            rate_limit = event.get("rate_limit_info")
        elif kind == "assistant":
            message = event.get("message", {})
            # One API response arrives as one assistant event per content block, each carrying
            # the response's usage: count each message id once. The stream's output count is
            # the first chunk's, not the response's, so only the input side is summed here — a
            # cross-check of the result object's `usage`, which is authoritative.
            if (
                event.get("parent_tool_use_id") is None
                and isinstance(message.get("usage"), dict)
                and message.get("id") not in seen_messages
            ):
                seen_messages.add(message.get("id"))
                requests += 1
                for key in summed:
                    summed[key] += int(message["usage"].get(key) or 0)
            for block in message.get("content", []):
                if block.get("type") == "tool_use":
                    call = {
                        "id": block.get("id"),
                        "name": block.get("name"),
                        "input": block.get("input"),
                        "denied": False,
                        "error": False,
                        "result_chars": 0,
                    }
                    calls.append(call)
                    if call["id"]:
                        by_id[call["id"]] = call
        elif kind == "user":
            for block in event.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    call = by_id.get(block.get("tool_use_id", ""))
                    if call is None:
                        continue
                    content = block.get("content")
                    if isinstance(content, list):
                        text = "".join(c.get("text", "") for c in content if isinstance(c, dict))
                    else:
                        text = content if isinstance(content, str) else json.dumps(content)
                    call["result_chars"] = len(text)
                    call["error"] = bool(block.get("is_error"))
        elif kind == "result":
            result = event
    return {
        "init": init,
        "result": result,
        "rate_limit": rate_limit,
        "tool_calls": calls,
        "requests": requests,
        "stream_usage": summed,
    }


def tokens_of(usage: dict | None) -> int | None:
    if not usage:
        return None
    return sum(
        int(usage.get(k) or 0)
        for k in (
            "input_tokens",
            "output_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
        )
    )


def is_limited(parsed: dict[str, object], run: dict[str, object]) -> bool:
    result = parsed["result"]
    rate = parsed["rate_limit"] or {}
    if isinstance(rate, dict) and rate.get("status") == "rejected":
        return True
    if isinstance(result, dict) and result.get("is_error"):
        text = str(result.get("result", "")).lower()
        if result.get("api_error_status") == 429 or "limit" in text and "usage" in text:
            return True
        if "rate limit" in text or "rate_limit" in text:
            return True
    stderr = str(run.get("stderr", "")).lower()
    return "usage limit" in stderr or "rate limit" in stderr


def build_record(
    *,
    task: Task,
    arm: Arm,
    run_number: int,
    settings: Settings,
    argv: list[str],
    parsed: dict[str, object],
    run: dict[str, object],
    graded: dict[str, object],
    checkout: Checkout | None,
    index: dict[str, object] | None,
    stream_file: str,
    replayed_from: str | None = None,
) -> dict[str, object]:
    result = parsed["result"] if isinstance(parsed["result"], dict) else None
    init = parsed["init"] if isinstance(parsed["init"], dict) else None
    usage = result.get("usage") if result else None
    if run.get("timed_out"):
        status = "timeout"
    elif is_limited(parsed, run):
        status = "limited"
    elif result is None or run.get("returncode") not in (0, None):
        status = "error"
    elif graded.get("passed") is True:
        status = "pass"
    elif graded.get("passed") is False:
        status = "fail"
    else:
        status = "error"
    tool_calls = parsed["tool_calls"] if isinstance(parsed["tool_calls"], list) else []
    counts: dict[str, int] = {}
    for call in tool_calls:
        counts[call["name"]] = counts.get(call["name"], 0) + 1
    mcp_servers = init.get("mcp_servers", []) if init else []
    return {
        "schema": 1,
        "task": task.name,
        "family": task.family,
        "arm": arm.name,
        "run": run_number,
        "system_prompt": system_prompt_for(arm),
        "status": status,
        "passed": graded.get("passed"),
        "model": settings.model,
        "model_used": init.get("model") if init else None,
        "claude_code_version": init.get("claude_code_version") if init else None,
        "max_turns": settings.max_turns,
        "tokens": tokens_of(usage),
        "usage": usage,
        "model_usage": result.get("modelUsage") if result else None,
        "stream_usage": parsed["stream_usage"],
        "requests": parsed["requests"],
        "total_cost_usd": result.get("total_cost_usd") if result else None,
        "num_turns": result.get("num_turns") if result else None,
        "duration_ms": result.get("duration_ms") if result else None,
        "duration_api_ms": result.get("duration_api_ms") if result else None,
        "wall_seconds": run.get("wall_seconds"),
        "returncode": run.get("returncode"),
        "timed_out": run.get("timed_out", False),
        "subtype": result.get("subtype") if result else None,
        "is_error": result.get("is_error") if result else None,
        "stop_reason": result.get("stop_reason") if result else None,
        "terminal_reason": result.get("terminal_reason") if result else None,
        "permission_denials": result.get("permission_denials") if result else None,
        "tool_counts": counts,
        "tool_calls": tool_calls,
        "mcp_servers": mcp_servers,
        "cttp_connected": any(
            s.get("name") == "cttp" and s.get("status") == "connected" for s in mcp_servers
        ),
        "tools_available": init.get("tools") if init else None,
        "rate_limit": parsed["rate_limit"],
        "session_id": result.get("session_id") if result else None,
        "final_text": (result.get("result") if result else None),
        "grade": graded,
        "base_sha": checkout.base_sha if checkout else None,
        "index": index,
        "argv": argv,
        "stream_file": stream_file,
        "recorded_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "replayed_from": replayed_from,
        "stderr": run.get("stderr", ""),
    }


def run_once(
    task: Task, arm: Arm, run_number: int, settings: Settings, out_dir: Path, keep: bool
) -> dict[str, object]:
    """One run: checkout, config, index (links arm), Claude Code, grade, record."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stream_path = out_dir / f"{run_number}.stream.jsonl"
    work = Path(tempfile.mkdtemp(prefix=f"cttp-bench-{task.name}-{arm.name}-"))
    try:
        checkout = prepare_checkout(task, work / "w")
        config = write_config(work, checkout, settings.registries)
        env = cttp_env(work, config)
        index = None
        mcp_config = None
        if arm.mcp or task.needs_index:
            # the links arm's tools read the index; so does an impact task's grader, whichever
            # arm ran — the index is built before the agent starts, from the committed checkout
            index = prepare_index(checkout, env)
        if arm.mcp:
            mcp_config = write_mcp_config(work, env)
        argv = claude_argv(task, arm, settings, mcp_config)
        run = run_claude(argv, checkout.path, venv_env(env), settings.timeout, stream_path)
        lines = stream_path.read_text(encoding="utf-8", errors="replace").splitlines()
        parsed = parse_stream(lines)
        g = grade(task, checkout, venv_env(env))
        graded = {
            "passed": g.passed,
            "returncode": g.returncode,
            "timed_out": g.timed_out,
            "output": g.output[-4000:],
            "diff": g.diff[-20000:],
            "command": task.command,
            "checks": g.checks,
        }
        record = build_record(
            task=task,
            arm=arm,
            run_number=run_number,
            settings=settings,
            argv=argv,
            parsed=parsed,
            run=run,
            graded=graded,
            checkout=checkout,
            index=index,
            stream_file=stream_path.name,
        )
    finally:
        if keep:
            print(f"  kept {work}", file=sys.stderr)
        else:
            shutil.rmtree(work, ignore_errors=True)
    (out_dir / f"{run_number}.json").write_text(
        json.dumps(record, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    return record


def resolve_stream(stream_path: Path) -> Path:
    """The recorded stream as it is on disk: `<name>.jsonl`, or the `.gz` beside it. Ninety runs
    of real tasks are tens of megabytes of stream (one impact run reached 1 MB), so the committed
    streams are gzipped — `gzip -9` takes the JSONL down by about an order of magnitude. The
    records themselves stay plain JSON: they are what anyone reads."""
    if stream_path.is_file():
        return stream_path
    packed = stream_path.with_suffix(stream_path.suffix + ".gz")
    if packed.is_file():
        return packed
    raise HarnessError(f"{stream_path} is missing (no .gz either); nothing to replay")


def read_stream(stream_path: Path) -> list[str]:
    """The stream's lines, whether it is stored plain or gzipped."""
    path = resolve_stream(stream_path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def replay(record_path: Path, out_dir: Path | None) -> dict[str, object]:
    """Re-derive a record from its recorded stream: the same numbers, no subscription used. The
    grade is taken from the record (the checkout is gone)."""
    old = json.loads(record_path.read_text(encoding="utf-8"))
    stream_path = resolve_stream(record_path.parent / old["stream_file"])
    lines = read_stream(stream_path)
    parsed = parse_stream(lines)
    tasks = {t.name: t for t in load_tasks()}
    task = tasks.get(old["task"])
    if task is None:
        raise HarnessError(f"task {old['task']!r} no longer exists")
    arm = ARMS[old["arm"]]
    settings = Settings(old["model"], old["max_turns"], 0, [])
    run = {
        "returncode": old["returncode"],
        "wall_seconds": old["wall_seconds"],
        "timed_out": old["timed_out"],
        "stderr": old.get("stderr", ""),
    }
    record = build_record(
        task=task,
        arm=arm,
        run_number=old["run"],
        settings=settings,
        argv=old["argv"],
        parsed=parsed,
        run=run,
        graded=old["grade"],
        checkout=None,
        index=old.get("index"),
        stream_file=old["stream_file"],
        replayed_from=str(record_path),
    )
    record["base_sha"] = old.get("base_sha")
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        if (out_dir / stream_path.name).resolve() != stream_path.resolve():
            shutil.copy2(stream_path, out_dir / stream_path.name)
        (out_dir / record_path.name).write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
    return record


NUMBERS = (
    "tokens", "usage", "model_usage", "stream_usage", "requests", "total_cost_usd",
    "num_turns", "duration_ms", "duration_api_ms", "wall_seconds", "tool_counts", "status",
    "passed", "permission_denials", "cttp_connected",
)  # fmt: skip


def numbers(record: dict[str, object]) -> dict[str, object]:
    """The fields a replay must reproduce exactly."""
    return {k: record.get(k) for k in NUMBERS}


# --- the driver --------------------------------------------------------------------------------


def wait_for_reset(rate_limit: dict | None) -> None:
    reset = None
    if isinstance(rate_limit, dict):
        reset = rate_limit.get("resetsAt")
    if not reset:
        raise HarnessError("limited, and the stream carried no reset time; try again later")
    seconds = max(0, int(reset) - int(time.time())) + 60
    when = dt.datetime.fromtimestamp(int(reset)).isoformat(timespec="minutes")
    print(f"usage limit reached; waiting until {when} ({seconds // 60} min)", file=sys.stderr)
    time.sleep(seconds)


def weekly_utilization(rate_limit: dict | None) -> float | None:
    """The seven-day window's utilization as the last rate-limit event reported it, or None."""
    if not isinstance(rate_limit, dict):
        return None
    windows = rate_limit.get("unifiedWindows")
    if not isinstance(windows, dict):
        return None
    week = windows.get("seven_day")
    if not isinstance(week, dict):
        return None
    used = week.get("utilization")
    return float(used) if isinstance(used, (int, float)) else None


def say(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


def summarize(records: list[dict[str, object]]) -> str:
    lines = [
        f"{'task':<24} {'arm':<9} {'run':>3} {'status':<8} {'tokens':>9} {'turns':>5} "
        f"{'wall s':>7} {'cost $':>7}"
    ]
    for r in records:
        lines.append(
            f"{r['task']:<24} {r['arm']:<9} {r['run']:>3} {r['status']:<8} "
            f"{(r['tokens'] if r['tokens'] is not None else '-'):>9} "
            f"{(r['num_turns'] if r['num_turns'] is not None else '-'):>5} "
            f"{(r['wall_seconds'] if r['wall_seconds'] is not None else '-'):>7} "
            f"{(round(r['total_cost_usd'], 3) if r['total_cost_usd'] is not None else '-'):>7}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bench.agent.harness", description=__doc__.split("\n\n")[0]
    )
    add = parser.add_argument
    add("--list", action="store_true", help="list the tasks and stop")
    add(
        "--check-graders",
        action="store_true",
        help="every grader fails the unmodified checkout and passes the reference solution",
    )
    add("--task", action="append", help="run this task (repeatable; default all)")
    add("--arm", action="append", choices=list(ARMS), help="run this arm (default both)")
    add("--runs", type=int, default=1, help="runs per task and arm (default 1)")
    add("--model", default="opus", help="`--model` for both arms (default opus)")
    add("--max-turns", type=int, default=40)
    add("--timeout", type=int, default=1200, help="seconds per run (default 1200)")
    add("--date", default=dt.date.today().isoformat(), help="results directory (default today)")
    add("--redo", action="store_true", help="run again even where a result exists")
    add("--keep", action="store_true", help="keep the scratch checkouts")
    add(
        "--wait-for-reset",
        action="store_true",
        help="on a usage limit, sleep until the window resets and continue",
    )
    add("--replay", type=Path, help="re-derive a record from its stream; write under --out")
    add("--out", type=Path, help="where --replay writes")
    add(
        "--jobs",
        type=int,
        default=1,
        metavar="N",
        help=(
            "run N tasks at a time (default 1). A run is mostly waiting on the model — the "
            "links arm sits in 4-minute loops on the impact tasks — and every run has its own "
            "checkout, cache and index, so tasks parallelise cleanly"
        ),
    )
    add(
        "--stop-above",
        type=float,
        default=0.85,
        metavar="FRACTION",
        help=(
            "stop when the seven-day window passes this utilization (default 0.85; 0 disables). "
            "One turn-capped run can cost 1.9M tokens, so a long sweep is guarded rather than "
            "trusted to an estimate"
        ),
    )
    args = parser.parse_args(argv)

    try:
        tasks = load_tasks(args.task)
    except TaskError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.list:
        for t in tasks:
            note = "" if t.fetched else "  (source not on disk: bash bench/agent/fetch.sh)"
            print(f"{t.name:<28} {t.family:<12} {t.summary}{note}")
        print(f"{len(tasks)} task(s)")
        return 0
    if args.replay:
        record = replay(args.replay, args.out)
        print(json.dumps(numbers(record), indent=2))
        return 0
    if args.check_graders:
        ok = True
        with tempfile.TemporaryDirectory(prefix="cttp-bench-graders-") as tmp:
            for t in tasks:
                r = check_grader(t, Path(tmp) / t.name)
                ok &= bool(r["ok"])
                print(f"{t.name:<24} {'ok' if r['ok'] else 'FAIL'}  {r['why']}")
                if not r["ok"] and r.get("output"):
                    print(r["output"])
        return 0 if ok else 1
    if not tasks:
        print("no tasks under bench/agent/tasks/", file=sys.stderr)
        return 2

    if shutil.which("claude") is None:
        print("error: `claude` is not on PATH", file=sys.stderr)
        return 2
    unfetched = [t.name for t in tasks if not t.fetched]
    if unfetched:
        print(
            f"error: source repositories not on disk for {', '.join(unfetched)}; "
            "run `bash bench/agent/fetch.sh` first",
            file=sys.stderr,
        )
        return 2
    settings = Settings(args.model, args.max_turns, args.timeout, effective_registries())
    arms = [ARMS[a] for a in (args.arm or list(ARMS))]
    date_dir = RESULTS / args.date
    records: list[dict[str, object]] = []
    lock = threading.Lock()
    stop = threading.Event()
    exit_code = 0

    def keep(record: dict[str, object]) -> None:
        with lock:
            records.append(record)

    def halt(code: int, message: str) -> None:
        """First worker to hit a limit wins; the rest finish their current run and stop."""
        nonlocal exit_code
        with lock:
            if not stop.is_set():
                exit_code = code
                stop.set()
                say(message)

    def one_task(t: Task) -> None:
        """A whole task, its arms and runs in order. Tasks are what `--jobs` runs in parallel:
        a run is mostly waiting on the model, and every run already has its own checkout,
        cache and index, so nothing is shared but the subscription."""
        for arm in arms:
            for n in range(1, args.runs + 1):
                if stop.is_set():
                    return
                out_dir = date_dir / t.name / arm.name
                existing = out_dir / f"{n}.json"
                if existing.is_file() and not args.redo:
                    old = json.loads(existing.read_text(encoding="utf-8"))
                    if old.get("status") != "limited":
                        say(f"{t.name} {arm.name} #{n}: exists ({old['status']}), skipped")
                        keep(old)
                        continue
                while not stop.is_set():
                    say(f"{t.name} {arm.name} #{n}: running…")
                    record = run_once(t, arm, n, settings, out_dir, args.keep)
                    say(
                        f"{t.name} {arm.name} #{n}: {record['status']}, {record['tokens']} "
                        f"tokens, {record['num_turns']} turns, {record['wall_seconds']} s"
                    )
                    if record["status"] != "limited":
                        keep(record)
                        used = weekly_utilization(record.get("rate_limit"))
                        if args.stop_above and used is not None and used > args.stop_above:
                            halt(
                                4,
                                f"stopping: the seven-day window is at {used:.0%}, above the "
                                f"--stop-above limit of {args.stop_above:.0%}. Runs already "
                                "recorded are kept; the same command resumes where it stopped.",
                            )
                        break
                    keep(record)
                    if not args.wait_for_reset:
                        halt(
                            3,
                            "stopped at a usage limit; run the same command again after the "
                            "window resets (or pass --wait-for-reset)",
                        )
                        return
                    wait_for_reset(record.get("rate_limit"))  # type: ignore[arg-type]

    jobs = max(1, args.jobs)
    if jobs == 1:
        for t in tasks:
            if stop.is_set():
                break
            one_task(t)
    else:
        say(f"running {len(tasks)} task(s), {jobs} at a time")
        with cf.ThreadPoolExecutor(max_workers=jobs) as pool:
            for future in cf.as_completed([pool.submit(one_task, t) for t in tasks]):
                future.result()
    with lock:
        records.sort(key=lambda r: (str(r["task"]), str(r["arm"]), int(r["run"])))  # type: ignore[arg-type]
    print(summarize(records))
    return exit_code


def median(values: list[int | float]) -> float | None:
    return statistics.median(values) if values else None


if __name__ == "__main__":
    sys.exit(main())
