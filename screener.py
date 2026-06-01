"""
issuer-screener — SINGLE-FILE build (engine + registry + fields + runner).
Drop this file next to your notebook and run:   exec(open("screener.py").read())
Then:   api = yf.Ticker("BALL");  res = inspect(api)        # prints every field
        all_fields = build_all(api)                          # dict {field: contract}
"""
import pandas as pd
import numpy as np

# ==========================================================================
# SECTION: engine.py
# ==========================================================================
"""
issuer-screener — DATE ENGINE + FIELD CONTRACT  (foundation module)
====================================================================

Everything date-related lives here so no getter ever hand-rolls date logic again.

Design goals (locked with the desk):
  1. AUTOMATIC, ROBUST dates. One place coerces, sorts, and de-NaNs every statement
     line, picks the latest, and slices "since the last fiscal-year start".
  2. FREQUENCY-AWARE. Detect quarterly / semi-annual / annual reporting and roll the
     right number of periods for a trailing-twelve-month (TTM) figure (4 / 2 / n.a.).
  3. FY-START FLOOR. Every field, every ticker, always returns at least the last annual
     value (`fy_baseline`) even when interim/TTM data is missing.
  4. "LATEST" MATCHES THE FIELD'S DEFINITION. A field declares its basis
     (ttm / level / market / ratio); the engine resolves "latest" on that basis
     (e.g. revenues=ttm → latest is the latest TTM, never a raw quarter).
  5. EVERY value is dated. We always know exactly which date the latest came from.

Fiscal years are inferred per issuer (not assumed calendar), so non-December and
semi-annual European reporters work without special-casing.
"""



# ─────────────────────────────────────────────────────────────────────────────
#  1.  LOW-LEVEL DATE / SERIES HYGIENE
# ─────────────────────────────────────────────────────────────────────────────

def _to_ts(c):
    """Coerce any column label to a tz-naive pandas Timestamp (NaT if impossible)."""
    try:
        t = pd.Timestamp(c)
        return t.tz_localize(None) if t.tzinfo is not None else t
    except Exception:
        return pd.NaT


def _safe(api, attr):
    """Return a non-empty DataFrame for `attr`, else None. Never raises."""
    try:
        df = getattr(api, attr, None)
        return df if (df is not None and hasattr(df, "empty") and not df.empty) else None
    except Exception:
        return None


def clean_series(df, line):
    """
    A statement line as a clean, ASCENDING, tz-naive, NaN-free Series indexed by date.
    Returns an empty Series if the line/frame is absent. This is the ONLY way getters
    should read a row — it guarantees consistent dates and ordering everywhere.
    """
    if df is None or line not in df.index:
        return pd.Series(dtype=float)
    s = df.loc[line]
    s = pd.Series(s.values, index=[_to_ts(c) for c in s.index], dtype="float64")
    s = s[~s.index.isna()].dropna()
    return s.sort_index()


# ─────────────────────────────────────────────────────────────────────────────
#  2.  FISCAL-YEAR + FREQUENCY INFERENCE
# ─────────────────────────────────────────────────────────────────────────────

def infer_fy_end_month(annual_series):
    """Most common month among annual statement dates = the issuer's FY-end month."""
    if annual_series is None or annual_series.empty:
        return 12
    months = pd.Index(annual_series.index).month
    return int(pd.Series(months).value_counts().idxmax())


def infer_frequency(interim_series):
    """
    Detect interim reporting cadence from the spacing of interim dates.
    Returns (label, periods_per_year):  quarterly→4, semiannual→2, else annual→1.
    """
    if interim_series is None or len(interim_series) < 2:
        return ("annual", 1)
    gaps = pd.Series(interim_series.sort_index().index).diff().dropna().dt.days
    if gaps.empty:
        return ("annual", 1)
    med = float(gaps.median())
    if med <= 115:           # ~3 months
        return ("quarterly", 4)
    if med <= 250:           # ~6 months
        return ("semiannual", 2)
    return ("annual", 1)


def last_fy_end(annual_series, interim_series=None, fy_end_month=12):
    """
    The most recent COMPLETED fiscal-year-end date — the 'beginning of year' anchor.
    Prefer the latest annual statement date; if none, synthesize from the latest
    interim date and the FY-end month.
    """
    if annual_series is not None and not annual_series.empty:
        return annual_series.index.max()
    if interim_series is not None and not interim_series.empty:
        d = interim_series.index.max()
        yr = d.year if d.month > fy_end_month else d.year - 1
        return pd.Timestamp(yr, fy_end_month, 1) + pd.offsets.MonthEnd(0)
    return pd.NaT


def since_fy_start(interim_series, anchor):
    """Interim points strictly AFTER the last FY-end anchor = the current-FY YTD points."""
    if interim_series is None or interim_series.empty or pd.isna(anchor):
        return pd.Series(dtype=float)
    return interim_series[interim_series.index > anchor]


# ─────────────────────────────────────────────────────────────────────────────
#  3.  CONTRACT BUILDERS  (one per basis)
# ─────────────────────────────────────────────────────────────────────────────
#  Every getter returns this uniform shape:
#    {field, unit, basis, frequency,
#     latest:{value, as_of, basis, window?},
#     fy_baseline:{value, fy, as_of},
#     since_fy_start:[{date, value}...],   ytd_cumulative? (flows),
#     source, formula, is_proxy}
#  unit ∈ {mm, x, decimal}.  Money divided by 1e6 by the caller's `scale`.
# ─────────────────────────────────────────────────────────────────────────────

def _iso(d):
    return None if pd.isna(d) else pd.Timestamp(d).date().isoformat()


def _series_records(s, scale):
    return [{"date": _iso(d), "value": float(v) / scale} for d, v in s.items()]


def resolve_flow(field, q_series, a_series, *, unit="mm", scale=1e6,
                 source="", formula="", is_proxy=False):
    """
    FLOW field (income/cash-flow item). 'latest' = trailing-twelve-month, rolled over
    the detected frequency (4 quarters / 2 semiannual). fy_baseline = last annual.
    since_fy_start = the current-FY interim flows (each dated) + their cumulative sum.
    """
    freq_label, ppy = infer_frequency(q_series)
    fy_end_m = infer_fy_end_month(a_series)
    anchor   = last_fy_end(a_series, q_series, fy_end_m)

    # latest = TTM if we have a full cycle of interims, else fall back to last annual
    latest = None
    if ppy in (2, 4) and len(q_series) >= ppy:
        win = q_series.iloc[-ppy:]
        latest = {"value": float(win.sum()) / scale,
                  "as_of": _iso(win.index[-1]),
                  "basis": f"TTM ({ppy}×{'Q' if ppy==4 else 'H'} rolling)",
                  "window": f"{_iso(win.index[0])}→{_iso(win.index[-1])}"}
    elif not a_series.empty:                      # annual-only reporter
        latest = {"value": float(a_series.iloc[-1]) / scale,
                  "as_of": _iso(a_series.index[-1]),
                  "basis": "FY (no interim cadence — annual is the latest)"}

    fy_baseline = None
    if not a_series.empty:
        fy_baseline = {"value": float(a_series.iloc[-1]) / scale,
                       "fy": int(a_series.index[-1].year),
                       "as_of": _iso(a_series.index[-1])}

    ytd = since_fy_start(q_series, anchor)
    return {
        "field": field, "unit": unit, "basis": "ttm", "frequency": freq_label,
        "latest": latest, "fy_baseline": fy_baseline,
        "since_fy_start": _series_records(ytd, scale),
        "ytd_cumulative": (float(ytd.sum()) / scale if len(ytd) else None),
        "source": source, "formula": formula, "is_proxy": is_proxy,
    }


