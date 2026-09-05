"""The tree-sitter extractor for C (plan P6-T1): definitions, spans, signatures, the comment
above, identity and shape, links in C comments, the crawl and the queries over a C repository."""

import json
from pathlib import Path

import pytest
from conftest import add_remote_repo, commit_to_remote
from typer.testing import CliRunner

from cttp.cli import app
from cttp.extract import ExtractError, definitions, extract, language_of
from cttp.extract import treesitter as ts
from cttp.hashing import ShapeError, identity, shape, shape_text
from cttp.index.crawl import add, crawl
from cttp.index.queries import dups, search, who
from cttp.index.schema import open_index
from cttp.resolve import ResolveError, latest, resolve
from cttp.schemas import validate

runner = CliRunner()
CREPO = "github.com/leorinaldi/crepo"
SENSOR = f"{CREPO}@main/src/sensor.c"
FIXTURES = Path(__file__).parent / "fixtures" / "crepo"
CORPUS = Path(__file__).resolve().parent.parent / "bench" / "drivers" / "corpus" / "drivers"

DECODER = """static inline long reg_to_mc(s16 temp, u8 resolution)
{
\treturn ((temp >> (16 - resolution)) * 1000) >> (resolution - 8);
}
"""


def resolve_json(address: str) -> dict:
    res = runner.invoke(app, ["resolve", address, "--json"])
    assert res.exit_code == 0, res.output
    body = json.loads(res.stdout)
    assert not validate("resolve", body)
    return body


# --- definitions -------------------------------------------------------------------------------


def test_c_and_headers_have_the_c_extractor():
    assert language_of("drivers/hwmon/lm75.c") == "c" and language_of("lm75.h") == "c"
    assert language_of("README.md") == "text" and language_of("x.py") == "python"


def test_every_kind_of_definition_in_source_order():
    src = (FIXTURES / "src" / "sensor.c").read_text(encoding="utf-8")
    assert definitions("src/sensor.c", src) == [
        "SENSOR_REG_CONF",  # a macro
        "enum.sensor_type",  # a tagged type: struct.<tag>, enum.<tag>, union.<tag>
        "struct.sensor_data",
        "sensor_t",  # a typedef
        "sample_times",  # a table: a declaration with an initializer
        "reg_to_mc",
        "sensor_alloc",  # returns a pointer: the name is under a pointer_declarator
        "main",  # after MODULE_DEVICE_TABLE(…), which the grammar does not know
    ]
    header = (FIXTURES / "include" / "sensor.h").read_text(encoding="utf-8")
    # a prototype is a declaration, not a definition; guards and typedefs are
    assert definitions("include/sensor.h", header) == [
        "SENSOR_H", "SENSOR_REG_TEMP", "REG_TO_MC", "s16", "u8",
    ]  # fmt: skip


# (symbol, kind, span, signature, the comment above)
PAGES = [
    ("SENSOR_REG_CONF", "macro", [6, 6], "SENSOR_REG_CONF", "The sensor's registers"),
    ("enum.sensor_type", "type", [8, 11], "enum sensor_type", None),
    ("struct.sensor_data", "type", [13, 16], "struct sensor_data", None),
    ("sensor_t", "type", [18, 18], "typedef struct sensor_data sensor_t", None),
    ("sample_times", "constant", [20, 20], "static const int sample_times[]", None),
    ("reg_to_mc", "function", [29, 32], "static inline long reg_to_mc(s16 temp, u8 resolution)",
     "reg_to_mc - convert a raw register word to millidegrees Celsius"),  # kernel-doc summary
    ("sensor_alloc", "function", [35, 42],
     "static struct sensor_data *sensor_alloc(int resolution)",
     None),  # the comment above it is a link line, not a description
    ("main", "function", [46, 52], "int main(void)", None),
]  # fmt: skip


@pytest.mark.parametrize("symbol,kind,span,signature,doc", PAGES)
def test_each_page_exact(registry, symbol, kind, span, signature, doc):
    j = resolve_json(f"{SENSOR}#{symbol}")
    assert j["kind"] == kind and j["language"] == "c" and j["symbol"] == symbol
    assert j["span"] == span and j["signature"] == signature and j["docstring"] == doc
    assert j["shape"] is not None and j["refs"] == [] and j["unresolved"] == []
    assert j["imports"] == {"stdlib": [], "third_party": [], "statements": []}
    lines = (FIXTURES / "src" / "sensor.c").read_text(encoding="utf-8").split("\n")
    assert j["source"].rstrip("\n") == "\n".join(lines[span[0] - 1 : span[1]])
    assert j["address"].endswith(f"/src/sensor.c#{symbol}")


