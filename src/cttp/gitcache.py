"""The git cache: bare clones under ~/.cache/cttp/repos/<host>/<owner>/<repo>. Spec §5.

Plain `git` does everything: `clone --bare` and `fetch` bring a repository in, `rev-parse` turns a
tag or branch into a SHA, `cat-file` reads a blob at a rev, `ls-tree` enumerates one. The license
is derived from the `LICENSE*` / `COPYING*` file at the rev by a small SPDX matcher; a file that
matches nothing is `None` — "not available" — never its first line.
"""

import os
import re
import subprocess
from pathlib import Path

from cttp.address import is_sha

LICENSE_FILE_RE = re.compile(r"^(LICEN[CS]E|COPYING)(\.[A-Za-z0-9]+)?$", re.IGNORECASE)

# SPDX id → the phrases that identify the license text, all of which must appear. Versioned
# licenses are recognized by their title, in the head of the file (a preamble may come first),
# because their bodies quote other licenses: the MPL cites the GPL and LGPL, the GPL the AGPL
# and LGPL. The GNU family is told apart by which of its titles comes first. BSD-3 is tried
# before BSD-2 because it contains it.
HEAD = 2000  # characters of normalized text that hold a title, preamble included
SPDX_PHRASES: list[tuple[str, tuple[str, ...], bool]] = [
    ("Apache-2.0", ("apache license", "version 2.0"), True),
    ("MPL-2.0", ("mozilla public license", "2.0"), True),
    ("GPL-3.0", ("gnu general public license", "version 3"), True),
    ("GPL-2.0", ("gnu general public license", "version 2"), True),
    (
        "MIT",
        ("permission is hereby granted, free of charge, to any person obtaining a copy",),
        False,
    ),
    (
        "ISC",
        ("permission to use, copy, modify, and/or distribute this software for any purpose",),
        False,
    ),
    (
        "BSD-3-Clause",
        ("redistribution and use in source and binary forms", "neither the name"),
        False,
    ),
    ("BSD-2-Clause", ("redistribution and use in source and binary forms",), False),
]
GNU_TITLES = (
    "gnu general public license",
    "gnu lesser general public license",
    "gnu affero general public license",
)


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
        _clone(url, dest)
    return dest


def _clone(url: str, dest: Path) -> None:
    """Clone into a sibling temporary directory and move it into place, so two callers cloning
    one repository at once (the MCP server answering `resolve` and `closure` in the same turn)
    both end with a whole clone at `dest`, and a crash never leaves a half clone there."""
    import shutil
    import tempfile

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():  # a half clone from a crash — no HEAD, so nothing to keep
        shutil.rmtree(dest)
    tmp = Path(tempfile.mkdtemp(prefix=f".{dest.name}-", dir=dest.parent))
    try:
        target = tmp / "clone"
        _git("clone", "--bare", "--quiet", url, str(target))
        try:
            os.rename(target, dest)
        except OSError:
            if not (dest / "HEAD").exists():  # not another caller's clone: a real failure
                raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _has_commit(repo: Path, sha: str) -> bool:
    try:
        rev_parse(repo, sha)
    except GitError:
        return False
    return True


def default_branch(repo: Path) -> str:
    """The branch a bare clone's HEAD points at — the origin's default branch when it was cloned."""
    try:
        return _git("symbolic-ref", "--short", "HEAD", cwd=repo).strip()
    except GitError:
        return "main"


def rev_parse(repo: Path, ref: str) -> str:
    return _git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", cwd=repo).strip()


def show(repo: Path, sha: str, path: str) -> str:
    """The blob at `path` in the tree at `sha`."""
    return _git("cat-file", "blob", f"{sha}:{path}", cwd=repo)


def license_of(repo: Path, sha: str) -> str | None:
    """Derived: the SPDX id of the repository's license file at `sha`; None when there is no
    license file, or none that the matcher knows."""
    names = _git("ls-tree", "--name-only", sha, cwd=repo).split("\n")
    for name in sorted(n for n in names if LICENSE_FILE_RE.match(n)):
        if found := spdx_of(show(repo, sha, name)):
            return found
    return None


def spdx_of(text: str) -> str | None:
    """The SPDX id of a license text, by its identifying phrases; None when unrecognized."""
    flat = " ".join(text.lower().split())
    head = flat[:HEAD]
    gnu = {t: head.find(t) for t in GNU_TITLES if t in head}
    gpl_title = min(gnu, key=gnu.get) == GNU_TITLES[0] if gnu else False
    for spdx, phrases, in_head in SPDX_PHRASES:
        if spdx.startswith("GPL"):
            if not gpl_title:
                continue  # the LGPL and AGPL name the GPL in their preambles; not this
            where = head[gnu[GNU_TITLES[0]] :]  # the version follows the title
        else:
            where = head if in_head else flat
        if all(phrase in where for phrase in phrases):
            return spdx
    return None


def ls_tree(repo: Path, sha: str) -> list[str]:
    """Every file path in the repository at `sha`."""
    return _git("ls-tree", "-r", "--name-only", sha, cwd=repo).split("\n")[:-1]
