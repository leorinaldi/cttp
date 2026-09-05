"""Identity and shape hashing (plan P1-T2)."""

import pytest

from cttp.hashing import SHORT, ShapeError, identity, normalize, shape, shape_text, short

# The identity of `print("hello world!")` under the spec §2 normalization. Pinned so that a change
# to the normalization is loud: every stamp in the world would drift with it.
HELLO_IDENTITY = "75a27070015ebce788a4dd572e5c3acffb9e0edffecb96611db6fc1da6f39acb"

F = '''
def reg_to_millicelsius(reg: int) -> int:
    """Convert the raw register value to millidegrees."""
    # nine-bit two's complement, 0.5 degree steps
    if reg & 0x8000:
        reg -= 0x10000
    return (reg >> 7) * 500
'''

# Names, whitespace, comments, the docstring and the literal values differ; the structure does not.
G = """
def decode(raw:int)->int:
    'Turn a register word into a temperature.'
    if raw & 0x80:
        raw -= 256   # sign
    return (raw >> 8) * 250
"""

# The same as F with two statements swapped: a different program, a different shape.
F_REORDERED = '''
def reg_to_millicelsius(reg: int) -> int:
    """Convert the raw register value to millidegrees."""
    if reg & 0x8000:
        return (reg >> 7) * 500
    reg -= 0x10000
'''


def test_normalize():
    assert normalize("  x\r\n  y  \r\n\n\n") == "x\ny\n"
    assert normalize("    def f():\n        pass") == "def f():\n    pass\n"
    assert normalize("x\ry\n") == "x\ny\n"


def test_identity_is_stable():
    assert identity('print("hello world!")') == HELLO_IDENTITY
    assert identity('  print("hello world!")\r\n\n') == HELLO_IDENTITY
    assert short(HELLO_IDENTITY) == HELLO_IDENTITY[:SHORT] == "75a27070015e"


def test_same_shape_different_identity():
    assert identity(F) != identity(G)
    assert shape(F) == shape(G)
    assert len(shape(F)) == 64 and len(short(shape(F))) == SHORT


def test_reordered_statements_change_the_shape():
    assert shape(F) != shape(F_REORDERED)


def test_crlf_and_lf_hash_identically():
    crlf = F.replace("\n", "\r\n")
    assert crlf != F
    assert identity(crlf) == identity(F)
    assert shape(crlf) == shape(F)


def test_shape_text_placeholders():
    text = shape_text("def add(a, b=1):\n    return a + b + len('x')\n")
    # identifiers are positional; keywords, builtins and operators are kept; literals are typed
    assert text == (
        "def $0 ( $1 , $2 = <num> ) : <nl> <in> return $1 + $2 + len ( <str> ) <nl> <out>"
    )
    assert shape_text("x = f'{y}'") == shape_text("name = f'value: {other}'")
    assert shape_text("x = 1") != shape_text("x = 'one'")  # literals are typed


def test_renaming_consistently_keeps_the_shape_but_aliasing_does_not():
    assert shape("a + b") == shape("x + y")
    assert shape("a + b") != shape("a + a")


def test_not_python_has_no_shape():
    with pytest.raises(ShapeError, match="not tokenizable"):
        shape("def f(:\n  'unterminated\n")