def test_the_macro_with_parameters_and_its_own_text():
    header = (FIXTURES / "include" / "sensor.h").read_text(encoding="utf-8")
    page = extract("include/sensor.h", header, "REG_TO_MC")
    assert page.kind == "macro" and page.signature == "REG_TO_MC(reg)"
    assert page.source == "#define REG_TO_MC(reg) (((reg) >> 7) * 500)\n"


def test_an_unknown_symbol_lists_the_definitions(registry):
    with pytest.raises(ResolveError, match="definitions: SENSOR_REG_CONF, enum.sensor_type"):
        resolve(f"{SENSOR}#sensor_data", registry)  # the tag is `struct.sensor_data`
    with pytest.raises(ExtractError, match="not a definition"):
        extract("a.c", "int x;\n", "x")  # a declaration without an initializer


def test_a_whole_c_file_is_a_script_page_with_a_shape(registry):
    j = resolve_json(SENSOR)
    assert j["kind"] == "script" and j["language"] == "c" and j["symbol"] is None
    assert j["span"] == [1, 52] and j["shape"] is not None and j["signature"] is None
    # its own text: the two link lines taken out (spec §4), as for a Python script page
    assert "cttp-see" not in j["source"] and "int main(void)" in j["source"]
    assert [(k["relation"], k["line"]) for k in j["links"]] == [("see", 34), ("see", 37)]
    h = resolve_json(f"{CREPO}@main/include/sensor.h")
    assert h["language"] == "c" and h["shape"] is not None


def test_links_in_c_comments_belong_to_the_definition_holding_them(registry):
    page = resolve(f"{SENSOR}#sensor_alloc", registry)
    (link,) = page.links
    assert link["relation"] == "see" and link["address"].endswith("include/sensor.h#REG_TO_MC")
    assert link["line"] == 3  # 1-based, within the page's own text
    assert resolve(f"{SENSOR}#reg_to_mc", registry).links == []


# --- identity and shape ------------------------------------------------------------------------


def test_the_same_function_in_two_files_is_one_identity(registry):
    a = resolve(f"{SENSOR}#reg_to_mc", registry)
    b = resolve(f"{CREPO}@main/src/twin.c#reg_to_mc", registry)
    assert a.identity_full == b.identity_full == identity(DECODER)
    assert a.shape_full == b.shape_full and a.source == DECODER


def test_two_functions_differing_only_in_identifiers_and_literals_are_one_shape(registry):
    a = resolve(f"{SENSOR}#reg_to_mc", registry)
    c = resolve(f"{CREPO}@main/src/other.c#raw_to_millic", registry)
    d = resolve(f"{CREPO}@main/src/other.c#reordered", registry)
    assert a.identity_full != c.identity_full
    assert a.shape_full == c.shape_full  # names, literals and the comment inside differ
    assert d.shape_full != a.shape_full  # the statements differ


def test_the_shape_text_of_c():
    words = shape_text(DECODER, "c")
    assert words == (
        "static inline long $0 ( $1 $2 , $3 $4 ) { return ( ( $2 >> ( <num> - $4 ) ) * <num> ) "
        ">> ( $4 - <num> ) ; }"
    )
    # comments are dropped; a macro body is tokenized too, keywords kept
    assert shape_text("/* x */ #define F(a) ((a) + sizeof(int) * 2) // y\n", "c") == (
        "#define $0 ( $1 ) ( ( $1 ) + sizeof ( int ) * <num> )"
    )
    assert shape_text('char *s = "a" "b";\n', "c") == "char * $0 = <str> ;"
    assert shape("int x = 1;\n", "c") == shape("long y = 2;\n".replace("long", "int"), "c")
    assert shape("int x = 1;\n", "c") != shape("long y = 2;\n", "c")  # `long` is a keyword
    with pytest.raises(ShapeError, match="no extractor"):
        shape_text("anything", "text")


def test_tokens_carry_rows_for_a_line_level_measurement():
    toks = ts.tokens("c", "int a = 1;\n\nint b = 2; // c\n")
    assert [(r, t) for r, _, t in toks] == [
        (0, "int"), (0, "a"), (0, "="), (0, "<num>"), (0, ";"),
        (2, "int"), (2, "b"), (2, "="), (2, "<num>"), (2, ";"),
    ]  # fmt: skip
    assert ts.shape_words(toks) == ["int", "$0", "=", "<num>", ";", "int", "$1", "=", "<num>", ";"]


def test_the_first_of_two_definitions_of_one_symbol_wins():
    src = "#ifdef A\nint f(void) { return 1; }\n#else\nint f(void) { return 2; }\n#endif\n"
    assert definitions("a.c", src) == ["f"]
    assert extract("a.c", src, "f").span == (2, 2)


# --- the index -------------------------------------------------------------------------------


