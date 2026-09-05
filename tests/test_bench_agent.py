"""The benchmark harness (plan P8-T1), without the subscription: tasks load, the smoke grader
tells the bug from the fix, the arms are what the README says, the stream parser reads a
recorded run, and a replay reproduces the recorded numbers exactly."""

import json
from pathlib import Path

import pytest

from bench.agent import graders, harness, report

RESULTS = Path(__file__).resolve().parents[1] / "bench" / "agent" / "results"
SMOKE_RECORDS = sorted(RESULTS.glob("*/smoke-pyrepo/*/1.json"))


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
