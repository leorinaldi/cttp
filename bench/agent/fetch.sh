#!/usr/bin/env bash
# Fetch the P8-T2 task repositories: full clones of the three Python projects the benchmark's
# tasks are taken from, under bench/agent/repos/<name> (gitignored). Every task pins a commit,
# so the clones may be at any HEAD; a task's `repo.rev` (and each dep's) must be reachable.
# `python -m bench.agent.harness --list` marks tasks whose repository is missing.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
repos=$here/repos
mkdir -p "$repos"

fetch() {  # name url
  if [ -e "$repos/$1/.git" ]; then
    echo "$1: already cloned ($(git -C "$repos/$1" rev-parse --short HEAD)); fetching"
    git -C "$repos/$1" fetch --quiet origin
  else
    echo "$1: cloning $2"
    git clone --quiet "$2" "$repos/$1"
  fi
}

fetch click https://github.com/pallets/click.git
fetch attrs https://github.com/python-attrs/attrs.git
fetch rich  https://github.com/Textualize/rich.git

# every task's commits must be present
python3 - "$here" <<'PY'
import sys, tomllib, subprocess, pathlib
here = pathlib.Path(sys.argv[1])
missing = []
for toml in sorted(here.glob("tasks/*/task.toml")):
    data = tomllib.loads(toml.read_text())
    repos = [data["repo"], *data.get("deps", [])]
    for r in repos:
        src = here.parents[1] / r["source"]
        if not (src / ".git").exists():
            continue
        shas = [r.get("rev")]
        for section in ("setup", "grade", "solution"):
            shas.append(data.get(section, {}).get("commit"))
        for sha in filter(None, shas):
            ok = subprocess.run(["git", "-C", str(src), "cat-file", "-e", f"{sha}^{{commit}}"],
                                capture_output=True).returncode == 0
            if not ok:
                missing.append(f"{toml.parent.name}: {sha} not in {src}")
if missing:
    print("\n".join(missing)); sys.exit(1)
print(f"all task commits present in {here / 'repos'}")
PY