def resolve_level(field, q_series, a_series, *, unit="mm", scale=1e6,
                  source="", formula="", is_proxy=False):
    """
    STOCK/level field (balance-sheet item). 'latest' = most recent snapshot (interim if
    available, else annual). fy_baseline = last annual snapshot. since_fy_start = the
    interim snapshots dated in the current FY (no cumulative — levels don't sum).
    """
    freq_label, _ = infer_frequency(q_series)
    fy_end_m = infer_fy_end_month(a_series)
    anchor   = last_fy_end(a_series, q_series, fy_end_m)

    if not q_series.empty:
        latest = {"value": float(q_series.iloc[-1]) / scale,
                  "as_of": _iso(q_series.index[-1]), "basis": "level (latest interim)"}
    elif not a_series.empty:
        latest = {"value": float(a_series.iloc[-1]) / scale,
                  "as_of": _iso(a_series.index[-1]), "basis": "level (latest FY)"}
    else:
        latest = None

    fy_baseline = None
    if not a_series.empty:
        fy_baseline = {"value": float(a_series.iloc[-1]) / scale,
                       "fy": int(a_series.index[-1].year),
                       "as_of": _iso(a_series.index[-1])}

    snaps = since_fy_start(q_series, anchor)
    return {
        "field": field, "unit": unit, "basis": "level", "frequency": freq_label,
        "latest": latest, "fy_baseline": fy_baseline,
        "since_fy_start": _series_records(snaps, scale),
        "source": source, "formula": formula, "is_proxy": is_proxy,
    }

# ==========================================================================
# SECTION: registry.py
# ==========================================================================
"""
issuer-screener — FIELD REGISTRY + DISPATCHER
=============================================
Each field DECLARES how the Excel defines it (excel_basis) + where it comes from.
The engine then resolves the headline pair (fy_baseline, latest) on that basis.
This is the operational form of "latest = the metric AS DEFINED IN THE EXCEL".

excel_basis:  'ttm'  (flow, trailing-twelve-month; rolled 4Q / 2H per frequency)
              'level'(balance-sheet stock; latest snapshot)
              'market' (price-derived; own date logic — handled elsewhere)
              'derived'(computed from other fields at both fy_baseline & latest)
"""

STMT = {  # logical statement -> (quarterly attr, annual attr)
    'income':  ('quarterly_income_stmt',   'income_stmt'),
    'cash':    ('quarterly_cash_flow',     'cash_flow'),
    'balance': ('quarterly_balance_sheet', 'balance_sheet'),
}

# ── REGISTRY ────────────────────────────────────────────────────────────────
# line: str OR list[str] (first present wins).  sign: multiplier applied to the raw
# series (capex stays as-reported = +1 negative; interest/taxes negated = -1).
FIELDS = {
 'revenues': dict(basis='ttm', stmt='income', line='Total Revenue', unit='mm', sign=1,
    desc="Trailing-twelve-month total revenue.",
    formula="revenues = TTM rolling of income_stmt['Total Revenue'];  fy_baseline = annual Total Revenue"),

 'ebitda': dict(basis='ttm', stmt='income', line='EBITDA', unit='mm', sign=1,
    desc="Trailing-twelve-month reported EBITDA.",
    formula="ebitda = TTM rolling of income_stmt['EBITDA'];  fy_baseline = annual EBITDA"),

 'capex': dict(basis='ttm', stmt='cash', line=['Capital Expenditure Reported','Capital Expenditure'],
    unit='mm', sign=1,   # kept NEGATIVE as Yahoo reports (outflow), so it sums into FCF
    desc="Trailing-twelve-month capital expenditure (negative = cash outflow).",
    formula="capex = TTM rolling of cash_flow['Capital Expenditure Reported'] "
            "(fallback 'Capital Expenditure'), kept negative"),

 'cash_interest': dict(basis='ttm', stmt='income', line='Interest Expense', unit='mm', sign=-1, is_proxy=True,
    desc="Cash interest paid — accrual proxy (Yahoo exposes no cash-paid-for-interest line).",
    formula="cash_interest = -(TTM rolling of income_stmt['Interest Expense'])  [accrual proxy]"),

 'ch_nwc': dict(basis='ttm', stmt='cash', line='Change In Working Capital', unit='mm', sign=1,
    desc="Change in net working capital (cash-signed: negative = cash consumed).",
    formula="ch_nwc = TTM rolling of cash_flow['Change In Working Capital']"),

 'cash': dict(basis='level', stmt='balance',
    line=['Cash Cash Equivalents And Short Term Investments','Cash And Cash Equivalents'], unit='mm', sign=1,
    desc="Cash, equivalents and short-term investments (latest balance-sheet level).",
    formula="cash = balance_sheet['Cash Cash Equivalents And Short Term Investments'] (latest snapshot)"),

 'total_debt': dict(basis='level', stmt='balance', line='Total Debt', unit='mm', sign=1,
    desc="Total debt (latest balance-sheet level).  [definition/leases = PM Decision 2]",
    formula="total_debt = balance_sheet['Total Debt'] (latest snapshot)"),

 'total_liabilities': dict(basis='level', stmt='balance', line='Total Liabilities Net Minority Interest',
    unit='mm', sign=1,
    desc="Total liabilities ex-minority-interest (latest level); CS-Model TOTAL_LIABILITIES.",
    formula="total_liabilities = balance_sheet['Total Liabilities Net Minority Interest'] (latest snapshot)"),
}

# ── DISPATCHER ──────────────────────────────────────────────────────────────
def _pick_series(api, stmt, line, sign):
    qattr, aattr = STMT[stmt]
    lines = line if isinstance(line, list) else [line]
    qdf, adf = _safe(api, qattr), _safe(api, aattr)
    for ln in lines:                       # first line present (in either frame) wins
        q = clean_series(qdf, ln) * sign
        a = clean_series(adf, ln) * sign
        if not q.empty or not a.empty:
            return q, a, ln
    return pd.Series(dtype=float), pd.Series(dtype=float), lines[0]

def resolve_field(api, name):
    """Resolve any registry field to the uniform contract via the engine."""
    s = FIELDS[name]
    q, a, used = _pick_series(api, s['stmt'], s['line'], s.get('sign', 1))
    common = dict(unit=s['unit'], source=f"Yahoo Finance · {s['stmt']}['{used}']",
                  formula=s['formula'], is_proxy=s.get('is_proxy', False))
    out = (resolve_flow(name, q, a, **common) if s['basis'] == 'ttm'
           else resolve_level(name, q, a, **common))
    out['desc'] = s['desc']
    return out

# ==========================================================================
# SECTION: fields.py
# ==========================================================================
"""
issuer-screener — FIELD GETTERS  (fully documented public API)
==============================================================
Every getter returns the uniform contract from engine.py:
    {field, unit, basis, frequency?, latest:{value,as_of,basis,...},
     fy_baseline:{value,fy,as_of}, since_fy_start:[...], source, formula, desc, is_proxy}

DOCUMENTATION STANDARD (applies to every function below):
  Each docstring states (1) the exact FORMULA, and (2) for each input xN: where it is
  pulled from, how it is transformed (TTM-rolled / raw / level / smoothed / sign / which
  close), and which DATE the value corresponds to. Nothing is left implicit.

Two headline numbers per field, both the metric AS DEFINED IN THE EXCEL:
    latest       = newest available (TTM rolled to frequency / latest level / latest market)
    fy_baseline  = value as of the last annual statement   (the always-available FLOOR)
"""



# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  A.  SIMPLE STATEMENT FIELDS  (thin registry wrappers — see registry.py)    ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

def get_revenues(api):
    """
    REVENUES.  basis=ttm  unit=mm.  FORMULA: revenues = TTM rolling of income_stmt['Total Revenue'].
      x1 income_stmt['Total Revenue'] — quarterly line; latest = Σ last 4Q (or 2H if semi-annual),
         as_of = newest interim date; fy_baseline = last ANNUAL Total Revenue (FY-end date).
    """
    return resolve_field(api, 'revenues')

def get_ebitda(api):
    """
    EBITDA.  basis=ttm  unit=mm.  FORMULA: ebitda = TTM rolling of income_stmt['EBITDA'].
      x1 income_stmt['EBITDA'] — quarterly; latest = Σ last 4Q/2H (as_of newest interim);
         fy_baseline = last annual EBITDA.  (Adjusted/normalized variant handled by get_adj_ebitda.)
    """
    return resolve_field(api, 'ebitda')

def get_capex(api):
    """
    CAPEX.  basis=ttm  unit=mm  (NEGATIVE = cash outflow, kept as Yahoo reports so it sums into FCF).
    FORMULA: capex = TTM rolling of cash_flow['Capital Expenditure Reported'] (fallback 'Capital Expenditure').
      x1 cash_flow['Capital Expenditure Reported'] — quarterly, sign kept negative; latest = Σ last 4Q/2H;
         fy_baseline = last annual capex.  First of the two line names that is present is used.
    """
    return resolve_field(api, 'capex')

def get_cash_interest(api):
    """
    CASH INTEREST.  basis=ttm  unit=mm  (NEGATIVE, outflow).  is_proxy=True.
    FORMULA: cash_interest = -(TTM rolling of income_stmt['Interest Expense']).
      x1 income_stmt['Interest Expense'] — quarterly accrual line, NEGATED (sign=-1); latest = -Σ last 4Q/2H;
         fy_baseline = -(last annual Interest Expense).
    PROXY: Yahoo exposes no cash-paid-for-interest line, so the accrual is used; it runs above true cash
    interest (non-cash OID/issuance-cost amortization + timing). Flagged is_proxy.
    """
    return resolve_field(api, 'cash_interest')

def get_cash(api):
    """
    CASH.  basis=level  unit=mm.  FORMULA: cash = balance_sheet['Cash Cash Equivalents And Short Term
    Investments'] (fallback 'Cash And Cash Equivalents'), latest snapshot.
      x1 balance-sheet cash line — a LEVEL (not summed); latest = newest interim snapshot (as_of that date);
         fy_baseline = FY-end snapshot.
    """
    return resolve_field(api, 'cash')

def get_total_debt(api):
    """
    TOTAL DEBT.  basis=level  unit=mm.  FORMULA: total_debt = balance_sheet['Total Debt'], latest snapshot.
      x1 balance_sheet['Total Debt'] — LEVEL; latest = newest interim snapshot; fy_baseline = FY-end.
    NOTE: leases-in/out and which period is PM Decision 2 — this returns Yahoo's 'Total Debt' as-is.
    """
    return resolve_field(api, 'total_debt')


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  B.  FIELDS WITH PROXY LADDERS  (explicit, each tier documented)            ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

_WC_COMPONENTS = ['Change In Receivables', 'Change In Inventory',
                  'Change In Payables And Accrued Expense', 'Change In Other Current Assets',
                  'Change In Other Current Liabilities', 'Change In Other Working Capital']

def get_ch_nwc(api):
    """
    CH NWC — Change in Net Working Capital.  basis=ttm  unit=mm  (cash-signed: neg = cash consumed).
    FORMULA (resolution ladder, first that yields a value wins):
      TIER 1  ch_nwc = TTM rolling of cash_flow['Change In Working Capital']                  [primary]
      TIER 2  ch_nwc = TTM rolling of Σ cash-flow WC component lines                          [same defn]
              (Change In Receivables + Inventory + Payables&Accrued + Other CA + Other CL + Other WC)
      TIER 3  ch_nwc = -[(AR+Inventory-AP)_t - (AR+Inventory-AP)_{t-1}]  balance-sheet proxy  [is_proxy]
    INPUTS:
      x1 cash_flow['Change In Working Capital'] — quarterly, cash-signed, summed over 4Q/2H for latest;
         fy_baseline = last annual value.  Source confirmed cash-flow concept (GuruFocus guide).
      TIER 2 lines — only those present are summed; the returned formula lists exactly which.
      TIER 3 — different definition (BS levels), flagged is_proxy; gives wrong sign on some names.
    """
    H = 'Change In Working Capital'
    q = clean_series(_safe(api, 'quarterly_cash_flow'), H)
    a = clean_series(_safe(api, 'cash_flow'), H)
    if not q.empty or not a.empty:
        return _attach(resolve_flow('ch_nwc', q, a, unit='mm',
            source="Yahoo Finance · cash_flow['Change In Working Capital']",
            formula="ch_nwc = TTM rolling of cash_flow['Change In Working Capital']"),
            "Change in net working capital (cash-signed).")
    # TIER 2 — component sum (same statement/definition)
    qcf, acf = _safe(api, 'quarterly_cash_flow'), _safe(api, 'cash_flow')
    def _sum_components(df):
        if df is None: return pd.Series(dtype=float)
        present = [c for c in _WC_COMPONENTS if c in df.index]
        if not present: return pd.Series(dtype=float)
        parts = [clean_series(df, c) for c in present]
        return pd.concat(parts, axis=1).sum(axis=1, min_count=1).dropna()
    q2, a2 = _sum_components(qcf), _sum_components(acf)
    if not q2.empty or not a2.empty:
        return _attach(resolve_flow('ch_nwc', q2, a2, unit='mm',
            source="Yahoo Finance · cash_flow WC component sum",
            formula="ch_nwc = TTM rolling of Σ(cash-flow working-capital component lines)"),
            "Change in NWC via component sum (headline line absent).")
    # TIER 3 — balance-sheet proxy (different basis)
    def _bs_nwc(df):
        if df is None: return pd.Series(dtype=float)
        ar, inv, ap = (clean_series(df, k) for k in ('Accounts Receivable','Inventory','Accounts Payable'))
        nwc = pd.concat([ar, inv, -ap], axis=1).sum(axis=1, min_count=3).dropna()
        return -(nwc.diff().dropna())          # -(NWC_t - NWC_{t-1})
    qb, ab = _bs_nwc(_safe(api,'quarterly_balance_sheet')), _bs_nwc(_safe(api,'balance_sheet'))
    out = resolve_flow('ch_nwc', qb, ab, unit='mm', is_proxy=True,
        source="Yahoo Finance · balance_sheet (AR+Inventory-AP) y/y, PM proxy",
        formula="ch_nwc = -[(AR+Inventory-AP)_t - (AR+Inventory-AP)_{t-1}]  [BS proxy]")
    return _attach(out, "Change in NWC via balance-sheet proxy (last resort).")

