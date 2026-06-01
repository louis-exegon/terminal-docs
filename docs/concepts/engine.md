# The engine

The engine handles dates and reporting cadence so the field getters don't have to.

## Frequency detection

`infer_frequency()` reads the spacing of the interim statements and classifies the issuer:

| cadence | periods/yr (`ppy`) | TTM roll |
|---|---|---|
| quarterly | 4 | sum of last 4 |
| semi-annual | 2 | sum of last 2 |
| annual-only | 1 | no TTM (FY value only) |

!!! warning "European semi-annual reporters"
    For many EU issuers the **half-year** statements are filed under yfinance's `quarterly_*` attributes (`quarterly_income_stmt`, etc.) — not a separate semi-annual frame. The engine reads `quarterly_*`, measures the ~6-month spacing, and detects `semiannual` automatically, so a TTM rolls 2 halves rather than 4 quarters.

## TTM rolling

A `ttm` flow is the sum of the last `ppy` interim periods, dated at the newest interim. We **roll our own** from interim statements rather than using Yahoo's `ttm_*` line, because rolling is uniform, dated, and semi-annual-capable.

## The FY-start floor

`fy_baseline` always comes from the **annual** statement. Because the annual figure exists for every issuer, every field is guaranteed to return at least its last-annual value — the floor — even when interim data is missing.

## Fiscal-year inference

The fiscal year-end month is inferred **per issuer** from the annual statement dates (not assumed to be December), which drives the FY boundaries used by interpolated fields such as `ltm_vs_2y_avg_ebitda`.
