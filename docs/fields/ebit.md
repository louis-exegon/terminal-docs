# EBIT

`ebit`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm`


Trailing-twelve-month operating profit (earnings before interest and tax). Primary source is the `EBIT` income-statement line; falls back to `EBITDA − D&A` if that line is absent. Three computation variants are always surfaced.


## Formula

```text
Primary (if 'EBIT' line present):
  ebit = TTM rolling of income_stmt['EBIT']

Fallback (if 'EBIT' line absent):
  ebit = TTM(EBITDA) - TTM(Reconciled Depreciation)
```

Reported at two points — **latest** (TTM rolled to the issuer's cadence) and **FY-baseline** (last annual value), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `EBIT` | `income_stmt['EBIT']` | TTM-rolled | **primary** |
| `EBITDA` | `income_stmt['EBITDA']` | TTM-rolled via `get_ebitda` | fallback term |
| `Reconciled Depreciation` | `income_stmt['Reconciled Depreciation']` | TTM-rolled | subtracted in fallback |
| `Operating Income` | `income_stmt['Operating Income']` | TTM-rolled | cross-check variant only |


## Variants (in order of preference)

All three are computed and exposed in `variants` for audit:

| # | label | formula |
|---|---|---|
| 1 | EBIT line | `TTM income_stmt['EBIT']` |
| 2 | EBITDA − Reconciled Depreciation | `TTM(EBITDA) − TTM(Reconciled Depreciation)` |
| 3 | Operating Income | `TTM income_stmt['Operating Income']` |

Variant 1 drives the primary if the `EBIT` line exists. Variant 2 is used otherwise. Variant 3 is a cross-check only.


## Simplified logic

```python
q, a = quarterly_income_stmt['EBIT'], income_stmt['EBIT']
if q or a non-empty:
    latest = q.iloc[-ppy:].sum()           # Variant 1
else:
    latest = TTM(EBITDA) - TTM(D&A)       # Variant 2
```
