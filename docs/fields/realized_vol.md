# Realized Equity Vol (1y)

`realized_vol`

!!! info "At a glance"

    **Basis:** `market` &nbsp;·&nbsp; **Unit:** `decimal`


Annualised standard deviation of daily log equity returns over the trailing 252 trading days. The structural model uses this in place of implied vol (`implied_vol` is parked).


## Formula

```text
realized_vol = stdev(ln(Close_t / Close_{t-1})) × sqrt(252)

latest:       trailing 252 trading days up to the most recent close
fy_baseline:  the last completed fiscal year window (FY-start → FY-end date)
```

Reported at two points — **latest** (trailing 252 trading days) and **FY-baseline** (last full fiscal year), each with its exact `as_of` date.


## Inputs

| input | source | transform | role |
|---|---|---|---|
| `Close` | `history(period='3y', auto_adjust=True)['Close']`, tz-stripped | daily log returns `ln(Close_t/Close_{t-1})`; stdev × √252 | both points |

History is fetched once with `period='3y'` to cover both the trailing-year window and the FY window. Prices are auto-adjusted for splits and dividends.


## Caveats & proxies

- Unit is a decimal (0.26 = 26%).
- Requires > 10 close observations; returns `None` if fewer exist.
- The FY window is inferred from annual EBITDA statement dates (same issuer-level FY inference the engine uses everywhere), not calendar year.
- This is **not** implied volatility; it is the historical equity volatility used as a structural model input.


## Simplified logic

```python
closes = history(period='3y', auto_adjust=True)['Close']
lr = np.log(closes / closes.shift(1)).dropna()

# latest — trailing 252 trading days
latest = lr.iloc[-252:].std() * np.sqrt(252)

# fy_baseline — last completed fiscal year
yr_slice = lr[(lr.index > fy_start) & (lr.index <= fy_end)]
fy_value = yr_slice.std() * np.sqrt(252)
```
