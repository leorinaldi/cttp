from cttp.links import find_links, format_stamped, parse_link


def test_short_form():
    link = parse_link(3, "# cttp: hello-world")
    assert link and link.address == "hello-world" and not link.stamped
    assert link.line == 3 and link.indent == "" and link.description is None


def test_stamped_form_with_description():
    line = "    # cttp: hello-world@d29352a4fbf1 id=sha256:75a27070015e  \"Prints 'hello world'.\""
    link = parse_link(0, line)
    assert link.stamped and link.address == "hello-world@d29352a4fbf1"
    assert link.fields == {"id": "sha256:75a27070015e"}
    assert link.description == "Prints 'hello world'." and not link.description_derived
    assert link.indent == "    "


def test_derived_description_marker():
    link = parse_link(0, '# cttp: x@abc id=sha256:def ~"first line of the docstring"')
    assert link.description_derived and link.description == "first line of the docstring"


def test_non_links_are_ignored():
    for line in ["print('# cttp: no')", "# cttp-see: later", "#cttp:", "", "# comment"]:
        assert parse_link(0, line) is None, line
    assert parse_link(0, "#cttp:hello-world").address == "hello-world"  # spacing is free


def test_find_links_keeps_line_numbers():
    lines = ["x = 1", "# cttp: a", "print(x)", "  # cttp: b@1 id=sha256:2"]
    found = find_links(lines)
    assert [(k.line, k.address) for k in found] == [(1, "a"), (3, "b@1")]


def test_format_stamped_round_trips():
    line = format_stamped("hello-world", "d29352a4fbf1", "75a27070015e", "Prints 'hello world'.")
    assert (
        line == "# cttp: hello-world@d29352a4fbf1 id=sha256:75a27070015e  \"Prints 'hello world'.\""
    )
    back = parse_link(0, line)
    assert (
        back.address == "hello-world@d29352a4fbf1" and back.description == "Prints 'hello world'."
    )
    assert (
        format_stamped("n", "a" * 12, "b" * 12, None)
        == f"# cttp: n@{'a' * 12} id=sha256:{'b' * 12}"
    )
