"""The benchmark harness (plan P8-T1) and task set (P8-T2), without the subscription: tasks
load, the smoke grader tells the bug from the fix, the arms are what the README says, the stream
parser reads a recorded run, a replay reproduces the recorded numbers exactly; overlays come from
commits, dependencies are cloned beside the checkout, the link check and the who check grade
what the plan says they grade. The acceptance over the real repositories is the `slow` test at
the end (skipped until `bash bench/agent/fetch.sh` has run)."""

import json
import subprocess
from pathlib import Path

import pytest

from bench.agent import graders, harness, report
from bench.agent.graders import LinkCheck, Overlay, Repo, Task, WhoCheck

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
RESULTS = ROOT / "bench" / "agent" / "results"
SMOKE_RECORDS = sorted(RESULTS.glob("*/*/*/1.json"))  # every committed first run, not only smoke
REAL_TASKS = [t for t in graders.load_tasks() if t.name != "smoke-pyrepo"]


def make_task(tmp_path: Path, repo: Repo, **fields) -> Task:
    """A task built in code, no task.toml."""
    defaults = dict(
        name="t",
        family="in-repo",
        summary="",
        prompt="p",
        repo=repo,
        deps=(),
        setup=None,
        grade=None,
        solution=None,
        command=None,
        timeout=60,
        link=None,
        who=None,
        directory=tmp_path,
    )
    defaults.update(fields)
    return Task(**defaults)


