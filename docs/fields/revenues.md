# Revenues

`revenues`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm`


Trailing-twelve-month total revenue — the top line, rolled to cover the last 12 months on whatever cadence the issuer reports.


## Formula

```text
revenues = TTM rolling of income_stmt['Total Revenue']
```

Reported at two points — **latest** (Σ of the last 4 quarters or 2 half-years of `Total Revenue`) and **FY-baseline** (the last annual `Total Revenue`), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Total Revenue` | `quarterly_income_stmt['Total Revenue']` (quarterly/semi-annual) | TTM-rolled: sum of last `ppy` periods | + |
| `Total Revenue` | `income_stmt['Total Revenue']` (annual) | used as `fy_baseline`; also as `latest` for annual-only reporters | + |


## Simplified logic

```python
q = quarterly_income_stmt['Total Revenue']   # ascending, NaN-free
a = income_stmt['Total Revenue']
# TTM: sum of last ppy (4Q or 2H) interim periods
latest = q.iloc[-ppy:].sum()
fy_baseline = a.iloc[-1]
```
