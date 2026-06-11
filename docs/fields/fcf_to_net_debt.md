# FCF / Net Debt

`fcf_to_net_debt`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `decimal` &nbsp;·&nbsp; **Proxy:** ⚠️ conditional


Deleveraging capacity: the fraction of net debt that levered FCF covers in a single year. Higher = faster deleveraging.


## Formula

```text
fcf_to_net_debt = fcf / (total_debt − cash)
```

Reported at two points — **latest** (TTM FCF over latest net-debt levels) and **FY-baseline** (FY FCF over FY-end net-debt levels), each with its exact `as_of` date.


## Inputs

| input | getter | transform | role |
|---|---|---|---|
| `fcf` | `get_fcf` | derived: `ebitda + capex + ch_nwc − cash_interest − cash_taxes` | numerator |
| `total_debt` | `get_total_debt` | level | denominator + |
| `cash` | `get_cash` | level | denominator − |


## Caveats & proxies

Inherits `fcf`'s proxy status — when `cash_interest` falls back to the accrual estimate, `fcf` (and by extension this ratio) carries `is_proxy=True`.


## Simplified logic

```python
nd    = v['total_debt'] - v['cash']
ratio = v['fcf'] / nd if nd else None
```
