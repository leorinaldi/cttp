import ast
import inspect

import pytest

import app
from app import env_flag


def test_yes_is_true(monkeypatch):
    monkeypatch.setenv("FLAG", "yes")
    assert env_flag("FLAG") is True


@pytest.mark.parametrize("value", ["true", "T", "Yes", "y", "ON", "1"])
def test_true_spellings(monkeypatch, value):
    monkeypatch.setenv("FLAG", value)
    assert env_flag("FLAG") is True


@pytest.mark.parametrize("value", ["false", "F", "No", "n", "OFF", "0"])
def test_false_spellings(monkeypatch, value):
    monkeypatch.setenv("FLAG", value)
    assert env_flag("FLAG") is False


def test_unset_gives_the_default(monkeypatch):
    monkeypatch.delenv("FLAG", raising=False)
    assert env_flag("FLAG") is False
    assert env_flag("FLAG", default=True) is True


def test_anything_else_is_an_error(monkeypatch):
    monkeypatch.setenv("FLAG", "maybe")
    with pytest.raises(ValueError):
        env_flag("FLAG")


def test_attrs_is_not_imported():
    """The library must not be imported — the point is to reuse the code, not depend
    on it. Parsed rather than grepped: a substring check also matches an attribution
    comment naming the library, which is exactly what a cttp link block carries."""
    banned = {"attr", "attrs"}
    tree = ast.parse(inspect.getsource(app))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in banned, alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in banned, node.module
