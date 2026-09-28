#!/usr/bin/env python3
"""screener_model_us.py — long-term scoring model for the US desk.

Inputs: data/panel_annual_latest.csv.gz (display values, restatement-aware),
        data/panel_annual.csv.gz (point-in-time, for the backtest via pit_frame()),
        prices/shard_*.csv.gz, data/meta.csv, data/sic.csv, data/universe.csv
Output: data/model_us.json — one record per name: pillars, score, valuation with
        PEAK-EARNINGS caveat, pressured-quality flag, and a citation for every
        fundamental figure (concept, period end, filed date, accession).

Pillars (long-term only, no swing): quality, growth, balance, cash, capital,
valuation, trend-lite. Lenders (banks/insurers, no GP/OpInc in filings) are scored
on the lender model: ROE, NI growth, EPS growth; margin/capex pillars excluded and
weights renormalized — same treatment the NSE desk gives banks.
Scores are coverage-weighted percentile ranks, 0-100.
"""
import glob, gzip, json
import numpy as np
import pandas as pd

W = {"quality": 22, "growth": 22, "balance": 12, "cash": 14, "capital": 8,
     "valuation": 14, "trend": 8}

def load():
    A = pd.read_csv("data/panel_annual_latest.csv.gz", parse_dates=["end", "filed"])
    meta = pd.read_csv("data/meta.csv")
    sic = pd.read_csv("data/sic.csv")
    uni = pd.read_csv("data/universe.csv")
    px = pd.concat([pd.read_csv(f, parse_dates=["date"])
                    for f in sorted(glob.glob("prices/shard_*.csv.gz"))])
    return A, meta.merge(sic, on="cik", how="left"), uni, px

def series(A, cik, key, n=4):
    """Last n annual values for a concept, oldest->newest, with citation of newest."""
    g = A[(A.cik == cik) & (A.key == key)].sort_values("end").drop_duplicates("end", keep="last")
    if g.empty: return [], None
    tail = g.tail(n)
    cite = tail.iloc[-1]
    return list(tail["val"]), {"concept": cite["concept"], "end": str(cite["end"].date()),
                               "filed": str(cite["filed"].date()), "accn": cite["accn"],
                               "form": cite["form"]}

def cagr(vals, yrs=3):
    if len(vals) < yrs + 1: return None
    a, b = vals[-yrs-1], vals[-1]
    # BOTH ends must be positive: a negative ratio to a fractional power silently
    # yields a Python complex number, which poisons ranks and kills json.dump.
    if a is None or b is None or a <= 0 or b <= 0: return None
    return (b / a) ** (1 / yrs) - 1

def pct_rank(s):
    return s.rank(pct=True) * 100

def build_records(A, meta, uni, px):
    px = px.sort_values(["ticker", "date"])
    last = px.groupby("ticker").tail(1).set_index("ticker")
    ret12, off52, above200 = {}, {}, {}
    for tk, g in px.groupby("ticker"):
        c = g["close"].values
        if len(c) > 252: ret12[tk] = c[-1] / c[-253] - 1
        if len(c) > 60:
            off52[tk] = c[-1] / max(c[-252:]) - 1
            above200[tk] = c[-1] > np.mean(c[-200:]) if len(c) >= 200 else None
    rows = []
    for _, m in meta.iterrows():
        cik, tk = m["cik"], m["ticker"]
        if tk not in uni["ticker"].values or tk not in last.index: continue
        F, C = {}, {}
        for key in ("rev", "ni", "op", "gp", "ocf", "capex", "assets", "eq",
                    "debt_lt", "cash", "shares_d", "eps_d", "buyback", "div"):
            vals, cite = series(A, cik, key)
            F[key] = vals
            if cite: C[key] = cite
        price = float(last.loc[tk, "close"])
        shares = m["shares_now"]
        mcap = price * shares if pd.notna(shares) else None
        ni, rev, eq, ocf = F["ni"], F["rev"], F["eq"], F["ocf"]
        r = {"cik": int(cik), "ticker": tk, "name": m["name"], "lender": bool(m["lender"]),
             "sic": m.get("sic"), "sector": m.get("sic_desc"), "price": price,
             "mcap": mcap, "cites": C}
        # ---- factor values
        r["roe"] = ni[-1] / eq[-1] if ni and eq and eq[-1] else None
        r["nm"] = ni[-1] / rev[-1] if ni and rev and rev[-1] else None
        r["gm"] = F["gp"][-1] / rev[-1] if F["gp"] and rev and rev[-1] else None
        r["om"] = F["op"][-1] / rev[-1] if F["op"] and rev and rev[-1] else None
        r["om_trend"] = (r["om"] - F["op"][0] / rev[0]) if r["om"] and len(F["op"]) >= 4 and rev[0] else None
        r["rev_g3"] = cagr(rev); r["ni_g3"] = cagr(ni); r["eps_g3"] = cagr(F["eps_d"])
        r["rev_g1"] = rev[-1] / rev[-2] - 1 if len(rev) >= 2 and rev[-2] else None
        r["ni_g1"] = ni[-1] / ni[-2] - 1 if len(ni) >= 2 and ni[-2] and ni[-2] > 0 else None
        r["de"] = (F["debt_lt"][-1] / eq[-1]) if F["debt_lt"] and eq and eq[-1] and eq[-1] > 0 else None
        r["debt_ocf"] = F["debt_lt"][-1] / ocf[-1] if F["debt_lt"] and ocf and ocf[-1] and ocf[-1] > 0 else None
        r["ocf_ni3"] = (sum(ocf[-3:]) / sum(ni[-3:])) if len(ocf) >= 3 and len(ni) >= 3 and sum(ni[-3:]) > 0 else None
        fcf = (ocf[-1] - (F["capex"][-1] if F["capex"] else 0)) if ocf else None
        r["fcf"] = fcf
        r["fcf_yield"] = fcf / mcap if fcf is not None and mcap else None
        r["dilution3"] = (F["shares_d"][-1] / F["shares_d"][-4] - 1) if len(F["shares_d"]) >= 4 and F["shares_d"][-4] else None
        sh_yield = ((F["buyback"][-1] if F["buyback"] else 0) + (F["div"][-1] if F["div"] else 0))
        r["shareholder_yield"] = sh_yield / mcap if mcap else None
        # valuation + the peak-earnings caveat (the war lesson, built in from day one)
        r["pe"] = mcap / ni[-1] if mcap and ni and ni[-1] and ni[-1] > 0 else None
        ni3avg = np.mean(ni[-3:]) if len(ni) >= 3 else None
        r["pe_norm"] = mcap / ni3avg if mcap and ni3avg and ni3avg > 0 else None
        r["peak_earnings"] = bool(ni and ni3avg and ni[-1] > 1.6 * ni3avg)
        r["ps"] = mcap / rev[-1] if mcap and rev and rev[-1] else None
        r["ret12"] = ret12.get(tk); r["off52"] = off52.get(tk); r["above200"] = above200.get(tk)
        rows.append(r)
    return pd.DataFrame(rows)

