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

    def confirm(r):
        seen.append(r.address)
        return True

    assert run_address("hello-world", registry, confirm) == 0
    assert run_address("hello-world", registry, confirm) == 0
    assert run_file(hello, registry, confirm) == 0
    assert len(seen) == 1 and seen[0].startswith("hello-world@"), "asked once per pinned address"
    assert capfd.readouterr().out == "hello world!\n" * 3


def test_declined_run_leaves_no_cache_entry(registry, hello, capfd):
    with pytest.raises(NotConfirmed, match="hello-world@.*not run"):
        run_address("hello-world", registry, lambda r: False)
    with pytest.raises(NotConfirmed):
        run_file(hello, registry, lambda r: False)
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
