# Net Debt / Enterprise Value

`net_debt_to_ev`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `decimal`


Leverage relative to enterprise value — the share of EV funded by net debt. The EV here is the simple two-component form (equity + net debt), without minority interest, to avoid a dependency on the separately computed `enterprise_value` field.


## Formula

```text
net_debt = total_debt − cash
ev       = equity_cap + net_debt        (simplified EV: equity + net debt, no MI)
net_debt_to_ev = net_debt / ev
```

Reported at two points — **latest** (market `equity_cap` at the price date, plus balance-sheet net debt) and **FY-baseline** (FY-end `equity_cap` plus FY-end net debt), each with its exact `as_of` date.


## Inputs

| input | getter | transform | role |
|---|---|---|---|
| `total_debt` | `get_total_debt` | level | net debt + |
| `cash` | `get_cash` | level | net debt − |
| `equity_cap` | `get_equity_cap` | market (shares × price, subunit-corrected) | EV equity component |


## Caveats & proxies

`equity_cap` is on a **price** date while `total_debt` and `cash` are on the balance-sheet date, so `period_consistent` is typically `False` here — correctly flagging the unavoidable date mismatch between market and accounting data.

Note: this EV excludes minority interest. For the full PM EV (including minority interest and with multiple cash variants), see `enterprise_value`.


## Simplified logic

```python
nd  = v['total_debt'] - v['cash']
ev  = v['equity_cap'] + nd
ratio = nd / ev if ev else None
```
