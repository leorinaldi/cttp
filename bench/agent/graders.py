"""Tasks and graders for the agent benchmark (plan P8).

A task is a directory under `bench/agent/tasks/<name>/` holding `task.toml` and up to three
overlays: `setup/` (copied over the checkout and committed before the agent runs — the bug, the
visible tests), `grade/` (copied over after the run, never committed — the hidden tests) and
`solution/` (the reference fix; `--check-graders` proves the grader tells them apart). An overlay
is either a directory of the task or a list of paths taken from a commit of the task's source
repository (`commit = "<sha>"`, `paths = [...]`) — how the in-repository tasks carry a real fix
and its tests without copying them into this repository.

A checkout is built the way the test suite builds one: the task's source files committed on
`main`, a bare clone as the "remote", and a working clone whose `origin` is that bare repository,
reachable as the task's locator through `[remotes]` in a per-run cttp config. `cttp index add
<checkout>` reads exactly that. A task's `[[deps]]` — other repositories a cross-repository task
reuses code from — get the same treatment, checked out beside the agent's working copy as
`deps/<name>` so that both arms can reach them, and indexed with it.

Grading is the task's test command (exit 0 passes), then, when the task asks for them, the
`[grade.link]` check (a `# cttp:` link in the named file resolves to the expected definition, and
no stamp on it is wrong) and the `[grade.who]` check (the agent's answer file names exactly the
definitions `cttp who` finds for the target on the run's index).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from cttp.links import LinkError, find_links

ROOT = Path(__file__).resolve().parents[2]
TASKS = Path(__file__).resolve().parent / "tasks"
FETCH = "bash bench/agent/fetch.sh"
FIXTURE_REGISTRY = ROOT / "tests" / "fixtures" / "registry"
FAMILIES = ("in-repo", "cross-repo", "impact")
GIT = ["git", "-c", "user.name=cttp-bench", "-c", "user.email=bench@localhost"]
CTTP = Path(sys.executable).parent / "cttp"


class TaskError(Exception):
    pass


@dataclass(frozen=True)
class Repo:
    """A repository a task is built from: a directory of this repository (copied and committed as
    the base) or a git repository on disk (cloned at `rev`, fetched by `fetch.sh` from `url`)."""

    name: str
    source: Path
    locator: str
    rev: str | None  # commit to check out when `source` is a git repository; None = HEAD
    url: str | None  # where fetch.sh clones it from (informational)

    @property
    def is_git(self) -> bool:
        return (self.source / ".git").exists()

    @property
    def fetched(self) -> bool:
        return self.source.is_dir()


@dataclass(frozen=True)
class Overlay:
    """Files laid over a checkout: a directory of the task, or paths from a commit of its source
    repository."""

    directory: Path | None
    commit: str | None
    paths: tuple[str, ...]


@dataclass(frozen=True)
class LinkCheck:
    """`[grade.link]`: `file` must carry an `is` link that resolves to `target`'s identity."""

    file: str
    target: str


@dataclass(frozen=True)
class WhoCheck:
    """`[grade.who]`: `answer` must name exactly the definitions that use `path#symbol`."""

    answer: str
    path: str
    symbol: str


@dataclass(frozen=True)
class Task:
    name: str
    family: str
    summary: str
    prompt: str
    repo: Repo
    deps: tuple[Repo, ...]
    setup: Overlay | None
    grade: Overlay | None
    solution: Overlay | None
    command: str | None  # the test command: the grader, and the one Bash command the agent may run
    timeout: int  # seconds for the grader
    link: LinkCheck | None
    who: WhoCheck | None
    directory: Path = field(repr=False)

    @property
    def test_command(self) -> str | None:
        return self.command

    @property
    def source(self) -> Path:
        return self.repo.source

    @property
    def locator(self) -> str:
        return self.repo.locator

    @property
    def rev(self) -> str | None:
        return self.repo.rev

    @property
    def fetched(self) -> bool:
        return self.repo.fetched and all(d.fetched for d in self.deps)

    @property
    def needs_index(self) -> bool:
        """The grader itself reads an index (the `who` check), whichever arm ran."""
        return self.who is not None


