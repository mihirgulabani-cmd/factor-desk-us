#!/usr/bin/env python3
"""fetch_prices.py — 11 years of daily adjusted OHLCV for the universe via yfinance.
Chunked, cached in shards (prices/shard_XX.csv.gz), incremental top-up on later runs.
Also writes data/universe.csv = universe_raw filtered to market cap >= $300M
(close x dei shares from meta.csv). Run in GitHub Actions."""
import glob, os, time
import pandas as pd
import yfinance as yf

SHARD = 250
YEARS = 11
os.makedirs("prices", exist_ok=True)

def main():
    uni = pd.read_csv("data/universe_raw.csv")
    tickers = uni["ticker"].tolist()
    start = (pd.Timestamp.now() - pd.DateOffset(years=YEARS)).strftime("%Y-%m-%d")
    frames = []
    for i in range(0, len(tickers), SHARD):
        chunk = tickers[i:i + SHARD]
        spath = f"prices/shard_{i // SHARD:02d}.csv.gz"
        since = start
        old = None
        if os.path.exists(spath):
            old = pd.read_csv(spath, parse_dates=["date"])
            since = (old["date"].max() - pd.Timedelta(days=5)).strftime("%Y-%m-%d")
        for attempt in range(3):
            try:
                dl = yf.download(chunk, start=since, interval="1d", group_by="ticker",
                                 auto_adjust=True, threads=True, progress=False)
                break
            except Exception:
                time.sleep(20 * (attempt + 1))
        rows = []
        for tk in chunk:
            try:
                g = dl[tk].dropna(subset=["Close"])
            except Exception:
                continue
            if g.empty: continue
            r = g.reset_index()[["Date", "Open", "High", "Low", "Close", "Volume"]]
            r.columns = ["date", "open", "high", "low", "close", "volume"]
            r.insert(0, "ticker", tk)
            rows.append(r)
        new = pd.concat(rows) if rows else pd.DataFrame()
        if old is not None and not new.empty:
            new = (pd.concat([old, new])
                     .drop_duplicates(["ticker", "date"], keep="last")
                     .sort_values(["ticker", "date"]))
        elif old is not None:
            new = old
        if not new.empty:
            new.to_csv(spath, index=False, compression="gzip")
        print(f"shard {i // SHARD}: {new['ticker'].nunique() if not new.empty else 0} names")
        time.sleep(2)
    # market-cap filter -> final universe
    meta = pd.read_csv("data/meta.csv")
    last = {}
    for f in glob.glob("prices/shard_*.csv.gz"):
        d = pd.read_csv(f, parse_dates=["date"])
        for tk, g in d.groupby("ticker"):
            last[tk] = g["close"].iloc[-1]
    meta["last_close"] = meta["ticker"].map(last)
    meta["mcap"] = meta["last_close"] * meta["shares_now"]
    # unresolved mcap = OUT. Run-#3 lesson: keeping NaN-mcap names let 1,663
    # warrants/SPAC shells (no dei share count) through the $300M floor.
    keep = meta[meta["mcap"] >= 300e6]
    out = uni[uni["ticker"].isin(keep["ticker"])]
    out.to_csv("data/universe.csv", index=False)
    print(f"final universe (>= $300M, mcap resolved): {len(out)}")

if __name__ == "__main__":
    main()
