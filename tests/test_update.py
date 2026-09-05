"""`cttp update` (plan P3-T3): follow pinned links forward, show the diff, rewrite on confirmation;
a `cttp-from:` link is shown its upstream diff and left alone."""

import json

from conftest import commit_to_remote
from typer.testing import CliRunner

from cttp.cli import NOT_CONFIRMED, app
from cttp.expand import check_file, expand_file, update_file

runner = CliRunner()
PYREPO = "github.com/leorinaldi/pyrepo"
LIB = f"{PYREPO}@v1/lib.py"
FIXTURE = "tests/fixtures/pyrepo/lib.py"


def advance(tmp_path) -> str:
    """Edit `deep`, `left` and `hyp` in the fixture repository and push; returns the new SHA."""
    text = open(FIXTURE, encoding="utf-8").read()
    text = text.replace("return x * 2", "return x * 3")
    text = text.replace("return x + 1", "return x + 10")
    text = text.replace("return math.hypot(a, b)", "return math.hypot(a, b) + 0.0")
    return commit_to_remote(tmp_path, "pyrepo", {"lib.py": text}, "edit deep, left and hyp")


def three_links(registry, tmp_path):
    """A file with `deep` (track=latest), `left`, and a fork of `hyp` as a `cttp-from:` link."""
    f = tmp_path / "prog.py"
    f.write_text(
        f"# cttp: {LIB}#deep track=latest\n\n# cttp: {LIB}#left\n\n# cttp: {LIB}#hyp\n\n"
        "print(deep(1), left(1), hyp(3, 4))\n"
    )
    expand_file(f, registry)
    f.write_text(f.read_text().replace("return math.hypot(a, b)", "return round(math.hypot(a, b))"))
    check_file(f, registry, fix=True)  # hyp drifted → cttp-from
    assert [(r.relation, r.status) for r in check_file(f, registry)] == [
        ("is", "ok"),
        ("is", "ok"),
        ("from", "ok"),
    ]
    return f


def test_acceptance_track_latest_updates_one_link_then_all_updates_the_rest(registry, tmp_path):
    f = three_links(registry, tmp_path)
    before = f.read_text()
    assert [r.status for r in update_file(f, registry)] == ["unchanged"], "nothing moved yet"
    head = advance(tmp_path)
    # default selection: the track=latest link only; the diff is shown; only it is rewritten
    reports = update_file(f, registry)
    assert [(r.address.split("#")[1], r.status) for r in reports] == [("deep", "updated")]
    (deep,) = reports
    assert deep.extra["to"] == f"{PYREPO}@{head[:12]}/lib.py#deep"
    assert deep.extra["rule"] == "same-path"
    assert "-    return x * 2\n+    return x * 3" in deep.extra["diff"]
    text = f.read_text()
    assert "return x * 3" in text and "return x + 1\n" in text, "left is still at v1"
    assert text.split("\n")[0].startswith(f"# cttp: {PYREPO}@{head[:12]}/lib.py#deep id=sha256:")
    assert "track=latest" in text.split("\n")[0], "the user's field survives"
    assert [r.status for r in check_file(f, registry)] == ["ok", "ok", "ok"]
    # --all: the rest; the from link is shown upstream and not rewritten
    reports = update_file(f, registry, all_=True)
    assert [(r.relation, r.status) for r in reports] == [
        ("is", "unchanged"),
        ("is", "updated"),
        ("from", "upstream"),
    ]
    assert "return x + 10" in f.read_text()
    assert "round(math.hypot(a, b))" in f.read_text(), "the fork is the user's"
    assert "+    return math.hypot(a, b) + 0.0" in reports[2].extra["diff"]
    assert [r.status for r in check_file(f, registry)] == ["ok", "ok", "ok"]
    assert before != f.read_text()


