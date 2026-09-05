# The driver corpus

The measurement the vision quotes was made over 736 C files of the Linux kernel: the files of five
driver directories — `drivers/gpio`, `drivers/hwmon`, `drivers/iio/accel`,
`drivers/iio/temperature`, `drivers/rtc` — each directory's own files, no subdirectories. This
directory reproduces the corpus and the two things the plan asks of it: acceptance test 1 of spec
§12 (the index rediscovers the duplicates) and the line-level measurement itself.

## Fetching

```bash
bash bench/drivers/fetch.sh          # ~60 MB: a sparse, blobless clone of torvalds/linux at v7.3-rc1
```

`corpus/` is then a git working copy of `github.com/torvalds/linux` at the tag, holding exactly the
736 `.c` files (plus the headers and other files of those directories, and the kernel's root files
so the license is readable). Nothing else has blobs: reading another path would fetch it from
GitHub, which is why the crawl restricts itself to a sparse checkout's files. `corpus/` is
gitignored; run the script again on a fresh machine.

## Provenance

The corpus was first fetched on 2026-09-04 as raw files from `torvalds/linux/master` (the
`urls.txt` files of the preserved copy say so) and copied here from that session's scratchpad. To
pin it, every file was hashed as a git blob and compared with the GitHub contents API listing of
each directory at master's first-parent commits: the source files are identical from
`275bc4eedf2c` (2026-08-28, the rtc merge — the last change to any of the five directories) through
`4d7d9486c04d` (2026-09-05). **v7.3-rc1** (`cee9395acd80`, 2026-08-30) lies in that window and is
the pin; `fetch.sh` reproduces the preserved copy byte for byte. The only files the original fetch
did not take are each directory's `Kconfig`, `Makefile` and (gpio's) `TODO`.

## Acceptance test 1 — `expected.json`

```bash
uv run cttp index add bench/drivers/corpus --index /tmp/drivers.db
uv run cttp index crawl --index /tmp/drivers.db        # ~2 min, 799 files, ~34,000 pages
uv run cttp dups --shape --index /tmp/drivers.db       # groups by shape
uv run cttp dups --index /tmp/drivers.db               # groups by identity
uv run pytest -m slow tests/test_acceptance_drivers.py # the same, as a test
```

`expected.json` records the groups the test looks for. They were derived by running the tool over
the corpus with no hint and confirmed by reading the functions — the file says so under
`derivation`. The vision's sentence about one decoder written four times across three subsystems,
two copies for the same silicon, came from the measurement session's own reading of the files and
was not preserved; what the tool finds at the granularity of a whole definition is:

- **by shape**, the eight-bit temperature decoder `return (s8)reg * 1000;` written four times in
  four hwmon drivers under three names (`TEMP_FROM_REG`, `LM93_TEMP_FROM_REG`, `temp_from_reg`),
  one of them indented with spaces where the others use tabs;
- **by identity**, `static inline long temp_from_reg(s8 reg) { return reg * 1000; }` byte for byte
  in two Nuvoton drivers (`nct6694-hwmon.c`, `w83795.c`), and `static inline int
  TEMP_FROM_REG(s8 val) { return val * 1000; }` byte for byte in `lm78.c` and `smsc47m192.c`.

The same eight-bit decoder appears nine times in the corpus in all; the definition-level shape
keeps keywords and types, so `int` versus `long` and `inline` versus not are different shapes. The
crawl also finds 26 functions duplicated verbatim across files, most of them `superio_*` register
access helpers copied between gpio and hwmon drivers for the same Super I/O chips.

## The line-level measurement — `measure.py`

```bash
uv run python bench/drivers/measure.py            # a small table; --json for the object
uv run pytest -m slow tests/test_acceptance_drivers.py::test_the_line_level_measurement_reproduces
```

The method is in the script's docstring: lines tokenized by the C grammar with comments gone;
substantive = at least one token that is not punctuation and not `#include`; shape = identifiers
abstracted by first appearance within the line, literals typed; verbatim = the tokens as written;
duplicate = another file has a line with the same key. Over Linux v7.3-rc1:

| | substantive lines | shape-identical to a line elsewhere | verbatim-identical |
|---|---|---|---|
| all substantive lines | 257,007 | 91.9 % | 42.2 % |
| lines of ≥ 3 tokens | 194,773 | 89.5 % | 31.4 % |
| lines of ≥ 5 tokens | 110,810 | 83.0 % | 22.9 % |
| lines of ≥ 8 tokens | 34,207 | 66.3 % | 15.9 % |

The vision first quoted 37 % and 14 % from the measurement session; that session's method was not
preserved and no reading of "substantive" or "abstracted" tried here reproduces those figures, so
the vision now carries these numbers and this method. `expected.json` records them under
`measurement`, and the slow test checks the script still produces them.
