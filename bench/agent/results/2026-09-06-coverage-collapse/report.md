# Agent benchmark — 2026-09-06-coverage-collapse

| task | family | runs | pass links | pass baseline | median tokens links | median tokens baseline | ratio | median turns links | median turns baseline |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| im-color-default-click | impact | 3+3 | 3/3 | 3/3 | 310,891 | 71,016 | 4.38 | 18 | 9 |
| im-nested-chain-click | impact | 3+3 | 3/3 | 3/3 | 321,008 | 52,634 | 6.10 | 19 | 7 |
| im-obj-setattr-attrs | impact | 3+3 | 3/3 | 0/3 | 300,850 | 96,770 | 3.11 | 15 | 10 |
| im-pick-bool-rich | impact | 3+3 | 3/3 | 3/3 | 163,368 | 71,441 | 2.29 | 15 | 7 |
| im-set-cell-size-rich | impact | 3+3 | 3/3 | 3/3 | 117,401 | 82,645 | 1.42 | 12 | 9 |
| **impact total** |  | 15+15 | 15/15 | 12/15 | 232,734 | 71,441 | 3.26 | 15 | 8 |
| **all tasks** |  | 15+15 | 15/15 | 12/15 | 232,734 | 71,441 | 3.26 | 15 | 8 |

## Run health

| arm | runs | scored | not scored | permission denials |
|---|---:|---:|---|---:|
| links | 15 | 15 | none | 8 |
| baseline | 15 | 15 | none | 20 |

## Impact grading: strict and folded

The prompt asks for the innermost definition; `who` credits the enclosing addressable one, so an agent that names a nested function is marked wrong under the strict rule. **Folded** walks such an answer up to its enclosing definition.

| arm | who checks | pass (strict) | pass (folded) |
|---|---:|---:|---:|
| links | 15 | 15 | 15 |
| baseline | 15 | 12 | 15 |

## Result files

- `im-color-default-click/links/1.json`
- `im-color-default-click/links/2.json`
- `im-color-default-click/links/3.json`
- `im-color-default-click/baseline/1.json`
- `im-color-default-click/baseline/2.json`
- `im-color-default-click/baseline/3.json`
- `im-nested-chain-click/links/1.json`
- `im-nested-chain-click/links/2.json`
- `im-nested-chain-click/links/3.json`
- `im-nested-chain-click/baseline/1.json`
- `im-nested-chain-click/baseline/2.json`
- `im-nested-chain-click/baseline/3.json`
- `im-obj-setattr-attrs/links/1.json`
- `im-obj-setattr-attrs/links/2.json`
- `im-obj-setattr-attrs/links/3.json`
- `im-obj-setattr-attrs/baseline/1.json`
- `im-obj-setattr-attrs/baseline/2.json`
- `im-obj-setattr-attrs/baseline/3.json`
- `im-pick-bool-rich/links/1.json`
- `im-pick-bool-rich/links/2.json`
- `im-pick-bool-rich/links/3.json`
- `im-pick-bool-rich/baseline/1.json`
- `im-pick-bool-rich/baseline/2.json`
- `im-pick-bool-rich/baseline/3.json`
- `im-set-cell-size-rich/links/1.json`
- `im-set-cell-size-rich/links/2.json`
- `im-set-cell-size-rich/links/3.json`
- `im-set-cell-size-rich/baseline/1.json`
- `im-set-cell-size-rich/baseline/2.json`
- `im-set-cell-size-rich/baseline/3.json`
