# Enterprise Value

`enterprise_value`

!!! info "At a glance"

    **Basis:** `market` &nbsp;·&nbsp; **Unit:** `mm`


Enterprise value in the PM (portfolio manager) definition: market cap + total debt + minority interest − cash. Five computation variants are surfaced; the primary uses `previousClose × balance-sheet shares` for the market cap component.


## Formula

```text
ev = market_cap + total_debt + minority_interest − cash
   = (shares × price / subunit_divisor) + Total Debt + Minority Interest
     − (Cash Cash Equivalents And Short Term Investments)
```

Reported at two points — **latest** (priced at `previousClose` × latest balance-sheet shares) and **FY-baseline** (FY-end shares × close on the FY-end date, plus FY-end debt/MI/cash), each with its exact `as_of` date.


## Inputs

| input | source | transform | role |
|---|---|---|---|
| `Ordinary Shares Number` | `balance_sheet['Ordinary Shares Number']` | level; most recent or FY-end | shares |
| `previousClose` | `info['previousClose']` | divided by `subunit_divisor` | live price |
| `Close` | `history()['Close']` | tz-stripped; latest or price on FY-end date | historical price |
| `Total Debt` | `balance_sheet['Total Debt']` | level | + debt |
| `Minority Interest` | `balance_sheet['Minority Interest']` | level | + MI |
| `Cash Cash Equivalents And Short Term Investments` | `balance_sheet` | level | − cash |
| `Cash And Cash Equivalents` | `balance_sheet` | level | − cash (narrower variant) |
| `info['enterpriseValue']` | `info['enterpriseValue']` | direct Yahoo figure | cross-check variant |


## Variants (in order of preference)

| # | label | formula | notes |
|---|---|---|---|
| 1 | PM live: mktcap+debt+MI−cash(Cash+STI) | `previousClose×shares + Total Debt + MI − (Cash+STI)` | **primary** |
| 2 | PM @stmt close: mktcap+debt+MI−cash(Cash+STI) | `close@stmt×shares + Total Debt + MI − (Cash+STI)` | uses close at the statement date |
| 3 | PM live, cash=Cash&Equivalents | `previousClose×shares + Total Debt + MI − Cash&Equivalents` | narrower cash definition |
| 4 | simple (no MI): mktcap+debt−cash(Cash+STI) | `previousClose×shares + Total Debt − (Cash+STI)` | excludes minority interest |
| 5 | info enterpriseValue (direct) | `info['enterpriseValue']` | Yahoo's pre-computed figure |

Variant 1 drives `latest`. All variants are exposed for audit. Variants 2–5 are only added when the required inputs are available.

The same subunit currency correction as `equity_cap` applies: prices are divided by 100 for tickers quoted in GBp / GBX / ZAc / ILA.


## FY-baseline

```text
fy_ev = (FY-end shares × close on FY-end date / subunit_divisor)
      + Total Debt (FY-end)
      + Minority Interest (FY-end)
      − (Cash+STI) (FY-end)
```

Requires: annual shares outstanding, at least one FY-end close, FY-end Total Debt.


## Simplified logic

```python
divisor = 100 if currency in {'GBp','GBX','ZAc','ILA'} else 1
mkt_live = shares * (previousClose / divisor) / 1e6

# Variant 1 (primary)
ev_latest = mkt_live + total_debt + minority_interest - cash_sti

# FY baseline
mkt_fy    = fy_shares * (close_on(fy_end_date) / divisor) / 1e6
ev_fy     = mkt_fy + total_debt_fy + mi_fy - cash_sti_fy
```