def get_cash_taxes(api):
    """
    CASH TAXES.  basis=ttm  unit=mm  (NEGATIVE, outflow).  is_proxy=True.
    FORMULA: cash_taxes = -(TTM Tax Provision - TTM Deferred Tax)     [current-tax expense, closer-to-cash]
             fallback if no Deferred line:  cash_taxes = -(TTM Tax Provision)
    INPUTS:
      x1 income_stmt['Tax Provision'] — quarterly TOTAL tax (current+deferred); TTM-rolled.
      x2 cash_flow['Deferred Tax'] (fallback 'Deferred Income Tax') — quarterly non-cash deferred piece;
         TTM-rolled and SUBTRACTED to leave current (closer-to-cash) tax.
      result negated (outflow). latest as_of = newest interim; fy_baseline = annual (Provision - Deferred).
    PROXY: still omits Δ taxes-payable (only in the 10-K 'cash paid for income taxes' line Yahoo lacks).
    """
    prov_q = clean_series(_safe(api,'quarterly_income_stmt'), 'Tax Provision')
    prov_a = clean_series(_safe(api,'income_stmt'), 'Tax Provision')
    def _deferred(qattr, aattr):
        for k in ('Deferred Tax', 'Deferred Income Tax'):
            dq, da = clean_series(_safe(api,qattr), k), clean_series(_safe(api,aattr), k)
            if not dq.empty or not da.empty: return dq, da, k
        return pd.Series(dtype=float), pd.Series(dtype=float), None
    dq, da, dkey = _deferred('quarterly_cash_flow', 'cash_flow')
    if dkey is not None:
        # align by date, current tax = provision - deferred, then negate
        q = (-(prov_q.subtract(dq, fill_value=0.0))).reindex(prov_q.index.union(dq.index)).dropna()
        a = (-(prov_a.subtract(da, fill_value=0.0))).reindex(prov_a.index.union(da.index)).dropna()
        out = resolve_flow('cash_taxes', q, a, unit='mm', is_proxy=True,
            source=f"Yahoo Finance · income_stmt['Tax Provision'] - cash_flow['{dkey}']",
            formula=f"cash_taxes = -(TTM Tax Provision - TTM {dkey})  [current-tax proxy]")
        return _attach(out, "Cash taxes = current tax expense (provision − deferred), TTM.")
    out = resolve_flow('cash_taxes', -prov_q, -prov_a, unit='mm', is_proxy=True,
        source="Yahoo Finance · income_stmt['Tax Provision']",
        formula="cash_taxes = -(TTM Tax Provision)  [total-tax fallback; deferred line absent]")
    return _attach(out, "Cash taxes = total tax provision (deferred line unavailable), TTM.")

def get_total_liabilities(api):
    """
    TOTAL LIABILITIES.  basis=level  unit=mm.  CS-Model TOTAL_LIABILITIES.
    FORMULA: total_liabilities = balance_sheet['Total Liabilities Net Minority Interest'] (latest snapshot)
             fallback:           balance_sheet['Total Assets'] - balance_sheet['Total Equity Gross Minority
                                 Interest']   (= liabilities net of MI, by the BS identity)
    INPUTS:
      x1 'Total Liabilities Net Minority Interest' — LEVEL; latest = newest interim snapshot; fy_baseline = FY-end.
      fallback x2,x3 'Total Assets' - 'Total Equity Gross Minority Interest' — same point-in-time.
    """
    L = 'Total Liabilities Net Minority Interest'
    q, a = clean_series(_safe(api,'quarterly_balance_sheet'), L), clean_series(_safe(api,'balance_sheet'), L)
    if not q.empty or not a.empty:
        return _attach(resolve_level('total_liabilities', q, a, unit='mm',
            source=f"Yahoo Finance · balance_sheet['{L}']",
            formula=f"total_liabilities = balance_sheet['{L}'] (latest level)"),
            "Total liabilities ex-minority-interest (level).")
    def _identity(df):
        if df is None: return pd.Series(dtype=float)
        ta, te = clean_series(df,'Total Assets'), clean_series(df,'Total Equity Gross Minority Interest')
        return ta.subtract(te, fill_value=np.nan).dropna()
    q2, a2 = _identity(_safe(api,'quarterly_balance_sheet')), _identity(_safe(api,'balance_sheet'))
    return _attach(resolve_level('total_liabilities', q2, a2, unit='mm',
        source="Yahoo Finance · Total Assets - Total Equity Gross Minority Interest",
        formula="total_liabilities = Total Assets - Total Equity Gross Minority Interest [identity; direct line absent]"),
        "Total liabilities via BS identity (direct line absent).")


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  C.  MARKET FIELDS  (price-derived; own date logic, same contract)          ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

def _closes(api):
    """Daily Close series, tz-stripped, ascending. From api.history(period='3y', auto_adjust=True)."""
    try:
        h = api.history(period='3y', auto_adjust=True)
        s = h['Close'].copy()
        s.index = pd.DatetimeIndex([_to_ts(d) for d in s.index])
        return s[~s.index.isna()].dropna().sort_index()
    except Exception:
        return pd.Series(dtype=float)

def _close_on(closes, date):
    """Close on `date`, or the last trading day BEFORE it (as-of)."""
    if closes.empty or pd.isna(date): return None
    sub = closes[closes.index <= pd.Timestamp(date)]
    return float(sub.iloc[-1]) if len(sub) else None

def get_equity_cap(api):
    """
    EQUITY CAP — market capitalisation.  basis=market  unit=mm.
    FORMULA: equity_cap = shares_outstanding × share_price.
    INPUTS:
      x1 shares = balance_sheet['Ordinary Shares Number'] — OUTSTANDING shares (subset held by public),
         NOT 'Share Issued' (issued ⊇ outstanding). A LEVEL; latest = newest interim count, FY = FY-end count.
      x2 price = daily Close from api.history (auto_adjust=True), tz-stripped.
         latest      = latest shares × latest Close (most recent trading day).
         fy_baseline = FY-end shares × Close ON the FY-end date (or last trading day before it).
    """
    L = 'Ordinary Shares Number'
    q = clean_series(_safe(api,'quarterly_balance_sheet'), L)
    a = clean_series(_safe(api,'balance_sheet'), L)
    closes = _closes(api)
    latest = fyb = None
    if not closes.empty and (not q.empty or not a.empty):
        sh_latest = (q if not q.empty else a)
        latest_close = float(closes.iloc[-1])
        latest = {'value': float(sh_latest.iloc[-1]) * latest_close / 1e6,
                  'as_of': _iso(closes.index[-1]),
                  'basis': f"latest shares ({_iso(sh_latest.index[-1])}) × latest close"}
    if not a.empty and not closes.empty:
        fy_d = a.index[-1]; px = _close_on(closes, fy_d)
        if px is not None:
            fyb = {'value': float(a.iloc[-1]) * px / 1e6, 'fy': int(fy_d.year), 'as_of': _iso(fy_d),
                   'basis': "FY-end shares × close on FY-end date"}
    return {'field':'equity_cap','unit':'mm','basis':'market','latest':latest,'fy_baseline':fyb,
            'source':"Yahoo Finance · Ordinary Shares Number × history Close",
            'formula':"equity_cap = Ordinary Shares Number (outstanding) × Close",
            'desc':"Market cap = outstanding shares × price.",'is_proxy':False}

