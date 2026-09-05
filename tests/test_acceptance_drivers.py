"""Spec §12 acceptance test 1, plan P6-T2: the index rediscovers the duplicates of the Linux
driver corpus with no hint. Needs the corpus fetched (`bench/drivers/fetch.sh`); crawling it takes
about two minutes, so the test is `slow` and deselected by default: `uv run pytest -m slow`."""

import json
from pathlib import Path

import pytest

from cttp.index.crawl import add, crawl
from cttp.index.queries import dups
from cttp.index.schema import open_index

BENCH = Path(__file__).resolve().parent.parent / "bench" / "drivers"
CORPUS = BENCH / "corpus"
EXPECTED = json.loads((BENCH / "expected.json").read_text(encoding="utf-8"))

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not (CORPUS / ".git").exists(), reason="the corpus is not fetched (bench/drivers/fetch.sh)"
    ),
]


def places(group: dict) -> set[str]:
    return {f"{loc['path']}#{loc['symbol']}" for loc in group["locations"]}


def test_the_index_rediscovers_the_duplicates(registry, tmp_path, monkeypatch):
    # a blobless clone must never reach for a blob it does not have: block every git protocol
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "none")
    conn = open_index(tmp_path / "drivers.db")
    added = add(conn, str(CORPUS), registry.config)
    assert added["repo"] == EXPECTED["corpus"]["repository"]
    assert added["default_branch"] == EXPECTED["corpus"]["tag"]  # a detached HEAD, named by tag
    [crawled] = crawl(conn, registry)
    assert crawled.status == "crawled" and crawled.sha == EXPECTED["corpus"]["commit"]
    assert crawled.skipped == []
    c_files = conn.execute(
        "SELECT count(*) FROM locations WHERE symbol IS NULL AND path LIKE '%.c'"
    ).fetchone()[0]
    assert c_files == EXPECTED["corpus"]["c_files"]  # the sparse checkout, nothing beyond it

    by_shape = dups(conn, by_shape=True)["groups"]
    by_identity = dups(conn)["groups"]
    for expected in EXPECTED["groups"]:
        groups = by_shape if expected["by"] == "shape" else by_identity
        want = set(expected["locations"])
        found = [g for g in groups if places(g) == want]
        assert found, f"no {expected['by']} group is exactly {sorted(want)}: {expected['what']}"
