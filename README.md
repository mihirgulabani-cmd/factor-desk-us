# factor-desk-us

The US long-term factor desk: all NYSE/Nasdaq/AMEX names ≥ $300M market cap (~2,500),
scored nightly on SEC EDGAR point-in-time fundamentals with every figure cited
(concept · period · filed date · accession), an 11-year price panel, a strictly
point-in-time 10-year backtest of the ranking (annual 1-year holds), a
**pressured-quality** section (top-30% fundamentals, ≥25% off highs, lagging their
sector, results still growing), and five-step research dossiers for the top 50
(see `dossiers/PROTOCOL.md`).

Long-term only by design: no swing tabs, no short-term signals.

## Plumbing (same pattern as factor-desk)
GitHub Actions nightly (22:30 UTC weekdays, after the US close) → runs the pipeline →
deploys GitHub Pages. Paste `workflow-build.yml` as `.github/workflows/build.yml` on
github.com (protected-file routine). Enable Pages: Settings → Pages → Source: GitHub
Actions.

Pipeline order (what the workflow runs):
1. `pipeline/universe.py` — SEC ticker/exchange file → raw universe
2. `pipeline/fetch_facts.py` — EDGAR companyfacts per CIK, cached + incremental; SIC codes
3. `pipeline/facts_to_panel.py` — XBRL → point-in-time panel (earliest filing kept for
   PIT truth, latest kept for display/restatements)
4. `pipeline/fetch_prices.py` — 11y daily adjusted prices, sharded + incremental;
   applies the $300M market-cap floor
5. `model/screener_model_us.py` — pillar scores (lender model for banks), peak-earnings
   flag, pressured-quality flag, citations → `data/model_us.json`
6. `backtest/pit_backtest.py` — annual July rebalances, only filings public by each
   date, top-25/top-decile/deciles vs universe EW → `data/backtest_us.json`
7. `site/build_html_us.py` — inlines both JSONs into `site/template_us.html` →
   `site/US-Factor-Desk.html` (deployed as index.html)

First run is heavy (~2,500 EDGAR pulls at SEC's rate limit + full price history):
expect ~60–90 min. Later runs are incremental via the Actions cache.

## Honesty notes (read before quoting numbers)
- **Survivorship**: the universe is today's listed names; delisted companies are absent,
  which flatters absolute backtest returns. Quote the top-vs-bottom decile SPREAD and
  the screener-vs-universe-EW gap as the signal, not the absolute CAGR.
- **Point-in-time**: backtest fundamentals use only filings with `filed <=` each
  rebalance date — no lookahead. Display values use latest filings (restatement-aware).
- **Peak earnings**: any name earning >1.6× its own 3-year average carries a PEAK EPS
  flag and is ranked on normalized PE (mcap ÷ 3y-avg NI), not headline PE.
- Historical market caps approximate shares with current counts (noted in the backtest
  output). Rank robustness, not level truth.

## Dossiers
`dossiers/PROTOCOL.md` holds the five-step prompt protocol verbatim. Dossier pages are
produced by Claude research sessions and committed as `dossiers/<TICKER>.html`; the
nightly build lists whatever exists. A dossier is stale after the company's next filing.
