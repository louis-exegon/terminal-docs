# Total Debt

`total_debt`

!!! info "At a glance"

    **Basis:** `level` &nbsp;·&nbsp; **Unit:** `mm`


Total debt — a balance-sheet level at the latest snapshot.


## Formula

```text
total_debt = balance_sheet['Total Debt']
```

Reported at two points — **latest** (the newest interim snapshot) and **FY-baseline** (the FY-end snapshot), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Total Debt` | `balance_sheet['Total Debt']` | level (latest snapshot) | + |


## Caveats & proxies

Whether finance/operating leases are in or out, and which period to anchor on, is **PM Decision 2** — this returns Yahoo's `Total Debt` as-is.


## Simplified logic

```python
return resolve_field(api, 'total_debt')
```
