#!/usr/bin/env python3
"""pit_backtest.py — the honesty engine: 10-year backtest of the long-term screener
with strictly point-in-time fundamentals.

At each annual rebalance date (first trading day of July, chosen so nearly all
Dec/Jan/Mar fiscal-year 10-Ks are FILED and public), the model is recomputed using
ONLY panel rows with filed <= rebalance date and prices <= that date. Top-quartile
and top-25 portfolios are held one year (his 1-year timeframe), equal weight,
0.2% round-trip cost. Deciles reported for monotonicity — a real factor rises
smoothly across deciles; a lucky one doesn't.

Survivorship caveat (printed with every result): the universe is today's listed
names — delisted companies are absent, which flatters absolute returns. Treat
SPREADS (top decile vs bottom, screener vs universe EW) as the honest signal.

Output: data/backtest_us.json (equity curves, yearly table, deciles, spreads)
"""
import glob, json
import numpy as np
import pandas as pd

COST = 0.002

def load():
    A = pd.read_csv("data/panel_annual.csv.gz", parse_dates=["end", "filed"])  # PIT (earliest filing)
    px = pd.concat([pd.read_csv(f, parse_dates=["date"])
                    for f in sorted(glob.glob("prices/shard_*.csv.gz"))])
    C = px.pivot_table(index="date", columns="ticker", values="close")
    meta = pd.read_csv("data/meta.csv")
    return A, C, meta

def pit_factors(A, meta, asof):
    """Factor table as knowable on `asof` — only filings with filed <= asof."""
    H = A[A["filed"] <= asof]
    out = []
    for cik, g in H.groupby("cik"):
        f = {}
        for key, sub in g.groupby("key"):
            sub = sub.sort_values("end").drop_duplicates("end", keep="last")
            f[key] = list(sub["val"].tail(4))
        ni, rev, eq, ocf = f.get("ni", []), f.get("rev", []), f.get("eq", []), f.get("ocf", [])
        if not ni or not rev: continue
        rec = {"cik": cik}
        rec["roe"] = ni[-1] / eq[-1] if eq and eq[-1] else None
        rec["nm"] = ni[-1] / rev[-1] if rev[-1] else None
        rec["rev_g3"] = (rev[-1] / rev[-4]) ** (1 / 3) - 1 if len(rev) >= 4 and rev[-4] and rev[-4] > 0 else None
        rec["ni_g3"] = (ni[-1] / ni[-4]) ** (1 / 3) - 1 if len(ni) >= 4 and ni[-4] and ni[-4] > 0 else None
        rec["ocf_ni"] = sum(ocf[-3:]) / sum(ni[-3:]) if len(ocf) >= 3 and len(ni) >= 3 and sum(ni[-3:]) > 0 else None
        capex = f.get("capex", [])
        rec["fcf"] = ocf[-1] - (capex[-1] if capex else 0) if ocf else None
        rec["ni_last"] = ni[-1]
        rec["ni_3avg"] = np.mean(ni[-3:]) if len(ni) >= 3 else None
        de = f.get("debt_lt", [])
        rec["de"] = de[-1] / eq[-1] if de and eq and eq[-1] and eq[-1] > 0 else None
        sh = f.get("shares_d", [])
        rec["dil3"] = sh[-1] / sh[-4] - 1 if len(sh) >= 4 and sh[-4] else None
        out.append(rec)
    F = pd.DataFrame(out)
    cm = dict(zip(meta["cik"], meta["ticker"]))
    F["ticker"] = F["cik"].map(cm)
    return F.dropna(subset=["ticker"])

def rank_score(F, mcaps):
    F = F.merge(mcaps, on="ticker", how="inner")
    F["pe_norm"] = F["mcap"] / F["ni_3avg"]
    F.loc[F["ni_3avg"] <= 0, "pe_norm"] = np.nan
    F["fcf_y"] = F["fcf"] / F["mcap"]
    up = ["roe", "nm", "rev_g3", "ni_g3", "ocf_ni", "fcf_y"]
    dn = ["de", "dil3", "pe_norm"]
    ranks = []
    for c in up: ranks.append(F[c].rank(pct=True))
    for c in dn: ranks.append(1 - F[c].rank(pct=True))
    F["score"] = pd.concat(ranks, axis=1).mean(axis=1, skipna=True)
    return F.dropna(subset=["score"])

