"""The benchmark report (plan P8-T3): one table from the result files of one date.

    uv run python -m bench.agent.report bench/agent/results/<date>

Reads every `<task>/<arm>/<run>.json` under the directory, prints the table, and writes
`report.md` beside them. One row per task and family totals: runs, pass rate per arm, median
tokens per arm, and the ratio of the medians (links over baseline — below 1 means the links arm
consumed less context). Every cell is traceable to the result files listed under it. `limited`,
`timeout` and `error` runs are counted but never enter a median or a pass rate.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ARMS = ("links", "baseline")
FAMILIES = ("in-repo", "cross-repo", "impact")


def load_records(directory: Path) -> list[dict]:
    records = []
    for path in sorted(directory.glob("*/*/*.json")):
        if path.name.endswith(".stream.jsonl"):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and {"task", "arm", "status"} <= record.keys():
            record["_file"] = str(path.relative_to(directory))
            records.append(record)
    return records


def _cell(values: list[int | float], fmt: str = "{:,.0f}") -> str:
    return fmt.format(statistics.median(values)) if values else "–"


def _rate(passed: int, total: int) -> str:
    return f"{passed}/{total}" if total else "–"


def summarize(records: list[dict]) -> dict[str, dict]:
    """task → arm → {runs, scored, passed, tokens[], turns[], files[]}."""
    table: dict[str, dict] = defaultdict(
        lambda: {
            arm: {"runs": 0, "scored": 0, "passed": 0, "tokens": [], "turns": [], "files": []}
            for arm in ARMS
        }
    )
    families: dict[str, str] = {}
    for r in records:
        if r["arm"] not in ARMS:
            continue
        cell = table[r["task"]][r["arm"]]
        families[r["task"]] = r.get("family", "")
        cell["runs"] += 1
        cell["files"].append(r["_file"])
        if r["status"] in ("pass", "fail"):
            cell["scored"] += 1
            cell["passed"] += r["status"] == "pass"
            if r.get("tokens") is not None:
                cell["tokens"].append(r["tokens"])
            if r.get("num_turns") is not None:
                cell["turns"].append(r["num_turns"])
    for task in table:
        table[task]["_family"] = families[task]
    return dict(table)


def render(table: dict[str, dict], title: str) -> str:
    header = (
        "| task | family | runs | pass links | pass baseline | median tokens links | "
        "median tokens baseline | ratio | median turns links | median turns baseline |"
    )
    lines = [f"# {title}", "", header, "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]

    def row(name: str, family: str, cells: dict) -> str:
        links, base = cells["links"], cells["baseline"]
        ratio = "–"
        if links["tokens"] and base["tokens"]:
            ratio = f"{statistics.median(links['tokens']) / statistics.median(base['tokens']):.2f}"
        pass_links = _rate(links["passed"], links["scored"])
        pass_base = _rate(base["passed"], base["scored"])
        return (
            f"| {name} | {family} | {links['runs']}+{base['runs']} | "
            f"{pass_links} | {pass_base} | "
            f"{_cell(links['tokens'])} | {_cell(base['tokens'])} | {ratio} | "
            f"{_cell(links['turns'])} | {_cell(base['turns'])} |"
        )

    for task in sorted(table):
        lines.append(row(task, table[task]["_family"], table[task]))
    for family in FAMILIES:
        members = [t for t in table if table[t]["_family"] == family]
        if not members:
            continue
        total = {
            arm: {
                "runs": sum(table[t][arm]["runs"] for t in members),
                "scored": sum(table[t][arm]["scored"] for t in members),
                "passed": sum(table[t][arm]["passed"] for t in members),
                "tokens": [x for t in members for x in table[t][arm]["tokens"]],
                "turns": [x for t in members for x in table[t][arm]["turns"]],
            }
            for arm in ARMS
        }
        lines.append(row(f"**{family} total**", "", total))
    lines += ["", "## Result files", ""]
    for task in sorted(table):
        for arm in ARMS:
            for f in table[task][arm]["files"]:
                lines.append(f"- `{f}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench.agent.report", description=__doc__)
    parser.add_argument("directory", type=Path, help="bench/agent/results/<date>")
    parser.add_argument("--no-write", action="store_true", help="print only")
    args = parser.parse_args(argv)
    records = load_records(args.directory)
    if not records:
        print(f"no result files under {args.directory}", file=sys.stderr)
        return 1
    text = render(summarize(records), f"Agent benchmark — {args.directory.name}")
    print(text, end="")
    if not args.no_write:
        (args.directory / "report.md").write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
