"""Tasks and graders for the agent benchmark (plan P8).

A task is a directory under `bench/agent/tasks/<name>/` holding `task.toml` and up to three
overlays: `setup/` (copied over the checkout and committed before the agent runs — the bug, the
visible tests), `grade/` (copied over after the run, never committed — the hidden tests) and
`solution/` (the reference fix; `--check-graders` proves the grader tells them apart).

A checkout is built the way the test suite builds one: the task's source files committed on
`main`, a bare clone as the "remote", and a working clone whose `origin` is that bare repository,
reachable as the task's locator through `[remotes]` in a per-run cttp config. `cttp index add
<checkout>` reads exactly that.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASKS = Path(__file__).resolve().parent / "tasks"
FAMILIES = ("in-repo", "cross-repo", "impact")
GIT = ["git", "-c", "user.name=cttp-bench", "-c", "user.email=bench@localhost"]


class TaskError(Exception):
    pass


@dataclass(frozen=True)
class Task:
    name: str
    family: str
    summary: str
    prompt: str
    source: Path  # a directory of this repository, or a git repository on disk
    locator: str
    rev: str | None  # commit to check out when `source` is a git repository; None = HEAD
    setup: Path | None
    grade: Path | None
    solution: Path | None
    command: str  # the test command: the grader, and the one Bash command the agent may run
    timeout: int  # seconds for the grader
    directory: Path = field(repr=False)

    @property
    def test_command(self) -> str:
        return self.command


def load_task(directory: Path) -> Task:
    """`task.toml` → Task, every path checked."""
    toml = directory / "task.toml"
    if not toml.is_file():
        raise TaskError(f"{directory}: no task.toml")
    data = tomllib.loads(toml.read_text(encoding="utf-8"))
    try:
        name = data["name"]
        family = data["family"]
        prompt = data["prompt"].strip()
        repo = data["repo"]
        grade = data["grade"]
        command = grade["command"]
    except KeyError as e:
        raise TaskError(f"{toml}: missing {e}") from e
    if name != directory.name:
        raise TaskError(f"{toml}: name {name!r} is not the directory name {directory.name!r}")
    if family not in FAMILIES:
        raise TaskError(f"{toml}: family {family!r} is not one of {', '.join(FAMILIES)}")
    source = (ROOT / repo["source"]).resolve()
    if not source.is_dir():
        raise TaskError(f"{toml}: repo.source {repo['source']!r} is not a directory")
    locator = repo.get("locator")
    if not locator or locator.count("/") != 2:
        raise TaskError(f"{toml}: repo.locator must be host/owner/repo")

    def overlay(section: str) -> Path | None:
        sub = data.get(section, {}).get("overlay")
        if sub is None:
            return None
        path = directory / sub
        if not path.is_dir():
            raise TaskError(f"{toml}: {section}.overlay {sub!r} is not a directory")
        return path

    return Task(
        name=name,
        family=family,
        summary=data.get("summary", ""),
        prompt=prompt,
        source=source,
        locator=locator,
        rev=repo.get("rev"),
        setup=overlay("setup"),
        grade=overlay("grade"),
        solution=overlay("solution"),
        command=command,
        timeout=int(grade.get("timeout", 300)),
        directory=directory,
    )


def load_tasks(names: list[str] | None = None) -> list[Task]:
    """Every task under `tasks/`, or the named ones, in name order."""
    if not TASKS.is_dir():
        return []
    dirs = sorted(p for p in TASKS.iterdir() if p.is_dir() and (p / "task.toml").is_file())
    tasks = [load_task(d) for d in dirs]
    if names:
        known = {t.name: t for t in tasks}
        missing = [n for n in names if n not in known]
        if missing:
            raise TaskError(f"unknown task(s): {', '.join(missing)}; --list shows them")
        tasks = [known[n] for n in names]
    return tasks


# --- the checkout ------------------------------------------------------------------------------


def _run(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if check and proc.returncode != 0:
        raise TaskError(f"{' '.join(args)} in {cwd}: {proc.stderr.strip()}")
    return proc


def _copy_tree(src: Path, dst: Path) -> None:
    """Copy `src`'s files over `dst` (no `.git`, no caches)."""
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in rel.parts):
            continue
        if path.is_dir():
            (dst / rel).mkdir(parents=True, exist_ok=True)
        else:
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dst / rel)


@dataclass(frozen=True)
class Checkout:
    """What `prepare_checkout` made: the working clone the agent edits, its bare origin, and the
    commit the agent starts from."""

    path: Path
    remote: Path
    base_sha: str
    locator: str