def _repo(toml: Path, data: dict, name: str) -> Repo:
    try:
        source = data["source"]
        locator = data["locator"]
    except KeyError as e:
        raise TaskError(f"{toml}: repo needs {e}") from e
    if not locator or locator.count("/") != 2:
        raise TaskError(f"{toml}: locator {locator!r} must be host/owner/repo")
    return Repo(
        name=data.get("name", name),
        source=(ROOT / source).resolve(),
        locator=locator,
        rev=data.get("rev"),
        url=data.get("url"),
    )


def _overlay(toml: Path, directory: Path, data: dict | None, section: str) -> Overlay | None:
    if not data:
        return None
    sub = data.get("overlay")
    commit = data.get("commit")
    paths = tuple(data.get("paths", ()))
    if sub is None and commit is None:
        return None
    if sub is not None and commit is not None:
        raise TaskError(f"{toml}: {section} has both an overlay directory and a commit")
    if sub is not None:
        path = directory / sub
        if not path.is_dir():
            raise TaskError(f"{toml}: {section}.overlay {sub!r} is not a directory")
        return Overlay(path, None, ())
    if not paths:
        raise TaskError(f"{toml}: {section}.commit needs paths")
    return Overlay(None, str(commit), paths)


def load_task(directory: Path) -> Task:
    """`task.toml` → Task, every field checked. The source repositories need not be on disk
    (`fetched` says); `prepare_checkout` is what needs them."""
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
    except KeyError as e:
        raise TaskError(f"{toml}: missing {e}") from e
    if name != directory.name:
        raise TaskError(f"{toml}: name {name!r} is not the directory name {directory.name!r}")
    if family not in FAMILIES:
        raise TaskError(f"{toml}: family {family!r} is not one of {', '.join(FAMILIES)}")
    command = grade.get("command")
    link = grade.get("link")
    who = grade.get("who")
    if command is None and link is None and who is None:
        raise TaskError(f"{toml}: grade needs a command, a link check or a who check")
    deps = tuple(_repo(toml, d, d.get("name", "")) for d in data.get("deps", []))
    for d in deps:
        if not d.name:
            raise TaskError(f"{toml}: every dep needs a name")
    return Task(
        name=name,
        family=family,
        summary=data.get("summary", ""),
        prompt=prompt,
        repo=_repo(toml, repo, "repo"),
        deps=deps,
        setup=_overlay(toml, directory, data.get("setup"), "setup"),
        grade=_overlay(toml, directory, grade, "grade"),
        solution=_overlay(toml, directory, data.get("solution"), "solution"),
        command=command,
        timeout=int(grade.get("timeout", 300)),
        link=LinkCheck(link["file"], link["target"]) if link else None,
        who=WhoCheck(who["answer"], who["path"], who["symbol"]) if who else None,
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


def apply_overlay(overlay: Overlay, repo: Repo, dst: Path) -> None:
    """Lay the overlay over `dst`: copy its directory, or write each path as it is at the
    commit of the source repository."""
    if overlay.directory is not None:
        _copy_tree(overlay.directory, dst)
        return
    for rel in overlay.paths:
        proc = _run(["git", "show", f"{overlay.commit}:{rel}"], cwd=repo.source)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(proc.stdout, encoding="utf-8")


@dataclass(frozen=True)
class Clone:
    """One repository of a run: the working clone (the agent's, or a dependency's), the bare
    repository it was cloned from, its commit and its locator."""

    name: str
    path: Path
    remote: Path
    sha: str
    locator: str


@dataclass(frozen=True)
class Checkout:
    """What `prepare_checkout` made: the working clone the agent edits, its bare origin, the
    commit the agent starts from, and the dependency clones beside it."""

    path: Path
    remote: Path
    base_sha: str
    locator: str
    deps: tuple[Clone, ...] = ()

    @property
    def clones(self) -> list[Clone]:
        return [Clone("repo", self.path, self.remote, self.base_sha, self.locator), *self.deps]


def _clone(repo: Repo, work: Path, name: str, setup: Overlay | None, dest: Path) -> Clone:
    """`dest` (a working clone of `repo` at its rev, plus `setup`) and `work/<name>.git` (its
    bare origin)."""
    if not repo.fetched:
        raise TaskError(f"{repo.source} is not on disk; run `{FETCH}` first")
    origin = work / f"{name}.origin"
    origin.mkdir(parents=True)
    if repo.is_git:
        _run(["git", "clone", "--quiet", "--no-local", str(repo.source), str(origin)], cwd=work)
        rev = repo.rev or "HEAD"
        _run(["git", "checkout", "--quiet", "-B", "main", rev], cwd=origin)
    else:
        _copy_tree(repo.source, origin)
        _run(["git", "init", "--quiet", "-b", "main"], cwd=origin)
        _run([*GIT, "add", "-A"], cwd=origin)
        _run([*GIT, "commit", "--quiet", "-m", f"{name}: base"], cwd=origin)
    if setup:
        apply_overlay(setup, repo, origin)
        _run([*GIT, "add", "-A"], cwd=origin)
        if _run(["git", "status", "--porcelain"], cwd=origin).stdout.strip():
            _run([*GIT, "commit", "--quiet", "-m", f"{name}: setup"], cwd=origin)
    remote = work / f"{name}.git"
    _run(["git", "clone", "--quiet", "--bare", str(origin), str(remote)], cwd=work)
    _run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=remote)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "clone", "--quiet", str(remote), str(dest)], cwd=work)
    sha = _run(["git", "rev-parse", "HEAD"], cwd=dest).stdout.strip()
    shutil.rmtree(origin)
    return Clone(name, dest, remote, sha, repo.locator)


