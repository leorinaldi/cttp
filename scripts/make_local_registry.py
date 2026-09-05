"""Create a local registry repository from tests/fixtures/registry (no network).

The normal way is a clone of the real one:
    git clone https://github.com/leorinaldi/cttp-registry ~/.local/share/cttp/registry

Usage: uv run python scripts/make_local_registry.py [dest]   (default ~/.local/share/cttp/registry)
"""

import sys
from pathlib import Path

from cttp.config import default_registry_path
from cttp.registry import create_local_registry

if __name__ == "__main__":
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else default_registry_path()
    files = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "registry"
    print(create_local_registry(dest, files))
