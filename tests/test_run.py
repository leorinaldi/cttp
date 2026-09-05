import pytest
from typer.testing import CliRunner

from cttp.cli import NOT_RUN, app
from cttp.expand import NotConfirmed, run_address, run_file
from cttp.gitcache import home

runner = CliRunner()


def test_run_address_and_file(registry, hello, capfd):
    assert run_address("hello-world", registry) == 0
    assert capfd.readouterr().out == "hello world!\n"
    assert run_file(hello, registry) == 0
    assert capfd.readouterr().out == "hello world!\n"
    assert hello.read_text() == "# cttp: hello-world\n", "run leaves the file untouched"


def test_first_run_asks_and_later_runs_do_not(registry, hello, capfd):
    seen = []

    def confirm(c):
        seen.append(c.address)
        return True

    assert run_address("hello-world", registry, confirm) == 0
    assert run_address("hello-world", registry, confirm) == 0
    assert run_file(hello, registry, confirm) == 0
    assert len(seen) == 1 and seen[0].startswith("hello-world@"), "asked once per pinned address"
    assert capfd.readouterr().out == "hello world!\n" * 3


def test_declined_run_leaves_no_cache_entry(registry, hello, capfd):
    with pytest.raises(NotConfirmed, match="hello-world@.*not run"):
        run_address("hello-world", registry, lambda c: False)
    with pytest.raises(NotConfirmed):
        run_file(hello, registry, lambda c: False)
    assert capfd.readouterr().out == ""
    assert not list((home() / "run").glob("hello-world@*")), "declined: nothing materialized"


def test_cli_without_a_terminal_refuses_and_says_how(registry, hello, capfd):
    res = runner.invoke(app, ["run", "hello-world"])
    assert res.exit_code == NOT_RUN, res.output
    assert "first run of hello-world@" in res.output and 'print("hello world!")' in res.output
    assert "license=MIT" in res.output and "pass --yes" in res.output
    assert capfd.readouterr().out == "", "nothing ran"
    assert runner.invoke(app, ["run", "hello-world", "--yes"]).exit_code == 0
    assert capfd.readouterr().out == "hello world!\n"
    assert runner.invoke(app, ["run", "hello-world"]).exit_code == 0, "confirmed once, no ask"
    assert runner.invoke(app, ["run", str(hello)]).exit_code == 0, "the file's address is confirmed"


def test_cli_run_targets(registry, tmp_path):
    res = runner.invoke(app, ["run", "no-such-name", "--yes"])
    assert res.exit_code == 1 and "no-such-name" in res.output
    res = runner.invoke(app, ["run", str(tmp_path / "missing.py"), "--yes"])
    assert res.exit_code == 1 and "neither an address nor a file" in res.output


# --- P3-T4: run, in full -------------------------------------------------------------------------

PYREPO = "github.com/leorinaldi/pyrepo"


def test_acceptance_run_a_file_with_one_link_leaves_it_at_one_line(registry, hello, capfd):
    assert runner.invoke(app, ["run", str(hello), "--yes"]).exit_code == 0
    assert capfd.readouterr().out == "hello world!\n"
    assert hello.read_text() == "# cttp: hello-world\n"


def test_acceptance_first_run_shows_the_source_and_waits_for_an_answer(
    registry, hello, capfd, monkeypatch
):
    monkeypatch.setattr("cttp.cli._interactive", lambda: True)
    res = runner.invoke(app, ["run", "hello-world"], input="n\n")
    assert res.exit_code == NOT_RUN, res.output
    assert 'print("hello world!")' in res.output and "Run it?" in res.output
    assert capfd.readouterr().out == "", "nothing ran"
    assert not list((home() / "run").glob("hello-world@*")), "declined: nothing materialized"
    res = runner.invoke(app, ["run", "hello-world"], input="y\n")
    assert res.exit_code == 0, res.output
    assert capfd.readouterr().out == "hello world!\n"


def test_first_run_confirmation_shows_every_page_of_the_closure(registry, tmp_path, capfd):
    seen = []

    def confirm(c):
        seen.append([n.page.symbol for n in c.nodes])
        return True

    assert run_address(f"{PYREPO}@main/lib.py#top", registry, confirm) == 0
    assert seen == [["left", "deep", "right", "top"]]
    res = runner.invoke(app, ["run", f"{PYREPO}@main/lib.py#right"])
    assert res.exit_code == NOT_RUN
    assert "1 dependenc(ies)" in res.output and "def deep(x: int) -> int:" in res.output
    assert "lib.py#deep  sha256:" in res.output and "license=MIT" in res.output


def test_run_a_file_whose_link_has_a_closure(registry, tmp_path, capfd):
    f = tmp_path / "t.py"
    f.write_text(f"# cttp: {PYREPO}@main/lib.py#top\nprint(top(3))\n")
    assert run_file(f, registry) == 0
    assert capfd.readouterr().out == "9\n"
    assert f.read_text() == f"# cttp: {PYREPO}@main/lib.py#top\nprint(top(3))\n"
