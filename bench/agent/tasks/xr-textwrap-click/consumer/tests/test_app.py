from app import wrap


def test_wrap_fills_a_paragraph():
    text = "the quick brown fox jumps over the lazy dog and keeps on running"
    assert wrap(text, 24) == "the quick brown fox\njumps over the lazy dog\nand keeps on running"