def prepare_checkout(task: Task, work: Path) -> Checkout:
    """Build `work/repo` (the checkout the agent edits), `work/remote.git` (its origin), and
    `work/deps/<name>` + `work/<name>.git` for every dependency."""
    if work.exists():
        shutil.rmtree(work)
    main = _clone(task.repo, work, "remote", task.setup, work / "repo")
    deps = tuple(_clone(d, work, d.name, None, work / "deps" / d.name) for d in task.deps)
    return Checkout(
        path=main.path, remote=main.remote, base_sha=main.sha, locator=task.locator, deps=deps
    )


def write_config(work: Path, checkout: Checkout, registries: list[str]) -> Path:
    """A cttp config for this run: the given registries, and every clone's locator mapped to
    its bare remote through `[remotes]` — how `cttp index add` learns a checkout's locator and
    how `resolve <locator>` reaches it without a network."""
    lines = ["registries = ["]
    lines += [f"  {r!r}," for r in registries]
    lines += ["]", "", "[remotes]"]
    lines += [f'"{c.locator}" = "{c.remote}"' for c in checkout.clones]
    lines.append("")
    path = work / "cttp.toml"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def cttp_env(work: Path, config: Path) -> dict[str, str]:
    """The run's own cttp: its config, its index, its cache."""
    return {
        "CTTP_CONFIG": str(config),
        "CTTP_INDEX": str(work / "index.db"),
        "CTTP_HOME": str(work / "cache"),
    }


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


def cttp_json(args: list[str], env: dict[str, str]) -> dict:
    """`cttp <args> --json` in the run's environment; the printed object (an `error` object
    with `exit` on failure)."""
    proc = subprocess.run(
        [str(CTTP), *args, "--json"], capture_output=True, text=True, env=venv_env(env)
    )
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        data = {}
    if proc.returncode != 0:
        data.setdefault("error", proc.stderr.strip() or proc.stdout.strip())
        data["exit"] = proc.returncode
    return data


def prepare_index(checkout: Checkout, env: dict[str, str]) -> dict[str, object]:
    """`cttp index add` for the checkout and every dependency clone, then one `crawl`, into the
    run's own index."""
    out: dict[str, object] = {"add": []}
    for clone in checkout.clones:
        data = cttp_json(["index", "add", str(clone.path)], env)
        if "exit" in data:
            raise TaskError(f"cttp index add {clone.path} failed: {data.get('error')}")
        out["add"].append(data)  # type: ignore[union-attr]
    data = cttp_json(["index", "crawl"], env)
    if "exit" in data:
        raise TaskError(f"cttp index crawl failed: {data.get('error')}")
    out["crawl"] = data
    return out