def get_realized_vol(api):
    """
    REALIZED EQUITY VOL (1y).  basis=market  unit=decimal (0.27 = 27%).
    FORMULA: vol = stdev(daily log returns) × sqrt(252).
    INPUTS:
      x1 Close = api.history daily Close (auto_adjust=True), tz-stripped.
         log_ret_t = ln(Close_t / Close_{t-1}).
         latest      = trailing 252 trading days up to the latest Close.
         fy_baseline = the LAST FULL FISCAL YEAR's daily log returns (FY-start date → FY-end date),
                       i.e. the calendar/fiscal-year vol the Excel/BVAL basis uses.
    """
    closes = _closes(api); a_ebitda = clean_series(_safe(api,'income_stmt'),'EBITDA')
    fy_end_m = infer_fy_end_month(a_ebitda)
    def _vol(px):
        lr = np.log(px / px.shift(1)).dropna()
        return float(lr.std() * np.sqrt(252)) if len(lr) > 5 else None
    latest = fyb = None
    if len(closes) > 10:
        win = closes.iloc[-252:]
        v = _vol(win)
        if v is not None:
            latest = {'value': v, 'as_of': _iso(closes.index[-1]), 'basis': "trailing 252 trading days"}
        a = _safe(api,'income_stmt')
        if a is not None and not a_ebitda.empty:
            fy_end = a_ebitda.index[-1]
            fy_start = pd.Timestamp(fy_end.year-1, fy_end.month, fy_end.day) if fy_end.month!=2 else fy_end - pd.Timedelta(days=365)
            yr = closes[(closes.index > fy_start) & (closes.index <= fy_end)]
            v2 = _vol(yr)
            if v2 is not None:
                fyb = {'value': v2, 'fy': int(fy_end.year), 'as_of': _iso(fy_end),
                       'basis': f"FY{fy_end.year} daily log-return vol ({_iso(fy_start)}→{_iso(fy_end)})"}
    return {'field':'realized_vol','unit':'decimal','basis':'market','latest':latest,'fy_baseline':fyb,
            'source':"Yahoo Finance · history Close (daily log returns)",
            'formula':"realized_vol = stdev(ln Close_t/Close_{t-1}) × sqrt(252)",
            'desc':"Annualised stdev of daily log returns.",'is_proxy':False}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  D.  DERIVED FIELDS  (computed at BOTH latest and fy_baseline)              ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

def _val(node):
    return None if not node else node.get('value')

def _derive(name, parts, combine, *, unit, desc, formula, is_proxy=None):
    """
    Evaluate a derived field at BOTH points. `parts` = {alias: getter_result}.
    `combine(values_dict) -> float`. Computes once from each part's LATEST value and once from each
    part's FY_BASELINE value, so the headline pair holds for derived fields too. latest carries the
    component dates + a period_consistent flag (True iff all components share one as_of date).
    """
    def at(point):
        vals, dates = {}, {}
        for alias, r in parts.items():
            node = (r or {}).get(point)
            v = _val(node)
            if v is None: return None, {}, {}
            vals[alias] = v
            dates[alias] = (node.get('as_of') if node else None) or (f"FY{node.get('fy')}" if node and node.get('fy') else None)
        return combine(vals), dates, vals
    lv, ld, lvals = at('latest'); fv, fd, fvals = at('fy_baseline')
    if is_proxy is None:
        is_proxy = any((r or {}).get('is_proxy') for r in parts.values())
    # period_consistent only over components that carry a real (ISO) date
    iso_dates = [d for d in ld.values() if isinstance(d, str) and d[:1].isdigit()]
    latest = None if lv is None else {
        'value': lv, 'as_of': (max(iso_dates) if iso_dates else None),
        'basis': 'derived from components\' latest',
        'components': {a: {'value': lvals[a], 'date': ld.get(a)} for a in lvals},
        'period_consistent': (len(set(iso_dates)) <= 1) if iso_dates else None}
    fy_isos = [d for d in fd.values() if isinstance(d, str) and d[:1].isdigit()]
    fyb = None if fv is None else {'value': fv, 'basis': "derived from components' FY-start",
                                   'as_of': (max(fy_isos) if fy_isos else None),
                                   'fy': (int(max(fy_isos)[:4]) if fy_isos else None),
                                   'components': {a: {'value': fvals[a], 'point': fd.get(a)} for a in fvals}}
    return {'field':name,'unit':unit,'basis':'derived','latest':latest,'fy_baseline':fyb,
            'source':'Computed from components','formula':formula,'desc':desc,'is_proxy':is_proxy}

def get_ebit(api):
    """
    EBIT.  basis=ttm  unit=mm.  FORMULA: ebit = TTM income_stmt['EBIT'] (fallback EBITDA - Reconciled Depreciation).
      x1 income_stmt['EBIT'] — quarterly; latest = Σ last 4Q/2H; fy_baseline = annual EBIT.
      fallback x2 = get_ebitda - TTM income_stmt['Reconciled Depreciation'] when 'EBIT' line is absent.
    """
    q, a = clean_series(_safe(api,'quarterly_income_stmt'),'EBIT'), clean_series(_safe(api,'income_stmt'),'EBIT')
    if not q.empty or not a.empty:
        return _attach(resolve_flow('ebit', q, a, unit='mm',
            source="Yahoo Finance · income_stmt['EBIT']", formula="ebit = TTM rolling of income_stmt['EBIT']"),
            "Operating profit (EBIT), TTM.")
    dq, da = clean_series(_safe(api,'quarterly_income_stmt'),'Reconciled Depreciation'), clean_series(_safe(api,'income_stmt'),'Reconciled Depreciation')
    eq = clean_series(_safe(api,'quarterly_income_stmt'),'EBITDA').subtract(dq, fill_value=np.nan).dropna()
    ea = clean_series(_safe(api,'income_stmt'),'EBITDA').subtract(da, fill_value=np.nan).dropna()
    return _attach(resolve_flow('ebit', eq, ea, unit='mm',
        source="Yahoo Finance · EBITDA - Reconciled Depreciation",
        formula="ebit = TTM(EBITDA) - TTM(Reconciled Depreciation)  [fallback; 'EBIT' line absent]"),
        "EBIT via EBITDA − D&A (fallback).")

