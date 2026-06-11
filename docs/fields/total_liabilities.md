# Total Liabilities

`total_liabilities`

!!! info "At a glance"

    **Basis:** `level` &nbsp;·&nbsp; **Unit:** `mm`


Total liabilities ex-minority-interest — the structural model's `TOTAL_LIABILITIES` input. A balance-sheet level taken at the latest snapshot. Primary is the direct line; the balance-sheet identity is the fallback.


## Formula

```text
Primary (direct line present):
  total_liabilities = balance_sheet['Total Liabilities Net Minority Interest']

Fallback (direct line absent):
  total_liabilities = balance_sheet['Total Assets']
                    − balance_sheet['Total Equity Gross Minority Interest']
```

Reported at two points — **latest** (the newest interim balance-sheet snapshot) and **FY-baseline** (the FY-end snapshot), each with its exact `as_of` date.


## Inputs

| input | source | transform | priority |
|---|---|---|---|
| `Total Liabilities Net Minority Interest` | `quarterly_balance_sheet` / `balance_sheet` | level (latest snapshot) | **primary** |
| `Total Assets` | `quarterly_balance_sheet` / `balance_sheet` | level | fallback — subtracted |
| `Total Equity Gross Minority Interest` | `quarterly_balance_sheet` / `balance_sheet` | level | fallback — balance-sheet identity |

The primary is used as long as the direct line is non-empty in either the quarterly or annual frame. The fallback activates only when it is absent entirely, and produces the mathematically equivalent result: Assets − Equity ≡ Liabilities.


## Simplified logic

```python
q = quarterly_balance_sheet['Total Liabilities Net Minority Interest']
a = balance_sheet['Total Liabilities Net Minority Interest']
if q or a non-empty:
    latest = (q or a).iloc[-1]          # primary
else:
    # identity fallback
    latest = Total_Assets - Total_Equity_Gross_Minority_Interest
```