# --- grading -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Grade:
    passed: bool
    returncode: int | None
    output: str
    timed_out: bool = False
    diff: str = ""  # what the agent changed, against the base commit
    checks: dict[str, object] = field(default_factory=dict)  # the link / who checks' findings


def _run_command(task: Task, checkout: Checkout, env: dict[str, str] | None) -> Grade:
    assert task.command is not None
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
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else ""
        return Grade(False, None, out, timed_out=True)
    return Grade(proc.returncode == 0, proc.returncode, proc.stdout + proc.stderr)


def check_link(check: LinkCheck, checkout: Checkout, env: dict[str, str]) -> dict[str, object]:
    """The cross-repository grader's second half. The file must hold an `is` link whose address
    resolves (through the run's config, so the dependency's bare clone answers) to the same
    identity as `check.target`; a link stamped with an `id=` that is not its page's identity
    fails. The stamp's completeness is recorded (`stamped`), not required: the baseline arm has
    no way to compute an identity hash."""
    result: dict[str, object] = {"file": check.file, "target": check.target, "links": []}
    path = checkout.path / check.file
    if not path.is_file():
        result.update(passed=False, why=f"{check.file} does not exist")
        return result
    try:
        links = [
            link for link in find_links(path.read_text(encoding="utf-8").splitlines())
            if link.relation == "is"
        ]  # fmt: skip
    except LinkError as e:
        result.update(passed=False, why=f"malformed link: {e}")
        return result
    expected = cttp_json(["resolve", check.target], env)
    if "exit" in expected:
        result.update(passed=False, why=f"the target does not resolve: {expected.get('error')}")
        return result
    want = expected["identity_full"]
    result["expected_identity"] = want
    found = False
    wrong_stamp = False
    for link in links:
        row: dict[str, object] = {
            "line": link.line + 1,
            "address": link.address,
            "id": link.fields.get("id"),
        }
        page = cttp_json(["resolve", link.address], env)
        if "exit" in page:
            row["resolves"] = False
            row["error"] = str(page.get("error"))[:300]
        else:
            row["resolves"] = True
            row["identity"] = page["identity_full"]
            row["matches_target"] = page["identity_full"] == want
            found |= bool(row["matches_target"])
            stamp = link.fields.get("id")
            if stamp:
                hexdigest = stamp.removeprefix("sha256:")
                row["stamp_ok"] = page["identity_full"].startswith(hexdigest)
                wrong_stamp |= not row["stamp_ok"]
        result["links"].append(row)  # type: ignore[union-attr]
    result["stamped"] = any(r.get("id") for r in result["links"])  # type: ignore[union-attr]
    result["passed"] = found and not wrong_stamp
    if result["passed"]:
        result["why"] = "ok"
    elif wrong_stamp:
        result["why"] = "a stamp names the wrong identity"
    else:
        result["why"] = "no link resolves to the target"
    return result


def innermost(backlinks: list[dict]) -> set[str]:
    """The definitions `who` found, as `path#symbol`, keeping the innermost: a class whose member
    is also listed is dropped (the class page's references include its methods'), and file pages
    (a module that imports the target) are left out."""
    pairs = {
        (b["source"]["path"], b["source"]["symbol"]) for b in backlinks if b["source"].get("symbol")
    }
    out = set()
    for path, symbol in pairs:
        if any(p == path and s.startswith(symbol + ".") for p, s in pairs):
            continue
        out.add(f"{path}#{symbol}")
    return out


def parse_answer(text: str) -> set[str]:
    """One `path#symbol` per line; blank lines, `#` comments and list bullets are ignored."""
    out = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for bullet in ("- ", "* ", "• "):
            if line.startswith(bullet):
                line = line[len(bullet) :].strip()
        line = line.strip("`")
        if line:
            out.add(line)
    return out