def score(df):
    up = ["roe", "gm", "om", "om_trend", "rev_g3", "ni_g3", "eps_g3", "rev_g1", "ni_g1",
          "ocf_ni3", "fcf_yield", "shareholder_yield", "ret12"]
    dn = ["de", "debt_ocf", "dilution3", "pe_norm", "ps"]
    R = {}
    for c in up: R[c] = pct_rank(df[c].astype(float))
    for c in dn: R[c] = 100 - pct_rank(df[c].astype(float))
    def avg(cols, row_i):
        vals = [R[c].iloc[row_i] for c in cols if pd.notna(R[c].iloc[row_i])]
        return float(np.mean(vals)) if vals else None
    pillars = {"quality": ["roe", "gm", "om", "om_trend", "ocf_ni3"],
               "growth": ["rev_g3", "ni_g3", "eps_g3", "rev_g1", "ni_g1"],
               "balance": ["de", "debt_ocf"],
               "cash": ["ocf_ni3", "fcf_yield"],
               "capital": ["shareholder_yield", "dilution3"],
               "valuation": ["pe_norm", "ps", "fcf_yield"],
               "trend": ["ret12"]}
    lender_pillars = {"quality": ["roe"], "growth": ["ni_g3", "eps_g3", "ni_g1"],
                      "balance": [], "cash": [],
                      "capital": ["shareholder_yield", "dilution3"],
                      "valuation": ["pe_norm"], "trend": ["ret12"]}
    out_p, out_s = [], []
    for i in range(len(df)):
        pl = lender_pillars if df["lender"].iloc[i] else pillars
        P = {k: avg(cols, i) for k, cols in pl.items()}
        wsum = sum(W[k] for k in P if P[k] is not None)
        s = sum(W[k] * P[k] for k in P if P[k] is not None) / wsum if wsum else None
        out_p.append(P); out_s.append(s)
    df["pillars"] = out_p; df["score"] = out_s
    # fundamental-only score for the pressured-quality screen (strip trend)
    fs = []
    for i in range(len(df)):
        P = dict(out_p[i]); P.pop("trend", None)
        wsum = sum(W[k] for k in P if P.get(k) is not None)
        fs.append(sum(W[k] * P[k] for k in P if P.get(k) is not None) / wsum if wsum else None)
    df["fund_score"] = fs
    return df

def pressured_quality(df):
    """Solid fundamentals, price beaten down by rotation/flows rather than results."""
    df["sic2"] = df["sic"].astype(str).str[:2]
    sec_ret = df.groupby("sic2")["ret12"].transform("median")
    cond = ((df["fund_score"] >= df["fund_score"].quantile(0.70)) &
            (df["off52"] <= -0.25) &
            (df["ret12"] - sec_ret <= -0.10) &
            (df["rev_g1"].fillna(0) >= 0) & (df["ni_g1"].fillna(-1) >= 0) &
            (~df["peak_earnings"]))
    df["pressured"] = cond
    return df

def main():
    A, meta, uni, px = load()
    df = build_records(A, meta, uni, px)
    df = score(df)
    df = pressured_quality(df)
    df = df.sort_values("score", ascending=False)
    recs = df.to_dict(orient="records")
    def js(v):                                              # json-safe, recursive
        if isinstance(v, dict): return {k: js(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)): return [js(x) for x in v]
        if isinstance(v, np.generic): v = v.item()
        if isinstance(v, complex): return None
        if isinstance(v, float) and not np.isfinite(v): return None
        return v
    recs = [{k: js(v) for k, v in r.items()} for r in recs]
    with open("data/model_us.json", "w") as f:
        json.dump({"asof": str(pd.Timestamp.now().date()), "n": len(recs),
                   "stocks": recs}, f)
    print(f"model: {len(recs)} scored · {int(df['pressured'].sum())} pressured-quality · "
          f"{int(df['peak_earnings'].sum())} peak-earnings flags")

if __name__ == "__main__":
    main()
