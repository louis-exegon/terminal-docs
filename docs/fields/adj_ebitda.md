# Adjusted EBITDA

`adj_ebitda`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm`


Trailing-twelve-month *normalized* EBITDA — Yahoo's `Normalized EBITDA` figure, which strips out unusual / one-off items. Use this alongside `ebitda` to flag earnings quality; the ratio is exposed as `ebitda_to_adj_ebitda`.


## Formula

```text
adj_ebitda = TTM rolling of income_stmt['Normalized EBITDA']
```

Reported at two points — **latest** (Σ of the last 4Q / 2H of `Normalized EBITDA`) and **FY-baseline** (the last annual `Normalized EBITDA`), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Normalized EBITDA` | `quarterly_income_stmt['Normalized EBITDA']` | TTM-rolled: sum of last `ppy` periods | + |
| `Normalized EBITDA` | `income_stmt['Normalized EBITDA']` | used as `fy_baseline`; also `latest` for annual-only reporters | + |


## Simplified logic

```python
q = quarterly_income_stmt['Normalized EBITDA']
a = income_stmt['Normalized EBITDA']
latest = q.iloc[-ppy:].sum()
fy_baseline = a.iloc[-1]
```
