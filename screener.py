"""
issuer-screener — SINGLE-FILE build (engine + registry + fields + runner).
Drop this file next to your notebook and run:   exec(open("screener.py").read())
Then:   api = yf.Ticker("BALL");  res = inspect(api)        # prints every field
        all_fields = build_all(api)                          # dict {field: contract}
"""

import numpy as np
import pandas as pd
import requests

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
        return (
            df if (df is not None and hasattr(df, "empty") and not df.empty) else None
        )
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
    if med <= 115:  # ~3 months
        return ("quarterly", 4)
    if med <= 250:  # ~6 months
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


def resolve_flow(
    field,
    q_series,
    a_series,
    *,
    unit="mm",
    scale=1e6,
    source="",
    formula="",
    is_proxy=False,
):
    """
    FLOW field (income/cash-flow item). 'latest' = trailing-twelve-month, rolled over
    the detected frequency (4 quarters / 2 semiannual). fy_baseline = last annual.
    since_fy_start = the current-FY interim flows (each dated) + their cumulative sum.

    When NO interim cadence exists, 'latest' FALLS BACK to the last annual value
    (it's the truthiest 12-month figure we have for that issuer).
    """
    freq_label, ppy = infer_frequency(q_series)
    fy_end_m = infer_fy_end_month(a_series)
    anchor = last_fy_end(a_series, q_series, fy_end_m)

    # latest = TTM if we have a full cycle of interims, else fall back to last annual
    latest = None
    if ppy in (2, 4) and len(q_series) >= ppy:
        win = q_series.iloc[-ppy:]
        latest = {
            "value": float(win.sum()) / scale,
            "as_of": _iso(win.index[-1]),
            "basis": f"TTM ({ppy}×{'Q' if ppy == 4 else 'H'} rolling)",
            "window": f"{_iso(win.index[0])}→{_iso(win.index[-1])}",
        }
    elif not a_series.empty:  # annual-only reporter — latest := last annual
        latest = {
            "value": float(a_series.iloc[-1]) / scale,
            "as_of": _iso(a_series.index[-1]),
            "basis": "FY (no interim cadence — annual is the latest)",
        }

    fy_baseline = None
    if not a_series.empty:
        fy_baseline = {
            "value": float(a_series.iloc[-1]) / scale,
            "fy": int(a_series.index[-1].year),
            "as_of": _iso(a_series.index[-1]),
        }

    ytd = since_fy_start(q_series, anchor)
    return {
        "field": field,
        "unit": unit,
        "basis": "ttm",
        "frequency": freq_label,
        "latest": latest,
        "fy_baseline": fy_baseline,
        "since_fy_start": _series_records(ytd, scale),
        "ytd_cumulative": (float(ytd.sum()) / scale if len(ytd) else None),
        "source": source,
        "formula": formula,
        "is_proxy": is_proxy,
    }


def resolve_level(
    field,
    q_series,
    a_series,
    *,
    unit="mm",
    scale=1e6,
    source="",
    formula="",
    is_proxy=False,
):
    """
    STOCK/level field (balance-sheet item). 'latest' = most recent snapshot (interim if
    available, else annual). fy_baseline = last annual snapshot. since_fy_start = the
    interim snapshots dated in the current FY (no cumulative — levels don't sum).
    """
    freq_label, _ = infer_frequency(q_series)
    fy_end_m = infer_fy_end_month(a_series)
    anchor = last_fy_end(a_series, q_series, fy_end_m)

    if not q_series.empty:
        latest = {
            "value": float(q_series.iloc[-1]) / scale,
            "as_of": _iso(q_series.index[-1]),
            "basis": "level (latest interim)",
        }
    elif not a_series.empty:
        latest = {
            "value": float(a_series.iloc[-1]) / scale,
            "as_of": _iso(a_series.index[-1]),
            "basis": "level (latest FY)",
        }
    else:
        latest = None

    fy_baseline = None
    if not a_series.empty:
        fy_baseline = {
            "value": float(a_series.iloc[-1]) / scale,
            "fy": int(a_series.index[-1].year),
            "as_of": _iso(a_series.index[-1]),
        }

    snaps = since_fy_start(q_series, anchor)
    return {
        "field": field,
        "unit": unit,
        "basis": "level",
        "frequency": freq_label,
        "latest": latest,
        "fy_baseline": fy_baseline,
        "since_fy_start": _series_records(snaps, scale),
        "source": source,
        "formula": formula,
        "is_proxy": is_proxy,
    }


# ==========================================================================
# SECTION: SEC EDGAR + CIK lookup helpers
# ==========================================================================
"""
SEC integration for US filers. Used by cash_interest and cash_taxes (NOT ch_nwc — we
proved EDGAR can't reproduce BBG's _OTHER residual definition there).

- _load_ticker_to_cik_map(): downloads SEC's public ticker→CIK map once, caches.
- _cik_for(ticker):           returns CIK for US-listed tickers, None otherwise.
                              Heuristic: a ticker with '.' has a foreign suffix
                              (.PA / .L / .DE / .MI / etc.), hence non-US.
- _sec_concept(cik, tag):     latest FY value for a us-gaap period tag (annual 10-K).
"""

_SEC_HEADERS = {"User-Agent": "issuer-screener your.email@firm.com"}
_TICKER_TO_CIK_CACHE = None


def _load_ticker_to_cik_map():
    """Fetch SEC's public ticker → CIK mapping once; cache globally."""
    global _TICKER_TO_CIK_CACHE
    if _TICKER_TO_CIK_CACHE is not None:
        return _TICKER_TO_CIK_CACHE
    url = "https://www.sec.gov/files/company_tickers.json"
    try:
        r = requests.get(url, headers=_SEC_HEADERS, timeout=15)
        r.raise_for_status()
        raw = r.json()
        _TICKER_TO_CIK_CACHE = {
            row["ticker"].upper(): str(row["cik_str"]).zfill(10) for row in raw.values()
        }
    except Exception:
        _TICKER_TO_CIK_CACHE = {}
    return _TICKER_TO_CIK_CACHE


def _cik_for(ticker):
    """CIK for US-listed tickers; None for foreign (anything with a '.' suffix)."""
    if not isinstance(ticker, str) or "." in ticker:
        return None
    cik_map = _load_ticker_to_cik_map()
    return cik_map.get(ticker.upper())


def _sec_concept(cik, tag):
    """Latest FY (10-K, >350 days) value for a us-gaap period tag. (val, date) or (None, None)."""
    if cik is None:
        return None, None
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json"
    try:
        r = requests.get(url, headers=_SEC_HEADERS, timeout=10)
        if r.status_code != 200:
            return None, None
        facts = r.json().get("units", {}).get("USD", [])
        if not facts:
            return None, None
        df = pd.DataFrame(facts)
        df["end"] = pd.to_datetime(df["end"])
        df["start"] = pd.to_datetime(df["start"], errors="coerce")
        df["days"] = (df["end"] - df["start"]).dt.days
        fy = df[(df["days"] > 350) & (df["form"] == "10-K")].sort_values("end")
        if fy.empty:
            return None, None
        last = fy.iloc[-1]
        return float(last["val"]), last["end"]
    except Exception:
        return None, None


# ==========================================================================
# SECTION: registry.py
# ==========================================================================
"""
issuer-screener — FIELD REGISTRY + DISPATCHER
=============================================
Simple fields are declared in FIELDS and dispatched through resolve_field.
Multi-tier fields (cash_interest, cash_taxes, ch_nwc) bypass the registry and have
their own resolvers in fields.py — they need variant/priority logic that the simple
registry can't express.
"""

STMT = {  # logical statement -> (quarterly attr, annual attr)
    "income": ("quarterly_income_stmt", "income_stmt"),
    "cash": ("quarterly_cash_flow", "cash_flow"),
    "balance": ("quarterly_balance_sheet", "balance_sheet"),
}

FIELDS = {
    "revenues": dict(
        basis="ttm",
        stmt="income",
        line="Total Revenue",
        unit="mm",
        sign=1,
        desc="Trailing-twelve-month total revenue.",
        formula="revenues = TTM rolling of income_stmt['Total Revenue'];  fy_baseline = annual Total Revenue",
    ),
    "ebitda": dict(
        basis="ttm",
        stmt="income",
        line="EBITDA",
        unit="mm",
        sign=1,
        desc="Trailing-twelve-month reported EBITDA.",
        formula="ebitda = TTM rolling of income_stmt['EBITDA'];  fy_baseline = annual EBITDA",
    ),
    "capex": dict(
        basis="ttm",
        stmt="cash",
        line=["Capital Expenditure Reported", "Capital Expenditure"],
        unit="mm",
        sign=1,
        desc="Trailing-twelve-month capital expenditure (negative = cash outflow).",
        formula="capex = TTM rolling of cash_flow['Capital Expenditure Reported'] "
        "(fallback 'Capital Expenditure'), kept negative",
    ),
    "cash": dict(
        basis="level",
        stmt="balance",
        line=[
            "Cash Cash Equivalents And Short Term Investments",
            "Cash And Cash Equivalents",
        ],
        unit="mm",
        sign=1,
        desc="Cash, equivalents and short-term investments (latest balance-sheet level).",
        formula="cash = balance_sheet['Cash Cash Equivalents And Short Term Investments'] (latest snapshot)",
    ),
    "total_debt": dict(
        basis="level",
        stmt="balance",
        line="Total Debt",
        unit="mm",
        sign=1,
        desc="Total debt (latest balance-sheet level).  [definition/leases = PM Decision 2]",
        formula="total_debt = balance_sheet['Total Debt'] (latest snapshot)",
    ),
    "total_liabilities": dict(
        basis="level",
        stmt="balance",
        line="Total Liabilities Net Minority Interest",
        unit="mm",
        sign=1,
        desc="Total liabilities ex-minority-interest (latest level); CS-Model TOTAL_LIABILITIES.",
        formula="total_liabilities = balance_sheet['Total Liabilities Net Minority Interest'] (latest snapshot)",
    ),
}


