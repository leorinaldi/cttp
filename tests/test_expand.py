import subprocess
from pathlib import Path

import pytest

from cttp.expand import check_file, expand_file, run_address, run_file
from cttp.resolve import resolve

SYSTEM_PYTHON = "/usr/bin/python3"


@pytest.fixture
def hello(tmp_path: Path) -> Path:
    f = tmp_path / "hello.py"
    f.write_text("# cttp: hello-world\n")
    return f


def test_expand_writes_stamp_and_code(registry, hello):
    reports = expand_file(hello, registry)
    r = resolve("hello-world", registry)
    assert [x.status for x in reports] == ["expanded"]
    assert hello.read_text() == (
        f"# cttp: hello-world@{r.rev[:12]} id={r.identity}  \"Prints 'hello world'.\"\n"
        'print("hello world!")\n'
    )
    assert expand_file(hello, registry)[0].status == "unchanged"


def test_expanded_file_runs_without_cttp(registry, hello):
    expand_file(hello, registry)
    probe = subprocess.run([SYSTEM_PYTHON, "-I", "-c", "import cttp"], capture_output=True)
    assert probe.returncode != 0, "the system interpreter must not have cttp installed"
    out = subprocess.run([SYSTEM_PYTHON, "-I", str(hello)], capture_output=True, text=True)
    assert out.stdout == "hello world!\n"


def test_check_passes_then_drifts(registry, hello):
    assert [r.status for r in check_file(hello, registry)] == ["unexpanded"]
    expand_file(hello, registry)
    assert [r.status for r in check_file(hello, registry)] == ["ok"]
    hello.write_text(hello.read_text().replace("hello world!", "goodbye"))
    (report,) = check_file(hello, registry)
    assert report.status == "drift" and "sha256:" in report.detail


def test_run_address_and_file(registry, hello, capfd):
    assert run_address("hello-world", registry) == 0
    assert capfd.readouterr().out == "hello world!\n"
    assert run_file(hello, registry) == 0
    assert capfd.readouterr().out == "hello world!\n"
    assert hello.read_text() == "# cttp: hello-world\n", "run leaves the file untouched"


def test_no_runtime_component(registry, hello):
    expand_file(hello, registry)
    assert "import cttp" not in hello.read_text()
    src = Path(__file__).parent.parent / "src" / "cttp"
    assert not any("meta_path" in p.read_text() for p in src.rglob("*.py"))
