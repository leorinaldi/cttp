"""`cttp fold` (plan P3-T4): the file as a list of what it does; a view that writes nothing."""

import json

from conftest import add_to_registry
from typer.testing import CliRunner

from cttp.cli import app
from cttp.expand import expand_file, fold_text
from cttp.resolve import resolve

runner = CliRunner()
GREET = 'def greet(name: str) -> str:\n    return f"hello {name}!"\n'
HELLO = '# cttp: greet\nprint(greet("world"))\n'


def spec_7_file(registry, tmp_path):
    add_to_registry(tmp_path, "greet", GREET)
    add_to_registry(tmp_path, "hello-world", HELLO)
    f = tmp_path / "main.py"
    f.write_text("# cttp: hello-world\n")
    expand_file(f, registry)
    return f, resolve("greet", registry), resolve("hello-world", registry)


def test_acceptance_fold_prints_two_link_lines_and_nothing_else(registry, tmp_path):
    f, g, h = spec_7_file(registry, tmp_path)
    before = f.read_bytes()
    res = runner.invoke(app, ["fold", str(f)])
    assert res.exit_code == 0, res.output
    assert res.output == (
        f"# cttp: {g.address} id={g.identity}\n# cttp: {h.address} id={h.identity}\n"
    )
    assert f.read_bytes() == before, "fold writes nothing"


def test_acceptance_open_unfolds_one_block(registry, tmp_path):
    f, g, h = spec_7_file(registry, tmp_path)
    res = runner.invoke(app, ["fold", str(f), "--open", "greet"])
    assert res.output == (
        f"# cttp: {g.address} id={g.identity}\n"
        'def greet(name: str) -> str:\n    return f"hello {name}!"\n\n'
        f"# cttp: {h.address} id={h.identity}\n"
    )
    # by the pinned address, too; and the root by name
    assert runner.invoke(app, ["fold", str(f), "--open", g.address]).output == res.output
    res = runner.invoke(app, ["fold", str(f), "--open", "hello-world"])
    assert res.output.endswith(f'# cttp: {h.address} id={h.identity}\nprint(greet("world"))\n')


def test_fold_json_lists_links_with_line_ranges(registry, tmp_path):
    f, g, h = spec_7_file(registry, tmp_path)
    j = json.loads(runner.invoke(app, ["fold", str(f), "--json"]).stdout)
    assert j[str(f)] == [
        {
            "line": 1,
            "relation": "is",
            "address": g.address,
            "description": None,
            "start": 2,
            "end": 3,
            "lines": 2,
            "folded": True,
        },
        {
            "line": 5,
            "relation": "is",
            "address": h.address,
            "description": None,
            "start": 6,
            "end": 6,
            "lines": 1,
            "folded": True,
        },
    ]


def test_fold_keeps_user_code_and_unexpanded_and_see_lines(registry, hello):
    hello.write_text("import sys\n\n# cttp-see: docs\n# cttp: hello-world\n\nprint(sys.argv)\n")
    expand_file(hello, registry)
    folded, entries = fold_text(hello.read_text())
    lines = folded.split("\n")
    assert lines[0:3] == ["import sys", "", "# cttp-see: docs"]
    assert lines[3].startswith("# cttp: hello-world@") and lines[4:] == ["", "print(sys.argv)", ""]
    assert [e["folded"] for e in entries] == [False, True]
    assert fold_text("# cttp: hello-world\nx = 1\n")[0] == "# cttp: hello-world\nx = 1\n", (
        "an unexpanded link owns no block"
    )


def test_fold_folds_a_from_block_and_shows_several_files(registry, hello, tmp_path):
    expand_file(hello, registry)
    fork = tmp_path / "fork.py"
    fork.write_text(hello.read_text().replace("# cttp:", "# cttp-from:").replace("!", "?"))
    res = runner.invoke(app, ["fold", str(hello), str(fork)])
    assert res.output.count("==> ") == 2 and "print(" not in res.output
