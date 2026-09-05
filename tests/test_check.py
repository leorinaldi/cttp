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


def test_check_reports_a_stamp_whose_page_does_not_hash_to_its_id(registry, hello):
    """The block hashes to its id — no drift — but the page at the address does not: mismatch."""
    from cttp.hashing import identity, short

    expand_file(hello, registry)
    address = hello.read_text().split()[2]  # the pinned hello-world address
    block = 'print("something else")\n'
    hello.write_text(f"# cttp: {address} id=sha256:{short(identity(block))}\n{block}")
    (report,) = check_file(hello, registry)
    assert report.status == "mismatch" and report.detail.startswith("id mismatch: the link says")


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


# --- P3-T3: check --fix ---------------------------------------------------------------------------


def test_acceptance_check_fix_turns_a_drifted_link_into_a_from_link(registry, hello, tmp_path):
    """One clean, one drifted, one unexpanded link: `check` lists exactly the two problems;
    `--fix` rewrites the drifted one to `cttp-from:`; `check` then reports only the unexpanded."""
    expand_file(hello, registry)
    stamped, code, _ = hello.read_text().split("\n")
    f = tmp_path / "three.py"
    f.write_text(
        f"{stamped}\n{code}\n\n"  # clean
        f"{stamped}\nprint('edited')\n\n"  # drifted
        "# cttp: hello-world\n"  # unexpanded
    )
    res = runner.invoke(app, ["check", str(f)])
    assert res.exit_code == 1
    problems = [line for line in res.output.split("\n") if line and ": ok " not in line]
    assert len(problems) == 2 and "drift" in problems[0] and "unexpanded" in problems[1]
    res = runner.invoke(app, ["check", str(f), "--fix"])
    assert res.exit_code == 1, "the unexpanded link is still a problem"
    assert ":4: fixed hello-world@" in res.output and "drift → cttp-from" in res.output
    lines = f.read_text().split("\n")
    assert lines[3] == stamped.replace("# cttp:", "# cttp-from:", 1), "address and stamp kept"
    assert lines[0] == stamped, "the clean link is untouched"
    reports = check_file(f, registry)
    assert [(r.relation, r.status) for r in reports] == [
        ("is", "ok"),
        ("from", "ok"),
        ("is", "unexpanded"),
    ]
    j = json.loads(runner.invoke(app, ["check", str(f), "--json"]).stdout)
    assert [x["status"] for x in j["links"][str(f)]] == ["ok", "ok", "unexpanded"]


def test_check_fix_keeps_the_comment_syntax(registry, tmp_path):
    from conftest import add_remote_repo

    locator = add_remote_repo(tmp_path, "cfile", {"a.c": "int x = 1;\n"})
    f = tmp_path / "use.c"
    f.write_text(f"// cttp: {locator}@main/a.c\n")
    expand_file(f, registry)
    f.write_text(f.read_text().replace("int x = 1;", "int x = 2;"))
    (report,) = check_file(f, registry, fix=True)
    assert report.status == "fixed"
    assert f.read_text().startswith(f"// cttp-from: {locator}@")
