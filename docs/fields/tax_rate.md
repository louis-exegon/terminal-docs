# Effective Tax Rate

`tax_rate`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `decimal`


The effective tax rate used to compute unlevered tax in `ufcf`. Resolved through a ladder and clamped to a sane band.


## Formula

```text
(1) TTM Tax Provision / TTM Pretax Income   if Pretax>0 and in [0, 0.40]
(2) income_stmt['Tax Rate For Calcs']               if in [0, 0.40]
(3) statutory assumption                            (is_proxy)
```

Reported at two points — **latest** (TTM effective rate) and **FY-baseline** (annual effective rate), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Tax Provision` | `income_stmt['Tax Provision']` | TTM-rolled / annual | numerator |
| `Pretax Income` | `income_stmt['Pretax Income']` | TTM-rolled / annual | denominator |


## Caveats & proxies

Unit is a decimal. Tier 3 (statutory) sets `is_proxy=True`. Final value clamped to [0, 0.40].


## Simplified logic

```python
r = TTM('Tax Provision') / TTM('Pretax Income')
return clamp(r, 0, 0.40)
```

## Reconciliation (Ball)

Ball ≈ **0.215** (real effective rate).

