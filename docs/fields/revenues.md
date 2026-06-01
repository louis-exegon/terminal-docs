# Revenues

`revenues`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm`


Trailing-twelve-month total revenue — the top line, rolled to cover the last 12 months on whatever cadence the issuer reports.


## Formula

```text
revenues = TTM rolling of income_stmt['Total Revenue']
```

Reported at two points — **latest** (Σ of the last 4 quarters (or 2 half-years) of `Total Revenue`) and **FY-baseline** (the last annual `Total Revenue`), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Total Revenue` | `income_stmt['Total Revenue']` | TTM-rolled (4Q / 2H) | + |


## Simplified logic

```python
return resolve_field(api, 'revenues')   # routed through the engine on its 'ttm' basis
```
