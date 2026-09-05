"""The Python extractor in full (plan P1-T3), through `cttp resolve <locator>#<symbol> --json`."""

import json

import pytest
from conftest import add_to_registry
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from cttp.cli import app
from cttp.expand import check_file, expand_file
from cttp.extract import ExtractError, extract
from cttp.resolve import ResolveError, resolve
from cttp.server.app import app as server

runner = CliRunner()

THERMO = "github.com/leorinaldi/thermo"
DECODE = f"{THERMO}@main/src/thermo/decode.py"
LM75 = f"{THERMO}@main/src/thermo/lm75.py"


def resolve_json(address: str) -> dict:
    res = runner.invoke(app, ["resolve", address, "--json"])
    assert res.exit_code == 0, res.output
    return json.loads(res.stdout)


# (address, kind, span, signature, first docstring line)
DEFINITIONS = [
    (f"{DECODE}#decode_cached", "function", [21, 24], "decode_cached(reg: int) -> int",
     "Memoized `reg_to_millicelsius`."),  # decorated: the span starts at the decorator
    (f"{DECODE}#read_async", "function", [27, 31], "async read_async(bus, address: int) -> int",
     "Read the temperature register, then convert it."),
    (f"{LM75}#LM75", "class", [11, 31], "LM75", "An LM75 on an I2C bus."),
    (f"{LM75}#LM75.read_temp", "function", [24, 27], "read_temp(self) -> float",
     "The temperature in degrees Celsius."),
    (f"{LM75}#LM75.ADDRESS", "constant", [17, 17], "ADDRESS", None),
    (f"{LM75}#LM75.RESOLUTION", "constant", [18, 18], "RESOLUTION: float", None),
    (f"{DECODE}#STEP_MILLICELSIUS", "constant", [8, 8], "STEP_MILLICELSIUS: int", None),
    (f"{DECODE}#REG_BITS", "constant", [7, 7], "REG_BITS", None),
]  # fmt: skip


@pytest.mark.parametrize("address, kind, span, signature, docstring", DEFINITIONS)
def test_definitions_have_exact_span_signature_and_docstring(
    registry, address, kind, span, signature, docstring
):
    j = resolve_json(address)
    assert (j["kind"], j["span"], j["signature"], j["docstring"]) == (
        kind,
        span,
        signature,
        docstring,
    )
    assert j["symbol"] == address.split("#")[1] and j["language"] == "python"
    assert j["address"] == address.replace("@main", "@" + j["rev"][:12])
    assert j["identity"].startswith("sha256:") and j["shape"].startswith("sha256:")
    assert j["origin"]["shape"] == "derived" and j["origin"]["refs"] == "derived"


def test_definition_source_is_the_span_dedented(registry):
    r = resolve(f"{LM75}#LM75.read_temp", registry)
    assert r.source == (
        "def read_temp(self) -> float:\n"
        '    """The temperature in degrees Celsius."""\n'
        "    raw = self.bus.read_word_data(self.address, 0)\n"
        "    return reg_to_millicelsius(raw) / 1000\n"
    )
    decorated = resolve(f"{DECODE}#decode_cached", registry)
    assert decorated.source.startswith("@functools.lru_cache(maxsize=256)\ndef decode_cached(")
    assert resolve(f"{LM75}#LM75.ADDRESS", registry).source == "ADDRESS = DEFAULT_ADDRESS\n"


def test_a_nested_function_is_not_addressable(registry):
    with pytest.raises(
        ResolveError, match="'inner'.*nested inside 'make_decoder'.*not addressable"
    ):
        resolve(f"{DECODE}#inner", registry)
    res = runner.invoke(app, ["resolve", f"{DECODE}#nope"])
    assert res.exit_code == 1
    assert "'nope' is not a definition" in res.output and "reg_to_millicelsius" in res.output


def test_derived_references_name_the_sibling_modules_locator(registry):
    j = resolve_json(f"{LM75}#LM75.read_temp")
    rev = j["rev"][:12]
    assert j["refs"] == [
        {
            "address": f"{THERMO}@{rev}/src/thermo/decode.py#reg_to_millicelsius",
            "relation": "ref",
            "origin": "derived",
        }
    ]
    # references within the same file, through an alias (`from . import decode`), and to a class
    step = resolve_json(f"{LM75}#LM75.step")
    assert [r["address"] for r in step["refs"]] == [
        f"{THERMO}@{rev}/src/thermo/decode.py#STEP_MILLICELSIUS"
    ]
    cls = resolve_json(f"{LM75}#LM75")
    assert [r["address"].split("/src/thermo/")[1] for r in cls["refs"]] == [
        "lm75.py#DEFAULT_ADDRESS",
        "decode.py#reg_to_millicelsius",
        "decode.py#STEP_MILLICELSIUS",
    ]
    reg = resolve_json(f"{DECODE}#reg_to_millicelsius")
    assert [r["address"].split("#")[1] for r in reg["refs"]] == ["REG_BITS", "STEP_MILLICELSIUS"]


