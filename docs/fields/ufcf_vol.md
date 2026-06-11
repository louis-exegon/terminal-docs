# UFCF Volatility (FCF_VOL_ABS)

`ufcf_vol`

!!! info "At a glance"

    **Basis:** `stat` &nbsp;·&nbsp; **Unit:** `mm` &nbsp;·&nbsp; **Proxy:** ⚠️ conditional


Standard deviation of the **annual** unlevered-FCF series — the structural model's barrier-volatility (σ_B) input. A dispersion statistic over several years; this field does **not** follow the `latest`/`fy_baseline` contract. Instead it returns a single `value` plus diagnostics.


## Formula

```text
annual UFCF_t = EBITDA_t − EBIT_t × tax_rate + CapEx_t + ΔNWC_t

fcf_vol_abs = sample_stdev(UFCF_t for all available fiscal years)
            = stdev(series, ddof=1)
```

All inputs are taken from the **annual** statements (`income_stmt`, `cash_flow`). `tax_rate` is fixed at the `get_tax_rate` `fy_baseline` value and applied uniformly across all years. `CapEx_t` is negative (cash outflow); `ΔNWC_t` is cash-signed.

A year is included only when all four components (`EBITDA`, `EBIT` or `Reconciled Depreciation`, `Capital Expenditure`, `Change In Working Capital`) are available for that year.


## Inputs

| input | source | transform | role |
|---|---|---|---|
| `EBITDA` | `income_stmt['EBITDA']` | annual value per year | + |
| `EBIT` | `income_stmt['EBIT']` | annual value per year; fallback `EBITDA − Reconciled Depreciation` | − (× tax) |
| `Reconciled Depreciation` | `income_stmt['Reconciled Depreciation']` | annual; used only in EBIT fallback | — |
| `Capital Expenditure Reported` | `cash_flow['Capital Expenditure Reported']` or `Capital Expenditure` | annual, **negative** | adds as negative |
| `Change In Working Capital` | `cash_flow['Change In Working Capital']` | annual, cash-signed | cash-signed |
| `tax_rate` | `get_tax_rate` `fy_baseline` | decimal; held constant across years | scales EBIT charge |


## Outlier detection

The field identifies the single most extreme year (largest `|UFCF_t − mean|`) and computes `std_ex_extreme` — the sample std with that year removed. If removing it changes the std by more than 30%:

```
|std_full − std_ex_extreme| / std_full > 0.30  →  outlier_dominated = True
```

`is_proxy = True` when `n_years < 5` OR `outlier_dominated`. In those cases, consider overriding with a manual σ_B estimate.


## Output shape

This field does **not** return `latest` / `fy_baseline`. Instead:

| key | meaning |
|---|---|
| `value` | sample stdev (ddof=1) of the full annual UFCF series |
| `std_sample` | same as `value` |
| `std_pop` | population stdev (ddof=0) |
| `std_ex_extreme` | sample stdev after removing the most extreme year |
| `extreme_year` | the year removed in the outlier calculation |
| `outlier_dominated` | True if >30% change when extreme year removed |
| `n_years` | number of years in the series |
| `series` | `{year: ufcf_mm}` dict for all years used |
| `tax_rate_used` | the fixed tax rate applied |
| `is_proxy` | True if `n<5` or `outlier_dominated` |


## Simplified logic

```python
series = {}
for yr in sorted(years_with_all_components):
    e_i  = EBIT[yr] if EBIT else EBITDA[yr] - D&A[yr]
    series[yr] = (EBITDA[yr] - e_i * tax + CapEx[yr] + dNWC[yr]) / 1e6

value = np.std(list(series.values()), ddof=1)

# Outlier check
i_extreme = argmax(|series - mean|)
std_ex    = np.std(series_without_i_extreme, ddof=1)
outlier_dominated = abs(value - std_ex) / value > 0.30
```
