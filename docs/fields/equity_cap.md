# Equity Market Cap

`equity_cap`

!!! info "At a glance"

    **Basis:** `market` &nbsp;·&nbsp; **Unit:** `mm`


Market capitalisation = outstanding shares × share price. A **market** field, so it is valued on price dates, not statement dates. Four variants are computed; the balance-sheet share count × latest close is primary (with subunit correction for GBp/ZAc tickers).


## Formula

```text
Variant 1 (primary): equity_cap = Ordinary Shares Number × (Close / subunit_divisor)
Variant 2:           equity_cap = Ordinary Shares Number × (previousClose / subunit_divisor)
Variant 3:           equity_cap = info['sharesOutstanding'] × (previousClose / subunit_divisor)
Variant 4:           equity_cap = info['marketCap']
```

Reported at two points — **latest** (balance-sheet shares × latest close) and **FY-baseline** (FY-end shares × close on FY-end date), each with its exact `as_of` date.


## Inputs & variants (in order of preference)

| # | label | shares source | price source | notes |
|---|---|---|---|---|
| 1 | bs shares × latest close | `balance_sheet['Ordinary Shares Number']` | `history()['Close'].iloc[-1]` | **primary**; subunit-corrected |
| 2 | bs shares × previousClose | `balance_sheet['Ordinary Shares Number']` | `info['previousClose']` | live intraday reference |
| 3 | info sharesOutstanding × previousClose | `info['sharesOutstanding']` | `info['previousClose']` | uses Yahoo's reported float |
| 4 | info marketCap (direct) | — | — | Yahoo's pre-computed figure |


## Subunit currency correction

Some exchanges quote in **subunits** (pence, South African cents, Israeli agorot). Yahoo returns the price in subunits, but the shares are in units, so without correction the market cap is 100× overstated.

| Yahoo `currency` value | divisor | effect |
|---|---|---|
| `GBp`, `GBX` | 100 | GBp → GBP |
| `ZAc` | 100 | cents → ZAR |
| `ILA` | 100 | agorot → ILS |
| anything else | 1 | no change |

The divisor is applied to the price in all variants.


## Simplified logic

```python
shares = balance_sheet['Ordinary Shares Number'].iloc[-1]
divisor = 100 if currency in {'GBp','GBX','ZAc','ILA'} else 1
price   = history()['Close'].iloc[-1] / divisor       # Variant 1
latest  = shares * price / 1e6

# FY-baseline: shares at FY-end × close on FY-end date
fy_price = close_on(fy_end_date) / divisor
fy_value = annual_shares * fy_price / 1e6
```
