# Agent benchmark — 2026-09-05-who-coverage

| task | family | runs | pass links | pass baseline | median tokens links | median tokens baseline | ratio | median turns links | median turns baseline |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| im-color-default-click | impact | 3+3 | 3/3 | 3/3 | 635,046 | 73,449 | 8.65 | 24 | 9 |
| im-nested-chain-click | impact | 3+3 | 3/3 | 3/3 | 173,728 | 70,618 | 2.46 | 14 | 9 |
| im-obj-setattr-attrs | impact | 3+3 | 3/3 | 0/3 | 255,444 | 82,396 | 3.10 | 18 | 10 |
| im-pick-bool-rich | impact | 3+3 | 3/3 | 3/3 | 162,368 | 78,944 | 2.06 | 13 | 9 |
| im-set-cell-size-rich | impact | 3+3 | 3/3 | 3/3 | 122,805 | 64,155 | 1.91 | 14 | 6 |
| **impact total** |  | 15+15 | 15/15 | 12/15 | 174,040 | 72,525 | 2.40 | 14 | 9 |
| **all tasks** |  | 15+15 | 15/15 | 12/15 | 174,040 | 72,525 | 2.40 | 14 | 9 |

## Run health

| arm | runs | scored | not scored | permission denials |
|---|---:|---:|---|---:|
| links | 15 | 15 | none | 9 |
| baseline | 15 | 15 | none | 19 |

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
