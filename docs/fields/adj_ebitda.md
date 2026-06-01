# Adjusted EBITDA

`adj_ebitda`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm`


Trailing-twelve-month *normalized* EBITDA — Yahoo's figure with one-off / unusual items stripped out.


## Formula

```text
adj_ebitda = TTM rolling of income_stmt['Normalized EBITDA']
```

Reported at two points — **latest** (Σ of the last 4Q / 2H of `Normalized EBITDA`) and **FY-baseline** (the last annual `Normalized EBITDA`), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Normalized EBITDA` | `income_stmt['Normalized EBITDA']` | TTM-rolled | + |


## Simplified logic

```python
return resolve_field(api, 'adj_ebitda')
```

## Reconciliation (Ball)

Ball LTM ≈ **2,086**, FY2025 = **2,042** (close to reported — few adjustments).

