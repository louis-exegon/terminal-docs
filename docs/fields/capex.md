# Capital Expenditure

`capex`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm`


Trailing-twelve-month capex. Stored **negative** (a cash outflow), exactly as Yahoo reports it, so it sums straight into the cash-flow fields.


## Formula

```text
capex = TTM rolling of cash_flow['Capital Expenditure Reported']   (fallback 'Capital Expenditure')
```

Reported at two points — **latest** (Σ of the last 4Q / 2H, kept negative) and **FY-baseline** (the last annual capex), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Capital Expenditure Reported` | `cash_flow['Capital Expenditure Reported']` | TTM-rolled, sign kept negative | − (outflow) |


## Caveats & proxies

If `Capital Expenditure Reported` is absent the generic `Capital Expenditure` line is used (first present wins).


## Simplified logic

```python
return resolve_field(api, 'capex')
```

## Reconciliation (Ball)

Ball LTM ≈ **−554**, FY2025 = **−474**.