def get_tax_rate(api, statutory=0.25, lo=0.0, hi=0.40):
    """
    EFFECTIVE TAX RATE.  basis=derived  unit=decimal.  Used only to size unlevered tax in UFCF.
    FORMULA (ladder): (1) TTM Tax Provision / TTM Pretax Income, if Pretax>0 and in [lo,hi];
                      (2) income_stmt['Tax Rate For Calcs'] if in [lo,hi];
                      (3) statutory assumption (is_proxy).  Final clamped to [lo,hi].
      x1 income_stmt['Tax Provision'], x2 income_stmt['Pretax Income'] — both TTM-rolled, matched period.
    Returns latest (TTM rate) and fy_baseline (annual rate). 'value' is a decimal.
    """
    def rate_from(qP, qPre):
        if qP is None or qPre is None or qPre <= 0: return None
        r = qP / qPre
        return r if lo <= r <= hi else None
    def ttm(line):
        s = clean_series(_safe(api,'quarterly_income_stmt'), line)
        return float(s.iloc[-4:].sum()) if len(s) >= 4 else (float(clean_series(_safe(api,'income_stmt'),line).iloc[-1]) if not clean_series(_safe(api,'income_stmt'),line).empty else None)
    def annual(line):
        s = clean_series(_safe(api,'income_stmt'), line)
        return float(s.iloc[-1]) if not s.empty else None
    lat = rate_from(ttm('Tax Provision'), ttm('Pretax Income'))
    fyb = rate_from(annual('Tax Provision'), annual('Pretax Income'))
    src = "Tax Provision / Pretax Income (TTM & annual)"; isp = False; fla = "tax_rate = Tax Provision / Pretax Income"
    if lat is None or fyb is None:                          # tier 2/3 fallback
        trc = clean_series(_safe(api,'income_stmt'),'Tax Rate For Calcs')
        cand = float(trc.iloc[-1]) if not trc.empty and lo <= float(trc.iloc[-1]) <= hi else max(lo, min(hi, statutory))
        isp = trc.empty or not (lo <= (float(trc.iloc[-1]) if not trc.empty else 999) <= hi)
        src = "Tax Rate For Calcs / statutory"; fla = "tax_rate = Tax Rate For Calcs (else statutory)"
        lat = lat if lat is not None else cand
        fyb = fyb if fyb is not None else cand
    qi, ai = _safe(api,'quarterly_income_stmt'), _safe(api,'income_stmt')
    lat_date = _iso(clean_series(qi,'Tax Provision').index[-1]) if not clean_series(qi,'Tax Provision').empty \
               else (_iso(clean_series(ai,'Tax Provision').index[-1]) if not clean_series(ai,'Tax Provision').empty else None)
    fy_idx = clean_series(ai,'Tax Provision')
    fy_date = _iso(fy_idx.index[-1]) if not fy_idx.empty else None
    return {'field':'tax_rate','unit':'decimal','basis':'derived',
            'latest':{'value':lat,'as_of':lat_date,'basis':'TTM effective rate'},
            'fy_baseline':{'value':fyb,'as_of':fy_date,'fy':(int(fy_date[:4]) if fy_date else None),'basis':'annual effective rate'},
            'source':f"Yahoo Finance · {src}",'formula':fla,
            'desc':"Effective tax rate for the unlevered tax in UFCF.",'is_proxy':isp}

def get_ufcf(api):
    """
    UFCF — Unlevered Free Cash Flow.  basis=derived  unit=mm.  (CS-Model barrier-drift input.)
    FORMULA: ufcf = ebitda - (ebit × tax_rate) + capex + ch_nwc
             [= NOPAT + D&A - CapEx - ΔNWC; capex & ch_nwc already cash-signed]
    INPUTS (each at latest AND fy_baseline):
      x1 ebitda     get_ebitda      TTM income_stmt['EBITDA']                      (+)
      x2 ebit       get_ebit        TTM income_stmt['EBIT'] (or EBITDA−ReconDepr)  (+)  →  unlevered tax = ebit×tax
      x3 tax_rate   get_tax_rate    TTM Tax Provision/Pretax (clamped)             (decimal)
      x4 capex      get_capex       TTM cash_flow['Capital Expenditure Reported']  (NEGATIVE)
      x5 ch_nwc     get_ch_nwc      TTM cash_flow['Change In Working Capital']      (cash-signed; proxy ladder)
    NOT levered FCF: no interest term (financing-neutral); tax is on EBIT.
    """
    parts = {'ebitda':get_ebitda(api),'ebit':get_ebit(api),'tax':get_tax_rate(api),
             'capex':get_capex(api),'ch_nwc':get_ch_nwc(api)}
    combine = lambda v: v['ebitda'] - v['ebit']*v['tax'] + v['capex'] + v['ch_nwc']
    return _derive('ufcf', parts, combine, unit='mm',
        desc="Unlevered FCF = NOPAT + D&A − CapEx − ΔNWC (simplified to EBITDA − EBIT·tax − CapEx − ΔNWC).",
        formula="ufcf = ebitda - (ebit × tax_rate) + capex + ch_nwc")

def get_fcf(api):
    """
    FCF — Free Cash Flow (levered).  [Excel Y6 = SUM(S6:X6)]  basis=derived  unit=mm.
    FORMULA: fcf = ebitda + capex + ch_nwc + cash_interest + cash_taxes   (all cash-signed → straight sum).
    INPUTS (each at latest AND fy_baseline):
      x1 ebitda        get_ebitda         TTM EBITDA                                    (+)
      x2 capex         get_capex          TTM capex                                     (NEGATIVE)
      x3 ch_nwc        get_ch_nwc         TTM Change In Working Capital                 (cash-signed; proxy ladder)
      x4 cash_interest get_cash_interest  -TTM Interest Expense                         (NEGATIVE; accrual proxy)
      x5 cash_taxes    get_cash_taxes     -(TTM Tax Provision − Deferred)               (NEGATIVE; current-tax proxy)
    NOT Yahoo's 'Free Cash Flow' line (opaque, doesn't reconcile). is_proxy inherited from interest/taxes.
    """
    parts = {'ebitda':get_ebitda(api),'capex':get_capex(api),'ch_nwc':get_ch_nwc(api),
             'cash_interest':get_cash_interest(api),'cash_taxes':get_cash_taxes(api)}
    combine = lambda v: v['ebitda']+v['capex']+v['ch_nwc']+v['cash_interest']+v['cash_taxes']
    return _derive('fcf', parts, combine, unit='mm',
        desc="Levered FCF = EBITDA + capex + ΔNWC + cash interest + cash taxes (all cash-signed).",
        formula="fcf = ebitda + capex + ch_nwc + cash_interest + cash_taxes")

def get_ebitda_less_capex_to_interest(api):
    """
    EBITDA-LESS-CAPEX / INTEREST.  [Excel AE6]  basis=derived  unit=x (multiple).
    FORMULA: m = (ebitda + capex) / (-cash_interest).
      x1 ebitda        get_ebitda          TTM EBITDA              (+)
      x2 capex         get_capex           TTM capex               (NEGATIVE → adds, reducing numerator)
      x3 cash_interest get_cash_interest   -TTM Interest Expense   (NEGATIVE; negated again in denom)
    Inherits the cash-interest accrual proxy in the denominator → amplifies that gap. is_proxy.
    """
    parts = {'ebitda':get_ebitda(api),'capex':get_capex(api),'cash_interest':get_cash_interest(api)}
    def combine(v):
        denom = -v['cash_interest']
        return (v['ebitda'] + v['capex']) / denom if denom else None
    return _derive('ebitda_less_capex_to_interest', parts, combine, unit='x', is_proxy=True,
        desc="(EBITDA + capex) / −cash interest, a coverage multiple.",
        formula="ebitda_less_capex_to_interest = (ebitda + capex) / -cash_interest")

def _net_debt(api):
    """net_debt result-like dict with latest & fy_baseline = total_debt − cash (both levels, same date)."""
    td, cash = get_total_debt(api), get_cash(api)
    return _derive('net_debt', {'td':td,'cash':cash}, lambda v: v['td']-v['cash'], unit='mm',
        desc="Net debt = total debt − cash.", formula="net_debt = total_debt - cash")

