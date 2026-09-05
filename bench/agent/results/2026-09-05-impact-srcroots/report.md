# Agent benchmark — 2026-09-05-impact-srcroots

| task | family | runs | pass links | pass baseline | median tokens links | median tokens baseline | ratio | median turns links | median turns baseline |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| im-color-default-click | impact | 3+3 | 3/3 | 3/3 | 1,329,911 | 56,303 | 23.62 | 43 | 8 |
| im-nested-chain-click | impact | 3+3 | 3/3 | 3/3 | 653,777 | 81,084 | 8.06 | 27 | 8 |
| im-obj-setattr-attrs | impact | 3+3 | 2/3 | 0/3 | 530,465 | 90,872 | 5.84 | 26 | 10 |
| im-pick-bool-rich | impact | 3+3 | 3/3 | 3/3 | 105,738 | 60,769 | 1.74 | 13 | 10 |
| im-set-cell-size-rich | impact | 3+3 | 3/3 | 3/3 | 86,216 | 82,981 | 1.04 | 9 | 8 |
| **impact total** |  | 15+15 | 14/15 | 12/15 | 513,234 | 77,217 | 6.65 | 25 | 8 |
| **all tasks** |  | 15+15 | 14/15 | 12/15 | 513,234 | 77,217 | 6.65 | 25 | 8 |

## Run health

| arm | runs | scored | not scored | permission denials |
|---|---:|---:|---|---:|
| links | 15 | 15 | none | 23 |
| baseline | 15 | 15 | none | 18 |

## Impact grading: strict and folded

The prompt asks for the innermost definition; `who` credits the enclosing addressable one, so an agent that names a nested function is marked wrong under the strict rule. **Folded** walks such an answer up to its enclosing definition.

| arm | who checks | pass (strict) | pass (folded) |
|---|---:|---:|---:|
| links | 15 | 14 | 15 |
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
