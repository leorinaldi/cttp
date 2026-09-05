"""The git cache: bare clones under ~/.cache/cttp/repos/<host>/<owner>/<repo>. Spec §5."""

import os
import subprocess
from pathlib import Path

from cttp.address import is_sha

LICENSE_FILES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")
# Spike: a first line → SPDX id map. P2-T1 brings a real matcher.
LICENSE_FIRST_LINES = {"MIT License": "MIT", "Apache License": "Apache-2.0"}


class GitError(RuntimeError):
    pass


def home() -> Path:
    return Path(os.environ.get("CTTP_HOME", str(Path.home() / ".cache" / "cttp")))


def repos_dir() -> Path:
    return home() / "repos"


def _git(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def ensure_repo(locator: str, url: str, want: str | None = None) -> Path:
    """Clone `url` as a bare repo for `locator`, or fetch it if already cached.

    A fetch is skipped when `want` is a commit SHA the cache already has: pinned addresses never
    move, so `check` on an expanded file needs no network once the repository is cached.
    """
    dest = repos_dir() / locator
    if (dest / "HEAD").exists():
        if want and is_sha(want) and _has_commit(dest, want):
            return dest
        _git(
            "fetch",
            "--quiet",
            url,
            "+refs/heads/*:refs/heads/*",
            "+refs/tags/*:refs/tags/*",
            cwd=dest,
        )
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        _git("clone", "--bare", "--quiet", url, str(dest))
    return dest


def _has_commit(repo: Path, sha: str) -> bool:
    try:
        rev_parse(repo, sha)
    except GitError:
        return False
    return True


def rev_parse(repo: Path, ref: str) -> str:
    return _git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", cwd=repo).strip()


def show(repo: Path, sha: str, path: str) -> str:
    return _git("show", f"{sha}:{path}", cwd=repo)


def license_of(repo: Path, sha: str) -> str | None:
    """Derived: the repository's license, from its license file; None when there is none."""
    names = set(_git("ls-tree", "--name-only", sha, cwd=repo).split())
    for candidate in LICENSE_FILES:
        if candidate in names:
            first = show(repo, sha, candidate).strip().split("\n", 1)[0].strip()
            return LICENSE_FIRST_LINES.get(first, first or None)
    return None


def ls_tree(repo: Path, sha: str) -> list[str]:
    """Every file path in the repository at `sha`."""
    return _git("ls-tree", "-r", "--name-only", sha, cwd=repo).split("\n")[:-1]