def get_net_debt_to_ebitda(api):
    """
    NET DEBT / EBITDA.  basis=derived  unit=x.  FORMULA: (total_debt - cash) / ebitda.
      x1 total_debt get_total_debt  LEVEL (latest snapshot / FY-end)
      x2 cash       get_cash        LEVEL (latest snapshot / FY-end)
      x3 ebitda     get_ebitda      TTM EBITDA
    latest mixes a LEVEL numerator (as-of newest BS date) with a TTM denominator (as-of newest interim);
    period_consistent flags if those dates differ.
    """
    parts = {'td':get_total_debt(api),'cash':get_cash(api),'ebitda':get_ebitda(api)}
    return _derive('net_debt_to_ebitda', parts, lambda v:(v['td']-v['cash'])/v['ebitda'] if v['ebitda'] else None,
        unit='x', desc="Leverage: net debt / TTM EBITDA.",
        formula="net_debt_to_ebitda = (total_debt - cash) / ebitda")

def get_fcf_to_net_debt(api):
    """
    FCF / NET DEBT.  basis=derived  unit=decimal.  FORMULA: fcf / (total_debt - cash).
      x1 fcf get_fcf (TTM levered FCF; proxy) ;  x2 total_debt LEVEL ;  x3 cash LEVEL.
    """
    parts = {'fcf':get_fcf(api),'td':get_total_debt(api),'cash':get_cash(api)}
    return _derive('fcf_to_net_debt', parts, lambda v: v['fcf']/(v['td']-v['cash']) if (v['td']-v['cash']) else None,
        unit='decimal', desc="FCF / net debt.", formula="fcf_to_net_debt = fcf / (total_debt - cash)")

def get_net_debt_to_ev(api):
    """
    NET DEBT / EV.  basis=derived  unit=decimal.  FORMULA: (total_debt - cash) / (equity_cap + total_debt - cash).
      x1 total_debt LEVEL ; x2 cash LEVEL ; x3 equity_cap MARKET (shares×price).  EV = equity_cap + net_debt.
    """
    parts = {'td':get_total_debt(api),'cash':get_cash(api),'eq':get_equity_cap(api)}
    def combine(v):
        nd = v['td']-v['cash']; ev = v['eq']+nd
        return nd/ev if ev else None
    return _derive('net_debt_to_ev', parts, combine, unit='decimal',
        desc="Net debt / enterprise value.", formula="net_debt_to_ev = (total_debt - cash) / (equity_cap + total_debt - cash)")


# small helper to attach a desc onto an engine result
def _attach(d, desc):
    d['desc'] = desc
    return d

# ==========================================================================
# SECTION: extras.py
# ==========================================================================
"""
issuer-screener — remaining getters + runner + inspector
"""

def get_adj_ebitda(api):
    """
    ADJUSTED (NORMALIZED) EBITDA.  basis=ttm  unit=mm.
    FORMULA: adj_ebitda = TTM rolling of income_stmt['Normalized EBITDA'] (strips one-off/unusual items).
      x1 income_stmt['Normalized EBITDA'] — quarterly; latest = Σ last 4Q/2H; fy_baseline = annual.
    """
    q, a = clean_series(_safe(api,'quarterly_income_stmt'),'Normalized EBITDA'), clean_series(_safe(api,'income_stmt'),'Normalized EBITDA')
    return _attach(resolve_flow('adj_ebitda', q, a, unit='mm',
        source="Yahoo Finance · income_stmt['Normalized EBITDA']",
        formula="adj_ebitda = TTM rolling of income_stmt['Normalized EBITDA']"),
        "Adjusted/normalized EBITDA (unusual items stripped), TTM.")

def get_ebitda_to_adj_ebitda(api):
    """
    EBITDA / ADJ EBITDA.  basis=derived  unit=x.  FORMULA: ebitda / adj_ebitda.
      x1 ebitda     get_ebitda      TTM reported EBITDA
      x2 adj_ebitda get_adj_ebitda  TTM normalized EBITDA
    Near 1.0 = few adjustments; <1 = reported below normalized.
    """
    parts = {'ebitda':get_ebitda(api),'adj':get_adj_ebitda(api)}
    return _derive('ebitda_to_adj_ebitda', parts, lambda v: v['ebitda']/v['adj'] if v['adj'] else None,
        unit='x', desc="Reported vs adjusted EBITDA ratio.", formula="ebitda_to_adj_ebitda = ebitda / adj_ebitda")

