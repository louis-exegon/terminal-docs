# Net Debt / EBITDA

`net_debt_to_ebitda`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `x`


Headline leverage. A balance-sheet level numerator over a TTM flow denominator.


## Formula

```text
net_debt_to_ebitda = (total_debt - cash) / ebitda
```

Reported at two points — **latest** (levels at the newest balance-sheet date over TTM EBITDA) and **FY-baseline** (FY-end levels over annual EBITDA), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `total_debt` | `get_total_debt` | level | numerator |
| `cash` | `get_cash` | level | numerator |
| `ebitda` | `get_ebitda` | TTM | denominator |


## Caveats & proxies

`period_consistent` flags when the level date (balance sheet) and the TTM date (latest interim) differ.


## Simplified logic

```python
nd = v['total_debt'] - v['cash']
ratio = nd / v['ebitda']
```
