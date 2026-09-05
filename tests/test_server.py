from fastapi.testclient import TestClient

from cttp.server.app import app


def test_registry_contract(registry):
    c = TestClient(app)
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
