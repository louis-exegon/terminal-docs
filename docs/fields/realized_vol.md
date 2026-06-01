# Realized Equity Vol (1y)

`realized_vol`

!!! info "At a glance"

    **Basis:** `market` &nbsp;·&nbsp; **Unit:** `decimal`


Annualised standard deviation of daily log equity returns. The structural model uses this in place of implied vol.


## Formula

```text
realized_vol = stdev(ln(Close_t / Close_{t-1})) × sqrt(252)
```

Reported at two points — **latest** (trailing 252 trading days up to the latest close) and **FY-baseline** (the last full fiscal year's daily log returns), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Close` | `history(auto_adjust=True)['Close']`, tz-stripped | daily log returns; std × √252 | — |


## Caveats & proxies

Unit is a decimal (0.26 = 26%). The FY value uses the calendar/fiscal-year window the Excel/BVAL basis assumes.


## Simplified logic

```python
lr = np.log(close / close.shift(1)).dropna()
latest = lr.iloc[-252:].std() * np.sqrt(252)
```
