"""Plan P7-T3: `cttp serve --export <dir>` writes every route of the contract for every name as
static files identical to the live responses, so a static host (cttp.ai) is a registry."""

import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from cttp.cli import app as cli
from cttp.config import Config, load_config
from cttp.registry import HttpRegistry, Registries
from cttp.resolve import resolve
from cttp.schemas import validate
from cttp.server.app import app
from cttp.server.export import export, routes_for

runner = CliRunner()


def test_export_is_the_live_responses_byte_for_byte(registry, tmp_path):
    from conftest import add_to_registry

    add_to_registry(tmp_path, "greet", 'print("hi")\n', "Says hi.")
    site = tmp_path / "site"
    out = export(site, Registries(load_config(), local_only=True))
    assert out.names == ["greet", "hello-world"]
    routes = [f.route for f in out.files]
    assert routes == [
        "/", "/greet", "/greet.json", "/greet@latest.json",
        "/hello-world", "/hello-world.json", "/hello-world@latest.json",
    ]  # fmt: skip
    paths = {f.route: f.path for f in out.files}
    assert paths["/"] == Path("index.html") and paths["/greet"] == Path("greet/index.html")
    assert paths["/hello-world@latest.json"] == Path("hello-world@latest.json")
    live = TestClient(app)
    for f in out.files:
        assert (site / f.path).read_bytes() == live.get(f.route).content, f.route
        assert f.bytes == (site / f.path).stat().st_size
    body = json.loads((site / "hello-world.json").read_text(encoding="utf-8"))
    assert validate("resolve", body) == [] and body["identity"] == "sha256:75a27070015e"
    assert "hello-world" in (site / "index.html").read_text(encoding="utf-8")


def test_a_static_host_serving_the_export_is_a_registry(registry, tmp_path):
    """An HttpRegistry over the exported directory answers what the local registry answers."""
    site = tmp_path / "site"
    export(site, Registries(load_config(), local_only=True))

    def serve(request: httpx.Request) -> httpx.Response:
        rel = request.url.path.lstrip("/")
        f = site / (rel or "index.html")
        if f.is_dir():
            f = f / "index.html"
        if not f.exists():
            return httpx.Response(404, json={"detail": f"{rel} is not here"})
        ctype = "application/json" if f.suffix == ".json" else "text/html"
        return httpx.Response(200, content=f.read_bytes(), headers={"content-type": ctype})

    cfg = load_config()
    static = Registries(Config(("https://cttp.ai", *cfg.registries), cfg.remotes, cfg.path))
    static.items[0] = HttpRegistry(
        "https://cttp.ai", client=httpx.Client(transport=httpx.MockTransport(serve))
    )
    remote = resolve("hello-world", static)
    local = resolve("hello-world", registry)
    assert remote.registry == "https://cttp.ai"
    assert remote.to_json() | {"registry": local.registry} == local.to_json()
    assert resolve("hello-world@latest", static).rev == local.rev
    # a name the static site lacks falls through to the next registry, as the contract says
    from conftest import add_to_registry

    add_to_registry(tmp_path, "later", 'print("later")\n')
    assert resolve("later", static).registry != "https://cttp.ai"


def test_serve_export_cli(registry, tmp_path):
    res = runner.invoke(cli, ["--json", "serve", "--export", str(tmp_path / "out")])
    assert res.exit_code == 0, res.output
    body = json.loads(res.stdout)
    assert validate("serve --export", body) == []
    assert body["count"] == 4 and body["names"] == ["hello-world"]
    assert (tmp_path / "out" / "hello-world" / "index.html").exists()
    text = runner.invoke(cli, ["serve", "--export", str(tmp_path / "out2")]).output
    assert "4 file(s) for 1 name(s)" in text
    # --registry picks the registry to export
    out3, reg = str(tmp_path / "out3"), str(tmp_path / "registry")
    res = runner.invoke(cli, ["--json", "serve", "--export", out3, "--registry", reg])
    assert res.exit_code == 0 and json.loads(res.stdout)["names"] == ["hello-world"]
    assert len(routes_for(Registries(load_config()))) == 4


def test_the_default_registry_list_is_cttp_ai_first(tmp_path, monkeypatch):
    monkeypatch.setenv("CTTP_CONFIG", str(tmp_path / "c.toml"))
    monkeypatch.delenv("CTTP_REGISTRY", raising=False)
    assert load_config().registries[:2] == ("https://cttp.ai", "http://localhost:3120")
