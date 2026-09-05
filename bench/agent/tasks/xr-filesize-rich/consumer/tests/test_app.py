from app import human_size


def test_kilobytes():
    assert human_size(1500) == "1.5 kB"
