from lib import top


def test_top_adds_the_siblings():
    # left(3) + right(3) = 4 + 5
    assert top(3) == 9