def _pick_series(api, stmt, line, sign):
    qattr, aattr = STMT[stmt]
    lines = line if isinstance(line, list) else [line]
    qdf, adf = _safe(api, qattr), _safe(api, aattr)
    for ln in lines:  # first line present (in either frame) wins
        q = clean_series(qdf, ln) * sign
        a = clean_series(adf, ln) * sign
        if not q.empty or not a.empty:
            return q, a, ln
    return pd.Series(dtype=float), pd.Series(dtype=float), lines[0]


def resolve_field(api, name):
    """Resolve any registry field to the uniform contract via the engine."""
    s = FIELDS[name]
    q, a, used = _pick_series(api, s["stmt"], s["line"], s.get("sign", 1))
    common = dict(
        unit=s["unit"],
        source=f"Yahoo Finance · {s['stmt']}['{used}']",
        formula=s["formula"],
        is_proxy=s.get("is_proxy", False),
    )
    out = (
        resolve_flow(name, q, a, **common)
        if s["basis"] == "ttm"
        else resolve_level(name, q, a, **common)
    )
    out["desc"] = s["desc"]
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

Two headline numbers per field, both the metric AS DEFINED IN THE EXCEL:
    latest       = newest available (TTM rolled to frequency / latest level / latest market)
    fy_baseline  = value as of the last annual statement   (the always-available FLOOR)
"""


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  A.  SIMPLE STATEMENT FIELDS  (thin registry wrappers — see registry.py)    ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def get_revenues(api):
    """REVENUES.  basis=ttm  unit=mm. revenues = TTM rolling of income_stmt['Total Revenue']."""
    return resolve_field(api, "revenues")


def get_ebitda(api, stale_years=2):
    """
    EBITDA. basis=ttm  unit=mm.

    Tier 1 (primary): yfinance 'EBITDA' headline (TTM-rolled / FY annual)
    Tier 2 (cross-check / fallback):
        first principles = Net Income + Tax Provision + Interest Expense
                         + Reconciled Depreciation
        — same date alignment; primarily a sanity check on Tier 1.

    No sanity auto-flip — both tiers shown in variants; primary picks Tier 1.
    """
    qi = _safe(api, "quarterly_income_stmt")
    ai = _safe(api, "income_stmt")

    tiers = []

    # ---- Tier 1: yfinance 'EBITDA' headline ----
    q1 = clean_series(qi, "EBITDA")
    a1 = clean_series(ai, "EBITDA")
    if not q1.empty or not a1.empty:
        r = resolve_flow("x", q1, a1, unit="mm")
        lat = (r["latest"] or {}).get("value")
        fyb = (r["fy_baseline"] or {}).get("value")
        lat_dt = (r["latest"] or {}).get("as_of")
        fy_dt = (r["fy_baseline"] or {}).get("as_of")
        age = _age_years(lat_dt or fy_dt)
        tiers.append(
            {
                "label": "yf income_stmt['EBITDA']",
                "latest_mm": lat,
                "latest_as_of": lat_dt,
                "fy_mm": fyb,
                "fy_as_of": fy_dt,
                "source": "Yahoo Finance · income_stmt['EBITDA']",
                "formula": "TTM rolling of income_stmt['EBITDA']",
                "priority": 1,
                "is_stale": (age is not None and age > stale_years),
                "age_years": round(age, 1) if age is not None else None,
                "is_proxy": False,
            }
        )

    # ---- Tier 2: first principles = NI + Tax + Interest + D&A ----
    def _component(df, line):
        return clean_series(df, line)

    def _build_fp(df):
        ni = _component(df, "Net Income")
        tx = _component(df, "Tax Provision")
        ie = _component(df, "Interest Expense")
        da = _component(df, "Reconciled Depreciation")
        if ni.empty or da.empty:
            return pd.Series(dtype=float), []
        # NI keeps its sign (can be negative); add-back items are taken absolute as expenses
        comp = pd.concat([ni, tx.abs(), ie.abs(), da.abs()], axis=1)
        s = comp.sum(axis=1, min_count=comp.shape[1]).dropna()
        used = [
            "Net Income",
            "Tax Provision",
            "Interest Expense",
            "Reconciled Depreciation",
        ]
        return s, used

    q2, used_q = _build_fp(qi)
    a2, used_a = _build_fp(ai)
    if not q2.empty or not a2.empty:
        r = resolve_flow("x", q2, a2, unit="mm")
        lat = (r["latest"] or {}).get("value")
        fyb = (r["fy_baseline"] or {}).get("value")
        lat_dt = (r["latest"] or {}).get("as_of")
        fy_dt = (r["fy_baseline"] or {}).get("as_of")
        age = _age_years(lat_dt or fy_dt)
        labels_str = " + ".join(used_q or used_a)
        tiers.append(
            {
                "label": "first principles: NI + Tax + Interest + D&A",
                "latest_mm": lat,
                "latest_as_of": lat_dt,
                "fy_mm": fyb,
                "fy_as_of": fy_dt,
                "source": f"Yahoo Finance · income_stmt Σ({labels_str})",
                "formula": f"TTM rolling of Σ({labels_str})  [first principles]",
                "priority": 2,
                "is_stale": (age is not None and age > stale_years),
                "age_years": round(age, 1) if age is not None else None,
                "is_proxy": False,
            }
        )

    return _multi_tier_contract(
        "ebitda",
        tiers,
        desc="EBITDA. Multi-tier: yf headline → first principles (NI+Tax+Interest+D&A).",
        sanity_check_ratio=None,
    )


def get_capex(api):
    """CAPEX.  basis=ttm  unit=mm  (NEGATIVE). TTM rolling of cash_flow['Capital Expenditure Reported']."""
    return resolve_field(api, "capex")


def get_cash(api):
    """CASH.  basis=level  unit=mm.  PRIMARY: 'Cash Cash Equivalents And Short Term Investments'."""
    out = resolve_field(api, "cash")
    csti_l, csti_f, _, _ = _level_mm(
        api, "Cash Cash Equivalents And Short Term Investments"
    )
    ce_l, ce_f, _, _ = _level_mm(api, "Cash And Cash Equivalents")
    out["variants"] = [
        _var(
            "Cash + ST investments",
            csti_l,
            csti_f,
            "balance_sheet['Cash Cash Equivalents And Short Term Investments']",
        ),
        _var(
            "Cash & equivalents only",
            ce_l,
            ce_f,
            "balance_sheet['Cash And Cash Equivalents']",
        ),
    ]
    return out


def get_total_debt(api):
    """TOTAL DEBT.  basis=level  unit=mm.  PRIMARY: 'Total Debt'."""
    out = resolve_field(api, "total_debt")
    td_l, td_f, _, _ = _level_mm(api, "Total Debt")
    ltd_l, ltd_f, _, _ = _level_mm(api, "Long Term Debt")
    cd_l, cd_f, _, _ = _level_mm(api, "Current Debt")
    ltcl_l, ltcl_f, _, _ = _level_mm(api, "Long Term Debt And Capital Lease Obligation")
    cdcl_l, cdcl_f, _, _ = _level_mm(api, "Current Debt And Capital Lease Obligation")
    variants = [
        _var("Total Debt (yfinance)", td_l, td_f, "balance_sheet['Total Debt']")
    ]
    if ltd_l is not None or cd_l is not None:
        variants.append(
            _var(
                "LT Debt + Current Debt",
                _z(ltd_l) + _z(cd_l),
                (_z(ltd_f) + _z(cd_f) if (ltd_f or cd_f) else None),
                "Long Term Debt + Current Debt",
            )
        )
    if ltcl_l is not None or cdcl_l is not None:
        variants.append(
            _var(
                "LT + Current incl. leases",
                _z(ltcl_l) + _z(cdcl_l),
                (_z(ltcl_f) + _z(cdcl_f) if (ltcl_f or cdcl_f) else None),
                "Long Term Debt And Capital Lease Obligation + Current Debt And Capital Lease Obligation",
            )
        )
    out["variants"] = variants
    return out


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  B.  MULTI-TIER FIELDS  (SEC + yfinance + accrual proxy ladders)            ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
"""
Three fields use a multi-tier resolution:
  - cash_interest  : SEC InterestPaidNet → yf Interest Paid Cff/Cfo/Supplemental → accrual proxy
  - cash_taxes     : SEC IncomeTaxesPaidNet → yf Taxes Refund Paid / Supplemental (no accrual)
  - ch_nwc         : yf cash_flow ['Change In Working Capital'] → yf BS proxy (-Δ(AR+Inv−AP))

