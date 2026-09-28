# The Dossier Protocol — factor-desk-us

Every name in the screener's top 50, plus any ticker called on demand, gets a five-step
dossier. Each dossier is a static page under `dossiers/` with EVERY figure tagged
VERIFIED (live source, cited with date), STALE (source found but older than the claim
needs), or UNVERIFIED (could not be sourced — never silently filled from memory).
The five steps run in order; Step 4 audits Steps 1–3; Step 5 is written last and is
the only part meant to be re-read months later.

Dossiers are produced by Claude research sessions (with live web access), not by the
nightly Actions build. The build only lists and links whatever dossiers exist. Refresh
policy: a dossier is STALE after the company's next 10-Q/10-K filing, and its page
banner says so with the filing that outdated it.

---

## Step 1 — Deep dive

Do a deep research dive on [TICKER]. Use live sources and cite every figure with its
source and the date it was reported.

Cover:
- What the business actually does and where the revenue comes from, by segment and by percentage
- Financial health: revenue growth, margins and their direction, free cash flow, debt, and cash position, with the last 3 years for trend
- The competitive moat, and specifically what would have to happen for it to stop working
- Near-term catalysts, with dates where they exist
- The three biggest risks, ranked

Then score it 1 to 10 on financial health, moat strength, and growth prospects, and
explain each score in one sentence.

Rules: cite the source and date for every number. If you cannot verify a figure, write
UNVERIFIED rather than using the most recent one you remember. Separate what you found
from what you are inferring. Do not tell me whether to buy it.

## Step 2 — Competitors

Compare [TICKER] against its most relevant competitors: [LIST 2 TO 4].

Build a table with, for each company: market cap, P/E and forward P/E, revenue growth
rate, gross and operating margin, free cash flow, and debt to equity. Source and date
every cell.

Then tell me:
- Where [TICKER] is genuinely better, genuinely worse, and roughly equivalent
- Whether any valuation gap between them is justified by the fundamentals or not, and say explicitly which parts of that you can support with data versus which are judgment
- What the market appears to believe about each company that the numbers do not obviously support

Do not rank them by which is the better investment. Rank them on each metric separately
and let me do the combining.

## Step 3 — The short seller

You are a short seller who has just been assigned [TICKER] and your job is to build the
case against it. You have no position and no loyalty to the bull thesis.

Argue the strongest possible case that this is a bad investment right now. Specifically:
- What is the most likely way the bull thesis breaks
- Which parts of the growth story depend on assumptions rather than results
- What competitive, regulatory, or macro risk is being underpriced
- What is in the filings that the enthusiasm skips over
- Who is on the other side of this trade and what do they know

Then give me the specific conditions under which you would be wrong, and a concrete
invalidation level: the price or the business event at which the bear case is defeated.

Cite sources. Do not soften anything to be balanced. I have already read the bull case.

## Step 4 — The audit

Here is the analysis you produced on [TICKER]: [ALL THREE OUTPUTS]

Now audit your own work as a skeptic with no attachment to it.

For every single number in those three outputs, tell me: the exact source, the date it
was reported, and whether you retrieved it live or produced it from memory. Mark each
one VERIFIED, STALE, or UNVERIFIED.

Then flag: any figure you cannot source, any claim stated as fact that is actually an
inference, any place the three analyses contradict each other, and anything where you
expressed more confidence than the evidence supports.

List everything I need to check myself before this influences a decision.

## Step 5 — The decision record

Based on everything above, write a decision record for [TICKER] that I will re-read in
6 months.

Include: the core thesis in two sentences, the three things that must be true for it to
work, the specific evidence for each, the bear case in two sentences, my invalidation
level, what I expect to happen and roughly when, and what I am uncertain about.

Do not include a recommendation. Write it so that future me can tell whether present me
was reasoning well or just got lucky.

---

## Mechanical verification layer

Independent of the web research, every dossier page also renders the company's EDGAR
XBRL figures directly from the desk's panel — value, period, FILED date, accession
number linking to the filing on sec.gov. Where a Step 1–3 claim and the filed figure
disagree, the filed figure wins and the discrepancy is flagged automatically. EDGAR is
the primary source; news and data aggregators are secondary.
