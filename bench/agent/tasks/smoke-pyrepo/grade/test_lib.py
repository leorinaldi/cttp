from lib import deep, left, right, top


def test_top_adds_the_siblings():
    assert top(3) == 9


def test_each_link_of_the_chain():
    assert deep(3) == 6
    assert left(3) == 4
    assert right(3) == 5
