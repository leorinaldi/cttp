"""The link convention in full (plan P1-T4): three markers, fields, `~`, stacks, the block, any
comment syntax."""

from pathlib import Path

import pytest

from cttp.expand import check_file, expand_file
from cttp.links import LinkError, find_links, format_stamped, parse_link

LM75 = Path(__file__).parent.parent / "bench/drivers/corpus/drivers/hwmon/lm75.c"

SPEC_4_LINES = [  # every example line in spec §4, byte for byte
    "# cttp: hello-world",
    "# cttp: hello-world@8f4c2e1d9a03 id=sha256:7f3a9c1e42b8  \"Prints 'hello world'.\"",
    '# cttp: greet@8f4c2e1d9a03 id=sha256:7f3a9c1e42b8  ~"def greet(name: str) -> str — Return a '
    'greeting."',
    "# cttp: hello-world@8f4c2e1d9a03 id=sha256:7f3a9c1e42b8 license=MIT track=latest",
    "# cttp-from: hello-world@8f4c2e1d9a03 id=sha256:7f3a9c1e42b8",
    "# cttp-see: hello-world",
]


def test_short_form():
    link = parse_link(3, "# cttp: hello-world")
    assert link and link.address == "hello-world" and not link.stamped
    assert link.line == 3 and link.indent == "" and link.description is None
    assert link.relation == "is" and link.comment == "#"


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


@pytest.mark.parametrize("line", SPEC_4_LINES)
def test_spec_4_lines_round_trip(line):
    link = parse_link(0, line)
    assert link is not None and link.format() == line


def test_fields_keep_order_and_arbitrary_keys():
    link = parse_link(0, "# cttp: x id=sha256:a license=MIT track=latest note=see-issue-12")
    assert link.fields == {
        "id": "sha256:a",
        "license": "MIT",
        "track": "latest",
        "note": "see-issue-12",
    }
    assert link.format() == "# cttp: x id=sha256:a license=MIT track=latest note=see-issue-12"


def test_three_relations_in_one_file():
    lines = [
        "# cttp-see: lm75-datasheet",  # above a module docstring line
        '"""Read an LM75."""',
        "# cttp-from: leo.thermo#reg_to_millicelsius",
        "def reg_to_c(reg):",
        "    return reg >> 7",
        "# cttp: hello-world",
    ]
    links = find_links(lines)
    assert [(k.line, k.relation, k.address) for k in links] == [
        (0, "see", "lm75-datasheet"),
        (2, "from", "leo.thermo#reg_to_millicelsius"),
        (5, "is", "hello-world"),
    ]


def test_non_links_are_ignored():
    for line in ["print('# cttp: no')", "", "# comment", "x = 1  # cttp: trailing", "# cttps: x"]:
        assert parse_link(0, line) is None, line
    assert parse_link(0, "#cttp:hello-world").address == "hello-world"  # spacing is free


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("// cttp-see: hello-world", ("//", "see")),
        ("-- cttp: hello-world", ("--", "is")),
        ("; cttp-from: hello-world", (";", "from")),
        (";; cttp: hello-world", (";;", "is")),
        ('/* cttp: hello-world@8f4c2e1d9a03 id=sha256:7f3a9c1e42b8  "Prints." */', ("/*", "is")),
        ("\t# cttp: hello-world", ("#", "is")),
    ],
)
def test_one_expression_finds_a_link_in_any_comment_syntax(line, expected):
    link = parse_link(0, line)
    assert link and (link.comment, link.relation) == expected
    assert link.address.startswith("hello-world") and link.format() == line.lstrip("\t")


def test_a_c_file_from_the_corpus_yields_one_link():
    if not LM75.exists():
        pytest.skip("the driver corpus is fetched, not committed")
    lines = LM75.read_text().split("\n")
    assert find_links(lines) == [], "the driver has no links of its own"
    lines.insert(1, "// cttp-see: leo.thermo#LM75")
    (link,) = find_links(lines)
    assert (link.line, link.relation, link.address, link.comment) == (
        1,
        "see",
        "leo.thermo#LM75",
        "//",
    )


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("# cttp: x license=MIT License", "field `license`"),
        ("# cttp: x oops", "after the address"),
        ("# cttp: x id=sha256:a id=sha256:b", "field `id` given twice"),
        ('# cttp: x "desc" id=1', "the description is the only quoted field"),
        ("# cttp:", "no address"),
        ("/* cttp: x", "must close on the same line"),
        ("# cttp: x 1st=no", "not a field name"),
    ],
)
def test_malformed_links_are_errors_naming_the_part(line, message):
    with pytest.raises(LinkError, match=message) as e:
        parse_link(4, line)
    assert str(e.value).startswith("line 5:")


def test_find_links_keeps_line_numbers():
    lines = ["x = 1", "# cttp: a", "print(x)", "  # cttp: b@1 id=sha256:2"]
    found = find_links(lines)
    assert [(k.line, k.address) for k in found] == [(1, "a"), (3, "b@1")]


