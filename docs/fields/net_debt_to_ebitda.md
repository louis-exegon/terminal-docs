# Net Debt / EBITDA

`net_debt_to_ebitda`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `x`


Headline leverage multiple: how many years of EBITDA it would take to repay net debt. A balance-sheet numerator over a TTM flow denominator.


## Formula

```text
net_debt_to_ebitda = (total_debt − cash) / ebitda
```

Reported at two points — **latest** (balance-sheet levels at the most recent snapshot over TTM EBITDA) and **FY-baseline** (FY-end debt/cash levels over annual EBITDA), each with its exact `as_of` date.


## Inputs

| input | getter | transform | role |
|---|---|---|---|
| `total_debt` | `get_total_debt` | level (latest balance-sheet snapshot) | numerator + |
| `cash` | `get_cash` | level (latest balance-sheet snapshot) | numerator − |
| `ebitda` | `get_ebitda` | TTM (multi-tier: yf headline → first principles) | denominator |


## Caveats & proxies

`period_consistent` flags when the balance-sheet date (debt/cash) and the TTM date (EBITDA) differ — the typical case for the `latest` point.


## Simplified logic

```python
nd    = v['total_debt'] - v['cash']
ratio = nd / v['ebitda'] if v['ebitda'] else None
```
