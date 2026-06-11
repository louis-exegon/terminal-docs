# LTM EBITDA / 2-Year Average

`ltm_vs_2y_avg_ebitda`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `x`


Earnings-momentum smoother: LTM EBITDA against its trailing two-year average. A ratio above 1.0 signals improving trend; below 1.0 signals deterioration. The `latest` and `fy_baseline` points use deliberately different average constructions.


## Formula

```text
ratio = ltm_ebitda / two_year_avg_ebitda
```

**Latest point — interpolated 24-month average:**

```text
ytd       = Σ EBITDA (interim periods in current FY, up to latest date)
fy1       = annual EBITDA for FY-1 (last completed full year)
tail      = ((ppy − n) / ppy) × annual EBITDA for FY-2
              where n = current interim period index within the FY
                    ppy = periods per year (4 for quarterly, 2 for semi-annual)

two_year_avg = (ytd + fy1 + tail) / 2
ratio_latest = ltm_ebitda / two_year_avg
```

At a fiscal year-end (`n = ppy`), `tail = 0` and the interpolated average collapses to `(fy1 + fy2) / 2` — identical to the FY baseline.

**FY-baseline point — simple annual mean:**

```text
two_year_avg = mean(last 2 annual EBITDA values)
ratio_fy     = fy_ebitda / two_year_avg
```


## Inputs

| input | source | transform | role |
|---|---|---|---|
| `ltm_ebitda` | `get_ebitda` `latest.value` | TTM (multi-tier) | numerator (latest point) |
| `fy_ebitda` | `get_ebitda` `fy_baseline.value` | annual | numerator (FY point) |
| `EBITDA` interims | `quarterly_income_stmt['EBITDA']` | YTD current-FY sum | 24m build |
| `EBITDA` annual | `income_stmt['EBITDA']` | last 2 FY values | 24m build + FY mean |


## Caveats & proxies

- The interpolation reconstructs 24 months from annual statements + current-FY interims because Yahoo rarely exposes 8 consecutive interim periods.
- `n` (current period index in the FY) is derived from the latest interim date and the issuer's inferred FY-end month.
- Annual-only reporters (no quarterly): `two_year_avg` falls back to `mean(annual[-2:])` for both points.
- At least 2 annual EBITDA observations are required to compute the FY baseline; at least 1 prior-year annual (`fy1`) is required for the interpolated latest.


## Simplified logic

```python
ytd   = sum(q_ebitda[q_ebitda.index in current_fy]) / 1e6
fy1   = annual_ebitda[-1] / 1e6
fy2   = annual_ebitda[-2] / 1e6 if available else None
tail  = ((ppy - n) / ppy) * fy2 if fy2 else 0
two_y = (ytd + fy1 + tail) / 2
ratio_latest = ltm_ebitda / two_y

# FY baseline
two_y_fy = (fy1 + fy2) / 2
ratio_fy  = fy1 / two_y_fy
```