def test_the_block_ends_at_a_blank_line_before_a_non_indented_line():
    lines = [
        "# cttp: greet@1 id=sha256:2",
        "def greet(name):",
        "    if name:",
        "",  # a blank inside the definition does not end it
        "        return name",
        "    return 'you'",
        "",
        "",
        "print(greet('x'))",  # the user's code: not part of the block
        "# cttp: hello-world@1 id=sha256:2",
        'print("hello world!")',
        "",
    ]
    first, second = find_links(lines)
    assert (first.start, first.end) == (1, 6) and first.block(lines) == lines[1:6]
    assert (second.start, second.end) == (10, 11)


def test_the_block_ends_at_the_next_link_line_and_at_eof():
    lines = ["# cttp: a@1 id=sha256:2", "x = 1", "# cttp-see: b", "y = 2", "", ""]
    a, b = find_links(lines)
    assert a.block(lines) == ["x = 1"]
    assert b.block(lines) == ["y = 2"]  # trailing blanks are never part of a block
    (last,) = find_links(["# cttp: a@1 id=sha256:2"])
    assert last.block(["# cttp: a@1 id=sha256:2"]) == []


def test_indentation_is_relative_to_the_link():
    lines = [
        "class A:",
        "    # cttp: m@1 id=sha256:2",
        "    def m(self):",
        "        pass",
        "",
        "    def other(self):",  # same indent as the link: ends the block
        "        pass",
    ]
    (link,) = find_links(lines)
    assert link.block(lines) == lines[2:4]


def test_stacked_links_share_the_block():
    lines = ["# cttp-see: docs", "# cttp: greet@1 id=sha256:2", "def greet():", "    pass"]
    see, is_ = find_links(lines)
    assert see.block(lines) == is_.block(lines) == lines[2:]


def test_format_stamped_round_trips():
    line = format_stamped("hello-world@d29352a4fbf1", "75a27070015e", "Prints 'hello world'.")
    assert (
        line == "# cttp: hello-world@d29352a4fbf1 id=sha256:75a27070015e  \"Prints 'hello world'.\""
    )
    back = parse_link(0, line)
    assert (
        back.address == "hello-world@d29352a4fbf1" and back.description == "Prints 'hello world'."
    )
    assert (
        format_stamped(f"n@{'a' * 12}", "b" * 12, None)
        == f"# cttp: n@{'a' * 12} id=sha256:{'b' * 12}"
    )
    derived = format_stamped("g@" + "a" * 12, "b" * 12, 'def g() — Say "hi".', derived=True)
    assert derived.endswith("  ~\"def g() — Say 'hi'.\"")  # a description cannot carry a quote
    assert format_stamped("x@" + "a" * 12, "b" * 12, None, comment="//").startswith("// cttp: x@")


def test_format_stamped_locator():
    line = format_stamped("github.com/leo/thermo@" + "a" * 12 + "/src/a.py", "b" * 12, None)
    back = parse_link(0, line)
    assert (
        back and back.stamped and back.address == "github.com/leo/thermo@" + "a" * 12 + "/src/a.py"
    )


# --- through expand and check ---------------------------------------------------------------


def test_user_code_after_an_expanded_link_is_not_drift(registry, tmp_path):
    f = tmp_path / "use.py"
    f.write_text("# cttp: hello-world\nprint('after')\n")
    expand_file(f, registry)
    lines = f.read_text().split("\n")
    assert lines[1:] == ['print("hello world!")', "", "print('after')", ""]
    assert [r.status for r in check_file(f, registry)] == ["ok"]
    # expanding again changes nothing
    assert [r.status for r in expand_file(f, registry)] == ["unchanged"]
    assert lines == f.read_text().split("\n")


def test_from_and_see_links_are_resolved_but_never_hashed(registry, tmp_path):
    f = tmp_path / "fork.py"
    f.write_text(
        "# cttp-see: hello-world\n"
        "# cttp-from: hello-world\n"
        "print('a fork, edited freely')\n"
        "# cttp-see: no-such-name\n"
        "# cttp: hello-world\n"
    )
    reports = expand_file(f, registry)
    assert [(r.relation, r.status) for r in reports] == [
        ("see", "unchanged"),
        ("from", "unchanged"),
        ("see", "unchanged"),
        ("is", "expanded"),
    ]
    assert "print('a fork, edited freely')" in f.read_text()
    reports = check_file(f, registry)
    assert [(r.relation, r.status) for r in reports] == [
        ("see", "ok"),
        ("from", "ok"),
        ("see", "unresolvable"),
        ("is", "ok"),
    ]
    assert reports[1].to_json()["relation"] == "from"


def test_a_stack_expands_beneath_the_whole_stack(registry, tmp_path):
    f = tmp_path / "stack.py"
    f.write_text("# cttp: hello-world\n# cttp-see: docs\nprint('after')\n")
    expand_file(f, registry)
    lines = f.read_text().split("\n")
    assert lines[0].startswith("# cttp: hello-world@") and lines[1] == "# cttp-see: docs"
    assert lines[2:] == ['print("hello world!")', "", "print('after')", ""]
    assert [r.status for r in check_file(f, registry)][0] == "ok"


def test_a_malformed_link_is_an_error_through_the_cli(registry, tmp_path):
    from typer.testing import CliRunner

    from cttp.cli import app

    f = tmp_path / "bad.py"
    f.write_text("x = 1\n# cttp: hello-world license=MIT License\n")
    res = CliRunner().invoke(app, ["check", str(f)])
    assert res.exit_code == 1 and "line 2: unexpected `License` after field `license`" in res.output
