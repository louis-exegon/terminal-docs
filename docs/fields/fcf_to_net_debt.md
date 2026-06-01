# FCF / Net Debt

`fcf_to_net_debt`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `decimal` &nbsp;·&nbsp; **Proxy:** ⚠️ yes


Deleveraging capacity: how much of net debt the levered FCF covers in a year.


## Formula

```text
fcf_to_net_debt = fcf / (total_debt - cash)
```

Reported at two points — **latest** (TTM FCF over latest net-debt levels) and **FY-baseline** (FY FCF over FY-end net-debt levels), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `fcf` | `get_fcf` | TTM levered (proxy) | numerator |
| `total_debt` | `get_total_debt` | level | denominator |
| `cash` | `get_cash` | level | denominator |


## Caveats & proxies

Inherits `fcf`'s interest/tax proxies → `is_proxy=True`.


## Simplified logic

```python
ratio = v['fcf'] / (v['total_debt'] - v['cash'])
```
