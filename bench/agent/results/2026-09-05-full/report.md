# Agent benchmark — 2026-09-05-full

| task | family | runs | pass links | pass baseline | median tokens links | median tokens baseline | ratio | median turns links | median turns baseline |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| im-color-default-click | impact | 3+3 | 2/2 of 3 | 3/3 | 2,829,962 | 70,836 | 39.95 | 57 | 8 |
| im-nested-chain-click | impact | 3+3 | 3/3 | 3/3 | 1,583,572 | 50,991 | 31.06 | 48 | 7 |
| im-obj-setattr-attrs | impact | 3+3 | 3/3 | 0/3 | 1,526,474 | 78,619 | 19.42 | 59 | 9 |
| im-pick-bool-rich | impact | 3+3 | 3/3 | 3/3 | 115,944 | 60,216 | 1.93 | 15 | 8 |
| im-set-cell-size-rich | impact | 3+3 | 3/3 | 3/3 | 89,833 | 62,765 | 1.43 | 11 | 9 |
| ir-choice-metavar-click | in-repo | 3+3 | 2/3 | 0/3 | 231,426 | 91,824 | 2.52 | 18 | 10 |
| ir-pretty-dataclass-rich | in-repo | 3+3 | 3/3 | 3/3 | 90,884 | 39,245 | 2.32 | 9 | 5 |
| ir-slots-getattr-attrs | in-repo | 3+3 | 3/3 | 3/3 | 151,772 | 91,199 | 1.66 | 12 | 9 |
| ir-table-highlight-rich | in-repo | 3+3 | 3/3 | 3/3 | 76,510 | 38,512 | 1.99 | 7 | 5 |
| ir-write-usage-click | in-repo | 3+3 | 3/3 | 3/3 | 161,059 | 83,373 | 1.93 | 11 | 8 |
| xr-escape-rich | cross-repo | 3+3 | 3/3 | 3/3 | 59,573 | 65,963 | 0.90 | 8 | 8 |
| xr-filesize-rich | cross-repo | 3+3 | 3/3 | 3/3 | 56,878 | 48,255 | 1.18 | 7 | 7 |
| xr-join-options-click | cross-repo | 3+3 | 3/3 | 3/3 | 56,265 | 146,224 | 0.38 | 8 | 15 |
| xr-textwrap-click | cross-repo | 3+3 | 3/3 | 3/3 | 119,865 | 186,774 | 0.64 | 9 | 15 |
| xr-to-bool-attrs | cross-repo | 3+3 | 3/3 | 3/3 | 63,275 | 57,770 | 1.10 | 7 | 8 |
| **in-repo total** |  | 15+15 | 14/15 | 12/15 | 151,772 | 76,428 | 1.99 | 11 | 8 |
| **cross-repo total** |  | 15+15 | 15/15 | 15/15 | 59,573 | 65,963 | 0.90 | 7 | 8 |
| **impact total** |  | 15+15 | 14/14 of 15 | 12/15 | 1,021,954 | 62,765 | 16.28 | 40 | 8 |
| **all tasks** |  | 45+45 | 43/44 of 45 | 39/45 | 112,634 | 65,963 | 1.71 | 10 | 8 |

## Run health

| arm | runs | scored | not scored | permission denials |
|---|---:|---:|---|---:|
| links | 45 | 44 | 1 error | 43 |
| baseline | 45 | 45 | none | 76 |

## Stamps written (cross-repo tasks)

| arm | graded links | carried an `id=` |
|---|---:|---:|
| links | 15 | 15 |
| baseline | 15 | 0 |

## Impact grading: strict and folded

The prompt asks for the innermost definition; `who` credits the enclosing addressable one, so an agent that names a nested function is marked wrong under the strict rule. **Folded** walks such an answer up to its enclosing definition.

| arm | who checks | pass (strict) | pass (folded) |
|---|---:|---:|---:|
| links | 15 | 14 | 14 |
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
- `ir-choice-metavar-click/links/1.json`
- `ir-choice-metavar-click/links/2.json`
- `ir-choice-metavar-click/links/3.json`
- `ir-choice-metavar-click/baseline/1.json`
- `ir-choice-metavar-click/baseline/2.json`
- `ir-choice-metavar-click/baseline/3.json`
- `ir-pretty-dataclass-rich/links/1.json`
- `ir-pretty-dataclass-rich/links/2.json`
- `ir-pretty-dataclass-rich/links/3.json`
- `ir-pretty-dataclass-rich/baseline/1.json`
- `ir-pretty-dataclass-rich/baseline/2.json`
- `ir-pretty-dataclass-rich/baseline/3.json`
- `ir-slots-getattr-attrs/links/1.json`
- `ir-slots-getattr-attrs/links/2.json`
- `ir-slots-getattr-attrs/links/3.json`
- `ir-slots-getattr-attrs/baseline/1.json`
- `ir-slots-getattr-attrs/baseline/2.json`
- `ir-slots-getattr-attrs/baseline/3.json`
- `ir-table-highlight-rich/links/1.json`
- `ir-table-highlight-rich/links/2.json`
- `ir-table-highlight-rich/links/3.json`
- `ir-table-highlight-rich/baseline/1.json`
- `ir-table-highlight-rich/baseline/2.json`
- `ir-table-highlight-rich/baseline/3.json`
- `ir-write-usage-click/links/1.json`
- `ir-write-usage-click/links/2.json`
- `ir-write-usage-click/links/3.json`
- `ir-write-usage-click/baseline/1.json`
- `ir-write-usage-click/baseline/2.json`
- `ir-write-usage-click/baseline/3.json`
- `xr-escape-rich/links/1.json`
- `xr-escape-rich/links/2.json`
- `xr-escape-rich/links/3.json`
- `xr-escape-rich/baseline/1.json`
- `xr-escape-rich/baseline/2.json`
- `xr-escape-rich/baseline/3.json`
- `xr-filesize-rich/links/1.json`
- `xr-filesize-rich/links/2.json`
- `xr-filesize-rich/links/3.json`
- `xr-filesize-rich/baseline/1.json`
- `xr-filesize-rich/baseline/2.json`
- `xr-filesize-rich/baseline/3.json`
- `xr-join-options-click/links/1.json`
- `xr-join-options-click/links/2.json`
- `xr-join-options-click/links/3.json`
- `xr-join-options-click/baseline/1.json`
- `xr-join-options-click/baseline/2.json`
- `xr-join-options-click/baseline/3.json`
- `xr-textwrap-click/links/1.json`
- `xr-textwrap-click/links/2.json`
- `xr-textwrap-click/links/3.json`
- `xr-textwrap-click/baseline/1.json`
- `xr-textwrap-click/baseline/2.json`
- `xr-textwrap-click/baseline/3.json`
- `xr-to-bool-attrs/links/1.json`
- `xr-to-bool-attrs/links/2.json`
- `xr-to-bool-attrs/links/3.json`
- `xr-to-bool-attrs/baseline/1.json`
- `xr-to-bool-attrs/baseline/2.json`
- `xr-to-bool-attrs/baseline/3.json`