def check_who(check: WhoCheck, checkout: Checkout, env: dict[str, str]) -> dict[str, object]:
    """The impact grader: the answer file names exactly the innermost definitions `cttp who`
    finds for the target at the checkout's commit, on the run's index."""
    address = f"{checkout.locator}@{checkout.base_sha}/{check.path}#{check.symbol}"
    result: dict[str, object] = {"address": address, "answer_file": check.answer}
    who = cttp_json(["who", address], env)
    if "exit" in who:
        result.update(passed=False, why=f"who failed: {who.get('error')}")
        return result
    expected = innermost(who["backlinks"])
    result["who_count"] = who["count"]
    result["expected"] = sorted(expected)
    path = checkout.path / check.answer
    if not path.is_file():
        result.update(passed=False, why=f"{check.answer} does not exist", answer=[])
        return result
    answer = parse_answer(path.read_text(encoding="utf-8", errors="replace"))
    result["answer"] = sorted(answer)
    result["missing"] = sorted(expected - answer)
    result["extra"] = sorted(answer - expected)
    result["passed"] = answer == expected
    result["why"] = (
        "ok"
        if result["passed"]
        else f"{len(result['missing'])} missing, {len(result['extra'])} extra"  # type: ignore[arg-type]
    )
    return result


def grade(task: Task, checkout: Checkout, env: dict[str, str] | None = None) -> Grade:
    """Overlay the hidden tests and run the task's command in the checkout (pass = exit 0), then
    the link and who checks the task asks for. `env` carries the run's cttp variables; the
    checks need them."""
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
        apply_overlay(task.grade, task.repo, checkout.path)
    if task.command is not None:
        g = _run_command(task, checkout, env)
    else:
        g = Grade(True, None, "")
    checks: dict[str, object] = {}
    passed = g.passed
    if not g.timed_out:
        cttp_vars = {k: v for k, v in (env or {}).items() if k.startswith("CTTP_")}
        if task.link is not None:
            checks["link"] = check_link(task.link, checkout, cttp_vars)
            passed &= bool(checks["link"]["passed"])  # type: ignore[index]
        if task.who is not None:
            checks["who"] = check_who(task.who, checkout, cttp_vars)
            passed &= bool(checks["who"]["passed"])  # type: ignore[index]
    return Grade(passed, g.returncode, g.output, g.timed_out, diff, checks)


def prepare_run(
    task: Task, work: Path, registries: list[str] | None = None
) -> tuple[Checkout, dict[str, str]]:
    """Checkout, config and environment for one run or one grader check; the index too when
    the grader needs it (the links arm indexes in any case — see the harness). With no
    registries given, the fixture registry stands in: a config needs at least one."""
    checkout = prepare_checkout(task, work / "w")
    config = write_config(work, checkout, registries or [str(FIXTURE_REGISTRY)])
    env = cttp_env(work, config)
    if task.needs_index:
        prepare_index(checkout, env)
    return checkout, env


def check_grader(task: Task, work: Path) -> dict[str, object]:
    """The P8-T2 acceptance for one task: the grader fails the unmodified checkout and passes
    the reference solution."""
    result: dict[str, object] = {"task": task.name}
    if not task.fetched:
        result.update(ok=False, why=f"source repository not on disk; run `{FETCH}`")
        return result
    checkout, env = prepare_run(task, work / "unmodified")
    before = grade(task, checkout, venv_env(env))
    result["unmodified"] = {"passed": before.passed, "returncode": before.returncode}
    if task.solution is None:
        result["solution"] = None
        result["ok"] = not before.passed
        result["why"] = "no solution overlay" if result["ok"] else "unmodified checkout passes"
        return result
    checkout, env = prepare_run(task, work / "solved")
    apply_overlay(task.solution, task.repo, checkout.path)
    after = grade(task, checkout, venv_env(env))
    result["solution"] = {"passed": after.passed, "returncode": after.returncode}
    result["checks"] = {"unmodified": before.checks, "solution": after.checks}
    result["ok"] = (not before.passed) and after.passed
    result["why"] = (
        "ok"
        if result["ok"]
        else ("unmodified checkout passes" if before.passed else "reference solution fails")
    )
    if not result["ok"]:
        failed = before if before.passed else after
        result["output"] = failed.output[-2000:]
        result["failed_checks"] = failed.checks
    return result
