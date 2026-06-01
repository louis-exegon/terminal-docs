# EBITDA

`ebitda`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm`


Trailing-twelve-month reported EBITDA. The reported (not adjusted) figure; the adjusted variant is `adj_ebitda`.


## Formula

```text
ebitda = TTM rolling of income_stmt['EBITDA']
```

Reported at two points — **latest** (Σ of the last 4Q / 2H of `EBITDA`) and **FY-baseline** (the last annual `EBITDA`), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `EBITDA` | `income_stmt['EBITDA']` | TTM-rolled | + |


## Simplified logic

```python
return resolve_field(api, 'ebitda')
```