def main():
    A, C, meta = load()
    dates = C.index
    years = sorted({d.year for d in dates})
    rebs = []
    for y in years:
        cand = dates[(dates >= f"{y}-07-01") & (dates <= f"{y}-07-10")]
        if len(cand): rebs.append(cand[0])
    rebs = [d for d in rebs if d <= dates[-1] - pd.Timedelta(days=200)]
    print("rebalances:", [str(d.date()) for d in rebs])
    curves = {"top25": [1.0], "topq": [1.0], "ew": [1.0], "deciles": []}
    yearly = []
    for d in rebs:
        i0 = dates.get_loc(d)
        i1 = min(i0 + 252, len(dates) - 1)
        px0, px1 = C.iloc[i0], C.iloc[i1]
        # shares outstanding unknown historically -> use price-only mcap proxy via
        # today's shares (approximation, disclosed); rank robustness beats level truth
        shares = dict(zip(meta["ticker"], meta["shares_now"]))
        mc = pd.DataFrame({"ticker": px0.index,
                           "mcap": [px0[t] * shares.get(t, np.nan) for t in px0.index]}).dropna()
        F = rank_score(pit_factors(A, meta, d), mc)
        F = F[F["ticker"].isin(px0.dropna().index)]
        rets = (px1 / px0 - 1)
        F["ret"] = F["ticker"].map(rets)
        F = F.dropna(subset=["ret"])
        if len(F) < 100: continue
        F["decile"] = pd.qcut(F["score"], 10, labels=False, duplicates="drop")
        dec = F.groupby("decile")["ret"].mean()
        top25 = F.nlargest(25, "score")["ret"].mean() - COST
        topq = F[F["decile"] >= 9]["ret"].mean() - COST
        ew = F["ret"].mean()
        curves["top25"].append(curves["top25"][-1] * (1 + top25))
        curves["topq"].append(curves["topq"][-1] * (1 + topq))
        curves["ew"].append(curves["ew"][-1] * (1 + ew))
        curves["deciles"].append([round(x, 4) for x in dec.reindex(range(10)).tolist()])
        yearly.append({"date": str(d.date()), "n": len(F), "top25": round(top25, 4),
                       "topq": round(topq, 4), "ew": round(ew, 4),
                       "spread": round(topq - dec.get(0, np.nan), 4)})
        print(f"{d.date()}  n={len(F):4d}  top25 {top25*100:+6.1f}%  topQ {topq*100:+6.1f}%  "
              f"EW {ew*100:+6.1f}%  spread {(topq - dec.get(0, np.nan))*100:+6.1f}pp")
    yrs = len(yearly)
    res = {"yearly": yearly,
           "cagr_top25": round(curves["top25"][-1] ** (1 / yrs) - 1, 4) if yrs else None,
           "cagr_topq": round(curves["topq"][-1] ** (1 / yrs) - 1, 4) if yrs else None,
           "cagr_ew": round(curves["ew"][-1] ** (1 / yrs) - 1, 4) if yrs else None,
           "curves": {k: [round(x, 4) for x in v] for k, v in curves.items() if k != "deciles"},
           "deciles": curves["deciles"],
           "caveats": ["survivorship: today's listed universe — spreads are the honest signal",
                       "mcap uses current shares outstanding (approximation)",
                       "point-in-time fundamentals: only filings public by each rebalance date"]}
    with open("data/backtest_us.json", "w") as f:
        json.dump(res, f)
    print(f"\nCAGRs — top25 {res['cagr_top25']}, top-decile {res['cagr_topq']}, universe EW {res['cagr_ew']}")

if __name__ == "__main__":
    main()
