# LTM EBITDA / 2-Year Average

`ltm_vs_2y_avg_ebitda`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `x`


Earnings-momentum smoother: LTM EBITDA against its trailing two-year average. The two points use deliberately different averages.


## Formula

```text
ratio = ltm_ebitda / two_year_avg
LATEST two_year_avg = [ YTD(current FY) + FY-1(full) + ((ppy-n)/ppy)·FY-2(full) ] / 2
FY     two_year_avg = mean(last 2 annual EBITDA)
```

Reported at two points — **latest** (interpolated trailing-24-month average (ppy = 4 quarterly / 2 semi-annual; n = current interim index)) and **FY-baseline** (simple mean of the last two annual statements), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `ltm_ebitda` | `get_ebitda` latest | TTM | numerator |
| `interim EBITDA` | `quarterly_income_stmt['EBITDA']` (EU halves live here too) | YTD of current FY | 24m build |
| `annual EBITDA` | `income_stmt['EBITDA']` | FY-1 full + fractional FY-2 tail | 24m build |


## Caveats & proxies

The interpolation reconstructs exactly 24 months from annuals + current-FY interims, because Yahoo rarely exposes 8 interim periods. At a fiscal year-end the interpolated value collapses to the annual mean, as it should; mid-year they diverge.


## Simplified logic

```python
ytd = Σ current-FY interim EBITDA up to latest date
two_y_latest = (ytd + annual[fy-1] + ((ppy-n)/ppy)*annual[fy-2]) / 2
two_y_fy     = mean(annual[-2:])
```
