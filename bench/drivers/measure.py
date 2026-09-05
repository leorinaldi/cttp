"""The line-level measurement the vision quotes, recomputed from the corpus with the tool's own
normalization (plan P6-T3).

    uv run python bench/drivers/measure.py [--corpus DIR] [--json]

Method. Every `.c` file of the corpus is parsed with the C extractor's grammar and its tokens
grouped by line (`cttp.extract.treesitter.tokens`): comments are gone, so a line's tokens are its
code. A line is **substantive** when it has at least one token that is not punctuation and is not
a preprocessor `#include`. Its **shape** is its tokens with identifiers replaced by `$0`, `$1`, …
in order of first appearance *within the line* and literals by `<num>` / `<str>` — the same
abstraction the definition-level shape uses (`hashing.shape_text`), applied line by line. Its
**verbatim** text is its tokens as written (identifiers and literals kept), so whitespace and
comments do not count as differences. A line is a **duplicate** when another file has a line with
the same key. The percentages are over substantive lines. `#include` lines and punctuation-only
lines (`{`, `};`, `)`) are excluded from the count because they are identical everywhere by
nature and would only inflate both numbers.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from cttp.extract import treesitter as ts

HERE = Path(__file__).resolve().parent
DEFAULT_CORPUS = HERE / "corpus" / "drivers"
PUNCTUATION = frozenset("{}()[];,")


def line_keys(text: str) -> list[tuple[int, str, str]]:
    """(tokens, shape, verbatim) per substantive line of one file's text; `tokens` counts the
    line's tokens that are not punctuation."""
    rows: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for row, category, token in ts.tokens("c", text):
        rows[row].append((category, token))
    keys = []
    for row in sorted(rows):
        toks = rows[row]
        if all(cat == "tok" and tok in PUNCTUATION for cat, tok in toks):
            continue
        if toks[0] == ("tok", "#include"):
            continue
        n = sum(1 for cat, tok in toks if not (cat == "tok" and tok in PUNCTUATION))
        shape = " ".join(ts.shape_words([(row, c, t) for c, t in toks]))
        keys.append((n, shape, " ".join(t for _, t in toks)))
    return keys


def measure(corpus: Path = DEFAULT_CORPUS) -> dict:
    files = sorted(corpus.rglob("*.c"))
    if not files:
        raise SystemExit(f"no .c files under {corpus}; run bench/drivers/fetch.sh first")
    shape_files: dict[str, set[int]] = defaultdict(set)
    verbatim_files: dict[str, set[int]] = defaultdict(set)
    per_file: list[list[tuple[int, str, str]]] = []
    lines = 0
    for i, f in enumerate(files):
        text = f.read_text(encoding="utf-8", errors="replace")
        lines += text.count("\n") + (0 if text.endswith("\n") else 1)
        keys = line_keys(text)
        per_file.append(keys)
        for _, shape, verbatim in keys:
            shape_files[shape].add(i)
            verbatim_files[verbatim].add(i)
    out = {"corpus": str(corpus), "files": len(files), "lines": lines}
    out.update(_rates(per_file, shape_files, verbatim_files, 1))
    # the same, over lines of at least N tokens: how much the numbers owe to short lines
    out["by_min_tokens"] = {
        str(n): _rates(per_file, shape_files, verbatim_files, n) for n in (3, 5, 8)
    }
    return out


def _rates(per_file, shape_files, verbatim_files, min_tokens: int) -> dict:
    kept = [(s, v) for keys in per_file for n, s, v in keys if n >= min_tokens]
    substantive = len(kept)
    shape_dup = sum(1 for s, _ in kept if len(shape_files[s]) > 1)
    verbatim_dup = sum(1 for _, v in kept if len(verbatim_files[v]) > 1)
    return {
        "substantive_lines": substantive,
        "shape_duplicate_lines": shape_dup,
        "shape_duplicate_percent": round(100 * shape_dup / substantive, 1),
        "verbatim_duplicate_lines": verbatim_dup,
        "verbatim_duplicate_percent": round(100 * verbatim_dup / substantive, 1),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--json", action="store_true", dest="json_")
    args = ap.parse_args(argv)
    m = measure(args.corpus)
    if args.json_:
        json.dump(m, sys.stdout, indent=2)
        print()
        return
    rows = [
        ("files", f"{m['files']:,}"),
        ("lines", f"{m['lines']:,}"),
        ("substantive lines", f"{m['substantive_lines']:,}"),
        (
            "shape-identical to a line in another file",
            f"{m['shape_duplicate_lines']:,}  ({m['shape_duplicate_percent']} %)",
        ),
        (
            "verbatim-identical to a line in another file",
            f"{m['verbatim_duplicate_lines']:,}  ({m['verbatim_duplicate_percent']} %)",
        ),
    ]
    width = max(len(k) for k, _ in rows)
    for k, v in rows:
        print(f"{k:<{width}}  {v}")
    print()
    print("over lines of at least N tokens:   N   substantive   shape-dup   verbatim-dup")
    for n, r in m["by_min_tokens"].items():
        print(
            f"{'':35}{n:>2}   {r['substantive_lines']:>11,}   "
            f"{r['shape_duplicate_percent']:>7} %   {r['verbatim_duplicate_percent']:>10} %"
        )


if __name__ == "__main__":
    main()