Each variant computes BOTH `latest` (TTM rolled to frequency) and `fy_baseline` (annual).
Primary is picked by (not_stale, priority, non_zero, recency).
ALL variants are surfaced in `variants` for audit.
"""


def _age_years(date_str_or_ts):
    """Years since a date (ISO string or pd.Timestamp). None if input is None."""
    if date_str_or_ts is None:
        return None
    try:
        d = pd.Timestamp(date_str_or_ts)
        return (pd.Timestamp.now() - d).days / 365.25
    except Exception:
        return None


def _sec_tier(cik, tag, *, priority=1, stale_years=2):
    """
    Wrap an SEC concept fetch into a tier dict matching the multi-tier scheme.
    Returns POSITIVE magnitude (cash paid). Returns None if the tag doesn't exist.
    """
    if cik is None:
        return None
    val, date = _sec_concept(cik, tag)
    if val is None:
        return None
    age = _age_years(date)
    mag_mm = abs(val) / 1e6
    return {
        "label": f"SEC us-gaap:{tag}",
        # SEC is annual-only — latest equals fy_baseline (both the same FY 10-K value)
        "latest_mm": mag_mm,
        "latest_as_of": _iso(date),
        "fy_mm": mag_mm,
        "fy_as_of": _iso(date),
        "source": f"SEC EDGAR · us-gaap:{tag}",
        "formula": f"SEC us-gaap:{tag} (annual 10-K)",
        "priority": priority,
        "is_stale": (age is not None and age > stale_years),
        "age_years": round(age, 1) if age is not None else None,
        "is_proxy": False,
    }


def _yf_cash_tier(api, labels, *, priority=2, stale_years=2):
    """
    Sum quarterly and annual yfinance cash-flow labels (labels = list).
    Returns POSITIVE magnitude (cash paid). TTM-rolled `latest` + annual `fy_baseline`.
    Returns None if no labels present.
    """
    qcf = _safe(api, "quarterly_cash_flow")
    acf = _safe(api, "cash_flow")

    def _sum(df):
        if df is None:
            return pd.Series(dtype=float), []
        present = [l for l in labels if l in df.index]
        if not present:
            return pd.Series(dtype=float), []
        parts = [clean_series(df, l) for l in present]
        s = pd.concat(parts, axis=1).sum(axis=1, min_count=1).dropna()
        return s, present

    q_sum, q_labels = _sum(qcf)
    a_sum, a_labels = _sum(acf)
    if q_sum.empty and a_sum.empty:
        return None

    # Force POSITIVE magnitude (yfinance returns these negative; we want cash-paid magnitude)
    q_sum = q_sum.abs()
    a_sum = a_sum.abs()

    labels_str = " + ".join(q_labels or a_labels)
    r = resolve_flow("x", q_sum, a_sum, unit="mm")
    lat = (r["latest"] or {}).get("value")
    fyb = (r["fy_baseline"] or {}).get("value")
    lat_dt = (r["latest"] or {}).get("as_of")
    fy_dt = (r["fy_baseline"] or {}).get("as_of")
    age = _age_years(lat_dt or fy_dt)
    return {
        "label": f"yf cash_flow Σ({labels_str})",
        "latest_mm": lat,
        "latest_as_of": lat_dt,
        "fy_mm": fyb,
        "fy_as_of": fy_dt,
        "source": f"Yahoo Finance · cash_flow Σ({labels_str})",
        "formula": f"|TTM rolling of Σ({labels_str})|",
        "priority": priority,
        "is_stale": (age is not None and age > stale_years),
        "age_years": round(age, 1) if age is not None else None,
        "is_proxy": False,
    }


def _yf_accrual_tier(
    api,
    statement_attr_q,
    statement_attr_a,
    line,
    *,
    priority=3,
    stale_years=2,
    label_override=None,
):
    """
    Accrual proxy from an income/cash-flow statement line.
    Returns POSITIVE magnitude. Used for cash_interest: |TTM Interest Expense|.
    """
    q = clean_series(_safe(api, statement_attr_q), line)
    a = clean_series(_safe(api, statement_attr_a), line)
    if q.empty and a.empty:
        return None
    # Force POSITIVE magnitude
    q = q.abs()
    a = a.abs()
    r = resolve_flow("x", q, a, unit="mm")
    lat = (r["latest"] or {}).get("value")
    fyb = (r["fy_baseline"] or {}).get("value")
    lat_dt = (r["latest"] or {}).get("as_of")
    fy_dt = (r["fy_baseline"] or {}).get("as_of")
    age = _age_years(lat_dt or fy_dt)
    return {
        "label": label_override or f"accrual proxy: |{line}|",
        "latest_mm": lat,
        "latest_as_of": lat_dt,
        "fy_mm": fyb,
        "fy_as_of": fy_dt,
        "source": f"Yahoo Finance · income/cash['{line}']",
        "formula": f"|TTM rolling of '{line}'|  [accrual proxy]",
        "priority": priority,
        "is_stale": (age is not None and age > stale_years),
        "age_years": round(age, 1) if age is not None else None,
        "is_proxy": True,
    }


def _pick_primary(tiers, sanity_check_ratio=None):
    """
    Pick the primary tier from a list of tier dicts.
    Sort key: (is_stale, priority, is_zero_latest, -date).

    sanity_check_ratio: if set (e.g. 0.30), and best cash tier (priority<accrual) has
      |latest| < ratio × |accrual_latest|, fall back to accrual with a note flag.
    """
    if not tiers:
        return None, False
    # Only tiers with at least a fy_mm or latest_mm
    usable = [
        t
        for t in tiers
        if (t.get("latest_mm") is not None or t.get("fy_mm") is not None)
    ]
    if not usable:
        return None, False

    def sort_key(t):
        latest = t.get("latest_mm")
        date_str = t.get("latest_as_of") or t.get("fy_as_of")
        try:
            ts = pd.Timestamp(date_str).timestamp() if date_str else 0
        except Exception:
            ts = 0
        is_zero = latest is not None and abs(latest) < 0.5
        return (t["is_stale"], t["priority"], is_zero, -ts)

    sorted_tiers = sorted(usable, key=sort_key)
    best = sorted_tiers[0]
    sanity_failed = False

    if sanity_check_ratio is not None:
        # Find accrual fallback (highest priority number = lowest preference but still cash-like)
        accrual_tiers = [t for t in usable if t.get("is_proxy")]
        cash_tiers = [t for t in usable if not t.get("is_proxy")]
        if accrual_tiers and cash_tiers:
            best_cash = sorted(cash_tiers, key=sort_key)[0]
            acc = accrual_tiers[0]
            bc_lat = best_cash.get("latest_mm")
            ac_lat = acc.get("latest_mm")
            if bc_lat is not None and ac_lat is not None and abs(ac_lat) > 0:
                if abs(bc_lat) < sanity_check_ratio * abs(ac_lat):
                    best = acc
                    sanity_failed = True

    return best, sanity_failed


def _multi_tier_contract(field_name, tiers, *, desc, sanity_check_ratio=None):
    """Assemble the uniform contract from a list of tiers + pick primary."""
    if not tiers:
        return {
            "field": field_name,
            "unit": "mm",
            "basis": "ttm",
            "latest": None,
            "fy_baseline": None,
            "variants": [],
            "source": "unavailable",
            "formula": "",
            "desc": desc,
            "is_proxy": False,
        }

    primary, sanity_failed = _pick_primary(tiers, sanity_check_ratio=sanity_check_ratio)
    if primary is None:
        return {
            "field": field_name,
            "unit": "mm",
            "basis": "ttm",
            "latest": None,
            "fy_baseline": None,
            "variants": [],
            "source": "no usable tier",
            "formula": "",
            "desc": desc,
            "is_proxy": False,
        }

    # Build latest / fy_baseline nodes from primary
    latest_node = None
    if primary.get("latest_mm") is not None:
        latest_node = {
            "value": primary["latest_mm"],
            "as_of": primary["latest_as_of"],
            "basis": "TTM" if not primary.get("is_proxy") else "TTM (accrual proxy)",
            "methodology": primary["label"],
        }
        if sanity_failed:
            latest_node["note"] = (
                "Cash variant < 30% of accrual → fell back to accrual proxy"
            )
        if primary.get("is_stale"):
            latest_node["stale"] = True
            latest_node["age_years"] = primary.get("age_years")

    fy_node = None
    if primary.get("fy_mm") is not None:
        fy_dt = primary.get("fy_as_of")
        fy_node = {
            "value": primary["fy_mm"],
            "as_of": fy_dt,
            "fy": (int(fy_dt[:4]) if fy_dt else None),
            "basis": "annual",
            "methodology": primary["label"],
        }
        if primary.get("is_stale"):
            fy_node["stale"] = True
            fy_node["age_years"] = primary.get("age_years")

    # Variants list (all tiers, sorted by priority)
    variants = []
    for t in sorted(tiers, key=lambda x: x["priority"]):
        variants.append(
            {
                "label": t["label"],
                "latest": t.get("latest_mm"),
                "fy_baseline": t.get("fy_mm"),
                "latest_as_of": t.get("latest_as_of"),
                "fy_as_of": t.get("fy_as_of"),
                "formula": t.get("formula"),
                "is_stale": t.get("is_stale"),
                "is_proxy": t.get("is_proxy"),
                "age_years": t.get("age_years"),
            }
        )

    return {
        "field": field_name,
        "unit": "mm",
        "basis": "ttm",
        "latest": latest_node,
        "fy_baseline": fy_node,
        "variants": variants,
        "source": primary["source"],
        "formula": primary["formula"],
        "desc": desc,
        "is_proxy": primary.get("is_proxy", False),
    }


def get_cash_interest(api, stale_years=2):
    """
    CASH INTEREST PAID. basis=ttm  unit=mm.
    SIGN CONVENTION: returned as POSITIVE magnitude (cash paid out for interest).
    Downstream FCF formula SUBTRACTS this value.

    Tier 1 (any): yf cash_flow Σ(Interest Paid Cff + Interest Paid Cfo
                                + Interest Paid Supplemental Data)
                  TTM-rolled for `latest`, annual for `fy_baseline`.
                  PREFERRED — 'Interest Paid Supplemental Data' typically matches
                  the cash-paid magnitude exactly when present.
    Tier 2 (US filers): SEC us-gaap:InterestPaidNet → fallback InterestPaid
                        (annual 10-K; stale-flagged if >2yr old)
    Tier 3 (proxy, any): |TTM Interest Expense| from income_stmt.
                  Sanity check: if best cash variant < 30% of accrual, fall back to accrual.

    Primary selection: (not_stale, priority, non_zero, recency).
    """
    ticker = getattr(api, "ticker", None)
    cik = _cik_for(ticker)
    tiers = []

    # ---- Tier 1: yf cash labels (any filer) ----
    yf_labels = [
        "Interest Paid Cff",
        "Interest Paid Cfo",
        "Interest Paid Supplemental Data",
    ]
    t1 = _yf_cash_tier(api, yf_labels, priority=1, stale_years=stale_years)
    if t1 is not None:
        tiers.append(t1)

    # ---- Tier 2: SEC (US only) ----
    if cik:
        t2a = _sec_tier(cik, "InterestPaidNet", priority=2, stale_years=stale_years)
        t2b = _sec_tier(cik, "InterestPaid", priority=2, stale_years=stale_years)
        if t2a is not None:
            tiers.append(t2a)
        if t2b is not None:
            tiers.append(t2b)

    # ---- Tier 3: accrual proxy ----
    t3 = _yf_accrual_tier(
        api,
        "quarterly_income_stmt",
        "income_stmt",
        "Interest Expense",
        priority=3,
        stale_years=stale_years,
        label_override="accrual proxy: |TTM Interest Expense|",
    )
    if t3 is not None:
        tiers.append(t3)

    return _multi_tier_contract(
        "cash_interest",
        tiers,
        desc="Cash interest paid (POSITIVE = cash outflow magnitude). Multi-tier: yf cash → SEC cash → accrual proxy.",
        sanity_check_ratio=0.30,
    )


def get_cash_taxes(api, stale_years=2):
    """
    CASH TAXES PAID. basis=ttm  unit=mm.
    SIGN CONVENTION: returned as POSITIVE magnitude (cash paid out for taxes).
    Downstream FCF formula SUBTRACTS this value.

    Tier 1 (any): yf cash_flow Σ(Taxes Refund Paid + Income Tax Paid Supplemental Data)
                  PREFERRED — typically matches cash-paid magnitude when present.
    Tier 2 (US filers): SEC us-gaap:IncomeTaxesPaidNet → fallback IncomeTaxesPaid
                        (stale-flagged; non-zero preferred over zero — e.g. CCL has
                         stale Net=0 and stale Paid=15 → picker chooses 15)

    NO ACCRUAL PROXY — Tax Provision − Deferred Tax is unreliable.
    If both tiers fail, returns unavailable.

    Primary selection: (not_stale, priority, non_zero, recency).
    """
    ticker = getattr(api, "ticker", None)
    cik = _cik_for(ticker)
    tiers = []

    # ---- Tier 1: yf cash labels (any filer) ----
    yf_labels = ["Taxes Refund Paid", "Income Tax Paid Supplemental Data"]
    t1 = _yf_cash_tier(api, yf_labels, priority=1, stale_years=stale_years)
    if t1 is not None:
        tiers.append(t1)

    # ---- Tier 2: SEC (US only) ----
    if cik:
        t2a = _sec_tier(cik, "IncomeTaxesPaidNet", priority=2, stale_years=stale_years)
        t2b = _sec_tier(cik, "IncomeTaxesPaid", priority=2, stale_years=stale_years)
        if t2a is not None:
            tiers.append(t2a)
        if t2b is not None:
            tiers.append(t2b)

    return _multi_tier_contract(
        "cash_taxes",
        tiers,
        desc="Cash taxes paid (POSITIVE = cash outflow magnitude). Multi-tier: yf cash → SEC cash. No accrual proxy.",
        sanity_check_ratio=None,
    )


def get_ch_nwc(api, stale_years=2):
    """
    CH NWC — Change in Net Working Capital. basis=ttm  unit=mm.
    Sign convention: NEGATIVE = NWC increased = cash outflow.

    Tier 1: yf cash_flow ['Change In Working Capital']
            TTM-rolled `latest` (4Q sum) / annual `fy_baseline`.
            For annual-only reporters (no quarterly) `latest` falls back to the annual.
    Tier 2: yf balance-sheet proxy (boss's formula): -Δ(AR + Inventory − AP)
            `latest`     = quarterly Y/Y at most recent quarter end (~1y back match)
            `fy_baseline`= annual Y/Y at last FY end
            Used when CFS headline absent OR as a cross-check.

    EDGAR REMOVED (we proved no us-gaap tag or combination reproduces BBG's
    TRAIL_12M_CHNG_IN_WORK_CAP_OTHER residual definition).
    """
    tiers = []

    # ---- Tier 1: yf CFS headline ----
    qcf = _safe(api, "quarterly_cash_flow")
    acf = _safe(api, "cash_flow")
    H = "Change In Working Capital"
    q1 = clean_series(qcf, H)
    a1 = clean_series(acf, H)
    if not q1.empty or not a1.empty:
        r = resolve_flow("x", q1, a1, unit="mm")
        lat = (r["latest"] or {}).get("value")
        fyb = (r["fy_baseline"] or {}).get("value")
        lat_dt = (r["latest"] or {}).get("as_of")
        fy_dt = (r["fy_baseline"] or {}).get("as_of")
        age = _age_years(lat_dt or fy_dt)
        tiers.append(
            {
                "label": "cash_flow['Change In Working Capital']",
                "latest_mm": lat,
                "latest_as_of": lat_dt,
                "fy_mm": fyb,
                "fy_as_of": fy_dt,
                "source": "Yahoo Finance · cash_flow['Change In Working Capital']",
                "formula": "TTM rolling of cash_flow['Change In Working Capital']  "
                "(annual-only reporters: latest = fy_baseline)",
                "priority": 1,
                "is_stale": (age is not None and age > stale_years),
                "age_years": round(age, 1) if age is not None else None,
                "is_proxy": False,
            }
        )

    # ---- Tier 2: yf BS proxy (boss's formula) ----
    def _bs_nwc(df):
        if df is None:
            return pd.Series(dtype=float)
        ar = clean_series(df, "Accounts Receivable")
        inv = clean_series(df, "Inventory")
        ap = clean_series(df, "Accounts Payable")
        if inv.empty and not ar.empty:
            inv = pd.Series(0.0, index=ar.index)
        if ar.empty or ap.empty:
            return pd.Series(dtype=float)
        nwc = (
            pd.concat([ar, inv, -ap], axis=1)
            .sum(axis=1, min_count=2)
            .dropna()
            .sort_index()
        )
        return -nwc.diff().dropna()

    q3 = _bs_nwc(_safe(api, "quarterly_balance_sheet"))
    a3 = _bs_nwc(_safe(api, "balance_sheet"))
    if not q3.empty or not a3.empty:
        r = resolve_flow("x", q3, a3, unit="mm")
        lat = (r["latest"] or {}).get("value")
        fyb = (r["fy_baseline"] or {}).get("value")
        lat_dt = (r["latest"] or {}).get("as_of")
        fy_dt = (r["fy_baseline"] or {}).get("as_of")
        age = _age_years(lat_dt or fy_dt)
        tiers.append(
            {
                "label": "BS proxy: -Δ(AR + Inv − AP)",
                "latest_mm": lat,
                "latest_as_of": lat_dt,
                "fy_mm": fyb,
                "fy_as_of": fy_dt,
                "source": "Yahoo Finance · balance_sheet (-Δ(AR+Inv-AP)) y/y",
                "formula": "-[(AR+Inv-AP)_t - (AR+Inv-AP)_{t-1}]  [BS proxy; boss's formula]",
                "priority": 2,
                "is_stale": (age is not None and age > stale_years),
                "age_years": round(age, 1) if age is not None else None,
                "is_proxy": True,
            }
        )

    return _multi_tier_contract(
        "ch_nwc",
        tiers,
        desc="Change in net working capital (cash-signed). Primary: yf CFS headline. Fallback: BS proxy.",
        sanity_check_ratio=None,
    )


def get_total_liabilities(api):
    """
    TOTAL LIABILITIES.  basis=level  unit=mm.  CS-Model TOTAL_LIABILITIES.
    FORMULA: total_liabilities = balance_sheet['Total Liabilities Net Minority Interest']
    fallback: balance_sheet['Total Assets'] − 'Total Equity Gross Minority Interest'.
    """
    L = "Total Liabilities Net Minority Interest"
    q, a = (
        clean_series(_safe(api, "quarterly_balance_sheet"), L),
        clean_series(_safe(api, "balance_sheet"), L),
    )
    if not q.empty or not a.empty:
        return _attach(
            resolve_level(
                "total_liabilities",
                q,
                a,
                unit="mm",
                source=f"Yahoo Finance · balance_sheet['{L}']",
                formula=f"total_liabilities = balance_sheet['{L}'] (latest level)",
            ),
            "Total liabilities ex-minority-interest (level).",
        )

    def _identity(df):
        if df is None:
            return pd.Series(dtype=float)
        ta, te = (
            clean_series(df, "Total Assets"),
            clean_series(df, "Total Equity Gross Minority Interest"),
        )
        return ta.subtract(te, fill_value=np.nan).dropna()

    q2, a2 = (
        _identity(_safe(api, "quarterly_balance_sheet")),
        _identity(_safe(api, "balance_sheet")),
    )
    return _attach(
        resolve_level(
            "total_liabilities",
            q2,
            a2,
            unit="mm",
            source="Yahoo Finance · Total Assets - Total Equity Gross Minority Interest",
            formula="total_liabilities = Total Assets - Total Equity Gross Minority Interest [identity; direct line absent]",
        ),
        "Total liabilities via BS identity (direct line absent).",
    )


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  C.  MARKET FIELDS  (price-derived; own date logic, same contract)          ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _closes(api):
    """Daily Close series, tz-stripped, ascending. From api.history(period='3y', auto_adjust=True)."""
    try:
        h = api.history(period="3y", auto_adjust=True)
        s = h["Close"].copy()
        s.index = pd.DatetimeIndex([_to_ts(d) for d in s.index])
        return s[~s.index.isna()].dropna().sort_index()
    except Exception:
        return pd.Series(dtype=float)


def _close_on(closes, date):
    """Close on `date`, or the last trading day BEFORE it (as-of)."""
    if closes.empty or pd.isna(date):
        return None
    sub = closes[closes.index <= pd.Timestamp(date)]
    return float(sub.iloc[-1]) if len(sub) else None


# ── currency + variant helpers ────────────────────────────────────────────────
def _info(api):
    try:
        return api.info or {}
    except Exception:
        return {}


# venues yfinance quotes in SUBUNITS (pence / cents / agorot) — price is 100× the major unit.
_SUBUNIT_CCY = {"GBp", "GBX", "ZAc", "ILA"}


def _price_scale(api):
    """Divisor that turns a quoted price into the MAJOR currency unit (GBp→GBP is /100)."""
    return 100.0 if (_info(api).get("currency") or "") in _SUBUNIT_CCY else 1.0


def _level_mm(api, line, sign=1):
    """(latest_mm, fy_mm, latest_date, fy_date) for a balance-sheet line, in millions."""
    q = clean_series(_safe(api, "quarterly_balance_sheet"), line) * sign
    a = clean_series(_safe(api, "balance_sheet"), line) * sign
    src = q if not q.empty else a
    lat = float(src.iloc[-1]) / 1e6 if not src.empty else None
    lat_d = _iso(src.index[-1]) if not src.empty else None
    fy = float(a.iloc[-1]) / 1e6 if not a.empty else None
    fy_d = _iso(a.index[-1]) if not a.empty else None
    return lat, fy, lat_d, fy_d


def _ttm_pair(api, stmt, line, sign=1):
    """(latest_mm, fy_mm) for an income / cash-flow line, TTM-rolled via the engine."""
    qattr, aattr = STMT[stmt]
    q = clean_series(_safe(api, qattr), line) * sign
    a = clean_series(_safe(api, aattr), line) * sign
    r = resolve_flow("x", q, a, unit="mm")
    return ((r["latest"] or {}).get("value"), (r["fy_baseline"] or {}).get("value"))


def _var(label, latest, fy=None, formula=""):
    """One reported calculation method."""
    return {"label": label, "latest": latest, "fy_baseline": fy, "formula": formula}


def _z(v):
    return v if v is not None else 0.0


def get_equity_cap(api):
    """
    EQUITY CAP — market capitalisation.  basis=market  unit=mm.
    PRIMARY: balance-sheet Ordinary Shares Number × Close, prices subunit-corrected (GBp→GBP /100).
    """
    L = "Ordinary Shares Number"
    q = clean_series(_safe(api, "quarterly_balance_sheet"), L)
    a = clean_series(_safe(api, "balance_sheet"), L)
    closes = _closes(api)
    scale = _price_scale(api)
    info = _info(api)
    sh = q if not q.empty else a
    latest = fyb = None
    variants = []
    if not sh.empty and not closes.empty:
        sh_l = float(sh.iloc[-1])
        close_l = float(closes.iloc[-1]) / scale
        v1 = sh_l * close_l / 1e6
        latest = {
            "value": v1,
            "as_of": _iso(closes.index[-1]),
            "basis": f"bs shares ({_iso(sh.index[-1])}) × latest close /{scale:g}",
        }
        variants.append(
            _var(
                "bs shares × latest close",
                v1,
                None,
                "Ordinary Shares Number × Close (subunit-adj)",
            )
        )
        pc = info.get("previousClose")
        if pc:
            variants.append(
                _var(
                    "bs shares × previousClose (live)",
                    sh_l * (pc / scale) / 1e6,
                    None,
                    "Ordinary Shares Number × info['previousClose']",
                )
            )
            so = info.get("sharesOutstanding")
            if so:
                variants.append(
                    _var(
                        "info sharesOutstanding × previousClose",
                        so * (pc / scale) / 1e6,
                        None,
                        "info['sharesOutstanding'] × info['previousClose']",
                    )
                )
        if info.get("marketCap"):
            variants.append(
                _var(
                    "info marketCap (direct)",
                    info["marketCap"] / 1e6,
                    None,
                    "info['marketCap']",
                )
            )
    if not a.empty and not closes.empty:
        fy_d = a.index[-1]
        px = _close_on(closes, fy_d)
        if px is not None:
            v = float(a.iloc[-1]) * (px / scale) / 1e6
            fyb = {
                "value": v,
                "fy": int(fy_d.year),
                "as_of": _iso(fy_d),
                "basis": "FY-end shares × close@FY /scale",
            }
            if variants:
                variants[0]["fy_baseline"] = v
    return {
        "field": "equity_cap",
        "unit": "mm",
        "basis": "market",
        "latest": latest,
        "fy_baseline": fyb,
        "variants": variants,
        "source": "Yahoo · Ordinary Shares Number × Close",
        "formula": "equity_cap = shares × price (subunit-corrected)",
        "desc": "Market cap = outstanding shares × price.",
        "is_proxy": False,
    }


def get_enterprise_value(api):
    """ENTERPRISE VALUE.  basis=market  unit=mm.  EV = mkt_cap + debt + MI − cash."""
    info = _info(api)
    scale = _price_scale(api)
    closes = _closes(api)
    shq = clean_series(_safe(api, "quarterly_balance_sheet"), "Ordinary Shares Number")
    sha = clean_series(_safe(api, "balance_sheet"), "Ordinary Shares Number")
    sh = shq if not shq.empty else sha
    td_l, td_f, _, _ = _level_mm(api, "Total Debt")
    mi_l, mi_f, _, _ = _level_mm(api, "Minority Interest")
    csti_l, csti_f, _, _ = _level_mm(
        api, "Cash Cash Equivalents And Short Term Investments"
    )
    ce_l, ce_f, _, _ = _level_mm(api, "Cash And Cash Equivalents")
    pc = info.get("previousClose")
    mkt_live = (
        float(sh.iloc[-1]) * (pc / scale) / 1e6 if (not sh.empty and pc) else None
    )
    mkt_q = (
        float(sh.iloc[-1]) * (float(closes.iloc[-1]) / scale) / 1e6
        if (not sh.empty and not closes.empty)
        else None
    )
    variants = []
    if mkt_live is not None and td_l is not None:
        variants.append(
            _var(
                "PM live: mktcap+debt+MI−cash(Cash+STI)",
                mkt_live + _z(td_l) + _z(mi_l) - _z(csti_l),
                None,
                "previousClose×shares + Total Debt + Minority Interest − (Cash+STI)",
            )
        )
    if mkt_q is not None and td_l is not None:
        variants.append(
            _var(
                "PM @stmt close: mktcap+debt+MI−cash(Cash+STI)",
                mkt_q + _z(td_l) + _z(mi_l) - _z(csti_l),
                None,
                "close@stmt×shares + debt + MI − (Cash+STI)",
            )
        )
    if mkt_live is not None and td_l is not None:
        variants.append(
            _var(
                "PM live, cash=Cash&Equivalents",
                mkt_live + _z(td_l) + _z(mi_l) - _z(ce_l),
                None,
                "previousClose×shares + debt + MI − Cash&Equivalents",
            )
        )
        variants.append(
            _var(
                "simple (no MI): mktcap+debt−cash(Cash+STI)",
                mkt_live + _z(td_l) - _z(csti_l),
                None,
                "previousClose×shares + Total Debt − (Cash+STI)",
            )
        )
    if info.get("enterpriseValue"):
        variants.append(
            _var(
                "info enterpriseValue (direct)",
                info["enterpriseValue"] / 1e6,
                None,
                "info['enterpriseValue']",
            )
        )
    fyb = None
    if not sha.empty and not closes.empty and td_f is not None:
        fy_d = sha.index[-1]
        px = _close_on(closes, fy_d)
        if px is not None:
            mkt_fy = float(sha.iloc[-1]) * (px / scale) / 1e6
            fyb = {
                "value": mkt_fy + _z(td_f) + _z(mi_f) - _z(csti_f),
                "fy": int(fy_d.year),
                "as_of": _iso(fy_d),
                "basis": "FY-end PM: mktcap@FY + debt + MI − (Cash+STI)",
            }
            if variants:
                variants[0]["fy_baseline"] = fyb["value"]
    latest = (
        {
            "value": variants[0]["latest"],
            "as_of": _iso(closes.index[-1]) if not closes.empty else None,
            "basis": "PM live",
        }
        if variants
        else None
    )
    return {
        "field": "enterprise_value",
        "unit": "mm",
        "basis": "market",
        "latest": latest,
        "fy_baseline": fyb,
        "variants": variants,
        "source": "Yahoo · market cap + debt + MI − cash",
        "formula": "EV = market_cap + total_debt + minority_interest − cash",
        "desc": "Enterprise value (PM definition: includes minority interest).",
        "is_proxy": False,
    }


def get_realized_vol(api):
    """REALIZED EQUITY VOL (1y).  basis=market  unit=decimal.  vol = stdev(daily log returns) × sqrt(252)."""
    closes = _closes(api)
    a_ebitda = clean_series(_safe(api, "income_stmt"), "EBITDA")
    fy_end_m = infer_fy_end_month(a_ebitda)

    def _vol(px):
        lr = np.log(px / px.shift(1)).dropna()
        return float(lr.std() * np.sqrt(252)) if len(lr) > 5 else None

    latest = fyb = None
    if len(closes) > 10:
        win = closes.iloc[-252:]
        v = _vol(win)
        if v is not None:
            latest = {
                "value": v,
                "as_of": _iso(closes.index[-1]),
                "basis": "trailing 252 trading days",
            }
        a = _safe(api, "income_stmt")
        if a is not None and not a_ebitda.empty:
            fy_end = a_ebitda.index[-1]
            fy_start = (
                pd.Timestamp(fy_end.year - 1, fy_end.month, fy_end.day)
                if fy_end.month != 2
                else fy_end - pd.Timedelta(days=365)
            )
            yr = closes[(closes.index > fy_start) & (closes.index <= fy_end)]
            v2 = _vol(yr)
            if v2 is not None:
                fyb = {
                    "value": v2,
                    "fy": int(fy_end.year),
                    "as_of": _iso(fy_end),
                    "basis": f"FY{fy_end.year} daily log-return vol ({_iso(fy_start)}→{_iso(fy_end)})",
                }
    return {
        "field": "realized_vol",
        "unit": "decimal",
        "basis": "market",
        "latest": latest,
        "fy_baseline": fyb,
        "source": "Yahoo Finance · history Close (daily log returns)",
        "formula": "realized_vol = stdev(ln Close_t/Close_{t-1}) × sqrt(252)",
        "desc": "Annualised stdev of daily log returns.",
        "is_proxy": False,
    }


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  D.  DERIVED FIELDS  (computed at BOTH latest and fy_baseline)              ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _val(node):
    return None if not node else node.get("value")


def _derive(name, parts, combine, *, unit, desc, formula, is_proxy=None):
    """
    Evaluate a derived field at BOTH points. `parts` = {alias: getter_result}.
    `combine(values_dict) -> float`. Computes once from each part's LATEST value and once from each
    part's FY_BASELINE value, so the headline pair holds for derived fields too.
    """

    def at(point):
        vals, dates = {}, {}
        for alias, r in parts.items():
            node = (r or {}).get(point)
            v = _val(node)
            if v is None:
                return None, {}, {}
            vals[alias] = v
            dates[alias] = (node.get("as_of") if node else None) or (
                f"FY{node.get('fy')}" if node and node.get("fy") else None
            )
        return combine(vals), dates, vals

    lv, ld, lvals = at("latest")
    fv, fd, fvals = at("fy_baseline")
    if is_proxy is None:
        is_proxy = any((r or {}).get("is_proxy") for r in parts.values())
    iso_dates = [d for d in ld.values() if isinstance(d, str) and d[:1].isdigit()]
    latest = (
        None
        if lv is None
        else {
            "value": lv,
            "as_of": (max(iso_dates) if iso_dates else None),
            "basis": "derived from components' latest",
            "components": {a: {"value": lvals[a], "date": ld.get(a)} for a in lvals},
            "period_consistent": (len(set(iso_dates)) <= 1) if iso_dates else None,
        }
    )
    fy_isos = [d for d in fd.values() if isinstance(d, str) and d[:1].isdigit()]
    fyb = (
        None
        if fv is None
        else {
            "value": fv,
            "basis": "derived from components' FY-start",
            "as_of": (max(fy_isos) if fy_isos else None),
            "fy": (int(max(fy_isos)[:4]) if fy_isos else None),
            "components": {a: {"value": fvals[a], "point": fd.get(a)} for a in fvals},
        }
    )
    return {
        "field": name,
        "unit": unit,
        "basis": "derived",
        "latest": latest,
        "fy_baseline": fyb,
        "source": "Computed from components",
        "formula": formula,
        "desc": desc,
        "is_proxy": is_proxy,
    }


def get_ebit(api):
    """EBIT.  basis=ttm  unit=mm.  PRIMARY: income_stmt['EBIT'] (fallback EBITDA − Reconciled Depreciation)."""
    q, a = (
        clean_series(_safe(api, "quarterly_income_stmt"), "EBIT"),
        clean_series(_safe(api, "income_stmt"), "EBIT"),
    )
    if not q.empty or not a.empty:
        out = _attach(
            resolve_flow(
                "ebit",
                q,
                a,
                unit="mm",
                source="Yahoo Finance · income_stmt['EBIT']",
                formula="ebit = TTM rolling of income_stmt['EBIT']",
            ),
            "Operating profit (EBIT), TTM.",
        )
    else:
        dq, da = (
            clean_series(
                _safe(api, "quarterly_income_stmt"), "Reconciled Depreciation"
            ),
            clean_series(_safe(api, "income_stmt"), "Reconciled Depreciation"),
        )
        eq = (
            clean_series(_safe(api, "quarterly_income_stmt"), "EBITDA")
            .subtract(dq, fill_value=np.nan)
            .dropna()
        )
        ea = (
            clean_series(_safe(api, "income_stmt"), "EBITDA")
            .subtract(da, fill_value=np.nan)
            .dropna()
        )
        out = _attach(
            resolve_flow(
                "ebit",
                eq,
                ea,
                unit="mm",
                source="Yahoo Finance · EBITDA - Reconciled Depreciation",
                formula="ebit = TTM(EBITDA) - TTM(Reconciled Depreciation)  [fallback; 'EBIT' line absent]",
            ),
            "EBIT via EBITDA − D&A (fallback).",
        )
    ebit_l, ebit_f = _ttm_pair(api, "income", "EBIT")
    eb = get_ebitda(api)
    rec_l, rec_f = _ttm_pair(api, "income", "Reconciled Depreciation")
    eb_l = eb["latest"]["value"] if eb["latest"] else None
    eb_f = eb["fy_baseline"]["value"] if eb["fy_baseline"] else None
    op_l, op_f = _ttm_pair(api, "income", "Operating Income")
    out["variants"] = [
        _var("EBIT line", ebit_l, ebit_f, "TTM income_stmt['EBIT']"),
        _var(
            "EBITDA − Reconciled Depreciation",
            (eb_l - rec_l) if (eb_l is not None and rec_l is not None) else None,
            (eb_f - rec_f) if (eb_f is not None and rec_f is not None) else None,
            "TTM EBITDA − TTM Reconciled Depreciation",
        ),
        _var("Operating Income", op_l, op_f, "TTM income_stmt['Operating Income']"),
    ]
    return out


def get_tax_rate(api, statutory=0.25, lo=0.0, hi=0.40):
    """EFFECTIVE TAX RATE.  basis=derived  unit=decimal.  Tax Provision / Pretax Income (clamped)."""

    def rate_from(qP, qPre):
        if qP is None or qPre is None or qPre <= 0:
            return None
        r = qP / qPre
        return r if lo <= r <= hi else None

    def ttm(line):
        s = clean_series(_safe(api, "quarterly_income_stmt"), line)
        return (
            float(s.iloc[-4:].sum())
            if len(s) >= 4
            else (
                float(clean_series(_safe(api, "income_stmt"), line).iloc[-1])
                if not clean_series(_safe(api, "income_stmt"), line).empty
                else None
            )
        )

    def annual(line):
        s = clean_series(_safe(api, "income_stmt"), line)
        return float(s.iloc[-1]) if not s.empty else None

    lat = rate_from(ttm("Tax Provision"), ttm("Pretax Income"))
    fyb = rate_from(annual("Tax Provision"), annual("Pretax Income"))
    src = "Tax Provision / Pretax Income (TTM & annual)"
    isp = False
    fla = "tax_rate = Tax Provision / Pretax Income"
    if lat is None or fyb is None:
        trc = clean_series(_safe(api, "income_stmt"), "Tax Rate For Calcs")
        cand = (
            float(trc.iloc[-1])
            if not trc.empty and lo <= float(trc.iloc[-1]) <= hi
            else max(lo, min(hi, statutory))
        )
        isp = trc.empty or not (
            lo <= (float(trc.iloc[-1]) if not trc.empty else 999) <= hi
        )
        src = "Tax Rate For Calcs / statutory"
        fla = "tax_rate = Tax Rate For Calcs (else statutory)"
        lat = lat if lat is not None else cand
        fyb = fyb if fyb is not None else cand
    qi, ai = _safe(api, "quarterly_income_stmt"), _safe(api, "income_stmt")
    lat_date = (
        _iso(clean_series(qi, "Tax Provision").index[-1])
        if not clean_series(qi, "Tax Provision").empty
        else (
            _iso(clean_series(ai, "Tax Provision").index[-1])
            if not clean_series(ai, "Tax Provision").empty
            else None
        )
    )
    fy_idx = clean_series(ai, "Tax Provision")
    fy_date = _iso(fy_idx.index[-1]) if not fy_idx.empty else None
    return {
        "field": "tax_rate",
        "unit": "decimal",
        "basis": "derived",
        "latest": {"value": lat, "as_of": lat_date, "basis": "TTM effective rate"},
        "fy_baseline": {
            "value": fyb,
            "as_of": fy_date,
            "fy": (int(fy_date[:4]) if fy_date else None),
            "basis": "annual effective rate",
        },
        "source": f"Yahoo Finance · {src}",
        "formula": fla,
        "desc": "Effective tax rate for the unlevered tax in UFCF.",
        "is_proxy": isp,
    }


def get_ufcf(api):
    """
    UFCF — Unlevered Free Cash Flow.  basis=derived  unit=mm.
    FORMULA: ufcf = ebitda - (ebit × tax_rate) + capex + ch_nwc
    """
    parts = {
        "ebitda": get_ebitda(api),
        "ebit": get_ebit(api),
        "tax": get_tax_rate(api),
        "capex": get_capex(api),
        "ch_nwc": get_ch_nwc(api),
    }
    combine = lambda v: v["ebitda"] - v["ebit"] * v["tax"] + v["capex"] + v["ch_nwc"]
    return _derive(
        "ufcf",
        parts,
        combine,
        unit="mm",
        desc="Unlevered FCF = EBITDA − EBIT·tax − CapEx − ΔNWC.",
        formula="ufcf = ebitda - (ebit × tax_rate) + capex + ch_nwc",
    )


def get_fcf(api):
    """
    FCF — Free Cash Flow (levered).  basis=derived  unit=mm.
    FORMULA: fcf = ebitda + capex + ch_nwc - cash_interest - cash_taxes

    Sign conventions of components:
      - ebitda        : POSITIVE
      - capex         : NEGATIVE (as Yahoo reports, kept as outflow)
      - ch_nwc        : cash-signed (NEGATIVE if NWC increased = outflow)
      - cash_interest : POSITIVE magnitude (cash paid) → SUBTRACTED
      - cash_taxes    : POSITIVE magnitude (cash paid) → SUBTRACTED
    """
    parts = {
        "ebitda": get_ebitda(api),
        "capex": get_capex(api),
        "ch_nwc": get_ch_nwc(api),
        "cash_interest": get_cash_interest(api),
        "cash_taxes": get_cash_taxes(api),
    }
    combine = lambda v: (
        v["ebitda"] + v["capex"] + v["ch_nwc"] - v["cash_interest"] - v["cash_taxes"]
    )
    out = _derive(
        "fcf",
        parts,
        combine,
        unit="mm",
        desc="Levered FCF = EBITDA + capex + ΔNWC − cash interest − cash taxes.",
        formula="fcf = ebitda + capex + ch_nwc - cash_interest - cash_taxes",
    )
    comp_l = out["latest"]["value"] if out["latest"] else None
    comp_f = out["fy_baseline"]["value"] if out["fy_baseline"] else None
    yf_l, yf_f = _ttm_pair(api, "cash", "Free Cash Flow")
    ocf_l, ocf_f = _ttm_pair(api, "cash", "Operating Cash Flow")
    cpx = get_capex(api)
    cpx_l = cpx["latest"]["value"] if cpx["latest"] else None
    cpx_f = cpx["fy_baseline"]["value"] if cpx["fy_baseline"] else None
    out["variants"] = [
        _var("components (EBITDA+capex+ΔNWC−int−tax)", comp_l, comp_f, "our build"),
        _var(
            "yfinance Free Cash Flow (direct)",
            yf_l,
            yf_f,
            "TTM cash_flow['Free Cash Flow']",
        ),
        _var(
            "Operating CF − capex",
            (ocf_l + cpx_l) if (ocf_l is not None and cpx_l is not None) else None,
            (ocf_f + cpx_f) if (ocf_f is not None and cpx_f is not None) else None,
            "TTM Operating Cash Flow + capex (capex negative)",
        ),
    ]
    return out


def get_ebitda_less_capex_to_interest(api):
    """
    EBITDA-LESS-CAPEX / INTEREST.  basis=derived  unit=x.
    FORMULA: (ebitda + capex) / cash_interest.
      ebitda        : POSITIVE
      capex         : NEGATIVE (so it reduces the numerator)
      cash_interest : POSITIVE magnitude (denominator)
    """
    parts = {
        "ebitda": get_ebitda(api),
        "capex": get_capex(api),
        "cash_interest": get_cash_interest(api),
    }

    def combine(v):
        denom = v["cash_interest"]
        return (v["ebitda"] + v["capex"]) / denom if denom else None

    return _derive(
        "ebitda_less_capex_to_interest",
        parts,
        combine,
        unit="x",
        desc="(EBITDA + capex) / cash interest, a coverage multiple.",
        formula="ebitda_less_capex_to_interest = (ebitda + capex) / cash_interest",
    )


def _net_debt(api):
    """net_debt result-like dict with latest & fy_baseline = total_debt − cash."""
    td, cash = get_total_debt(api), get_cash(api)
    return _derive(
        "net_debt",
        {"td": td, "cash": cash},
        lambda v: v["td"] - v["cash"],
        unit="mm",
        desc="Net debt = total debt − cash.",
        formula="net_debt = total_debt - cash",
    )


def get_net_debt_to_ebitda(api):
    """NET DEBT / EBITDA.  basis=derived  unit=x.  (total_debt - cash) / ebitda."""
    parts = {
        "td": get_total_debt(api),
        "cash": get_cash(api),
        "ebitda": get_ebitda(api),
    }
    return _derive(
        "net_debt_to_ebitda",
        parts,
        lambda v: (v["td"] - v["cash"]) / v["ebitda"] if v["ebitda"] else None,
        unit="x",
        desc="Leverage: net debt / TTM EBITDA.",
        formula="net_debt_to_ebitda = (total_debt - cash) / ebitda",
    )


def get_fcf_to_net_debt(api):
    """FCF / NET DEBT.  basis=derived  unit=decimal.  fcf / (total_debt - cash)."""
    parts = {"fcf": get_fcf(api), "td": get_total_debt(api), "cash": get_cash(api)}
    return _derive(
        "fcf_to_net_debt",
        parts,
        lambda v: v["fcf"] / (v["td"] - v["cash"]) if (v["td"] - v["cash"]) else None,
        unit="decimal",
        desc="FCF / net debt.",
        formula="fcf_to_net_debt = fcf / (total_debt - cash)",
    )


def get_net_debt_to_ev(api):
    """NET DEBT / EV.  basis=derived  unit=decimal."""
    parts = {
        "td": get_total_debt(api),
        "cash": get_cash(api),
        "eq": get_equity_cap(api),
    }

    def combine(v):
        nd = v["td"] - v["cash"]
        ev = v["eq"] + nd
        return nd / ev if ev else None

    return _derive(
        "net_debt_to_ev",
        parts,
        combine,
        unit="decimal",
        desc="Net debt / enterprise value.",
        formula="net_debt_to_ev = (total_debt - cash) / (equity_cap + total_debt - cash)",
    )


# small helper to attach a desc onto an engine result
def _attach(d, desc):
    d["desc"] = desc
    return d


# ==========================================================================
# SECTION: extras.py
# ==========================================================================
"""
issuer-screener — remaining getters + runner + inspector
"""


def get_adj_ebitda(api):
    """ADJUSTED (NORMALIZED) EBITDA.  basis=ttm  unit=mm.  TTM rolling of income_stmt['Normalized EBITDA']."""
    q, a = (
        clean_series(_safe(api, "quarterly_income_stmt"), "Normalized EBITDA"),
        clean_series(_safe(api, "income_stmt"), "Normalized EBITDA"),
    )
    return _attach(
        resolve_flow(
            "adj_ebitda",
            q,
            a,
            unit="mm",
            source="Yahoo Finance · income_stmt['Normalized EBITDA']",
            formula="adj_ebitda = TTM rolling of income_stmt['Normalized EBITDA']",
        ),
        "Adjusted/normalized EBITDA (unusual items stripped), TTM.",
    )


def get_ebitda_to_adj_ebitda(api):
    """EBITDA / ADJ EBITDA.  basis=derived  unit=x."""
    parts = {"ebitda": get_ebitda(api), "adj": get_adj_ebitda(api)}
    return _derive(
        "ebitda_to_adj_ebitda",
        parts,
        lambda v: v["ebitda"] / v["adj"] if v["adj"] else None,
        unit="x",
        desc="Reported vs adjusted EBITDA ratio.",
        formula="ebitda_to_adj_ebitda = ebitda / adj_ebitda",
    )


def get_ltm_vs_2y_avg_ebitda(api):
    """LTM EBITDA / 2Y-AVG EBITDA.  basis=derived  unit=x."""
    qe = clean_series(_safe(api, "quarterly_income_stmt"), "EBITDA")
    ae = clean_series(_safe(api, "income_stmt"), "EBITDA")
    ltm = get_ebitda(api)["latest"]
    ltm_v = ltm["value"] if ltm else None
    _, ppy = infer_frequency(qe)
    fy_end_m = infer_fy_end_month(ae)

    def fy_of(d):
        return d.year if d.month <= fy_end_m else d.year + 1

    def per_n(d):
        m_in_fy = ((d.month - fy_end_m - 1) % 12) + 1
        return min(ppy, ((m_in_fy - 1) // (12 // ppy)) + 1) if ppy > 1 else 1

    ann_by_fy = {fy_of(d): float(v) / 1e6 for d, v in ae.items()}

    two_y_latest = None
    if ppy in (2, 4) and len(qe) and ltm_v is not None:
        d = qe.index[-1]
        fy = fy_of(d)
        n = per_n(d)
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
    if two_y_latest is None and len(ae) >= 2:
        two_y_latest = float(ae.iloc[-2:].mean()) / 1e6

    lat = None
    if ltm_v and two_y_latest:
        lat = {
            "value": ltm_v / two_y_latest,
            "as_of": ltm["as_of"],
            "basis": "LTM EBITDA / interpolated trailing-24m average",
            "components": {
                "ltm_ebitda": {"value": ltm_v, "date": ltm["as_of"]},
                "two_year_avg": {"value": two_y_latest, "date": ltm["as_of"]},
            },
        }
    fyb = None
    if len(ae) >= 2:
        two_y_fy = float(ae.iloc[-2:].mean()) / 1e6
        fy_ebitda = float(ae.iloc[-1]) / 1e6
        fy_date = _iso(ae.index[-1])
        fyb = {
            "value": fy_ebitda / two_y_fy,
            "as_of": fy_date,
            "fy": int(ae.index[-1].year),
            "basis": "FY EBITDA / mean(last 2 annual EBITDA)",
            "components": {
                "fy_ebitda": {"value": fy_ebitda, "point": fy_date},
                "two_year_avg": {"value": two_y_fy, "point": fy_date},
            },
        }
    return {
        "field": "ltm_vs_2y_avg_ebitda",
        "unit": "x",
        "basis": "derived",
        "latest": lat,
        "fy_baseline": fyb,
        "source": "Computed from EBITDA series",
        "formula": "ltm_vs_2y_avg_ebitda = ltm_ebitda / two_year_avg (latest: interpolated 24m; FY: 2-annual mean)",
        "desc": "LTM EBITDA vs its trailing-2-year average (interpolated for latest).",
        "is_proxy": False,
    }


def get_ufcf_vol(api, ddof=1, outlier_tol=0.30):
    """UFCF VOL — stdev of annual UFCF series; CS-Model σ_B input."""
    inc, cf = _safe(api, "income_stmt"), _safe(api, "cash_flow")
    tax = get_tax_rate(api)["fy_baseline"]["value"]

    def by_year(df, line):
        s = clean_series(df, line)
        return {d.year: float(v) for d, v in s.items()}

    eb, ei, dep = (
        by_year(inc, "EBITDA"),
        by_year(inc, "EBIT"),
        by_year(inc, "Reconciled Depreciation"),
    )
    cx = by_year(cf, "Capital Expenditure Reported") or by_year(
        cf, "Capital Expenditure"
    )
    wc = by_year(cf, "Change In Working Capital")
    yrs = sorted(set(eb) & set(cx) & set(wc) & (set(ei) if ei else set(dep)))
    series = {}
    for y in yrs:
        e_i = ei.get(y) if ei else (eb[y] - dep[y])
        series[y] = (eb[y] - e_i * tax + cx[y] + wc[y]) / 1e6
    if len(series) < 2:
        return {
            "field": "ufcf_vol",
            "unit": "mm",
            "basis": "stat",
            "value": None,
            "n_years": len(series),
            "series": series,
            "is_proxy": True,
            "source": "insufficient history",
            "formula": "fcf_vol_abs = stdev(annual UFCF) — needs ≥2 yrs",
            "desc": "UFCF dispersion (σ_B input).",
        }
    a = np.array(list(series.values()))
    i = int(np.argmax(np.abs(a - a.mean())))
    ex = np.delete(a, i)
    std_ex = float(ex.std(ddof=ddof)) if len(ex) >= 2 else None
    dominated = (
        std_ex is not None
        and a.std(ddof=ddof) > 0
        and abs(a.std(ddof=ddof) - std_ex) / a.std(ddof=ddof) > outlier_tol
    )
    return {
        "field": "ufcf_vol",
        "unit": "mm",
        "basis": "stat",
        "value": float(a.std(ddof=ddof)),
        "std_sample": float(a.std(ddof=1)),
        "std_pop": float(a.std(ddof=0)),
        "std_ex_extreme": std_ex,
        "extreme_year": sorted(series)[i],
        "outlier_dominated": bool(dominated),
        "n_years": len(series),
        "series": {int(k): round(v, 1) for k, v in series.items()},
        "tax_rate_used": tax,
        "is_proxy": bool(len(series) < 5 or dominated),
        "source": "Computed — stdev of annual UFCF series",
        "formula": "fcf_vol_abs = stdev(annual UFCF); UFCF_t = EBITDA_t - EBIT_t·tax - CapEx_t - ΔNWC_t",
        "desc": "Std-dev of annual UFCF — CS-Model barrier vol σ_B input.",
    }


def get_implied_vol(api):
    """1Y IMPLIED EQUITY VOL.  basis=market  unit=decimal.  PARKED."""
    return {
        "field": "implied_vol",
        "unit": "decimal",
        "basis": "market",
        "latest": None,
        "fy_baseline": None,
        "source": "parked (Yahoo option IV unusable)",
        "formula": "implied_vol → substitute realized_vol",
        "desc": "1y implied equity vol — parked; realized stands in.",
        "is_proxy": False,
    }


# ── runner + inspector ───────────────────────────────────────────────────────
ALL_GETTERS = [
    "get_revenues",
    "get_ebitda",
    "get_adj_ebitda",
    "get_capex",
    "get_cash_interest",
    "get_cash_taxes",
    "get_ch_nwc",
    "get_cash",
    "get_total_debt",
    "get_total_liabilities",
    "get_equity_cap",
    "get_enterprise_value",
    "get_realized_vol",
    "get_implied_vol",
    "get_ebit",
    "get_tax_rate",
    "get_ufcf",
    "get_fcf",
    "get_ufcf_vol",
    "get_ebitda_to_adj_ebitda",
    "get_ltm_vs_2y_avg_ebitda",
    "get_ebitda_less_capex_to_interest",
    "get_net_debt_to_ebitda",
    "get_fcf_to_net_debt",
    "get_net_debt_to_ev",
]


def build_all(api):
    out = {}
    for g in ALL_GETTERS:
        try:
            out[g.replace("get_", "")] = globals()[g](api)
        except Exception as e:
            out[g.replace("get_", "")] = {"error": f"{type(e).__name__}: {e}"}
    return out


def inspect(api):
    res = build_all(api)
    for name, r in res.items():
        if "error" in r:
            print(f"\n■ {name:30s} ERROR: {r['error']}")
            continue
        u = r.get("unit", "")
        if r.get("basis") == "stat":
            print(
                f"\n■ {name:30s} [{u}]  value={r.get('value')}  n={r.get('n_years')}  outlier={r.get('outlier_dominated')}"
            )
            print(
                f"    series={r.get('series')}  std_ex_extreme={r.get('std_ex_extreme')}"
            )
            continue
        lat, fyb = r.get("latest"), r.get("fy_baseline")
        lv = f"{lat['value']:.4g}" if lat else "None"
        fv = f"{fyb['value']:.4g}" if fyb else "None"
        print(
            f"\n■ {name:30s} [{r.get('basis')}/{u}]  LATEST={lv} (as_of {lat.get('as_of') if lat else '-'})   FY_BASE={fv}"
        )
        if lat and lat.get("methodology"):
            print(f"      via: {lat['methodology']}")
        if lat and lat.get("note"):
            print(f"      note: {lat['note']}")
        if lat and lat.get("stale"):
            print(f"      ⚠ STALE: {lat.get('age_years')}y old")
        if lat and "components" in lat:
            for a, c in lat["components"].items():
                print(f"      └ {a:16s} latest={c['value']:>12.3f}  ({c.get('date')})")
            print(f"        period_consistent={lat.get('period_consistent')}")
        if fyb and "components" in fyb:
            for a, c in fyb["components"].items():
                print(f"      └ {a:16s} FY    ={c['value']:>12.3f}  ({c.get('point')})")
        if r.get("variants"):
            print("      ── ways to compute it ──")
            for v in r["variants"]:
                lv = f"{v['latest']:.6g}" if v.get("latest") is not None else "—"
                fv = (
                    f"{v['fy_baseline']:.6g}"
                    if v.get("fy_baseline") is not None
                    else "—"
                )
                lat_dt = v.get("latest_as_of") or "—"
                fy_dt = v.get("fy_as_of") or "—"
                stale_flag = " [STALE]" if v.get("is_stale") else ""
                proxy_flag = " [proxy]" if v.get("is_proxy") else ""
                print(
                    f"      ~ {v['label']:50s} latest={lv:>14} ({lat_dt})  FY={fv:>14} ({fy_dt}){stale_flag}{proxy_flag}"
                )
    return res
