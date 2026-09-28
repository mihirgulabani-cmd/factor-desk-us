#!/usr/bin/env python3
"""facts_to_panel.py — EDGAR XBRL companyfacts -> point-in-time fundamentals panel.

Every row keeps: value, period end, FILED date, accession, form. Nothing is ever used
in a backtest before its filed date; nothing on the site is shown without its citation.

Concept fallback chains validated on AAPL / JPM / CAT (tech, bank, industrial):
banks lacking GrossProfit/OperatingIncome/Capex get lender=True and are scored on the
lender model (ROE, NI growth, EPS) exactly like the NSE desk treats banks.

Outputs:
  data/panel_annual.csv.gz   one row per (cik, concept, fy-end)   with filed/accn
  data/panel_quarterly.csv.gz same for 10-Q durations
  data/meta.csv              cik, ticker, name, lender flag, latest dei shares
"""
import glob, gzip, json, os
import pandas as pd

CHAINS = {
    "rev":    ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
               "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax",
               "InterestAndDividendIncomeOperating"],
    "ni":     ["NetIncomeLoss"],
    "op":     ["OperatingIncomeLoss"],
    "gp":     ["GrossProfit"],
    "ocf":    ["NetCashProvidedByUsedInOperatingActivities",
               "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex":  ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "assets": ["Assets"],
    "eq":     ["StockholdersEquity",
               "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "debt_lt": ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations",
                "DebtLongtermAndShorttermCombinedAmount"],
    "cash":   ["CashAndCashEquivalentsAtCarryingValue"],
    "shares_d": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "eps_d":  ["EarningsPerShareDiluted"],
    "buyback": ["PaymentsForRepurchaseOfCommonStock"],
    "div":    ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
}
INSTANT = {"assets", "eq", "debt_lt", "cash"}          # balance-sheet points
UNIT_PREF = ["USD", "USD/shares", "shares", "pure"]

def pick_unit(units):
    for u in UNIT_PREF:
        if u in units: return units[u]
    return next(iter(units.values()))

def extract(gaap, key):
    """Return list of dicts for the first chain concept present, annual + quarterly."""
    for concept in CHAINS[key]:
        node = gaap.get(concept)
        if not node: continue
        rows = pick_unit(node.get("units", {}))
        out = []
        for x in rows:
            form = x.get("form", "")
            if form not in ("10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A"): continue
            if key not in INSTANT:
                # duration facts: annual ~365d, quarterly ~91d; drop YTD 6/9-month spans
                try:
                    days = (pd.Timestamp(x["end"]) - pd.Timestamp(x["start"])).days
                except Exception:
                    continue
                if 330 <= days <= 400: span = "FY"
                elif 80 <= days <= 100: span = "Q"
                else: continue
            else:
                span = "FY" if form.startswith(("10-K", "20-F")) else "Q"
            out.append({"concept": concept, "key": key, "span": span,
                        "end": x["end"], "val": x.get("val"),
                        "filed": x.get("filed"), "accn": x.get("accn"), "form": form})
        if out: return out
    return []

def main():
    files = sorted(glob.glob("facts/CIK*.json.gz"))
    uni = pd.read_csv("data/universe_raw.csv")
    cikmap = dict(zip(uni["cik"], zip(uni["ticker"], uni["name"])))
    rows, meta = [], []
    for i, path in enumerate(files):
        cik = int(os.path.basename(path)[3:13])
        if cik not in cikmap: continue
        tk, name = cikmap[cik]
        try:
            with gzip.open(path, "rt") as f: j = json.load(f)
        except Exception:
            continue
        gaap = j.get("facts", {}).get("us-gaap", {})
        dei = j.get("facts", {}).get("dei", {})
        got = {}
        for key in CHAINS:
            recs = extract(gaap, key)
            got[key] = bool(recs)
            for r in recs:
                r["cik"] = cik
                rows.append(r)
        lender = not (got["gp"] or got["op"]) and got["ni"]      # bank/insurer signature
        shares_now = None
        node = dei.get("EntityCommonStockSharesOutstanding")
        if node:
            u = pick_unit(node["units"])
            if u: shares_now = sorted(u, key=lambda x: x.get("filed") or "")[-1].get("val")
        meta.append({"cik": cik, "ticker": tk, "name": name,
                     "lender": lender, "shares_now": shares_now})
        if i % 250 == 0: print(f"  ...{i}/{len(files)}")
    df = pd.DataFrame(rows)
    # de-duplicate: same (cik,key,span,end) filed multiple times -> keep EARLIEST filing
    # for point-in-time truth, but also keep the latest value for display (restatements)
    df = df.sort_values("filed")
    first = df.drop_duplicates(["cik", "key", "span", "end"], keep="first")
    last = df.drop_duplicates(["cik", "key", "span", "end"], keep="last")
    first[first["span"] == "FY"].to_csv("data/panel_annual.csv.gz", index=False, compression="gzip")
    first[first["span"] == "Q"].to_csv("data/panel_quarterly.csv.gz", index=False, compression="gzip")
    last[last["span"] == "FY"].to_csv("data/panel_annual_latest.csv.gz", index=False, compression="gzip")
    pd.DataFrame(meta).to_csv("data/meta.csv", index=False)
    print(f"panel: {len(first)} PIT rows across {len(meta)} names "
          f"({sum(m['lender'] for m in meta)} lender-model)")

if __name__ == "__main__":
    main()
