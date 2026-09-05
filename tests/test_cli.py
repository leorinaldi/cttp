import json

from typer.testing import CliRunner

from cttp import __version__
from cttp.cli import app
from cttp.schemas import SCHEMA_VERSION

runner = CliRunner()


def test_version():
    assert runner.invoke(app, ["--version"]).stdout.strip() == f"cttp {__version__}"
    out = runner.invoke(app, ["--json", "--version"]).stdout
    assert json.loads(out) == {"schema_version": SCHEMA_VERSION, "version": __version__}


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


def test_resolve_accepts_a_locator(registry):
    """Plan P1-T1 acceptance: the locator form returns the same object as the name form."""
    name = runner.invoke(app, ["--json", "resolve", "hello-world"])
    loc = runner.invoke(
        app,
        [
            "--json",
            "resolve",
            "cttp:github.com/leorinaldi/cttp-registry@main/snippets/hello_world.py",
        ],
    )
    assert loc.exit_code == 0, loc.output
    n, by_loc = json.loads(name.stdout), json.loads(loc.stdout)
    assert {k: v for k, v in by_loc.items() if k != "address"} == {
        k: v for k, v in n.items() if k != "address"
    }
    assert (
        by_loc["address"]
        == f"github.com/leorinaldi/cttp-registry@{n['rev'][:12]}/snippets/hello_world.py"
    )


def test_resolve_bad_address_names_the_part(registry):
    res = runner.invoke(
        app, ["resolve", "github.com/leorinaldi/cttp-registry/snippets/hello_world.py"]
    )
    assert res.exit_code == 1 and "missing rev" in res.output
