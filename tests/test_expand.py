"""`cttp expand`, and the spec's acceptance test 4 verbatim through the CLI."""

import subprocess
from pathlib import Path

import pytest
from conftest import add_to_registry
from typer.testing import CliRunner

from cttp.cli import app
from cttp.expand import ExpandError, expand_file
from cttp.resolve import resolve

SYSTEM_PYTHON = "/usr/bin/python3"
runner = CliRunner()


def test_expand_writes_stamp_and_code(registry, hello):
    reports = expand_file(hello, registry)
    r = resolve("hello-world", registry)
    assert [x.status for x in reports] == ["expanded"]
    assert hello.read_text() == (
        f"# cttp: hello-world@{r.rev[:12]} id={r.identity}  \"Prints 'hello world'.\"\n"
        'print("hello world!")\n'
    )
    assert expand_file(hello, registry)[0].status == "unchanged"


def test_expand_keeps_indent_and_surroundings(registry, tmp_path):
    f = tmp_path / "prog.py"
    f.write_text("def main():\n    # cttp: hello-world\n\nmain()\n")
    expand_file(f, registry)
    lines = f.read_text().split("\n")
    assert lines[0] == "def main():" and lines[1].startswith("    # cttp: hello-world@")
    assert lines[2] == '    print("hello world!")' and lines[3:] == ["", "main()", ""]
    assert subprocess.run([SYSTEM_PYTHON, "-I", str(f)], capture_output=True, text=True).stdout == (
        "hello world!\n"
    )


def test_a_page_that_links_elsewhere_is_refused(registry, tmp_path):
    add_to_registry(tmp_path, "outer", "# cttp: hello-world\nprint('after')\n", "Links out.")
    f = tmp_path / "o.py"
    f.write_text("# cttp: outer\n")
    with pytest.raises(ExpandError, match="links to 1 other page.*hello-world.*P3-T1"):
        expand_file(f, registry)
    assert f.read_text() == "# cttp: outer\n", "nothing is written when expansion is refused"
    res = runner.invoke(app, ["expand", str(f)])
    assert res.exit_code == 1 and "closure expansion arrives" in res.output


def test_acceptance_test_4_hello_world(registry, hello, capfd):
    """Spec §12, test 4 — every step through the CLI, in order."""
    # a file containing only `# cttp: hello-world` is expanded by `cttp expand` into that line,
    # stamped, plus print("hello world!")
    assert hello.read_text() == "# cttp: hello-world\n"
    assert runner.invoke(app, ["expand", str(hello)]).exit_code == 0
    stamped, code, end = hello.read_text().split("\n")
    assert stamped.startswith("# cttp: hello-world@") and "id=sha256:" in stamped
    assert (
        stamped.endswith("\"Prints 'hello world'.\"")
        and code == 'print("hello world!")'
        and end == ""
    )
    # python runs it with cttp uninstalled
    probe = subprocess.run([SYSTEM_PYTHON, "-I", "-c", "import cttp"], capture_output=True)
    assert probe.returncode != 0, "the system interpreter must not have cttp installed"
    out = subprocess.run([SYSTEM_PYTHON, "-I", str(hello)], capture_output=True, text=True)
    assert out.stdout == "hello world!\n"
    # `cttp run hello-world` runs it with no file at all
    hello.unlink()
    assert runner.invoke(app, ["run", "hello-world", "--yes"]).exit_code == 0
    assert capfd.readouterr().out == "hello world!\n"
    # `cttp check` passes before and fails after the print line is edited
    runner.invoke(
        app, ["expand", str(hello.write_text("# cttp: hello-world\n") and hello or hello)]
    )
    assert runner.invoke(app, ["check", str(hello)]).exit_code == 0
    hello.write_text(hello.read_text().replace("hello world!", "goodbye"))
    res = runner.invoke(app, ["check", str(hello)])
    assert res.exit_code == 1 and "drift" in res.output and "hello-world@" in res.output


def test_no_runtime_component(registry, hello):
    expand_file(hello, registry)
    assert "import cttp" not in hello.read_text()
    src = Path(__file__).parent.parent / "src" / "cttp"
    assert not any("meta_path" in p.read_text() for p in src.rglob("*.py"))
