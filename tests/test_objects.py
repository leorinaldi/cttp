"""The object cache and identity resolution (plan P2-T2)."""

import json
import shutil

import pytest
from typer.testing import CliRunner

from cttp import objects
from cttp.cli import app
from cttp.resolve import ResolveError, resolve

runner = CliRunner()
LOCATOR = "github.com/leorinaldi/thermo@v1/src/thermo/decode.py#reg_to_millicelsius"


def test_every_resolution_is_stored_by_identity(registry):
    r = resolve("hello-world", registry)
    stored = objects.lookup(r.identity_full)
    assert stored and stored.source == r.source and stored.meta["kind"] == "script"
    (at,) = stored.locations
    assert (
        at["address"] == f"github.com/leorinaldi/cttp-registry@{r.rev[:12]}/snippets/hello_world.py"
    )
    assert at["name"] == "hello-world" and at["license"] == "MIT" and at["seen"].endswith("Z")
    # the same page seen through its locator is the same location, refreshed, not a second one
    resolve(at["address"], registry)
    assert len(objects.lookup(r.identity).locations) == 1


def test_an_identity_resolves_from_the_cache_after_the_origin_is_gone(registry, tmp_path):
    original = resolve(LOCATOR, registry)
    shutil.rmtree(tmp_path / "remotes" / "github.com" / "leorinaldi" / "thermo")  # the origin
    shutil.rmtree(tmp_path / "cache" / "repos")  # and the git cache
    with pytest.raises(Exception):  # noqa: B017 — nothing but the object cache can answer now
        resolve(LOCATOR, registry)
    for text in (f"sha256:{original.identity_full}", original.identity):  # full, and 12-hex
        r = resolve(text, registry)
        assert r.source == original.source and r.identity_full == original.identity_full
        assert r.address == original.address and r.symbol == "reg_to_millicelsius"
        assert r.signature == original.signature and r.license == "MIT" and r.rev == original.rev
        assert r.via == "cache"
        (at,) = r.locations
        assert at["address"] == original.address and at["origin"] == "cache"
        assert r.to_json()["origin"]["location"] == "cache"
    assert original.to_json()["origin"]["location"] == "repository"


def test_an_unknown_identity_says_who_was_asked(registry):
    res = runner.invoke(app, ["resolve", "sha256:" + "f" * 12])
    assert res.exit_code == 1
    assert "known to neither the object cache nor the index" in res.output


def test_an_ambiguous_prefix_lists_the_candidates(registry):
    for tail in ("1", "2"):
        identity = "abc123abc123" + tail * 52
        (objects.objects_dir()).mkdir(parents=True, exist_ok=True)
        (objects.objects_dir() / identity).write_text("x = 1\n")
        (objects.objects_dir() / f"{identity}.json").write_text(json.dumps({"locations": []}))
    with pytest.raises(objects.AmbiguousIdentity, match="prefix of 2 cached identities") as e:
        objects.lookup("abc123abc123")
    assert [c[:13] for c in e.value.candidates] == ["abc123abc1231", "abc123abc1232"]
    with pytest.raises(
        ResolveError, match="say which: sha256:abc123abc1231111, sha256:abc123abc1232"
    ):
        resolve("sha256:abc123abc123", registry)
    assert objects.lookup("abc123abc1231").identity.endswith("1")


def test_cache_status_and_clear(registry, tmp_path):
    resolve("hello-world", registry)
    res = runner.invoke(app, ["cache", "status", "--json"])
    st = json.loads(res.stdout)
    assert st["home"] == str(tmp_path / "cache")
    assert st["repos"]["count"] == 1 and st["objects"]["count"] == 1 and st["run"]["count"] == 0
    assert st["repos"]["bytes"] > 0 and st["objects"]["bytes"] > 0
    text = runner.invoke(app, ["cache", "status"]).output
    assert "repos: 1" in text and "objects: 1" in text
    res = runner.invoke(app, ["cache", "clear"])
    assert res.exit_code == 0 and "removed" in res.output
    st = json.loads(runner.invoke(app, ["cache", "status", "--json"]).stdout)
    assert st["repos"]["count"] == 0 and st["objects"]["count"] == 0
    assert runner.invoke(app, ["cache", "clear"]).output.strip() == "nothing to remove"


def test_cli_resolve_shows_where_an_identity_was_seen(registry):
    r = resolve("hello-world", registry)
    res = runner.invoke(app, ["resolve", r.identity])
    assert res.exit_code == 0
    assert "(from the object cache; seen at 1 location(s))" in res.output
    assert "# seen: github.com/leorinaldi/cttp-registry@" in res.output
    body = json.loads(runner.invoke(app, ["resolve", r.identity, "--json"]).stdout)
    assert body["via"] == "cache" and body["locations"][0]["origin"] == "cache"
