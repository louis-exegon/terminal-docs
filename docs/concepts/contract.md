# The field contract

Every getter returns the same shape, so fields are interchangeable downstream.

```python
{
  'field': 'fcf',
  'unit':  'mm',                 # mm | x | decimal
  'basis': 'derived',            # ttm | level | market | derived | stat
  'latest':      {'value': ..., 'as_of': 'YYYY-MM-DD', 'basis': ...},
  'fy_baseline': {'value': ..., 'as_of': 'YYYY-MM-DD', 'fy': 2025, 'basis': ...},
  'source':  'Yahoo Finance · ...',
  'formula': 'fcf = ebitda + capex + ch_nwc + cash_interest + cash_taxes',
  'desc':    '...',
  'is_proxy': True
}
```

## The two headline points

| point | meaning | comes from |
|---|---|---|
| `latest` | metric as the Excel defines it, newest available | TTM roll / latest level / latest market |
| `fy_baseline` | same metric as of the last annual statement (the floor) | the **annual** statement only |

`fy_baseline` is always sourced from the annual statement, never a sum of interim periods — that is what makes it the guaranteed floor for every ticker, including annual-only reporters.

## Basis types

- **`ttm`** — a flow, rolled to cover 12 months (4 quarters or 2 half-years).
- **`level`** — a balance-sheet stock, taken at the latest snapshot.
- **`market`** — price-derived, valued on price dates.
- **`derived`** — computed from other fields at both points.
- **`stat`** — a multi-year dispersion statistic (only `ufcf_vol`); no latest/FY pair.

## Derived fields: components & consistency

Derived fields are evaluated **twice** — once from each component's `latest`, once from each component's `fy_baseline` — and expose the in-between values:

```python
res['fcf']['latest']['components']
# {'ebitda': {'value': 2110, 'date': '2026-03-31'},
#  'capex':  {'value': -554, 'date': '2026-03-31'}, ... }

res['fcf']['latest']['period_consistent']   # True if all components share one date
```

`period_consistent=False` is not an error — it flags an unavoidable date mismatch, e.g. a market `equity_cap` (price date) sitting next to balance-sheet levels in `net_debt_to_ev`.

## Proxies

`is_proxy=True` marks a field that relies on an approximation (e.g. accrual interest standing in for cash interest). The flag propagates: any derived field built on a proxy inherits it.
