# Equity Market Cap

`equity_cap`

!!! info "At a glance"

    **Basis:** `market` &nbsp;·&nbsp; **Unit:** `mm`


Market capitalisation = outstanding shares × share price. A **market** field, so it is valued on price dates, not statement dates.


## Formula

```text
equity_cap = shares_outstanding × share_price
```

Reported at two points — **latest** (latest outstanding shares × latest close) and **FY-baseline** (FY-end outstanding shares × close on the FY-end date), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Ordinary Shares Number` | `balance_sheet['Ordinary Shares Number']` | level; **outstanding** (not 'Share Issued') | + |
| `Close` | `history(auto_adjust=True)['Close']`, tz-stripped | latest close / close on FY-end date | + |


## Caveats & proxies

Outstanding shares are the right base for market cap (issued ⊇ outstanding). When `equity_cap` feeds a ratio its date is the **price** date, which is why `net_debt_to_ev` can report `period_consistent=False`.


## Simplified logic

```python
shares = balance_sheet['Ordinary Shares Number']
price  = history()['Close']
latest = shares.iloc[-1] * price.iloc[-1]
fy     = shares_at_fy_end * close_on(fy_end_date)
```
