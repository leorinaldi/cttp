import inspect

import app
from app import human_size


def test_kilobytes():
    assert human_size(1500) == "1.5 kB"


def test_small_sizes_are_bytes():
    assert human_size(1) == "1 byte"
    assert human_size(999) == "999 bytes"


def test_precision_and_larger_units():
    assert human_size(30000, precision=2) == "30.00 kB"
    assert human_size(10**9) == "1.0 GB"
    assert human_size(2_500_000_000_000) == "2.5 TB"


def test_rich_is_not_imported():
    source = inspect.getsource(app)
    assert "import rich" not in source and "from rich" not in source
