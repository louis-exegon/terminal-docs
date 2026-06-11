# Implied Equity Vol (1y)

`implied_vol`

!!! info "At a glance"

    **Basis:** `market` &nbsp;·&nbsp; **Unit:** `decimal` &nbsp;·&nbsp; **Status:** 🚫 parked


One-year implied equity volatility — **parked**. Returns `None` for both `latest` and `fy_baseline`. The structural model substitutes `realized_vol`.


## Formula

```text
implied_vol → None   (substitute: realized_vol)
```


## Why it is parked

Yahoo Finance's option IV data (`impliedVolatility` from `option_chain()`) is unreliable for this universe:

- HY issuers often have illiquid option markets → wide bid/ask → solver bisection artifacts.
- IV varies by strike and expiry; Yahoo does not expose a consistent 1-year ATM surface.

Until a reliable IV source is wired in, `realized_vol` stands in for all structural model inputs that require equity volatility.


## Simplified logic

```python
return {
    'field': 'implied_vol',
    'latest': None,
    'fy_baseline': None,
    'source': 'parked (Yahoo option IV unusable)',
    'formula': 'implied_vol → substitute realized_vol',
}
```
