#!/usr/bin/env python3
"""fetch_facts.py — pull SEC EDGAR XBRL companyfacts for the whole universe, cached.

Every figure in the desk traces to one of these files: value + period end + FILED date +
accession number + form type. That is the citation spine ("100% verified" rule).

- Rate-limited to ~8 req/s (SEC cap is 10).
- Cache: facts/CIK##########.json.gz ; refreshed only when the company has filed since
  (checked via the lightweight submissions endpoint), so nightly runs are incremental.
Run in GitHub Actions.
"""
import gzip, json, os, sys, time, urllib.request

UA = {"User-Agent": "factor-desk-us research mihirgulabani@gmail.com",
      "Accept-Encoding": "gzip"}
CACHE = "facts"
os.makedirs(CACHE, exist_ok=True)

def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return json.loads(data)

def main():
    rows = [l.strip().split(",") for l in open("data/universe_raw.csv").read().splitlines()[1:]]
    ciks = [(int(r[0]), r[1]) for r in rows]
    print(f"fetching facts for {len(ciks)} names")
    done = fail = fresh = 0
    sicf = open("data/sic.csv", "w"); sicf.write("cik,sic,sic_desc\n")
    for cik, tk in ciks:
        cs = f"CIK{cik:010d}"
        path = os.path.join(CACHE, cs + ".json.gz")
        try:
            sub = get_json(f"https://data.sec.gov/submissions/{cs}.json")
            desc = (sub.get("sicDescription") or "").replace('"', "").replace(",", " ")
            sicf.write(f"{cik},{sub.get('sic','')},{desc}\n")
            time.sleep(0.06)
            if os.path.exists(path):
                # incremental: skip if no new filing since cache mtime
                latest = (sub.get("filings", {}).get("recent", {}).get("filingDate") or [""])[0]
                cache_day = time.strftime("%Y-%m-%d", time.gmtime(os.path.getmtime(path)))
                if latest and latest < cache_day:
                    fresh += 1; continue
            j = get_json(f"https://data.sec.gov/api/xbrl/companyfacts/{cs}.json")
            with gzip.open(path, "wt") as f:
                json.dump(j, f)
            done += 1
        except Exception as e:
            fail += 1
            if fail < 20: print(f"  {tk} ({cs}): {type(e).__name__}", file=sys.stderr)
        time.sleep(0.13)                                  # ~7.5 req/s
        if (done + fail + fresh) % 250 == 0:
            print(f"  ...{done} fetched, {fresh} cached-fresh, {fail} failed")
    sicf.close()
    print(f"facts done: {done} fetched, {fresh} unchanged, {fail} failed")

if __name__ == "__main__":
    main()