def get_ltm_vs_2y_avg_ebitda(api):
    """
    LTM EBITDA / 2Y-AVG EBITDA.  basis=derived  unit=x.  (Earnings-momentum smoother.)
    FORMULA: ratio = ltm_ebitda / two_year_avg_ebitda.
      x1 ltm_ebitda    = TTM EBITDA (Σ last 4Q / 2H).
      x2 two_year_avg:
         LATEST  = smoothed trailing-24-MONTH EBITDA / 2, built by LINEAR INTERPOLATION across the
                   FY-2 tail (yfinance rarely exposes 8 interim periods, so we reconstruct 24 months
                   from annuals + the current-FY interims):
                       trailing24m = YTD(current FY)  +  FY-1(full)  +  ((ppy - n)/ppy)·FY-2(full)
                   where ppy = interim periods/yr (4 quarterly, 2 semi-annual) and n = which interim
                   of the current FY the latest point is (so YTD has n periods, the FY-2 tail supplies
                   the remaining (ppy-n) to complete exactly 24 months). two_year_avg = trailing24m / 2.
         FY      = mean(last 2 ANNUAL EBITDA)  (simple, statement-based).
    So LATEST and FY genuinely differ: LATEST tracks the rolling 24m to today, FY is the clean annual mean.
    """
    qe = clean_series(_safe(api, 'quarterly_income_stmt'), 'EBITDA')   # interim (Q or H — EU halves live here too)
    ae = clean_series(_safe(api, 'income_stmt'), 'EBITDA')             # annual
    ltm = get_ebitda(api)['latest']; ltm_v = ltm['value'] if ltm else None
    _, ppy = infer_frequency(qe)                                       # 4 / 2 / 1
    fy_end_m = infer_fy_end_month(ae)
    def fy_of(d):  return d.year if d.month <= fy_end_m else d.year + 1
    def per_n(d):
        m_in_fy = ((d.month - fy_end_m - 1) % 12) + 1
        return min(ppy, ((m_in_fy - 1) // (12 // ppy)) + 1) if ppy > 1 else 1
    ann_by_fy = {fy_of(d): float(v) / 1e6 for d, v in ae.items()}

    # LATEST — interpolated trailing-24m average
    two_y_latest = None
    if ppy in (2, 4) and len(qe) and ltm_v is not None:
        d = qe.index[-1]; fy = fy_of(d); n = per_n(d)
        ytd = sum(float(v) for dd, v in qe.items() if fy_of(dd) == fy and dd <= d) / 1e6
        if (fy - 1) in ann_by_fy:
            fy1 = ann_by_fy[fy - 1]
            if n >= ppy:
                tail = 0.0
            elif (fy - 2) in ann_by_fy:
                tail = ((ppy - n) / ppy) * ann_by_fy[fy - 2]
            else:
                tail = None
            if tail is not None:
                two_y_latest = (ytd + fy1 + tail) / 2
    if two_y_latest is None and len(ae) >= 2:                          # fallback if interims too thin
        two_y_latest = float(ae.iloc[-2:].mean()) / 1e6

    lat = None
    if ltm_v and two_y_latest:
        lat = {'value': ltm_v / two_y_latest, 'as_of': ltm['as_of'],
               'basis': 'LTM EBITDA / interpolated trailing-24m average',
               'components': {'ltm_ebitda': {'value': ltm_v, 'date': ltm['as_of']},
                              'two_year_avg': {'value': two_y_latest, 'date': ltm['as_of']}}}
    # FY — simple mean of last two annual statements
    fyb = None
    if len(ae) >= 2:
        two_y_fy = float(ae.iloc[-2:].mean()) / 1e6
        fy_ebitda = float(ae.iloc[-1]) / 1e6
        fy_date = _iso(ae.index[-1])
        fyb = {'value': fy_ebitda / two_y_fy, 'as_of': fy_date, 'fy': int(ae.index[-1].year),
               'basis': 'FY EBITDA / mean(last 2 annual EBITDA)',
               'components': {'fy_ebitda': {'value': fy_ebitda, 'point': fy_date},
                              'two_year_avg': {'value': two_y_fy, 'point': fy_date}}}
    return {'field': 'ltm_vs_2y_avg_ebitda', 'unit': 'x', 'basis': 'derived', 'latest': lat, 'fy_baseline': fyb,
            'source': 'Computed from EBITDA series',
            'formula': "ltm_vs_2y_avg_ebitda = ltm_ebitda / two_year_avg (latest: interpolated 24m; FY: 2-annual mean)",
            'desc': "LTM EBITDA vs its trailing-2-year average (interpolated for latest).", 'is_proxy': False}

def get_ufcf_vol(api, ddof=1, outlier_tol=0.30):
    """
    UFCF VOL — FCF_VOL_ABS (std of the annual UFCF series; CS-Model σ_B input).  unit=mm.
    FORMULA: fcf_vol_abs = stdev(annual UFCF), tax held FIXED at the current effective rate.
      annual UFCF_t = EBITDA_t - EBIT_t·tax - CapEx_t - ΔNWC_t   (per fiscal year, from annual statements)
    DIAGNOSTICS: std_sample/pop, std excluding the most-extreme year, and an outlier_dominated flag
      (small ~4-pt sample → one anomalous year, e.g. a growth-capex cycle, can dominate). is_proxy if
      n<5 or outlier-dominated → consider the manual σ_B path (model USE_FCF_VOL=False).
    This is a dispersion statistic over multiple years — it has no latest/FY pair; 'value' is the std.
    """
    inc, cf = _safe(api,'income_stmt'), _safe(api,'cash_flow')
    tax = get_tax_rate(api)['fy_baseline']['value']
    def by_year(df, line):
        s = clean_series(df, line)
        return {d.year: float(v) for d, v in s.items()}
    eb, ei, dep = by_year(inc,'EBITDA'), by_year(inc,'EBIT'), by_year(inc,'Reconciled Depreciation')
    cx = by_year(cf,'Capital Expenditure Reported') or by_year(cf,'Capital Expenditure')
    wc = by_year(cf,'Change In Working Capital')
    yrs = sorted(set(eb) & set(cx) & set(wc) & (set(ei) if ei else set(dep)))
    series = {}
    for y in yrs:
        e_i = ei.get(y) if ei else (eb[y]-dep[y])
        series[y] = (eb[y] - e_i*tax + cx[y] + wc[y]) / 1e6
    if len(series) < 2:
        return {'field':'ufcf_vol','unit':'mm','basis':'stat','value':None,'n_years':len(series),
                'series':series,'is_proxy':True,'source':'insufficient history',
                'formula':"fcf_vol_abs = stdev(annual UFCF) — needs ≥2 yrs",'desc':"UFCF dispersion (σ_B input)."}
    a = np.array(list(series.values()))
    i = int(np.argmax(np.abs(a-a.mean()))); ex = np.delete(a,i)
    std_ex = float(ex.std(ddof=ddof)) if len(ex)>=2 else None
    dominated = std_ex is not None and a.std(ddof=ddof)>0 and abs(a.std(ddof=ddof)-std_ex)/a.std(ddof=ddof)>outlier_tol
    return {'field':'ufcf_vol','unit':'mm','basis':'stat','value':float(a.std(ddof=ddof)),
            'std_sample':float(a.std(ddof=1)),'std_pop':float(a.std(ddof=0)),'std_ex_extreme':std_ex,
            'extreme_year':sorted(series)[i],'outlier_dominated':bool(dominated),'n_years':len(series),
            'series':{int(k):round(v,1) for k,v in series.items()},'tax_rate_used':tax,
            'is_proxy':bool(len(series)<5 or dominated),'source':'Computed — stdev of annual UFCF series',
            'formula':"fcf_vol_abs = stdev(annual UFCF); UFCF_t = EBITDA_t - EBIT_t·tax - CapEx_t - ΔNWC_t",
            'desc':"Std-dev of annual UFCF — CS-Model barrier vol σ_B input."}

def get_implied_vol(api):
    """
    1Y IMPLIED EQUITY VOL.  basis=market  unit=decimal.  PARKED — returns None.
    Yahoo option-chain impliedVolatility is unusable for this universe (illiquid chains, solver
    bisection artifacts). The structural model substitutes realized_vol. Field kept for completeness.
    """
    return {'field':'implied_vol','unit':'decimal','basis':'market','latest':None,'fy_baseline':None,
            'source':'parked (Yahoo option IV unusable)','formula':"implied_vol → substitute realized_vol",
            'desc':"1y implied equity vol — parked; realized stands in.",'is_proxy':False}

# ── runner + inspector ───────────────────────────────────────────────────────
ALL_GETTERS = ['get_revenues','get_ebitda','get_adj_ebitda','get_capex','get_cash_interest',
    'get_cash_taxes','get_ch_nwc','get_cash','get_total_debt','get_total_liabilities',
    'get_equity_cap','get_realized_vol','get_implied_vol','get_ebit','get_tax_rate','get_ufcf',
    'get_fcf','get_ufcf_vol','get_ebitda_to_adj_ebitda','get_ltm_vs_2y_avg_ebitda',
    'get_ebitda_less_capex_to_interest','get_net_debt_to_ebitda','get_fcf_to_net_debt','get_net_debt_to_ev']

def build_all(api):
    out = {}
    for g in ALL_GETTERS:
        try: out[g.replace('get_','')] = globals()[g](api)
        except Exception as e: out[g.replace('get_','')] = {'error': f"{type(e).__name__}: {e}"}
    return out

def inspect(api):
    res = build_all(api)
    for name, r in res.items():
        if 'error' in r:
            print(f"\n■ {name:30s} ERROR: {r['error']}"); continue
        u = r.get('unit','')
        if r.get('basis')=='stat':
            print(f"\n■ {name:30s} [{u}]  value={r.get('value')}  n={r.get('n_years')}  outlier={r.get('outlier_dominated')}")
            print(f"    series={r.get('series')}  std_ex_extreme={r.get('std_ex_extreme')}"); continue
        lat, fyb = r.get('latest'), r.get('fy_baseline')
        lv = f"{lat['value']:.4g}" if lat else "None"; fv = f"{fyb['value']:.4g}" if fyb else "None"
        print(f"\n■ {name:30s} [{r.get('basis')}/{u}]  LATEST={lv} (as_of {lat.get('as_of') if lat else '-'})   FY_BASE={fv}")
        if lat and 'components' in lat:                      # the in-between values
            for a, c in lat['components'].items():
                print(f"      └ {a:16s} latest={c['value']:>12.3f}  ({c.get('date')})")
            print(f"        period_consistent={lat.get('period_consistent')}")
        if fyb and 'components' in fyb:
            for a, c in fyb['components'].items():
                print(f"      └ {a:16s} FY    ={c['value']:>12.3f}  ({c.get('point')})")
    return res
