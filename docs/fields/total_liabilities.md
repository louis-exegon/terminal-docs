# Total Liabilities

`total_liabilities`

!!! info "At a glance"

    **Basis:** `level` &nbsp;·&nbsp; **Unit:** `mm`


Total liabilities ex-minority-interest — the structural model's `TOTAL_LIABILITIES`. A balance-sheet level.


## Formula

```text
total_liabilities = balance_sheet['Total Liabilities Net Minority Interest']
fallback:           Total Assets - Total Equity Gross Minority Interest
```

Reported at two points — **latest** (the newest interim snapshot) and **FY-baseline** (the FY-end snapshot), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Total Liabilities Net Minority Interest` | `balance_sheet` | level | + |
| `Total Assets − Total Equity (fallback)` | `balance_sheet` | identity, same point-in-time | + |


## Caveats & proxies

If the direct line is missing, the balance-sheet identity (assets − equity) reproduces liabilities net of MI.


## Simplified logic

```python
return resolve_field(api, 'total_liabilities')
```
