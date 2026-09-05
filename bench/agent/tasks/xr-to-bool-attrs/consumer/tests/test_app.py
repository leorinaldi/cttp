from app import env_flag


def test_yes_is_true(monkeypatch):
    monkeypatch.setenv("FLAG", "yes")
    assert env_flag("FLAG") is True