def test_acceptance_update_on_a_from_link_prints_the_upstream_diff_and_changes_nothing(
    registry, tmp_path
):
    f = three_links(registry, tmp_path)
    advance(tmp_path)
    before = f.read_bytes()
    res = runner.invoke(app, ["update", str(f), f"{LIB}#hyp"])
    assert res.exit_code == 0, res.output
    assert "upstream" in res.output and "+    return math.hypot(a, b) + 0.0" in res.output
    assert f.read_bytes() == before, "byte-identical"
    j = json.loads(runner.invoke(app, ["update", str(f), f"{LIB}#hyp", "--json"]).stdout)
    (link,) = j["links"][str(f)]
    assert link["status"] == "upstream" and link["relation"] == "from" and link["diff"]


def test_update_asks_and_exit_2_without_a_terminal(registry, tmp_path, monkeypatch):
    f = three_links(registry, tmp_path)
    advance(tmp_path)
    before = f.read_bytes()
    res = runner.invoke(app, ["update", str(f)])
    assert res.exit_code == NOT_CONFIRMED, res.output
    assert "not-confirmed" in res.output and "pass --yes" in res.output
    assert "-    return x * 2" in res.output and f.read_bytes() == before
    # a person answering `n` at the prompt: nothing changes either
    monkeypatch.setattr("cttp.cli._interactive", lambda: True)
    res = runner.invoke(app, ["update", str(f)], input="n\n")
    assert res.exit_code == NOT_CONFIRMED and f.read_bytes() == before
    res = runner.invoke(app, ["update", str(f)], input="y\n")
    assert res.exit_code == 0, res.output
    assert "return x * 3" in f.read_text()
    assert runner.invoke(app, ["update", str(f), "--yes"]).exit_code == 0


def test_update_to_a_named_rev_and_a_project_that_tracks_latest(registry, tmp_path):
    f = three_links(registry, tmp_path)
    head = advance(tmp_path)
    # --to <rev>: the same page at that rev, for every selected link
    reports = update_file(f, registry, [f"{LIB}#left"], to=head[:12])
    assert [r.status for r in reports] == ["updated"] and reports[0].extra["rule"] == "to"
    assert f"@{head[:12]}/lib.py#left" in f.read_text()
    # a project cttp.toml with track = "latest" selects every link
    (tmp_path / "cttp.toml").write_text('track = "latest"\n')
    reports = update_file(f, registry)
    assert [r.status for r in reports] == ["updated", "unchanged", "upstream"]


def test_update_reports_drift_and_unexpanded_links_without_touching_them(registry, tmp_path):
    f = tmp_path / "p.py"
    f.write_text(f"# cttp: {LIB}#deep\n\n# cttp: {LIB}#left\n")
    expand_file(f, registry)
    f.write_text(f.read_text().replace("return x * 2", "return x * 22") + "# cttp: hello-world\n")
    advance(tmp_path)
    reports = update_file(f, registry, all_=True)
    assert [r.status for r in reports] == ["drift", "updated", "unexpanded"]
    assert "check --fix" in reports[0].detail and "expand" in reports[2].detail


def test_update_of_a_root_pulls_in_new_dependencies(registry, tmp_path):
    f = tmp_path / "t.py"
    f.write_text(f"# cttp: {LIB}#left track=latest\nprint(left(1))\n")
    expand_file(f, registry)
    text = (
        open(FIXTURE, encoding="utf-8")
        .read()
        .replace(
            "def left(x: int) -> int:\n    return x + 1",
            "def left(x: int) -> int:\n    return deep(x) + 1",
        )
    )
    commit_to_remote(tmp_path, "pyrepo", {"lib.py": text}, "left now calls deep")
    (report,) = update_file(f, registry)
    assert report.status == "updated"
    lines = f.read_text().split("\n")
    assert "/lib.py#deep id=sha256:" in lines[0] and lines[1].startswith("def deep(")
    assert [r.status for r in check_file(f, registry)] == ["ok", "ok"]
    import subprocess

    out = subprocess.run(["/usr/bin/python3", "-I", str(f)], capture_output=True, text=True)
    assert out.stdout == "3\n", out.stderr


def test_update_cli_needs_a_file(registry):
    res = runner.invoke(app, ["update", "hello-world"])
    assert res.exit_code == 1 and "at least one file" in res.output
