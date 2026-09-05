import json

from typer.testing import CliRunner

from cttp import __version__
from cttp.cli import app

runner = CliRunner()


def test_version():
    assert runner.invoke(app, ["--version"]).stdout.strip() == f"cttp {__version__}"
    out = runner.invoke(app, ["--json", "--version"]).stdout
    assert json.loads(out) == {"version": __version__}


def test_resolve_json(registry):
    res = runner.invoke(app, ["--json", "resolve", "hello-world"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout)["kind"] == "script"


def test_check_exit_codes(registry, tmp_path):
    f = tmp_path / "h.py"
    f.write_text("# cttp: hello-world\n")
    assert runner.invoke(app, ["check", str(f)]).exit_code == 1
    assert runner.invoke(app, ["expand", str(f)]).exit_code == 0
    assert runner.invoke(app, ["check", str(f)]).exit_code == 0


def test_json_flag_after_the_subcommand(registry):
    res = runner.invoke(app, ["resolve", "hello-world", "--json"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout)["address"].startswith("hello-world@")
