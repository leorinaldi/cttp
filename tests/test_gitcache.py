"""The git cache in full (plan P2-T1): fetch, tags to SHAs, blobs, trees, the license matcher."""

import subprocess

import pytest
from conftest import add_remote_repo

from cttp import gitcache
from cttp.gitcache import GitError, spdx_of

MIT = (
    "MIT License\n\nCopyright (c) 2026 Leo\n\nPermission is hereby granted, free of charge, to any "
    "person obtaining a copy of this software..."
)
APACHE = "Apache License\nVersion 2.0, January 2004\nhttp://www.apache.org/licenses/\n\nTERMS..."
BSD3 = (
    "Copyright (c) 2026 Leo. Redistribution and use in source and binary forms, with or without "
    "modification, are permitted provided that... 3. Neither the name of the copyright holder..."
)
BSD2 = (
    "Copyright (c) 2026 Leo. Redistribution and use in source and binary forms, with or without "
    "modification, are permitted provided that the following conditions are met: 1. ... 2. ..."
)
GPL2 = (
    "GNU GENERAL PUBLIC LICENSE\nVersion 2, June 1991\n\nCopyright (C) 1989, 1991 Free Software..."
)
GPL2_WITH_PREAMBLE = (  # git's COPYING: a note, then the text
    "Note that the only valid version of the GPL as far as this project is concerned is _this_ "
    "particular version of the license (ie v2, not v2.2 or v3.x or whatever), unless explicitly "
    "otherwise stated.\n\n" + GPL2
)
GPL3 = (
    "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n\n... 13. Use with the GNU Affero "
    "General Public License. ... the GNU General Public License, version 2 ..."
)
LGPL = (  # its preamble names the GPL: not a GPL match
    "GNU LESSER GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n\nThis version of the GNU Lesser "
    "General Public License incorporates the terms and conditions of version 3 of the GNU General "
    "Public License, supplemented by the additional permissions listed below."
)
AGPL = (
    "GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3, 19 November 2007\n\nThe GNU Affero General "
    "Public License is a free, copyleft license... It is a modified version of the ordinary GNU "
    "General Public License..."
)
MPL = (
    "Mozilla Public License Version 2.0\n\n1. Definitions\n... 1.12. Secondary License means "
    "either the GNU General Public License, Version 2.0, the GNU Lesser General Public License..."
)
ISC = (
    "ISC License\n\nCopyright (c) 2026 Leo\n\nPermission to use, copy, modify, and/or distribute "
    "this software for any purpose with or without fee is hereby granted..."
)


@pytest.mark.parametrize(
    ("text", "spdx"),
    [
        (MIT, "MIT"),
        (APACHE, "Apache-2.0"),
        (BSD3, "BSD-3-Clause"),
        (BSD2, "BSD-2-Clause"),
        (GPL2, "GPL-2.0"),
        (GPL2_WITH_PREAMBLE, "GPL-2.0"),
        (GPL3, "GPL-3.0"),
        (MPL, "MPL-2.0"),
        (ISC, "ISC"),
        (LGPL, None),  # not in the matcher: not available, never a guess
        (AGPL, None),
        ("Copyright 2011 Pallets\n\nSome license nobody wrote down.", None),
        ("", None),
    ],
)
def test_spdx_matcher(text, spdx):
    assert spdx_of(text) == spdx


def test_license_of_a_repository(registry, tmp_path):
    mit = add_remote_repo(tmp_path, "mit", {"LICENSE": MIT, "a.py": "x = 1\n"})
    none = add_remote_repo(tmp_path, "none", {"a.py": "x = 1\n"})
    odd = add_remote_repo(tmp_path, "odd", {"COPYING.txt": GPL2, "license.md": "unknown"})
    for locator, expected in ((mit, "MIT"), (none, None), (odd, "GPL-2.0")):
        repo = gitcache.ensure_repo(locator, registry.url_for(locator))
        assert gitcache.license_of(repo, gitcache.rev_parse(repo, "main")) == expected, locator


def test_tags_and_branches_resolve_to_shas_and_blobs_read_at_a_rev(registry, tmp_path):
    locator = add_remote_repo(tmp_path, "tagged", {"a.py": "x = 1\n"})
    repo = gitcache.ensure_repo(locator, registry.url_for(locator), want="v1")
    sha = gitcache.rev_parse(repo, "v1")
    assert len(sha) == 40 and gitcache.rev_parse(repo, "main") == sha
    assert gitcache.rev_parse(repo, sha[:12]) == sha
    assert gitcache.show(repo, sha, "a.py") == "x = 1\n"
    assert gitcache.ls_tree(repo, sha) == ["a.py"]
    with pytest.raises(GitError):
        gitcache.rev_parse(repo, "no-such-ref")
    with pytest.raises(GitError):
        gitcache.show(repo, sha, "missing.py")


def test_a_fetch_brings_a_new_commit_and_a_cached_sha_needs_none(registry, tmp_path):
    locator = add_remote_repo(tmp_path, "moving", {"a.py": "x = 1\n"})
    repo = gitcache.ensure_repo(locator, registry.url_for(locator))
    first = gitcache.rev_parse(repo, "main")
    # the origin moves on
    src = tmp_path / "moving"
    (src / "a.py").write_text("x = 2\n")
    git = ["git", "-c", "user.name=cttp", "-c", "user.email=cttp@localhost"]
    subprocess.run([*git, "commit", "-qam", "bump"], cwd=src, check=True)
    subprocess.run(
        ["git", "push", "-q", str(tmp_path / "remotes/github.com/leorinaldi/moving"), "main"],
        cwd=src,
        check=True,
    )
    # a branch always fetches; the pinned SHA is answered from the cache without one
    gitcache.ensure_repo(locator, registry.url_for(locator), want="main")
    second = gitcache.rev_parse(repo, "main")
    assert second != first and gitcache.show(repo, second, "a.py") == "x = 2\n"
    url_that_would_fail = "file:///nowhere"
    assert gitcache.ensure_repo(locator, url_that_would_fail, want=first) == repo
    with pytest.raises(GitError):
        gitcache.ensure_repo(locator, url_that_would_fail, want="main")


def test_no_test_connects_a_socket():
    import socket

    with pytest.raises(RuntimeError, match="never connect sockets"), socket.socket() as s:
        s.connect(("127.0.0.1", 1))


def test_two_callers_cloning_one_repository_at_once_both_get_it(registry, tmp_path):
    """The MCP server answers `resolve` and `closure` from one turn concurrently; the second
    clone used to fail with "destination path already exists"."""
    from concurrent.futures import ThreadPoolExecutor

    locator = add_remote_repo(tmp_path, "raced", {"a.py": "x = 1\n"})
    url = registry.url_for(locator)
    with ThreadPoolExecutor(4) as pool:
        repos = list(pool.map(lambda _: gitcache.ensure_repo(locator, url), range(4)))
    assert len(set(repos)) == 1 and (repos[0] / "HEAD").exists()
    assert gitcache.show(repos[0], gitcache.rev_parse(repos[0], "main"), "a.py") == "x = 1\n"
    assert [p.name for p in repos[0].parent.iterdir()] == ["raced"]  # no temp dirs left