def git_repo_from(tmp_path: Path, fixture: Path) -> tuple[Path, str, str]:
    """A git repository of a pyrepo-shaped directory with two commits: the base, and a "fix"
    that changes `lib.py` (`deep` doubles, then triples) and adds a test for it. Returns the
    path, the base sha and the fix sha."""
    src = tmp_path / "src"
    graders._copy_tree(fixture, src)
    git = [*graders.GIT, "-C", str(src)]
    subprocess.run(["git", "-C", str(src), "init", "-q", "-b", "main"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "base"], check=True)
    base = subprocess.run(
        ["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    lib = src / "lib.py"
    lib.write_text(lib.read_text().replace("return x * 2", "return x * 3"))
    test = "from lib import deep\n\n\ndef test_deep():\n    assert deep(2) == 6\n"
    (src / "test_deep.py").write_text(test)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "fix"], check=True)
    fix = subprocess.run(
        ["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    return src, base, fix


def test_the_smoke_task_loads_and_its_grader_tells_the_bug_from_the_fix(tmp_path):
    tasks = graders.load_tasks(["smoke-pyrepo"])
    assert [t.name for t in tasks] == ["smoke-pyrepo"]
    task = tasks[0]
    assert task.family == "in-repo" and task.locator == "github.com/leorinaldi/pyrepo"
    assert task.command == "python -m pytest -q test_lib.py"
    result = graders.check_grader(task, tmp_path / "g")
    assert result["ok"], result
    assert result["unmodified"] == {"passed": False, "returncode": 1}
    assert result["solution"] == {"passed": True, "returncode": 0}


def test_the_checkout_is_a_clone_of_a_bare_remote_the_config_maps_to_the_locator(tmp_path):
    task = graders.load_tasks(["smoke-pyrepo"])[0]
    checkout = graders.prepare_checkout(task, tmp_path / "w")
    assert (checkout.path / "lib.py").read_text().count("return x - 1") == 1
    assert (checkout.path / "test_lib.py").exists() and (checkout.remote / "HEAD").exists()
    config = graders.write_config(tmp_path, checkout, ["/nowhere/registry"])
    text = config.read_text()
    assert f'"{task.locator}" = "{checkout.remote}"' in text
    assert "'/nowhere/registry'" in text
    graded = graders.grade(task, checkout)
    assert not graded.passed and "test_each_link_of_the_chain" in graded.output
    assert graded.diff == ""  # nothing changed, __pycache__ not reported


def test_unknown_task_is_an_error():
    with pytest.raises(graders.TaskError, match="unknown task"):
        graders.load_tasks(["no-such-task"])


def test_the_arms_differ_only_in_how_code_is_found():
    links, base = harness.ARMS["links"], harness.ARMS["baseline"]
    command = "python -m pytest -q"
    assert set(links.tools) == set(base.tools) == {"Read", "Edit", "Write", "Bash"}
    assert links.mcp and not base.mcp
    assert links.allowed(command) == [
        *harness.MCP_TOOL_NAMES, "Read", "Edit", "Write", f"Bash({command})", f"Bash({command} *)",
    ]  # fmt: skip
    assert base.allowed(command) == links.allowed(command)[len(harness.MCP_TOOL_NAMES) :]
    denied = links.disallowed()
    assert "Bash(cat *)" in denied and "Bash(grep *)" in denied and "Bash(ls)" in denied
    assert base.disallowed() == []


def test_the_command_line_isolates_the_run(tmp_path):
    task = graders.load_tasks(["smoke-pyrepo"])[0]
    settings = harness.Settings("opus", 40, 1200, [])
    argv = harness.claude_argv(task, harness.ARMS["links"], settings, tmp_path / "mcp.json")
    text = " ".join(argv)
    for flag in (
        "--output-format stream-json",
        "--permission-mode dontAsk",
        "--permission-prompts none",
        "--setting-sources ",
        "--no-session-persistence",
        "--strict-mcp-config",
        "--mcp-config",
        "--max-turns 40",
        "--model opus",
    ):
        assert flag in text, flag
    assert "--bare" not in argv
    assert argv[argv.index("--append-system-prompt") + 1] == harness.APPEND_SYSTEM_PROMPT
    with pytest.raises(harness.HarnessError):
        harness.claude_argv(task, harness.ARMS["links"], settings, None)
    base = harness.claude_argv(task, harness.ARMS["baseline"], settings, None)
    assert "--mcp-config" not in base and "--disallowedTools" not in base


def test_the_stream_parser_reads_init_tool_calls_denials_and_the_result():
    usage = {"input_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 10}

    def assistant(tool_id, name, inp, output):
        block = {"type": "tool_use", "id": tool_id, "name": name, "input": inp}
        message = {"id": "m1", "usage": {**usage, "output_tokens": output}, "content": [block]}
        return {"type": "assistant", "parent_tool_use_id": None, "message": message}

    def tool_result(tool_id, content, error=False):
        return {
            "type": "tool_result",
            "tool_use_id": tool_id,
            "content": content,
            "is_error": error,
        }

    init = {"type": "system", "subtype": "init", "model": "m", "tools": ["Read"]}
    init["mcp_servers"] = [{"name": "cttp", "status": "connected"}]
    events = [
        init,
        {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "resetsAt": 1}},
        assistant("t1", "Bash", {"command": "cat x"}, 1),
        assistant("t2", "Read", {"file_path": "x"}, 7),  # the same message id: one response
        {"type": "system", "subtype": "permission_denied", "tool_use_id": "t1"},
        {"type": "user", "message": {"content": [
            tool_result("t1", "denied", error=True),
            tool_result("t2", [{"type": "text", "text": "abc"}]),
        ]}},
        "not json",
        {"type": "result", "subtype": "success", "is_error": False, "num_turns": 2,
         "usage": {**usage, "output_tokens": 50}, "total_cost_usd": 0.1, "result": "done",
         "permission_denials": [{"tool_name": "Bash"}]},
    ]  # fmt: skip
    stream = [e if isinstance(e, str) else json.dumps(e) for e in events]
    parsed = harness.parse_stream(stream)
    assert parsed["init"]["model"] == "m" and parsed["rate_limit"]["status"] == "allowed"
    assert parsed["requests"] == 1  # one message id, two events
    assert parsed["stream_usage"] == {
        "input_tokens": 5,
        "cache_read_input_tokens": 100,
        "cache_creation_input_tokens": 10,
    }
    calls = parsed["tool_calls"]
    assert [c["name"] for c in calls] == ["Bash", "Read"]
    assert calls[0]["denied"] and calls[0]["error"] and calls[0]["result_chars"] == 6
    assert not calls[1]["denied"] and calls[1]["result_chars"] == 3
    assert harness.tokens_of(parsed["result"]["usage"]) == 165
    assert not harness.is_limited(parsed, {"returncode": 0, "stderr": ""})
    parsed["rate_limit"] = {"status": "rejected"}
    assert harness.is_limited(parsed, {"returncode": 0, "stderr": ""})


@pytest.mark.skipif(not SMOKE_RECORDS, reason="no recorded smoke run under bench/agent/results")
@pytest.mark.parametrize("record_path", SMOKE_RECORDS, ids=lambda p: p.parent.name)
def test_a_replay_reproduces_the_recorded_numbers(record_path, tmp_path):
    """The dry run: the same record from the recorded stream, no subscription used."""
    recorded = json.loads(record_path.read_text(encoding="utf-8"))
    replayed = harness.replay(record_path, tmp_path / "out")
    assert harness.numbers(replayed) == harness.numbers(recorded)
    assert replayed["replayed_from"] == str(record_path)
    written = json.loads((tmp_path / "out" / record_path.name).read_text())
    assert harness.numbers(written) == harness.numbers(recorded)
    assert (tmp_path / "out" / recorded["stream_file"]).exists()
    # what the record says about isolation and the arm
    init_tools = set(recorded["tools_available"])
    if recorded["arm"] == "links":
        assert recorded["cttp_connected"] and set(harness.MCP_TOOL_NAMES) <= init_tools
    else:
        assert not recorded["cttp_connected"] and not any(t.startswith("mcp__") for t in init_tools)  # noqa: E501
    assert "--setting-sources" in recorded["argv"] and "--bare" not in recorded["argv"]


@pytest.mark.skipif(not SMOKE_RECORDS, reason="no recorded smoke run under bench/agent/results")
def test_the_report_renders_one_row_per_task_with_medians_and_a_ratio(tmp_path):
    date_dir = SMOKE_RECORDS[-1].parents[2]
    records = report.load_records(date_dir)
    assert {r["arm"] for r in records} >= {"links", "baseline"}
    table = report.summarize(records)
    assert "smoke-pyrepo" in table and table["smoke-pyrepo"]["_family"] == "in-repo"
    text = report.render(table, "t")
    assert "| smoke-pyrepo | in-repo |" in text and "**in-repo total**" in text
    assert "smoke-pyrepo/links/1.json" in text
    assert report.main([str(date_dir), "--no-write"]) == 0
    assert not (tmp_path / "report.md").exists()


# --- P8-T2: the task set ------------------------------------------------------------------------


def test_fifteen_real_tasks_load_five_per_family():
    by_family = {f: [t for t in REAL_TASKS if t.family == f] for f in graders.FAMILIES}
    assert {f: len(ts) for f, ts in by_family.items()} == {
        "in-repo": 5,
        "cross-repo": 5,
        "impact": 5,
    }
    for t in REAL_TASKS:
        assert t.prompt and t.summary, t.name
    for t in by_family["in-repo"]:
        # a real merged commit: the checkout is its parent, the grader its tests, the solution
        # its source
        assert t.repo.rev and t.grade and t.grade.commit and t.solution and t.solution.commit
        assert t.grade.commit == t.solution.commit and t.grade.commit != t.repo.rev
        assert all(p.startswith("tests/") for p in t.grade.paths), t.name
        assert t.command and t.command.startswith("python -m pytest")
    for t in by_family["cross-repo"]:
        assert len(t.deps) == 1 and t.deps[0].rev and t.link and t.command
        assert t.link.target.startswith(f"{t.deps[0].locator}@{t.deps[0].rev}/"), t.name
        assert (t.directory / "consumer" / "app.py").is_file()
        assert t.solution and (t.solution.directory / "app.py").is_file()
    for t in by_family["impact"]:
        assert t.who and t.command is None and not t.deps
        assert (t.solution.directory / "impact.txt").read_text().strip(), t.name
    repos = {t.repo.locator.split("/")[-1] for t in by_family["in-repo"]}
    assert repos == {"click", "attrs", "rich"}


def test_an_impact_task_has_no_bash_rule_and_the_links_arm_still_denies_the_readers():
    task = next(t for t in REAL_TASKS if t.family == "impact")
    assert harness.ARMS["links"].allowed(None) == [*harness.MCP_TOOL_NAMES, "Read", "Edit", "Write"]
    settings = harness.Settings("opus", 40, 1200, [])
    argv = harness.claude_argv(task, harness.ARMS["baseline"], settings, None)
    assert not any(a.startswith("Bash(") for a in argv)
    assert "Bash" in argv  # the tool itself stays: the baseline searches with it
    assert task.needs_index


def test_overlays_from_a_commit_grade_the_parent_against_the_fix(tmp_path):
    # the smoke task's setup: pyrepo's lib.py without its third-party import, plus a test
    src, base, fix = git_repo_from(tmp_path, graders.TASKS / "smoke-pyrepo" / "setup")
    repo = Repo("pyrepo", src, "github.com/leorinaldi/pyrepo", base, None)
    task = make_task(
        tmp_path,
        repo,
        grade=Overlay(None, fix, ("test_deep.py",)),
        solution=Overlay(None, fix, ("lib.py",)),
        command="python -m pytest -q test_deep.py",
    )
    result = graders.check_grader(task, tmp_path / "g")
    assert result["ok"], result
    assert result["unmodified"]["passed"] is False and result["solution"]["passed"] is True
    checkout = graders.prepare_checkout(task, tmp_path / "w")
    assert checkout.base_sha == base  # the agent starts from the parent
    assert not (checkout.path / "test_deep.py").exists()  # the hidden test is not committed


def test_a_task_whose_repository_is_not_fetched_says_so(tmp_path):
    repo = Repo("gone", tmp_path / "nowhere", "github.com/x/y", None, None)
    task = make_task(tmp_path, repo, command="true")
    assert not task.fetched
    result = graders.check_grader(task, tmp_path / "g")
    assert result["ok"] is False and "fetch.sh" in result["why"]
    with pytest.raises(graders.TaskError, match="fetch.sh"):
        graders.prepare_checkout(task, tmp_path / "w")


def test_dependencies_are_cloned_beside_the_checkout_and_mapped_in_the_config(tmp_path):
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    (consumer / "app.py").write_text('"""consumer"""\n')
    thermo = Repo("thermo", FIXTURES / "thermo", "github.com/leorinaldi/thermo", None, None)
    task = make_task(
        tmp_path,
        Repo("c", consumer, "github.com/leorinaldi/consumer", None, None),
        family="cross-repo",
        deps=(thermo,),
        command="true",
    )
    checkout = graders.prepare_checkout(task, tmp_path / "w")
    assert (checkout.path / "app.py").is_file()
    assert [d.name for d in checkout.deps] == ["thermo"]
    dep = checkout.deps[0]
    assert dep.path == tmp_path / "w" / "deps" / "thermo"  # ../deps/thermo from the checkout
    assert (dep.path / "src" / "thermo" / "decode.py").is_file() and (dep.remote / "HEAD").exists()
    config = graders.write_config(tmp_path, checkout, ["/nowhere"]).read_text()
    assert f'"github.com/leorinaldi/thermo" = "{dep.remote}"' in config
    assert f'"github.com/leorinaldi/consumer" = "{checkout.remote}"' in config


def test_the_link_check_resolves_the_agents_link_through_the_dependency(tmp_path):
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    (consumer / "app.py").write_text('"""consumer"""\n')
    thermo = Repo("thermo", FIXTURES / "thermo", "github.com/leorinaldi/thermo", None, None)
    target = "github.com/leorinaldi/thermo@main/src/thermo/decode.py#reg_to_millicelsius"
    task = make_task(
        tmp_path,
        Repo("c", consumer, "github.com/leorinaldi/consumer", None, None),
        family="cross-repo",
        deps=(thermo,),
        link=LinkCheck("app.py", target),
    )
    checkout, env = graders.prepare_run(task, tmp_path / "run")
    app = checkout.path / "app.py"
    source = (FIXTURES / "thermo" / "src" / "thermo" / "decode.py").read_text()
    body = source[source.index("def reg_to_millicelsius") :].split("\n\n\n")[0]

    def write(link_line: str) -> dict:
        app.write_text(f'"""consumer"""\n\n\n{link_line}\n{body}\n')
        return graders.check_link(task.link, checkout, env)

    # an unstamped link to the right definition: a pass, recorded as not stamped
    result = write(f"# cttp: {target}")
    assert result["passed"] and not result["stamped"], result
    assert result["links"][0]["matches_target"] and result["links"][0]["resolves"]
    # the right identity as a stamp
    identity = result["expected_identity"]
    result = write(f"# cttp: {target} id=sha256:{identity[:12]}")
    assert result["passed"] and result["stamped"] and result["links"][0]["stamp_ok"]
    # a wrong stamp fails, a link to another definition fails, no link fails
    result = write(f"# cttp: {target} id=sha256:{'0' * 12}")
    assert not result["passed"] and "wrong identity" in result["why"]
    result = write("# cttp: github.com/leorinaldi/thermo@main/src/thermo/decode.py#decode_cached")
    assert not result["passed"] and "no link resolves to the target" in result["why"]
    app.write_text(f'"""consumer"""\n\n\n{body}\n')
    assert not graders.check_link(task.link, checkout, env)["passed"]
    # the whole grade: the command passes, the link decides
    task_with_command = make_task(
        tmp_path,
        task.repo,
        family="cross-repo",
        deps=(thermo,),
        link=task.link,
        command="true",
    )
    g = graders.grade(task_with_command, checkout, graders.venv_env(env))
    assert not g.passed and g.checks["link"]["why"] == "no link resolves to the target"


def test_innermost_keeps_methods_over_their_class_and_drops_file_pages():
    def bl(path, symbol):
        return {"source": {"path": path, "symbol": symbol}, "relation": "ref", "origin": "derived"}

    backlinks = [
        bl("a.py", None),  # the module imports it: not a definition
        bl("a.py", "Klass"),  # the class page references what its methods reference
        bl("a.py", "Klass.method"),
        bl("a.py", "Klass.other"),
        bl("b.py", "Only"),  # a class with no member listed: the use is in its body
        bl("b.py", "func"),
    ]
    assert graders.innermost(backlinks) == {
        "a.py#Klass.method",
        "a.py#Klass.other",
        "b.py#Only",
        "b.py#func",
    }
    assert graders.parse_answer("# callers\n- a.py#f\n\n* `b.py#G.h`\n  c.py#i  \n") == {
        "a.py#f",
        "b.py#G.h",
        "c.py#i",
    }


def test_the_who_check_compares_the_answer_with_the_index(tmp_path):
    thermo = Repo("thermo", FIXTURES / "thermo", "github.com/leorinaldi/thermo", None, None)
    task = make_task(
        tmp_path,
        thermo,
        family="impact",
        who=WhoCheck("impact.txt", "src/thermo/decode.py", "reg_to_millicelsius"),
    )
    checkout, env = graders.prepare_run(task, tmp_path / "run")  # crawls the checkout
    assert (tmp_path / "run" / "index.db").exists()
    result = graders.check_who(task.who, checkout, env)
    assert not result["passed"] and "does not exist" in result["why"]
    expected = set(result["expected"])
    assert "src/thermo/lm75.py#LM75.read_temp" in expected  # the method, not the class
    assert "src/thermo/lm75.py#LM75" not in expected
    assert not any(e.endswith(".py") for e in expected)  # no file pages
    assert "src/thermo/decode.py#decode_cached" in expected
    answer = checkout.path / "impact.txt"
    answer.write_text("\n".join(sorted(expected)) + "\n")
    result = graders.check_who(task.who, checkout, env)
    assert result["passed"] and result["missing"] == [] and result["extra"] == []
    answer.write_text("\n".join(sorted(expected)[1:]) + "\nsrc/thermo/decode.py#nothing\n")
    result = graders.check_who(task.who, checkout, env)
    assert not result["passed"]
    assert result["missing"] == [sorted(expected)[0]]
    assert result["extra"] == ["src/thermo/decode.py#nothing"]
    g = graders.grade(task, checkout, graders.venv_env(env))
    assert not g.passed and g.checks["who"]["why"] == "1 missing, 1 extra"


@pytest.mark.slow
@pytest.mark.skipif(
    not all(t.fetched for t in REAL_TASKS),
    reason="the task repositories are not fetched (bash bench/agent/fetch.sh)",
)
@pytest.mark.parametrize("task", REAL_TASKS, ids=lambda t: t.name)
def test_every_real_grader_fails_the_checkout_and_passes_the_solution(task, tmp_path):
    """The P8-T2 acceptance, one task at a time (what `--check-graders` runs)."""
    result = graders.check_grader(task, tmp_path / "g")
    assert result["ok"], result
