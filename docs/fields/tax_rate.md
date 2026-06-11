# Effective Tax Rate

`tax_rate`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `decimal`


The effective income-tax rate used to compute unlevered tax in `ufcf`. Resolved through a two-stage ladder and clamped to the band [0.0, 0.40]. Returns `is_proxy=True` when the statutory rate is used.


## Formula

```text
Stage 1 — effective rate (preferred):
  tax_rate = Tax Provision / Pretax Income
  valid only when Pretax Income > 0 AND result ∈ [0.0, 0.40]

  latest     = Σ(last 4Q or 2H of Tax Provision) / Σ(last 4Q or 2H of Pretax Income)
  fy_baseline = annual Tax Provision / annual Pretax Income

Stage 2 — fallback (if Stage 1 yields None or is out of range):
  tax_rate = income_stmt['Tax Rate For Calcs']   if ∈ [0.0, 0.40]
             else statutory default (25%)         → is_proxy = True
```

Reported at two points — **latest** (TTM effective rate or Stage 2 value) and **FY-baseline** (annual effective rate or Stage 2 value), each with its exact `as_of` date. Both points share the same Stage 2 value if Stage 1 fails entirely.


## Inputs

| input | source | transform | stage |
|---|---|---|---|
| `Tax Provision` | `quarterly_income_stmt['Tax Provision']` | TTM sum (last `ppy` periods) | Stage 1 numerator |
| `Pretax Income` | `quarterly_income_stmt['Pretax Income']` | TTM sum (last `ppy` periods) | Stage 1 denominator |
| `Tax Provision` | `income_stmt['Tax Provision']` | annual value | Stage 1 FY baseline |
| `Pretax Income` | `income_stmt['Pretax Income']` | annual value | Stage 1 FY baseline |
| `Tax Rate For Calcs` | `income_stmt['Tax Rate For Calcs']` | scalar, clamped to [0, 0.40] | Stage 2 option A |
| statutory rate | hard-coded 25% | applied uniformly to both points | Stage 2 option B |


## Caveats & proxies

- The clamp [0.0, 0.40] rejects implausible effective rates (tax-loss carry-forwards producing 0%, or one-off deferred-tax reversals producing >40%). In those cases Stage 2 is used.
- Stage 2 option B (statutory 25%) sets `is_proxy=True`. Any field built on a proxy `tax_rate` inherits the flag.
- Unit is a decimal (0.21 = 21%).


## Simplified logic

```python
prov_ttm  = quarterly_income_stmt['Tax Provision'].iloc[-ppy:].sum()
pre_ttm   = quarterly_income_stmt['Pretax Income'].iloc[-ppy:].sum()
rate_ttm  = prov_ttm / pre_ttm if pre_ttm > 0 else None

if rate_ttm is not None and 0.0 <= rate_ttm <= 0.40:
    latest = rate_ttm                    # Stage 1
else:
    calcs = income_stmt['Tax Rate For Calcs'].iloc[-1]
    latest = calcs if 0 <= calcs <= 0.40 else 0.25   # Stage 2
```
