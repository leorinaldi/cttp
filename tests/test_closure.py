"""The closure (plan P3-T1): dependencies before dependents, imports kept and reported, honest
refusals, the budget — through `cttp closure <address> --json` and the API."""

import json

import pytest
from conftest import add_remote_repo, add_to_registry
from typer.testing import CliRunner

from cttp.cli import app
from cttp.closure import Budget, ClosureError, closure
from cttp.resolve import resolve

runner = CliRunner()
PYREPO = "github.com/leorinaldi/pyrepo"
LIB = f"{PYREPO}@main/lib.py"
THERMO = "github.com/leorinaldi/thermo"


def closure_json(address: str) -> dict:
    res = runner.invoke(app, ["closure", address, "--json"])
    assert res.exit_code == 0, res.output
    return json.loads(res.stdout)


def test_acceptance_three_definitions_in_dependency_order(registry):
    """`top` calls `left` and `right`; `right` calls `deep`: the three dependencies come first,
    each dependency before what uses it, the root last, each with pinned address and identity."""
    j = closure_json(f"{LIB}#top")
    rev = resolve(f"{LIB}#top", registry).rev[:12]
    assert [d["symbol"] for d in j["definitions"]] == ["left", "deep", "right", "top"]
    for d in j["definitions"]:
        assert d["address"] == f"{PYREPO}@{rev}/lib.py#{d['symbol']}"
        assert d["identity"].startswith("sha256:") and len(d["identity"]) == len("sha256:") + 12
        assert d["identity_full"] == resolve(d["address"], registry).identity_full
        assert d["source"].startswith("def ") and d["kind"] == "function"
    assert j["count"] == 4 and j["lines"] == sum(d["lines"] for d in j["definitions"])
    assert j["requires"] == [] and j["imports"] == [] and j["stdlib"] == []
    assert j["definitions"][-1]["needs"] == [
        f"{PYREPO}@{rev}/lib.py#left",
        f"{PYREPO}@{rev}/lib.py#right",
    ]
    assert j["origin"]["order"] == "derived"


def test_acceptance_a_third_party_import_is_kept_and_reported(registry):
    j = closure_json(f"{LIB}#fetch")
    assert j["requires"] == ["requests"] and j["imports"] == ["import requests"]
    assert [d["symbol"] for d in j["definitions"]] == ["fetch"]
    assert "requests.get(url)" in j["definitions"][0]["source"]
    text = runner.invoke(app, ["closure", f"{LIB}#fetch"]).output
    assert "imports: import requests" in text and "requires: requests" in text


def test_acceptance_an_unresolvable_name_stops_the_operation_naming_it(registry):
    res = runner.invoke(app, ["closure", f"{LIB}#broken"])
    assert res.exit_code == 1
    assert "`missing`" in res.output and "cannot be completed" in res.output


def test_acceptance_over_budget_is_refused_with_the_package_suggestion(registry):
    with pytest.raises(ClosureError, match=r"over budget: 51 definitions.*--package") as e:
        closure(f"{PYREPO}@main/many.py#f50", registry)
    assert "limits 50 and 2000" in str(e.value)
    assert len(closure(f"{PYREPO}@main/many.py#f50", registry, budget=None).nodes) == 51
    assert len(closure(f"{PYREPO}@main/many.py#f49", registry).nodes) == 50, "at the limit is fine"
    with pytest.raises(ClosureError, match="over budget"):
        closure(f"{LIB}#top", registry, budget=Budget(lines=5))


def test_the_stdlib_is_left_as_written(registry):
    c = closure(f"{LIB}#hyp", registry)
    assert c.stdlib == ["math"] and c.requires == [] and c.imports == ["import math"]
    c = closure(f"{THERMO}@main/src/thermo/decode.py#read_async", registry)
    assert c.imports == ["import struct", "from asyncio import sleep"]
    assert [n.page.symbol for n in c.nodes] == [
        "REG_BITS",
        "STEP_MILLICELSIUS",
        "reg_to_millicelsius",
        "read_async",
    ]


def test_mutual_recursion_is_a_cycle_the_closure_tolerates(registry):
    assert [n.page.symbol for n in closure(f"{LIB}#ping", registry).nodes] == ["pong", "ping"]


def test_a_reference_through_a_module_or_an_alias_is_refused(registry, tmp_path):
    with pytest.raises(ClosureError, match="reaches src/thermo/decode.py#STEP_MILLICELSIUS as "
                       "`decode.STEP_MILLICELSIUS`"):  # fmt: skip
        closure(f"{THERMO}@main/src/thermo/lm75.py#LM75", registry)
    locator = add_remote_repo(
        tmp_path,
        "aliased",
        {
            "a.py": "def helper():\n    return 1\n",
            "b.py": "from a import helper as h\nimport a\n\ndef use():\n    return h() + 1\n\n"
            "def whole():\n    return a\n",
        },
    )
    with pytest.raises(ClosureError, match="reaches a.py#helper as `h`"):
        closure(f"{locator}@main/b.py#use", registry)
    with pytest.raises(ClosureError, match="uses the module a.py as a whole"):
        closure(f"{locator}@main/b.py#whole", registry)


