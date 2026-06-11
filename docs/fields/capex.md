# Capital Expenditure

`capex`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm`


Trailing-twelve-month capex. Stored **negative** (a cash outflow), exactly as Yahoo reports it, so it sums straight into the cash-flow fields (`fcf`, `ufcf`).


## Formula

```text
capex = TTM rolling of cash_flow['Capital Expenditure Reported']
        (fallback: cash_flow['Capital Expenditure'])
```

Reported at two points — **latest** (Σ of the last 4Q / 2H, kept negative) and **FY-baseline** (the last annual capex, kept negative), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Capital Expenditure Reported` | `quarterly_cash_flow['Capital Expenditure Reported']` | TTM-rolled, sign kept negative | − (outflow) — **primary** |
| `Capital Expenditure` | `quarterly_cash_flow['Capital Expenditure']` | TTM-rolled, sign kept negative | − (outflow) — fallback if primary absent |

The first line present (in either the quarterly or annual frame) wins. Typical values are negative (e.g. −350 mm).


## Caveats & proxies

Sign is preserved as-is from Yahoo — there is no absolute-value transform. Any downstream field that consumes `capex` adds it (a negative number reduces the sum).


## Simplified logic

```python
# First line present in quarterly or annual cash_flow wins
for line in ['Capital Expenditure Reported', 'Capital Expenditure']:
    q = quarterly_cash_flow[line]    # negative
    a = cash_flow[line]              # negative
    if q or a non-empty:
        latest = q.iloc[-ppy:].sum() # still negative
        break
```
