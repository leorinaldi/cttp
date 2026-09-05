"""`cttp expand`, and the spec's acceptance test 4 verbatim through the CLI."""

import subprocess
from pathlib import Path

import pytest
from conftest import add_to_registry
from typer.testing import CliRunner

from cttp.cli import app
from cttp.closure import ClosureError
from cttp.expand import check_file, expand_file
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


# --- P3-T2: expansion with closure, and `add` -------------------------------------------------

PYREPO = "github.com/leorinaldi/pyrepo"
LIB = f"{PYREPO}@main/lib.py"
GREET = 'def greet(name: str) -> str:\n    return f"hello {name}!"\n'
HELLO = '# cttp: greet\nprint(greet("world"))\n'


def spec_7_registry(tmp_path) -> tuple:
    """A registry with the spec §7 names: `greet`, and `hello-world` linking to it."""
    add_to_registry(tmp_path, "greet", GREET)
    add_to_registry(tmp_path, "hello-world", HELLO)


def test_acceptance_the_spec_7_example_reproduces_byte_for_byte(registry, tmp_path):
    spec_7_registry(tmp_path)
    g, h = resolve("greet", registry), resolve("hello-world", registry)
    f = tmp_path / "main.py"
    f.write_text("# cttp: hello-world\n")
    assert [r.status for r in expand_file(f, registry)] == ["expanded"]
    assert f.read_text() == (
        f"# cttp: {g.address} id={g.identity}\n"
        'def greet(name: str) -> str:\n    return f"hello {name}!"\n'
        "\n"
        f"# cttp: {h.address} id={h.identity}\n"
        'print(greet("world"))\n'
    )
    assert g.address.startswith("greet@") and h.address.startswith("hello-world@")
    out = subprocess.run([SYSTEM_PYTHON, "-I", str(f)], capture_output=True, text=True)
    assert out.stdout == "hello world!\n", out.stderr
    assert [r.status for r in check_file(f, registry)] == ["ok", "ok"]
    # re-running expand is a no-op, byte for byte
    before = f.read_bytes()
    assert [r.status for r in expand_file(f, registry)] == ["unchanged", "unchanged"]
    assert f.read_bytes() == before


def test_acceptance_a_third_party_import_is_hoisted_and_reported(registry, tmp_path):
    f = tmp_path / "use.py"
    f.write_text(f"# cttp: {LIB}#fetch\nprint(fetch)\n")
    reports = expand_file(f, registry)
    assert [(r.status, r.detail) for r in reports][1:] == [
        ("requires", "requests"),
        ("deps", "not written; pass --write-deps to add requests"),
    ]
    lines = f.read_text().split("\n")
    assert lines[0] == "import requests" and lines[1] == ""
    assert lines[2].startswith(f"# cttp: {PYREPO}@") and "#fetch id=sha256:" in lines[2]
    assert lines[3] == "def fetch(url: str) -> str:"
    assert lines[-3:] == ["", "print(fetch)", ""]
    assert [r.status for r in check_file(f, registry)] == ["ok"]
    # the import is written once, even when a second link needs it too
    f.write_text(f.read_text() + f"# cttp: {LIB}#fetch\n")
    expand_file(f, registry)
    assert f.read_text().count("import requests") == 1


def test_acceptance_write_deps_adds_the_requirement_to_pyproject(registry, tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '# my project\n[project]\nname = "demo"\ndependencies = [\n  "typer>=0.12",\n]\n\n'
        "[tool.ruff]\nline-length = 100\n"
    )
    f = tmp_path / "use.py"
    f.write_text(f"# cttp: {LIB}#fetch\n")
    res = runner.invoke(app, ["expand", str(f), "--write-deps"])
    assert res.exit_code == 0, res.output
    assert "deps" in res.output and "requests" in res.output
    text = (tmp_path / "pyproject.toml").read_text()
    assert text == (
        '# my project\n[project]\nname = "demo"\ndependencies = [\n  "typer>=0.12",\n'
        '  "requests",\n]\n\n[tool.ruff]\nline-length = 100\n'
    ), text
    # already listed: nothing changes
    g = tmp_path / "again.py"
    g.write_text(f"# cttp: {LIB}#fetch\n")
    runner.invoke(app, ["expand", str(g), "--write-deps"])
    assert (tmp_path / "pyproject.toml").read_text() == text
    # no pyproject anywhere: an error naming what was needed
    nowhere = tmp_path / "elsewhere"
    nowhere.mkdir()
    h = nowhere / "h.py"
    h.write_text(f"# cttp: {LIB}#fetch\n")
    (tmp_path / "pyproject.toml").rename(tmp_path / "pyproject.bak")
    res = runner.invoke(app, ["expand", str(h), "--write-deps"])
    assert res.exit_code == 1 and "no pyproject.toml above" in res.output


