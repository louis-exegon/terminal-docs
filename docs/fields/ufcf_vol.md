# UFCF Volatility (FCF_VOL_ABS)

`ufcf_vol`

!!! info "At a glance"

    **Basis:** `stat` &nbsp;·&nbsp; **Unit:** `mm` &nbsp;·&nbsp; **Proxy:** ⚠️ yes


Standard deviation of the annual unlevered-FCF series — the structural model's barrier-volatility (σ_B) input. A dispersion statistic over several years, so it has **no** latest/FY pair; `value` is the std.


## Formula

```text
fcf_vol_abs = stdev(annual UFCF)
annual UFCF_t = EBITDA_t - EBIT_t·tax - CapEx_t - ΔNWC_t   (tax held fixed)
```

Reported at two points — **latest** (—) and **FY-baseline** (—), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `annual EBITDA / EBIT / capex / ΔNWC` | `income_stmt`, `cash_flow` | per fiscal year | — |
| `tax_rate` | `get_tax_rate` (fixed) | applied uniformly across years | — |


## Caveats & proxies

Small samples (~4 annual points) let one anomalous year dominate, so the field also reports `std_ex_extreme`, the `extreme_year`, and an `outlier_dominated` flag. If `n<5` or outlier-dominated it sets `is_proxy=True` — consider the manual σ_B path.


## Simplified logic

```python
series = {yr: EBITDA - EBIT*tax - CapEx - dNWC for each fiscal year}
value  = np.std(list(series.values()), ddof=1)
```
