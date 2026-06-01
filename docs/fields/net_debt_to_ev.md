# Net Debt / Enterprise Value

`net_debt_to_ev`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `decimal`


Leverage relative to enterprise value — the share of EV funded by net debt.


## Formula

```text
net_debt_to_ev = (total_debt - cash) / (equity_cap + total_debt - cash)
```

Reported at two points — **latest** (market equity_cap (price date) + net-debt levels) and **FY-baseline** (FY-end equity_cap + FY-end net-debt levels), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `total_debt` | `get_total_debt` | level | net debt |
| `cash` | `get_cash` | level | net debt |
| `equity_cap` | `get_equity_cap` | market (shares × price) | EV |


## Caveats & proxies

`equity_cap` is on a **price** date while debt/cash are on the balance-sheet date, so `period_consistent` is typically `False` here — correctly flagging the unavoidable date mismatch.


## Simplified logic

```python
nd = v['total_debt'] - v['cash']
ev = v['equity_cap'] + nd
ratio = nd / ev
```
