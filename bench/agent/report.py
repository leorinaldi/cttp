"""The benchmark report (plan P8-T3): one table from the result files of one date.

    uv run python -m bench.agent.report bench/agent/results/<date>

Reads every `<task>/<arm>/<run>.json` under the directory, prints the table, and writes
`report.md` beside them. One row per task, family totals and a grand total: runs, pass rate per
arm, median tokens per arm, and the ratio of the medians (links over baseline — below 1 means the
links arm consumed less context). Every cell is traceable to the result files listed under it.
`limited`, `timeout` and `error` runs are counted but never enter a median or a pass rate — a
pass cell reading `2/2 of 3` means the third run never finished, which is not the same as a
clean sweep; the
**run health** section says how many there were and how many permission denials each arm hit,
so the table's denominator and the deny list's cost are both visible. The **stamps** section
counts, over the cross-repo tasks, how often each arm's link carried an `id=` — the link check
accepts an unstamped link (the identity is reachable only through `resolve`), so this is
recorded rather than graded.
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


def _rate(passed: int, scored: int, runs: int | None = None) -> str:
    """`2/3`, or `2/2 of 3` when a run did not finish — an unscored run is not a tie. A bare
    `2/2` beside another arm's `3/3` reads as both perfect when one arm in fact gave up."""
    if not scored:
        return f"– of {runs}" if runs else "–"
    if runs is not None and runs != scored:
        return f"{passed}/{scored} of {runs}"
    return f"{passed}/{scored}"


def _merge_statuses(dicts) -> dict[str, int]:
    merged: dict[str, int] = defaultdict(int)
    for d in dicts:
        for k, v in d.items():
            merged[k] += v
    return dict(merged)


def summarize(records: list[dict]) -> dict[str, dict]:
    """task → arm → {runs, scored, passed, tokens[], turns[], files[]}."""
    table: dict[str, dict] = defaultdict(
        lambda: {
            arm: {
                "runs": 0,
                "scored": 0,
                "passed": 0,
                "tokens": [],
                "turns": [],
                "files": [],
                "statuses": defaultdict(int),
                "denials": 0,
                "stamped": 0,
                "linked": 0,
            }
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
        cell["statuses"][r["status"]] += 1
        cell["denials"] += len(r.get("permission_denials") or [])
        link = ((r.get("grade") or {}).get("checks") or {}).get("link")
        if isinstance(link, dict):
            cell["linked"] += 1
            cell["stamped"] += bool(link.get("stamped"))
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
        pass_links = _rate(links["passed"], links["scored"], links["runs"])
        pass_base = _rate(base["passed"], base["scored"], base["runs"])
        return (
            f"| {name} | {family} | {links['runs']}+{base['runs']} | "
            f"{pass_links} | {pass_base} | "
            f"{_cell(links['tokens'])} | {_cell(base['tokens'])} | {ratio} | "
            f"{_cell(links['turns'])} | {_cell(base['turns'])} |"
        )

    def totals(members: list[str]) -> dict:
        return {
            arm: {
                "runs": sum(table[t][arm]["runs"] for t in members),
                "scored": sum(table[t][arm]["scored"] for t in members),
                "passed": sum(table[t][arm]["passed"] for t in members),
                "tokens": [x for t in members for x in table[t][arm]["tokens"]],
                "turns": [x for t in members for x in table[t][arm]["turns"]],
                "denials": sum(table[t][arm]["denials"] for t in members),
                "stamped": sum(table[t][arm]["stamped"] for t in members),
                "linked": sum(table[t][arm]["linked"] for t in members),
                "statuses": _merge_statuses(table[t][arm]["statuses"] for t in members),
            }
            for arm in ARMS
        }

    for task in sorted(table):
        lines.append(row(task, table[task]["_family"], table[task]))
    for family in FAMILIES:
        members = [t for t in table if table[t]["_family"] == family]
        if not members:
            continue
        lines.append(row(f"**{family} total**", "", totals(members)))
    everything = totals(sorted(table))
    lines.append(row("**all tasks**", "", everything))

    # Run health: the denominator of every pass rate, and what the deny list cost.
    lines += ["", "## Run health", ""]
    lines.append("| arm | runs | scored | not scored | permission denials |")
    lines.append("|---|---:|---:|---|---:|")
    for arm in ARMS:
        cell = everything[arm]
        unscored = {k: v for k, v in cell["statuses"].items() if k not in ("pass", "fail")}
        detail = ", ".join(f"{v} {k}" for k, v in sorted(unscored.items())) or "none"
        lines.append(
            f"| {arm} | {cell['runs']} | {cell['scored']} | {detail} | {cell['denials']} |"
        )

    # Stamps: recorded, not graded — see the module docstring.
    linked = [t for t in table if table[t]["links"]["linked"] or table[t]["baseline"]["linked"]]
    if linked:
        lines += ["", "## Stamps written (cross-repo tasks)", ""]
        lines.append("| arm | graded links | carried an `id=` |")
        lines.append("|---|---:|---:|")
        for arm in ARMS:
            cell = totals(linked)[arm]
            lines.append(f"| {arm} | {cell['linked']} | {cell['stamped']} |")

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
