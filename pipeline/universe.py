#!/usr/bin/env python3
"""universe.py — build the US desk universe: all NYSE/Nasdaq/AMEX common stocks with
market cap >= $300M. Sources: SEC company_tickers_exchange.json (CIK<->ticker<->exchange,
official) + last close from the price shards (prices.py runs first on a seed list, then
universe is refined). First run bootstraps from the SEC file alone.

Outputs: data/universe.csv  (cik, ticker, name, exchange)
Run inside GitHub Actions (network) — sandbox/dev machines may lack EDGAR access.
"""
import json, os, time, urllib.request

UA = {"User-Agent": "factor-desk-us research mihirgulabani@gmail.com"}
OUT = "data"
os.makedirs(OUT, exist_ok=True)

def get(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if i == retries - 1: raise
            time.sleep(2 * (i + 1))

def main():
    # Official SEC mapping incl. exchange. Object of rows: cik, name, ticker, exchange
    j = get("https://www.sec.gov/files/company_tickers_exchange.json")
    fields = j["fields"]; rows = j["data"]
    ix = {f: i for i, f in enumerate(fields)}
    keep_ex = {"NYSE", "Nasdaq", "NYSE MKT"}   # no Arca/CBOE: those lists are mostly ETFs/ETNs with no company financials
    seen = set(); out = []
    for r in rows:
        cik, name, tk, ex = r[ix["cik"]], r[ix["name"]], r[ix["ticker"]], r[ix["exchange"]]
        if ex not in keep_ex: continue                     # drops OTC
        if not tk or "-" in tk and tk.split("-")[-1] in ("WT", "U", "R"): continue  # warrants/units
        if tk in seen: continue                            # first listing per ticker
        # skip obvious non-common share classes duplicating a CIK (keep first class listed)
        seen.add(tk)
        out.append((cik, tk, name.replace(",", " "), ex))
    with open(os.path.join(OUT, "universe_raw.csv"), "w") as f:
        f.write("cik,ticker,name,exchange\n")
        for cik, tk, name, ex in out:
            f.write(f"{cik},{tk},{name},{ex}\n")
    print(f"universe_raw: {len(out)} listed names (mcap filter applied after price pull)")

if __name__ == "__main__":
    main()
