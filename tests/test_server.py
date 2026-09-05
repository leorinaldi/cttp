import json

import httpx
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from cttp.cli import app as cli
from cttp.config import Config, load_config
from cttp.registry import HttpRegistry, Registries, RegistryError
from cttp.resolve import resolve
from cttp.server.app import app

runner = CliRunner()


@pytest.fixture
def client(registry) -> TestClient:
    return TestClient(app)


@pytest.fixture
def via_http(client, config_file) -> Registries:
    """Registries whose first entry is an HTTP registry talking to the app in-process."""
    cfg = load_config()
    regs = Registries(Config(("http://testserver", *cfg.registries), cfg.remotes, cfg.path))
    assert isinstance(regs.items[0], HttpRegistry)
    regs.items[0] = HttpRegistry("http://testserver", client=client)
    return regs


def test_registry_contract(client):
    c = client
    j = c.get("/hello-world.json")
    assert j.status_code == 200
    body = j.json()
    assert body["source"] == 'print("hello world!")\n' and body["license"] == "MIT"
    assert c.get("/hello-world@latest.json").json()["rev"] == body["rev"]
    page = c.get("/hello-world")
    assert page.status_code == 200 and "print(&#34;hello world!&#34;)" in page.text
    assert "asserted" in page.text and "derived" in page.text
    missing = c.get("/no-such-name.json")
    assert missing.status_code == 404 and "no-such-name" in missing.json()["detail"]
    assert c.get("/").status_code == 200 and "hello-world" in c.get("/").text


def test_http_registry_answers_first(via_http, registry):
    local = resolve("hello-world", registry)
    remote = resolve("hello-world", via_http)
    assert remote.registry == "http://testserver" and local.registry != remote.registry
    assert remote.to_json() | {"registry": local.registry} == local.to_json()
    assert resolve("hello-world@v1", via_http).rev == local.rev
    assert resolve(local.address, via_http).identity == local.identity


def test_http_miss_falls_through_and_names_both(via_http):
    with pytest.raises(RegistryError, match=r"(?s)any registry asked.*testserver.*registry") as e:
        resolve("no-such-name", via_http)
    assert str(e.value).count("no-such-name") >= 3  # the summary and each registry's reason


def test_http_bad_answers_are_errors(client, config_file):
    reg = HttpRegistry("http://testserver", client=client)
    with pytest.raises(RegistryError, match="not a name in registry http://testserver"):
        reg.fetch("no-such-name", None)
    with pytest.raises(RegistryError, match="not a name in registry"):
        reg.fetch("hello-world", "no-such-ref")
    html = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<p>")))
    with pytest.raises(RegistryError, match="answered 200, not a resolution"):
        HttpRegistry("http://x", client=html).fetch("hello-world", None)
    with pytest.raises(RegistryError, match=r"http://x/hello-world.json answered 500"):
        HttpRegistry(
            "http://x",
            client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500))),
        ).fetch("hello-world", None)


def test_serve_cli_never_asks_http(config_file):
    """`cttp serve` opens local registries only, so a config with itself first cannot recurse."""
    cfg = load_config()
    both = Config(("http://localhost:3120", *cfg.registries), cfg.remotes, cfg.path)
    assert [type(x).__name__ for x in Registries(both, local_only=True).items] == ["LocalRegistry"]
    with pytest.raises(RegistryError, match="no usable registry"):
        Registries(Config(("http://localhost:3120",)), local_only=True)


def test_resolve_json_is_the_same_with_the_server_up_or_down(via_http, registry):
    up = resolve("hello-world", via_http).to_json()
    down = resolve("hello-world", registry).to_json()
    assert up.pop("registry") == "http://testserver"
    assert down.pop("registry") == registry.items[0].describe()
    assert up == down
    cli_out = json.loads(runner.invoke(cli, ["--json", "resolve", "hello-world"]).stdout)
    cli_out.pop("registry")
    assert cli_out == down