def test_imports_outside_the_repository_are_split_into_stdlib_and_third_party(registry):
    # the whole file: everything it imports
    assert resolve_json(DECODE)["imports"] == {
        "stdlib": ["asyncio", "functools", "struct"],
        "third_party": [],
    }
    assert resolve_json(LM75)["imports"] == {"stdlib": [], "third_party": ["smbus2"]}
    # a definition: only what it uses
    assert resolve_json(f"{DECODE}#read_async")["imports"] == {
        "stdlib": ["asyncio", "struct"],
        "third_party": [],
    }
    assert resolve_json(f"{DECODE}#decode_cached")["imports"]["stdlib"] == ["functools"]
    assert resolve_json(f"{LM75}#LM75.__init__")["imports"]["third_party"] == ["smbus2"]
    assert resolve_json(f"{LM75}#LM75.read_temp")["imports"] == {
        "stdlib": [],
        "third_party": [],
    }
    # the package's __init__ references both modules of the package, nothing outside it
    init = resolve_json(f"{THERMO}@main/src/thermo/__init__.py")
    assert init["kind"] == "script" and init["imports"] == {"stdlib": [], "third_party": []}
    assert [r["address"].split("/src/thermo/")[1] for r in init["refs"]] == [
        "decode.py#reg_to_millicelsius",
        "lm75.py#LM75",
    ]


def test_a_whole_file_is_a_script_and_a_non_python_file_has_no_shape(registry):
    j = resolve_json(LM75)
    assert j["kind"] == "script" and j["symbol"] is None and j["signature"] is None
    assert j["span"] == [1, 31] and j["shape"] is not None
    readme = resolve_json(f"{THERMO}@main/README.md")
    assert readme["language"] == "text" and readme["shape"] is None and readme["refs"] == []
    with pytest.raises(ResolveError, match="not Python"):
        resolve(f"{THERMO}@main/README.md#x", registry)


def test_name_form_with_a_symbol_through_a_registry_entry(registry, tmp_path):
    add_to_registry(
        tmp_path, "leo.thermo", description="LM75 sensor.", target=f"{THERMO}/src/thermo/lm75.py"
    )
    r = resolve("leo.thermo#LM75.read_temp", registry)
    assert r.name == "leo.thermo" and r.symbol == "LM75.read_temp" and r.kind == "function"
    assert r.address == f"leo.thermo@{r.rev[:12]}#LM75.read_temp"
    assert r.description == "LM75 sensor."
    by_locator = resolve(f"{LM75}#LM75.read_temp", registry)
    assert by_locator.identity == r.identity and by_locator.name == "leo.thermo"


def test_the_contract_serves_a_symbol_percent_encoded(registry, tmp_path):
    add_to_registry(tmp_path, "leo.thermo", target=f"{THERMO}/src/thermo/lm75.py")
    client = TestClient(server)
    j = client.get("/leo.thermo%23LM75.read_temp.json")
    assert j.status_code == 200, j.text
    assert (
        j.json()["symbol"] == "LM75.read_temp"
        and j.json()["signature"] == "read_temp(self) -> float"
    )
    assert client.get("/leo.thermo@latest%23LM75.read_temp.json").json()["rev"] == j.json()["rev"]
    page = client.get("/leo.thermo%23LM75.read_temp")
    assert page.status_code == 200 and "read_temp(self) -&gt; float" in page.text
    assert "decode.py#reg_to_millicelsius" in page.text  # the derived reference is shown
    missing = client.get("/leo.thermo%23nope.json")
    assert missing.status_code == 404 and "'nope' is not a definition" in missing.json()["detail"]


def test_a_symbol_link_expands_and_checks(registry, tmp_path):
    f = tmp_path / "use.py"
    # nothing after the link: until P1-T4 the block beneath a link runs to the end of the file
    f.write_text(f"# cttp: {DECODE}#reg_to_millicelsius\n")
    reports = expand_file(f, registry)
    assert [r.status for r in reports] == ["expanded"]
    lines = f.read_text().split("\n")
    assert lines[0].startswith(f"# cttp: {THERMO}@")
    assert "/src/thermo/decode.py#reg_to_millicelsius id=sha256:" in lines[0]
    assert lines[1] == "def reg_to_millicelsius(reg: int) -> int:"
    assert [r.status for r in check_file(f, registry)] == ["ok"]


def test_a_parameter_shadows_a_module_level_import():
    src = (
        "import string\n\n"
        "def enc(string):\n    return string.upper()\n\n"
        "def tmpl():\n    return string.Template\n"
    )
    assert extract("x.py", src, "enc").stdlib == ()
    assert extract("x.py", src, "tmpl").stdlib == ("string",)


def test_a_wrapped_docstring_summary_is_one_line():
    src = 'def f():\n    """Encode a string. The result\n    is safe.\n\n    Details.\n    """\n'
    assert extract("x.py", src, "f").docstring == "Encode a string. The result is safe."


def test_extract_directly_without_a_repository():
    page = extract("x.py", "def f(a):\n    return a\n", "f")
    assert page.kind == "function" and page.refs == () and page.span == (1, 2)
    with pytest.raises(ExtractError, match="not valid Python"):
        extract("x.py", "def (:\n", "f")
    assert extract("x.py", "def (:\n").kind == "script"  # a broken file is still a script page