def prepare_checkout(task: Task, work: Path) -> Checkout:
    """Build `work/repo` (the checkout the agent edits) and `work/remote.git` (its origin)."""
    if work.exists():
        shutil.rmtree(work)
    origin = work / "origin"
    origin.mkdir(parents=True)
    if (task.source / ".git").exists():
        _run(["git", "clone", "--quiet", str(task.source), str(origin)], cwd=work)
        if task.rev:
            _run(["git", "checkout", "--quiet", "-B", "main", task.rev], cwd=origin)
        else:
            _run(["git", "checkout", "--quiet", "-B", "main"], cwd=origin)
    else:
        _copy_tree(task.source, origin)
        _run(["git", "init", "--quiet", "-b", "main"], cwd=origin)
        _run([*GIT, "add", "-A"], cwd=origin)
        _run([*GIT, "commit", "--quiet", "-m", f"{task.name}: base"], cwd=origin)
    if task.setup:
        _copy_tree(task.setup, origin)
        _run([*GIT, "add", "-A"], cwd=origin)
        status = _run(["git", "status", "--porcelain"], cwd=origin).stdout.strip()
        if status:
            _run([*GIT, "commit", "--quiet", "-m", f"{task.name}: setup"], cwd=origin)
    remote = work / "remote.git"
    _run(["git", "clone", "--quiet", "--bare", str(origin), str(remote)], cwd=work)
    _run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=remote)
    repo = work / "repo"
    _run(["git", "clone", "--quiet", str(remote), str(repo)], cwd=work)
    sha = _run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    shutil.rmtree(origin)
    return Checkout(path=repo, remote=remote, base_sha=sha, locator=task.locator)


def write_config(work: Path, checkout: Checkout, registries: list[str]) -> Path:
    """A cttp config for this run: the given registries, and the task's locator mapped to the
    bare remote through `[remotes]` — how `cttp index add` learns the checkout's locator and how
    `resolve <locator>` reaches it without a network."""
    lines = ["registries = ["]
    lines += [f"  {r!r}," for r in registries]
    lines += ["]", "", "[remotes]", f'"{checkout.locator}" = "{checkout.remote}"', ""]
    path = work / "cttp.toml"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def venv_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The environment a subprocess gets: this interpreter's bin directory first on PATH, so
    `python` and `cttp` are the project's."""
    env = dict(os.environ)
    bindir = str(Path(sys.executable).parent)
    env["PATH"] = bindir + os.pathsep + env.get("PATH", "")
    env["VIRTUAL_ENV"] = str(Path(sys.executable).parent.parent)
    env.pop("PYTHONPATH", None)
    if extra:
        env.update(extra)
    return env


# --- grading -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Grade:
    passed: bool
    returncode: int | None
    output: str
    timed_out: bool = False
    diff: str = ""  # what the agent changed, against the base commit


def grade(task: Task, checkout: Checkout, env: dict[str, str] | None = None) -> Grade:
    """Overlay the hidden tests and run the task's command in the checkout. Pass = exit 0."""
    diff = _run(["git", "diff", checkout.base_sha], cwd=checkout.path, check=False).stdout
    untracked = _run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=checkout.path, check=False
    ).stdout
    untracked = "\n".join(
        line for line in untracked.splitlines() if "__pycache__" not in line and line.strip()
    )
    if untracked:
        diff += "\n# untracked files:\n" + untracked + "\n"
    if task.grade:
        _copy_tree(task.grade, checkout.path)
    try:
        proc = subprocess.run(
            ["bash", "-lc", task.command],
            cwd=checkout.path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=task.timeout,
            env=env or venv_env(),
        )
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else ""
        return Grade(False, None, out, timed_out=True, diff=diff)
    return Grade(proc.returncode == 0, proc.returncode, proc.stdout + proc.stderr, diff=diff)


def check_grader(task: Task, work: Path) -> dict[str, object]:
    """The P8-T2 acceptance for one task: the grader fails the unmodified checkout and passes
    the reference solution."""
    result: dict[str, object] = {"task": task.name}
    checkout = prepare_checkout(task, work / "unmodified")
    before = grade(task, checkout)
    result["unmodified"] = {"passed": before.passed, "returncode": before.returncode}
    if task.solution is None:
        result["solution"] = None
        result["ok"] = not before.passed
        result["why"] = "no solution overlay" if result["ok"] else "unmodified checkout passes"
        return result
    checkout = prepare_checkout(task, work / "solved")
    _copy_tree(task.solution, checkout.path)
    after = grade(task, checkout)
    result["solution"] = {"passed": after.passed, "returncode": after.returncode}
    result["ok"] = (not before.passed) and after.passed
    result["why"] = (
        "ok"
        if result["ok"]
        else ("unmodified checkout passes" if before.passed else "reference solution fails")
    )
    if not result["ok"]:
        result["output"] = (before if before.passed else after).output[-2000:]
    return result