def test_write_deps_adds_the_table_or_the_key_when_missing():
    import tempfile

    from cttp.expand import write_dependencies

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "pyproject.toml"
        p.write_text('[project]\nname = "x"\n\n[tool.x]\ny = 1\n')
        assert write_dependencies(p, ["requests"]) == ["requests"]
        assert p.read_text() == (
            '[project]\ndependencies = [\n  "requests",\n]\nname = "x"\n\n[tool.x]\ny = 1\n'
        )
        p.write_text("[tool.x]\ny = 1\n")
        write_dependencies(p, ["requests", "httpx"])
        assert p.read_text().endswith('[project]\ndependencies = [\n  "requests",\n  "httpx",\n]\n')
        p.write_text('[project]\ndependencies = ["Requests>=2"]\n')
        assert write_dependencies(p, ["requests"]) == [], "listed under another spelling"


def test_acceptance_add_equals_writing_the_link_and_expanding(registry, tmp_path):
    spec_7_registry(tmp_path)
    by_hand = tmp_path / "by_hand.py"
    by_hand.write_text("# cttp: hello-world\n")
    expand_file(by_hand, registry)
    added = tmp_path / "added.py"
    res = runner.invoke(app, ["add", "hello-world", str(added)])
    assert res.exit_code == 0, res.output
    assert added.read_text() == by_hand.read_text()
    # into an existing file: at the end, or at a line
    prog = tmp_path / "prog.py"
    prog.write_text("import sys\n\nprint(sys.argv[0])\n")
    runner.invoke(app, ["add", "hello-world", str(prog), "--at", "3"])
    lines = prog.read_text().split("\n")
    assert lines[0:2] == ["import sys", ""] and lines[2].startswith("# cttp: greet@")
    assert lines[-3:] == ["", "print(sys.argv[0])", ""]
    runner.invoke(app, ["add", "greet", str(prog)])
    assert prog.read_text().split("\n")[-4].startswith("# cttp: greet@")
    assert runner.invoke(app, ["add", "not an address", str(prog)]).exit_code == 1


def test_a_dependency_already_expanded_above_is_not_written_twice(registry, tmp_path):
    f = tmp_path / "two.py"
    f.write_text(f"# cttp: {LIB}#right\n\n# cttp: {LIB}#top\n")
    expand_file(f, registry)
    defs = [line.split("(")[0] for line in f.read_text().split("\n") if line.startswith("def ")]
    assert defs == ["def deep", "def right", "def left", "def top"], "each once, in order"
    assert [r.status for r in check_file(f, registry)] == ["ok"] * 4
    out = subprocess.run(
        [SYSTEM_PYTHON, "-I", "-c", f"exec(open({str(f)!r}).read()); print(top(3))"],
        capture_output=True,
        text=True,
    )
    assert out.stdout == "9\n", out.stderr


def test_two_is_links_in_one_stack_are_refused(registry, tmp_path):
    from cttp.expand import ExpandError

    f = tmp_path / "stack.py"
    f.write_text(f"# cttp: {LIB}#right\n# cttp: {LIB}#top\n")
    with pytest.raises(ExpandError, match="line 1: two `cttp:` links stack above one block"):
        expand_file(f, registry)


def test_the_users_fields_and_description_survive_the_stamp(registry, tmp_path):
    f = tmp_path / "keep.py"
    f.write_text('# cttp: hello-world track=latest  "My own words."\n')
    expand_file(f, registry)
    first = f.read_text().split("\n")[0]
    assert first.startswith("# cttp: hello-world@") and first.endswith(
        ' id=sha256:75a27070015e track=latest  "My own words."'
    )


def test_a_pages_own_see_and_from_lines_join_the_stack(registry, tmp_path):
    add_to_registry(tmp_path, "annotated", "# cttp-see: hello-world\nprint('x')\n")
    f = tmp_path / "a.py"
    f.write_text("# cttp: annotated\n")
    expand_file(f, registry)
    lines = f.read_text().split("\n")
    assert lines[0].startswith("# cttp: annotated@") and lines[1] == "# cttp-see: hello-world"
    assert lines[2] == "print('x')"
    assert [r.status for r in check_file(f, registry)] == ["ok", "ok"]


def test_a_closure_error_leaves_the_file_untouched(registry, tmp_path):
    f = tmp_path / "b.py"
    f.write_text(f"# cttp: {LIB}#broken\n")
    with pytest.raises(ClosureError, match="`missing`"):
        expand_file(f, registry)
    assert f.read_text() == f"# cttp: {LIB}#broken\n"
    res = runner.invoke(app, ["expand", str(f)])
    assert res.exit_code == 1 and "`missing`" in res.output


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
