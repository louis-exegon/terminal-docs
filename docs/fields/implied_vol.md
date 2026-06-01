# Implied Equity Vol (1y)

`implied_vol`

!!! info "At a glance"

    **Basis:** `market` &nbsp;·&nbsp; **Unit:** `decimal`


One-year implied equity volatility — **[TODO]**. Returns `None`.


## Formula

```text
implied_vol → None   (substitute realized_vol)
```

Reported at two points — **latest** (`None`) and **FY-baseline** (`None`), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Yahoo option IV` | option chains | unusable for this universe | — |


## Caveats & proxies

Yahoo's `impliedVolatility` is unreliable here (illiquid chains, solver bisection artifacts). The field is kept for completeness; the model substitutes `realized_vol`.


## Simplified logic

```python
return {'latest': None, 'fy_baseline': None}   # [TODO]
```
