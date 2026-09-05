from pathlib import Path

import pytest

from cttp.registry import LocalRegistry, create_local_registry

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocalRegistry:
    """A local registry repository in tmp_path, with caches redirected there too."""
    monkeypatch.setenv("CTTP_HOME", str(tmp_path / "cache"))
    reg = create_local_registry(tmp_path / "registry", FIXTURES / "registry")
    monkeypatch.setenv("CTTP_REGISTRY", str(reg))
    return LocalRegistry(reg)
