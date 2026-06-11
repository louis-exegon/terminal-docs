# Total Debt

`total_debt`

!!! info "At a glance"

    **Basis:** `level` &nbsp;·&nbsp; **Unit:** `mm`


Total debt — a balance-sheet level at the latest snapshot. Three variants are computed and surfaced; Yahoo's `Total Debt` headline is primary. The lease-inclusive variant is available for PM decisions around lease treatment.


## Formula

```text
Variant 1 (primary):  total_debt = balance_sheet['Total Debt']
Variant 2:            total_debt = Long Term Debt + Current Debt
Variant 3:            total_debt = Long Term Debt And Capital Lease Obligation
                                 + Current Debt And Capital Lease Obligation
```

Reported at two points — **latest** (the newest interim balance-sheet snapshot) and **FY-baseline** (the FY-end snapshot), each with its exact `as_of` date.


## Inputs & variants (in order of preference)

| # | label | source fields | notes |
|---|---|---|---|
| 1 | Total Debt (yfinance) | `balance_sheet['Total Debt']` | **primary** — Yahoo's consolidated debt headline |
| 2 | LT Debt + Current Debt | `balance_sheet['Long Term Debt']` + `balance_sheet['Current Debt']` | sum of the two explicit lines; excludes lease obligations |
| 3 | LT + Current incl. leases | `balance_sheet['Long Term Debt And Capital Lease Obligation']` + `balance_sheet['Current Debt And Capital Lease Obligation']` | lease-inclusive sum; only surfaced when those lines are present |

Variants 2 and 3 are only added to the `variants` list when the underlying lines are non-empty. The primary always uses Variant 1.


## Caveats & proxies

Whether finance/operating leases are included is **PM Decision 2** — this field returns Yahoo's `Total Debt` as-is (which Yahoo typically includes lease obligations in). Use Variant 2 to strip them, or Variant 3 to confirm what is included.


## Simplified logic

```python
q = quarterly_balance_sheet['Total Debt']
a = balance_sheet['Total Debt']
latest = (q or a).iloc[-1]          # primary: Variant 1
fy_baseline = a.iloc[-1]
# Variant 2 and 3 computed separately and appended to variants[]
```
