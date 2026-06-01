# EBIT

`ebit`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm`


Trailing-twelve-month operating profit. Used to size the unlevered tax in `ufcf`.


## Formula

```text
ebit = TTM income_stmt['EBIT']   (fallback: TTM(EBITDA) - TTM(Reconciled Depreciation))
```

Reported at two points — **latest** (Σ of the last 4Q / 2H of `EBIT`) and **FY-baseline** (the last annual `EBIT`), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `EBIT` | `income_stmt['EBIT']` | TTM-rolled | + |
| `EBITDA − Reconciled Depreciation (fallback)` | `income_stmt` | TTM-rolled difference | + |


## Simplified logic

```python
return resolve_field-style: TTM('EBIT')  else  TTM('EBITDA') - TTM('Reconciled Depreciation')
```

## Reconciliation (Ball)

Ball LTM = **1,479**, FY2025 = **1,442**.

