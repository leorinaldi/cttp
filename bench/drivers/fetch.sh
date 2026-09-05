#!/usr/bin/env bash
# Reproduce the driver corpus: the files of five Linux kernel directories at v7.3-rc1 — the
# directories' own files, not their subdirectories — as a sparse, blobless clone of torvalds/linux
# under bench/drivers/corpus. README.md says how the tag was identified.
#
# `cttp index add bench/drivers/corpus` registers the clone as github.com/torvalds/linux at the
# tag; `cttp index crawl` reads only what the sparse checkout has (plus the root files).
set -euo pipefail

TAG=v7.3-rc1
URL=https://github.com/torvalds/linux.git
DIRS=(drivers/gpio drivers/hwmon drivers/iio/accel drivers/iio/temperature drivers/rtc)

here=$(cd "$(dirname "$0")" && pwd)
corpus=$here/corpus

if [ -e "$corpus" ] && [ ! -e "$corpus/.git" ]; then
  echo "$corpus exists and is not a clone; move it aside first" >&2
  exit 1
fi
if [ ! -e "$corpus/.git" ]; then
  echo "cloning $URL at $TAG (trees and the root files only) into $corpus"
  git clone --quiet --filter=blob:none --sparse --depth 1 --branch "$TAG" "$URL" "$corpus"
fi

# Non-cone patterns: each directory's own files and nothing else — no subdirectory (cone mode
# would take drivers/hwmon/pmbus and friends), no file of an ancestor (drivers/iio has files of
# its own). The root files stay so that the license is readable. Every directory is listed once,
# shallowest first, so that an exclusion never undoes a deeper inclusion that follows it.
patterns=("/*" "!/*/")
while read -r _ kind path; do
  if [ "$kind" = target ]; then
    patterns+=("$path/" "!$path/*/")
  else
    patterns+=("$path/" "!$path/*")
  fi
done < <(
  for d in "${DIRS[@]}"; do
    path=""
    IFS=/ read -ra parts <<< "$d"
    for part in "${parts[@]}"; do
      path="$path/$part"
      kind=ancestor
      [ "$path" = "/$d" ] && kind=target
      echo "${path//[^\/]/}" "$kind" "$path"
    done
  done | awk '{ print length($1), $2, $3 }' | sort -u | sort -s -n -k1,1
)
git -C "$corpus" sparse-checkout set --no-cone "${patterns[@]}"
echo "corpus: $(find "$corpus/drivers" -name '*.c' | wc -l) .c files at $(git -C "$corpus" describe --tags --exact-match HEAD) ($(git -C "$corpus" rev-parse HEAD))"
