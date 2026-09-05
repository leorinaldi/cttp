"""`cttp expand --package` (plan P3-T5): the vendored fallback for closures too large to inline."""

import subprocess

from typer.testing import CliRunner

from cttp.cli import app
from cttp.expand import check_file, expand_file, fold_text, update_file
from cttp.links import find_links

runner = CliRunner()
PYREPO = "github.com/leorinaldi/pyrepo"
MANY = f"{PYREPO}@main/many.py"
SYSTEM_PYTHON = "/usr/bin/python3"
# `-I` implies `-P` since Python 3.11: the script's directory is not on sys.path, so no local
# package — cttp_vendor included — is importable under it. `-E -s` still runs with no environment
# and no user site, which is what keeps cttp out of the picture; the test below proves that.
NO_CTTP = [SYSTEM_PYTHON, "-E", "-s"]


def test_the_flags_used_here_still_run_without_cttp():
    probe = subprocess.run([*NO_CTTP, "-c", "import cttp"], capture_output=True)
    assert probe.returncode != 0, "the system interpreter must not have cttp installed"


def test_acceptance_fifty_one_definitions_vendor_into_one_module_and_run(registry, tmp_path):
    f = tmp_path / "main.py"
    f.write_text(f"# cttp: {MANY}#f50\nprint(f50())\n")
    res = runner.invoke(app, ["expand", str(f)])
    assert res.exit_code == 1 and "over budget: 51 definitions" in res.output
    res = runner.invoke(app, ["expand", str(f), "--package"])
    assert res.exit_code == 0, res.output
    assert "vendored" in res.output and "cttp_vendor/pyrepo_many_f50.py" in res.output
    lines = f.read_text().split("\n")
    assert lines[0].startswith(f"# cttp: {PYREPO}@") and "#f50 id=sha256:" in lines[0]
    assert "vendor=cttp_vendor/pyrepo_many_f50.py" in lines[0]
    assert lines[1:] == ["from cttp_vendor.pyrepo_many_f50 import f50", "", "print(f50())", ""]
    module = tmp_path / "cttp_vendor" / "pyrepo_many_f50.py"
    assert module.exists() and (tmp_path / "cttp_vendor" / "__init__.py").exists()
    vendored = find_links(module.read_text().split("\n"))
    assert len(vendored) == 51 and all(k.stamped for k in vendored)
    assert vendored[-1].address.endswith("many.py#f50")
    out = subprocess.run([*NO_CTTP, str(f)], capture_output=True, text=True)
    assert out.stdout == "50\n", out.stderr
    # check on the project passes: the user's link is checked through the vendored module
    res = runner.invoke(app, ["check", str(f), str(module)])
    assert res.exit_code == 0, res.output
    assert f"{f}:1: ok" in res.output and "via cttp_vendor/pyrepo_many_f50.py:" in res.output
    # ... and fails when a vendored definition is edited
    module.write_text(module.read_text().replace("return f48() + 1", "return f48() + 2"))
    res = runner.invoke(app, ["check", str(f), str(module)])
    assert res.exit_code == 1 and "drift" in res.output
    assert [r.status for r in check_file(f, registry)] == ["ok"], "the root itself is intact"
    module.write_text(module.read_text().replace("return f49() + 1", "return f49() + 2"))
    (report,) = check_file(f, registry)
    assert report.status == "drift" and "via cttp_vendor" in report.detail
    module.unlink()
    (report,) = check_file(f, registry)
    assert report.status == "unresolvable" and "missing" in report.detail


def test_a_vendored_script_is_imported_for_its_effect_and_folds_like_any_block(
    registry, hello, tmp_path
):
    expand_file(hello, registry, package=True)
    lines = hello.read_text().split("\n")
    assert lines[1] == "import cttp_vendor.hello_world"
    assert "vendor=cttp_vendor/hello_world.py" in lines[0]
    out = subprocess.run([*NO_CTTP, str(hello)], capture_output=True, text=True)
    assert out.stdout == "hello world!\n", out.stderr
    assert fold_text(hello.read_text())[0] == lines[0] + "\n"
    assert [r.status for r in check_file(hello, registry)] == ["ok"]
    (report,) = update_file(hello, registry, all_=True)
    assert report.status == "vendored" and "cttp_vendor/hello_world.py" in report.detail
    module = tmp_path / "cttp_vendor" / "hello_world.py"
    assert [r.status for r in update_file(module, registry, all_=True)] == ["unchanged"]


def test_add_with_package(registry, tmp_path):
    f = tmp_path / "prog.py"
    res = runner.invoke(app, ["add", f"{MANY}#f50", str(f), "--package"])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "cttp_vendor" / "pyrepo_many_f50.py").exists()
    assert "from cttp_vendor.pyrepo_many_f50 import f50" in f.read_text()
