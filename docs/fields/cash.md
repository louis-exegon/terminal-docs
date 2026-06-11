# Cash & Equivalents

`cash`

!!! info "At a glance"

    **Basis:** `level` &nbsp;·&nbsp; **Unit:** `mm`


Cash, equivalents and short-term investments — a **balance-sheet level** at the latest snapshot. Two variants are computed and surfaced; the broader definition (cash + short-term investments) is primary.


## Formula

```text
Variant 1 (primary):  cash = balance_sheet['Cash Cash Equivalents And Short Term Investments']
Variant 2:            cash = balance_sheet['Cash And Cash Equivalents']
```

Reported at two points — **latest** (the newest interim balance-sheet snapshot) and **FY-baseline** (the FY-end snapshot), each with its exact `as_of` date. Levels are **not** summed; only the most recent snapshot is used.


## Inputs & variants (in order of preference)

| # | label | source field | notes |
|---|---|---|---|
| 1 | Cash + ST investments | `balance_sheet['Cash Cash Equivalents And Short Term Investments']` | **primary** — broader definition, includes money-market and short-term securities |
| 2 | Cash & equivalents only | `balance_sheet['Cash And Cash Equivalents']` | narrower; excludes short-term investments |

The primary drives `latest` and `fy_baseline`. Both variants are exposed for audit.


## Simplified logic

```python
q_broad = quarterly_balance_sheet['Cash Cash Equivalents And Short Term Investments']
a_broad = balance_sheet['Cash Cash Equivalents And Short Term Investments']
q_narrow = quarterly_balance_sheet['Cash And Cash Equivalents']
a_narrow = balance_sheet['Cash And Cash Equivalents']

# Primary: use the most recent snapshot from the broad line
latest = (q_broad or a_broad).iloc[-1]
fy_baseline = a_broad.iloc[-1]
```
