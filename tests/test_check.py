import json

from typer.testing import CliRunner

from cttp.cli import app
from cttp.expand import check_file, expand_file

runner = CliRunner()


def test_check_passes_then_drifts(registry, hello):
    assert [r.status for r in check_file(hello, registry)] == ["unexpanded"]
    expand_file(hello, registry)
    assert [r.status for r in check_file(hello, registry)] == ["ok"]
    hello.write_text(hello.read_text().replace("hello world!", "goodbye"))
    (report,) = check_file(hello, registry)
    assert report.status == "drift" and "sha256:" in report.detail


def test_check_reports_every_failure_kind(registry, hello, tmp_path):
    expand_file(hello, registry)
    stamped = hello.read_text().split("\n")[0]
    f = tmp_path / "many.py"
    f.write_text(
        "# cttp: hello-world\n"  # unexpanded
        + stamped
        + "\n"
        + 'print("hello world!")\n'  # ok
        + stamped.replace("hello-world@", "hello-world@000000000000")
        + '\nprint("hello world!")\n'  # bad rev
        + stamped
        + "\n"  # nothing beneath
    )
    reports = check_file(f, registry)
    assert [r.status for r in reports] == ["unexpanded", "ok", "unresolvable", "drift"]
    assert "000000000000" in reports[2].detail and "nothing beneath" in reports[3].detail


def test_check_cli_exit_codes_and_json(registry, hello):
    assert runner.invoke(app, ["check", str(hello)]).exit_code == 1  # unexpanded
    assert runner.invoke(app, ["expand", str(hello)]).exit_code == 0
    res = runner.invoke(app, ["check", str(hello), "--json"])
    assert res.exit_code == 0 and json.loads(res.stdout)["ok"] is True
    hello.write_text(hello.read_text().replace("hello world!", "bye"))
    res = runner.invoke(app, ["--json", "check", str(hello)])
    body = json.loads(res.stdout)
    assert res.exit_code == 1 and body["ok"] is False
    (link,) = body["links"][str(hello)]
    assert link["status"] == "drift" and link["line"] == 1
    text = runner.invoke(app, ["check", str(hello)]).output
    assert f"{hello}:1: drift hello-world@" in text


def test_locator_link_expands_and_checks(registry, tmp_path):
    f = tmp_path / "loc.py"
    f.write_text("# cttp: github.com/leorinaldi/cttp-registry@main/snippets/hello_world.py\n")
    expand_file(f, registry)
    first = f.read_text().split("\n")[0]
    assert (
        first.startswith("# cttp: github.com/leorinaldi/cttp-registry@") and "id=sha256:" in first
    )
    assert "@main" not in first  # the stamp pins a SHA, never a branch
    assert [r.status for r in check_file(f, registry)] == ["ok"]
