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


# --- the viewer over the index (plan P4-T4) ----------------------------------------------------


@pytest.fixture
def crawled(client, registry, tmp_path):
    """pyrepo and a consumer of hello-world crawled into the test index."""
    from conftest import add_remote_repo, clone_remote, commit_in

    from cttp.index.crawl import add, crawl
    from cttp.index.schema import open_index

    add_remote_repo(tmp_path, "consumer", {"README.md": "consumer\n"})
    work = clone_remote(tmp_path, "consumer")
    (work / "hello.py").write_text(
        "# cttp: hello-world\n\n# cttp: github.com/leorinaldi/pyrepo@v1/lib.py#deep\n",
        encoding="utf-8",
    )
    assert runner.invoke(cli, ["expand", str(work / "hello.py")]).exit_code == 0
    commit_in(work, "hello")
    conn = open_index(tmp_path / "index.db")
    for target in ("github.com/leorinaldi/pyrepo", "github.com/leorinaldi/cttp-registry", work):
        add(conn, str(target), registry.config)
    crawl(conn, registry)
    return conn


def test_pages_say_so_without_an_index(client):
    page = client.get("/hello-world")
    assert page.status_code == 200 and "No index yet" in page.text
    assert "Derived — from the code" in page.text and "Asserted — by people" in page.text
    assert client.get("/dups").status_code == 200 and "No index at" in client.get("/dups").text
    assert client.get("/?q=greet").status_code == 200
    assert client.get("/d/75a27070015e").status_code == 404
    assert client.get("/r/github.com/leorinaldi/pyrepo").status_code == 404


def test_name_page_shows_the_copy_under_who_links_here(client, crawled, registry):
    page = client.get("/hello-world")
    assert page.status_code == 200
    html = page.text
    who = html[html.index("Who links here") :]
    assert "consumer" in who and "hello.py" in who
    row = who[who.index("<tr>", who.index("</tr>")) :]  # the first backlink row
    assert '<code>is</code><span class="tag asserted">asserted</span>' in row
    assert 'sha256:75a27070015e</code></a><span class="tag derived">derived</span>' in row
    assert "History" in html and "cttp-registry@" in html[html.index("History") :]


def test_definition_repo_dups_and_search_pages(client, crawled, registry):
    ident = resolve("github.com/leorinaldi/pyrepo@v1/lib.py#deep", registry).identity_full
    d = client.get(f"/d/{ident[:12]}")
    assert d.status_code == 200 and "def deep" in d.text and "Seen at" in d.text
    assert "lib.py#deep" in d.text and "Who links here" in d.text and "lib.py#right" in d.text
    assert client.get("/d/sha256:" + ident[:12]).status_code == 200
    assert client.get("/d/" + "0" * 12).status_code == 404
    r = client.get("/r/github.com/leorinaldi/pyrepo")
    assert r.status_code == 200 and "Revisions crawled" in r.text and "many.py" in r.text
    assert "MIT" in r.text and f"/d/{ident[:12]}" in r.text
    assert client.get("/r/github.com/leorinaldi/nope").status_code == 404
    dups = client.get("/dups")
    assert dups.status_code == 200 and "deep" in dups.text  # the consumer's copy of deep
    assert "consumer@" in dups.text and "pyrepo@" in dups.text
    assert client.get("/dups?shape=1").status_code == 200
    s = client.get("/?q=bottom chain")
    assert s.status_code == 200 and "lib.py#deep" in s.text and "search: bottom chain" in s.text
    assert "No page in the index matches" in client.get("/?q=zzzz").text
    home = client.get("/")
    assert "3 revision(s)" not in home.text and "revision(s) crawled" in home.text