@pytest.fixture
def crawled(registry, tmp_path):
    conn = open_index(tmp_path / "index.db")  # CTTP_INDEX points here (conftest)
    add(conn, CREPO, registry.config)
    [r] = crawl(conn, registry)
    return conn, r


def test_the_crawl_indexes_every_c_definition(registry, crawled):
    conn, r = crawled
    # 4 file pages + 5 (sensor.h) + 8 (sensor.c) + 2 (twin.c) + 2 (other.c); README has no link
    assert r.pages == 4 + 5 + 8 + 2 + 2 and r.skipped == []
    assert r.definitions == r.pages - 1  # reg_to_mc twice is one identity
    assert r.links == 2
    rows = conn.execute("SELECT path, symbol, span_first FROM locations ORDER BY path, span_first")
    places = [tuple(x) for x in rows]
    assert ("src/sensor.c", "reg_to_mc", 29) in places and ("src/twin.c", "reg_to_mc", 5) in places
    kinds = {k for (k,) in conn.execute("SELECT DISTINCT kind FROM definitions")}
    assert kinds == {"script", "function", "constant", "type", "macro"}


def test_dups_find_the_copies_and_the_near_copies(registry, crawled):
    conn, _ = crawled
    (group,) = [g for g in dups(conn)["groups"] if g["names"] == ["reg_to_mc"]]
    assert sorted(loc["path"] for loc in group["locations"]) == ["src/sensor.c", "src/twin.c"]
    (group,) = [g for g in dups(conn, by_shape=True)["groups"] if len(g["locations"]) == 3]
    assert sorted((loc["path"], loc["symbol"]) for loc in group["locations"]) == [
        ("src/other.c", "raw_to_millic"),
        ("src/sensor.c", "reg_to_mc"),
        ("src/twin.c", "reg_to_mc"),
    ]


def test_who_links_to_a_macro_from_a_c_comment(registry, crawled):
    conn, _ = crawled
    result = who(conn, f"{CREPO}@main/include/sensor.h#REG_TO_MC", registry)
    (link,) = result["backlinks"]
    assert link["relation"] == "see" and link["line"] == 37
    assert link["source"]["path"] == "src/sensor.c" and link["source"]["symbol"] == "sensor_alloc"
    result = who(conn, "hello-world", registry)
    (link,) = [b for b in result["backlinks"] if b["source"]["path"] == "src/sensor.c"]
    assert link["line"] == 34 and link["source"]["symbol"] == "sensor_alloc"  # the block beneath


def test_search_finds_a_c_function_by_its_comment(registry, crawled):
    conn, _ = crawled
    hits = search(conn, "millidegrees")
    (hit,) = hits["hits"]  # one identity, seen in two files
    assert sorted((x["path"], x["symbol"]) for x in hit["locations"]) == [
        ("src/sensor.c", "reg_to_mc"),
        ("src/twin.c", "reg_to_mc"),
    ]


def test_latest_follows_a_moved_c_function_by_identity(registry, tmp_path):
    pinned = resolve(f"{SENSOR}#reg_to_mc", registry).address
    sensor = (FIXTURES / "src" / "sensor.c").read_text(encoding="utf-8")
    commit_to_remote(
        tmp_path,
        "crepo",
        {"src/sensor.c": sensor.replace(DECODER, ""), "src/decode.c": DECODER},
        "move the decoder",
    )
    found = latest(pinned, registry)
    assert found.found and found.rule == "same-identity"
    assert found.to.path in ("src/decode.c", "src/twin.c") and found.to.symbol == "reg_to_mc"


# --- the corpus: plan P6-T1's acceptance ---------------------------------------------------------


@pytest.mark.slow
@pytest.mark.skipif(not (CORPUS / "hwmon" / "lm75.c").exists(), reason="the corpus is not fetched")
def test_the_lm75_decoder_from_the_corpus(registry, tmp_path):
    files = {
        f"drivers/hwmon/{n}": (CORPUS / "hwmon" / n).read_text(encoding="utf-8")
        for n in ("lm75.c", "lm75.h")
    }
    locator = add_remote_repo(tmp_path, "linux", files)
    j = resolve_json(f"{locator}@main/drivers/hwmon/lm75.c#lm75_reg_to_mc")
    lines = files["drivers/hwmon/lm75.c"].split("\n")
    first = lines.index("static inline long lm75_reg_to_mc(s16 temp, u8 resolution)") + 1
    assert j["span"] == [first, first + 3] and j["kind"] == "function"
    assert j["signature"] == "static inline long lm75_reg_to_mc(s16 temp, u8 resolution)"
    assert j["origin"]["shape"] == "derived" and j["source"].endswith("(resolution - 8);\n}\n")
    assert j["shape_full"] == shape(DECODER, "c")  # the fixture's decoder is this one, renamed
    assert len(definitions("lm75.c", files["drivers/hwmon/lm75.c"])) > 40