def test_a_class_attribute_default_is_a_free_name_of_the_method_alone(registry):
    with pytest.raises(ClosureError, match="uses `ADDRESS`, which nothing defines"):
        closure(f"{THERMO}@main/src/thermo/lm75.py#LM75.__init__", registry)


def test_two_definitions_with_one_name_are_refused(registry, tmp_path):
    locator = add_remote_repo(
        tmp_path,
        "clash",
        {
            "a.py": "def helper():\n    return 1\n",
            "c.py": "def helper():\n    return 2\n\ndef mid():\n    return helper()\n",
            "b.py": "from a import helper\nfrom c import mid\n\ndef use():\n"
            "    return helper() + mid()\n",
        },
    )
    with pytest.raises(ClosureError, match="`helper` is defined twice in the closure") as e:
        closure(f"{locator}@main/b.py#use", registry)
    assert "a.py#helper" in str(e.value) and "c.py#helper" in str(e.value)


# --- links inside a page: the spec §7 "links upon links" -----------------------------------------


GREET = 'def greet(name: str) -> str:\n    return f"hello {name}!"\n'


def test_an_inner_link_is_a_dependency_and_the_page_hashes_to_its_own_text(registry, tmp_path):
    add_to_registry(tmp_path, "greet", GREET)
    add_to_registry(tmp_path, "hello-greet", '# cttp: greet\nprint(greet("world"))\n')
    r = resolve("hello-greet", registry)
    assert r.source == 'print(greet("world"))\n', "the page's own text excludes its link lines"
    assert r.links == [
        {
            "address": "greet",
            "relation": "is",
            "fields": {},
            "description": None,
            "derived": False,
            "line": 1,
            "indent": "",
            "origin": "asserted",
        }
    ]
    assert r.unresolved == ["greet"], "free in the text; the link provides it"
    c = closure("hello-greet", registry)
    assert [(n.page.name, n.via) for n in c.nodes] == [("greet", "link"), ("hello-greet", "root")]
    assert c.nodes[0].defines == ["greet"]


def test_a_stamped_inner_link_is_followed_by_its_pin_and_checked_against_its_id(registry, tmp_path):
    add_to_registry(tmp_path, "greet", GREET)
    g = resolve("greet", registry)
    stamped = f"# cttp: {g.address} id={g.identity}\n{g.source}\nprint(greet('x'))\n"
    add_to_registry(tmp_path, "uses-greet", stamped)
    r = resolve("uses-greet", registry)
    assert r.source == "print(greet('x'))\n", "the stamped block is greet's, not this page's"
    c = closure("uses-greet", registry)
    assert [n.page.address for n in c.nodes][0] == g.address
    wrong = stamped.replace(g.identity, "sha256:000000000000")
    add_to_registry(tmp_path, "wrong-greet", wrong)
    with pytest.raises(ClosureError, match="id mismatch"):
        closure("wrong-greet", registry)


def test_a_link_inside_a_definition_is_refused(registry, tmp_path):
    locator = add_remote_repo(
        tmp_path,
        "inner",
        {"a.py": "def f():\n    # cttp: hello-world\n    return 1\n"},
    )
    with pytest.raises(ClosureError, match="contains a `is` link at line 2 of its own text"):
        closure(f"{locator}@main/a.py#f", registry)
    with pytest.raises(ClosureError, match="inside a block at line 2"):
        closure(f"{locator}@main/a.py", registry)  # as a script: the link is indented


def test_an_unresolvable_inner_link_names_the_line(registry, tmp_path):
    add_to_registry(tmp_path, "dangling", "# cttp: no-such-name\nprint(1)\n")
    with pytest.raises(ClosureError, match="the link at line 1 of dangling@.* does not resolve"):
        closure("dangling", registry)


def test_a_reference_through_a_re_export_reaches_the_definition(registry, tmp_path):
    """`from pkg import greet` names `pkg/__init__.py#greet`, which only imports it; the resolver
    forwards the reference to `pkg/core.py#greet` and the closure inlines that definition — the
    page binds `greet` by its own name, so the expansion runs."""
    locator = add_remote_repo(
        tmp_path,
        "reexport",
        {
            "pkg/__init__.py": "from .core import greet as greet\n",
            "pkg/core.py": "def greet(n):\n    return f'hi {n}'\n",
            "app.py": "from pkg import greet\n\n\ndef main():\n    return greet('x')\n",
        },
    )
    page = resolve(f"{locator}@main/app.py#main", registry)
    assert [(r["address"].split("/", 3)[-1], r["name"]) for r in page.refs] == [
        ("pkg/core.py#greet", "greet")
    ]
    j = closure_json(f"{locator}@main/app.py#main")
    assert [(d["address"].split("/", 3)[-1], d["via"]) for d in j["definitions"]] == [
        ("pkg/core.py#greet", "ref"),
        ("app.py#main", "root"),
    ]
