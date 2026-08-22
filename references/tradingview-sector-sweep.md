# TradingView sector sweep — the primary data path

Read this before gathering data. It is the **primary** guide for this skill: how to pull the top
performers in every sector from the **TradingView (`Trading_View`) MCP connector**, triage them
against the CAN SLIM hard filters, hand the survivors to the sister skill **`can-slim-grader`**,
and turn the grades into the two recommendation lists.

`ibkr-data-guide.md` is the **fallback** guide — read it when TradingView is not connected, or
for the fundamental-source ladder (Daloopa / SEC EDGAR / FMP / web) that both paths share.

TradingView tools are **deferred** — load them with `ToolSearch` before use, e.g.
`ToolSearch("select:mcp__Trading_View__run_screener,mcp__Trading_View__get_ohlcv,mcp__Trading_View__get_symbol_data,mcp__Trading_View__get_financial_history,mcp__Trading_View__get_earnings_history,mcp__Trading_View__get_financials,mcp__Trading_View__get_quotes_batch,mcp__Trading_View__search_symbols")`.
Symbols are `EXCHANGE:TICKER` (e.g. `NASDAQ:AAPL`, `AMEX:SPY`).

---

## Freshness — non-negotiable, every run

**Re-issue every call on every run.** Never reuse a screener result, a bar series, a
`sector_screen.py` output file, a grade, or a filled dashboard from an earlier run, an earlier
session, or earlier in this conversation — **even for the same sectors, even minutes later**.
Sector leadership rotates intraday, and a quarter can land between two runs. A re-check ("run it
again", "is that still true?") is a **full re-run**, not a patched figure.

Take the as-of stamp **from the data**, not the wall clock: the newest bar date the provider
returned, and whether it is a close or an intraday print. Stamp `CONFIG.generatedAt` and every
`CONFIG.sourceMap[].pulled` with the real pull time of *this* run. If a source hands back
something stale or gated, say so in `CONFIG.dataWarning` and name what filled the gap.

---

## Step 0 — Market direction (M) first; it gates the tone and every row's score

Pull the index bars and count distribution days before any sector work:

```
get_ohlcv { symbol: "AMEX:SPY",     interval: "1D", count: 300 }
get_ohlcv { symbol: "NASDAQ:QQQ",   interval: "1D", count: 300 }
```

- **Distribution day** = an index close down >= 0.2% on heavier volume than the session before.
  Count them over the last ~25 sessions. **4-5+ → the market is under pressure.**
- Check price against the 50- and 200-day, and whether the index is making higher highs/lows.
- Cross-check with one web search for the current market read.
- Classify **Confirmed uptrend / Under pressure / Correction** and set `CONFIG.market.mGrade`
  to `pass` / `partial` / `fail`. M is graded **once** and applied to every row, so it moves all
  totals together — in a correction, `fail` costs every name a full point and the 4.5 cut
  correctly gets much harder to reach. That is the method working, not a bug: say so in the
  report rather than loosening the cut.

**Also record SPY's performance over the sweep window** (from the same bars, or
`get_symbol_data("AMEX:SPY", ["Perf.6M","Perf.Y","Perf.3M","Perf.YTD"])`). It is the benchmark
for every RS figure downstream — RS here is *window performance minus SPY's over the same
window*, so it must come from the same window you rank sectors by.

---

## Step 1 — The sector universe

TradingView's US market uses the **FactSet-style sector taxonomy** (not GICS). The 20 sectors:

```
Commercial Services      Communications          Consumer Durables      Consumer Non-Durables
Consumer Services        Distribution Services   Electronic Technology  Energy Minerals
Finance                  Health Services         Health Technology      Industrial Services
Miscellaneous            Non-Energy Minerals     Process Industries     Producer Manufacturing
Retail Trade             Technology Services     Transportation         Utilities
```

Sweep **all of them** by default (`Miscellaneous` is a catch-all — sweep it but expect little).
If the user scopes the run ("just tech", "the top 5 sectors"), sweep only those and say so in
`CONFIG.sweep.note`. **Verify the list at runtime** rather than trusting it blind: a sector name
that returns `totalCount: 0` from the screener has been renamed — re-derive the live list with
one broad `run_screener` reading the `sector` column and use what comes back.

---

## Step 2 — Top 10 performers per sector (`run_screener`)

**One `run_screener` call per sector.** This is the call whose shape matters most — the
parameters below are verified against the live connector:

```
run_screener {
  market: "america",
  sort_by: "Perf.6M",            // the ranking window - see below
  sort_order: "desc",
  limit: 10,                     // "the top 10 performers in each sector"
  symbol_types: ["stock"],
  filters: [
    {"left":"sector",                  "operation":"equal",    "right":"Electronic Technology"},
    {"left":"exchange",                "operation":"in_range", "right":["NASDAQ","NYSE","AMEX"]},
    {"left":"market_cap_basic",        "operation":"greater",  "right":1000000000},
    {"left":"close",                   "operation":"greater",  "right":15},
    {"left":"average_volume_10d_calc", "operation":"greater",  "right":400000}
  ],
  columns: ["name","description","close","Perf.3M","Perf.6M","Perf.Y","Perf.YTD",
            "market_cap_basic","average_volume_10d_calc","relative_volume_10d_calc",
            "sector","industry","price_52_week_high","price_52_week_low",
            "EMA50","EMA200","RSI","exchange","earnings_release_next_date"]
}
```

**Traps this exact shape avoids — each one cost a wrong answer in testing:**

- **The `exchange` filter is load-bearing.** Without it, OTC tickers leak in and dominate the
  ranking with junk figures (an OTC name printed `Perf.6M: 56400` from a single stale mark).
  Restrict to `NASDAQ` / `NYSE` / `AMEX` — US primary listings, as the method's price and
  liquidity rules assume.
- **`average_volume_50d_calc` does not exist** — the connector silently returns it in
  `ignored_filters` and the column comes back `null`. Use `average_volume_10d_calc`.
- **Always read `ignored_filters` in the response.** A filter listed there did *not* apply, so
  the rows are wider than you asked for. `typespecs` is commonly ignored too; ADRs (`type:"dr"`)
  can still slip through, so check the `type`/`description` on anything unfamiliar.
- **Do NOT use `analyze_sector_tool` for this.** Its `metric` argument does not reorder the
  scan the way its name suggests — asked for `perf_6m` it returned the sector's highest-volume
  names split into "leaders"/"laggards" by *today's* percentage change. It is fine for a quick
  sector feel; it is not "the top 10 performers by performance". `run_screener` sorted on a
  `Perf.*` column is.

**The ranking window.** Default to **`Perf.6M`** — long enough to be leadership rather than a
one-week pop, short enough to reflect the *current* leaders. Always pull `Perf.3M`, `Perf.Y` and
`Perf.YTD` alongside it so the report can show whether the move is accelerating or fading. If
the user names a window ("this year", "the last month"), rank on that column instead and set
`CONFIG.sweep.windowLabel` to match — one window for the sectors and every RS figure, no mixing.

---

## Step 3 — Triage the 200 names down (`scripts/sector_screen.py`)

Feed every screener row into the script exactly as it came back — never retype numbers:

```json
{ "asOf": "2026-08-21 (close)",
  "window": "Perf.6M",
  "benchmark": {"symbol": "AMEX:SPY", "perf": {"Perf.6M": 11.2}},
  "sectors": { "Electronic Technology": [ <row>, <row>, ... ], "Health Technology": [ ... ] } }
```

```
python scripts/sector_screen.py sweep.json --md      # readable
python scripts/sector_screen.py sweep.json           # JSON, incl. the grade queue
```

It computes % off the 52-week high, RS vs the benchmark, position vs the 50/200-day EMA, average
dollar volume, the **sector ranking** (median window performance of each sector's top 10), and a
per-name **triage verdict**. The hard filters it applies are the method's own disqualifiers:

| Drop when | Letter | Why |
|---|---|---|
| price < $15 | — | the method does not buy cheap stock |
| avg dollar volume < $20M | S | too thin for institutional sponsorship |
| market cap < $1B | S/I | below the sponsorship test |
| more than 25% below the 52-week high | N | no new-high ground; overhead supply |
| window performance <= SPY's | L | a laggard, not a leader |
| below the 200-day EMA | N/L | a downtrend |

A check whose input the screener did not return is **skipped and named** in `checks_skipped` —
a missing column never silently passes or fails a name. Tune the thresholds with `--min-price`,
`--min-dollar-vol`, `--max-off-high`, `--min-rs`, `--top` when the user's scope calls for it, and
say in `CONFIG.sweep.note` that you did.

The script's `grade_queue` is the exact list to grade next. **Report the funnel honestly** in
`CONFIG.sweep` — sectors swept, names pulled, cleared triage, fully graded — so a reader can see
what was dropped and why, rather than reading the sweep as full coverage.

---

## Step 4 — Grade the survivors with `can-slim-grader`

Every name that clears triage gets the **sister skill's** grade, so a 4.5 in this report means
exactly what a 4.5 means in a single-ticker report. If `can-slim-grader` is installed, invoke it
per ticker. If it is not, tell the user (install from
**https://github.com/thewongdirection/can-slim-grader**) and apply its rubric inline from
`canslim-methodology.md` — do not improvise a different scale.

Per ticker, five TradingView calls cover six of the seven letters:

| Call | Feeds |
|---|---|
| `get_ohlcv { interval:"1D", count:500 }` | N (base, breakout), S (volume), L (RS) — 500 is the floor: the 200-day EMA needs ~200 sessions before the displayed window |
| `get_ohlcv { interval:"1W", count:104 }` | N — base shape, depth and length |
| `get_symbol_data` (52-wk high/low, float, avg volume) | N, S |
| `get_financial_history { period:"fq" }` and `{ period:"fy" }` | C, A — both carry `yoy_pct` |
| `get_earnings_history` | C — street EPS actual vs consensus, beat rate, next report date |
| `get_financials` | A — ROE, margins, debt/equity |

Run `scripts/relative_strength.py` on the ticker's daily bars plus SPY's for the RS proxy, %
off the 52-week high, base depth/length and breakout volume. Both scripts read the provider
payload **as it came back**.

**Two TradingView traps that will misgrade a letter:**

1. `get_financial_history.eps` is **GAAP**. Grade **C** on `get_earnings_history.eps_actual`
   (the street figure); treat a wide GAAP/street gap as an earnings-quality check, not as C.
2. The **TTM** growth fields break across a spin-off or a restatement. Take growth from the
   per-period `yoy_pct`, never from TTM.

**I (institutional sponsorship) is the one letter TradingView cannot answer.** Take it from
13F/Form 4 — FMP `form13F`, or the `securities-filings-lookup` skill — or the web, and record
which in `CONFIG.sourceMap`. Never leave I ungraded: the dashboard's self-audit flags it.

**Grades follow their evidence.** If the `actual` you print concedes a miss ("just under 25%",
"hasn't cleared the high"), the letter **cannot be pass** — call it partial. Where a threshold
says *each* ("EPS up **each** of the last 3 years at >=25%"), every period must clear it; one
strong year among three weak ones is a partial. Magnitude of a beat, backlog, guidance or a big
volume day are colour for the `reason`, never grounds to promote a letter.

**What counts as a pivot** (get this wrong and the report invents a trade the method would never
take): a pivot needs **both** a sound base (>=7-8 weeks — 5-6 for a flat base, 4-7 for a square
box — formed after a >=30% advance, handle in the upper half and above the 10-week line) **and**
new-high ground. As a hard filter, **a candidate pivot more than ~10% below the 52-week high is
not a pivot.** A name with strong C and A but no valid pivot is a **WATCH** with "None now" plus
the condition that would create an entry — record `high52` on the pick so the dashboard can
check it.

---

## Step 5 — The two recommendation lists

Put **every fully graded name** into `CONFIG.picks[]` with its sector, its rank inside that
sector, its six letter grades and its verdict. The dashboard derives both lists — do not
hand-build them:

1. **Sector leaders** — every pick at or above `CONFIG.gradeThreshold` (**4.5 of 7** by
   default), grouped by sector, best sector first. A sector with no qualifier is a finding
   about that sector; record it in `CONFIG.excluded` rather than dropping the cut to fill it.
2. **Overall top N** — the `CONFIG.topCount` (default 10) highest grades market-wide, ties
   broken by RS then proximity to the 52-week high. **No sector cap applies here**, so this
   list can concentrate in one or two groups; the dashboard badges the overlap with list 1.

**Both lists are gated at the cut.** A name below 4.5 is not a recommendation just because
everything else scored worse, so it appears in neither list — it stays in the "Every name graded"
appendix with its full scorecard, where a reader can see exactly how close it came.

**When nothing clears the cut, list 2 renders EMPTY with an enumerated "why".** The dashboard
derives those reasons from the graded pool itself, so they are evidence rather than narration:

- the **M grade** and what it costs every row (a correction takes a full point off all seven);
- **which letters failed and how often** across the graded names, worst first — "C: 5 FAIL and 2
  PARTIAL of the 8 graded (none passed)";
- the **best score actually reached** and how far short of the cut it fell;
- how many of the pulled top performers **never reached grading**, dropped on the hard filters;
- that **every sector** came back empty, so it is a market-wide read rather than one weak group.

Add anything run-specific the grades cannot show on their own via `CONFIG.noQualifierReasons`
(an earnings season mid-flight, a connector gated for one letter) — the page appends it. Set
`CONFIG.shortfall` too; it carries the same message on list 1.

**A sector with no qualifier still shows its top 5.** `sector_screen.py` emits a `top5` per sector
(override the count with `--fallback N`); paste it into `CONFIG.sectors[].top5` for every sector.
The dashboard renders it **only** where `qualified` is 0, under an amber "ungraded - not
recommendations" banner, and marks each row with whether it cleared the hard filters. The point is
that a reader can still see where the strength sat in a group that produced nothing — these names
have no scorecard, no verdict and no buy point, and must never be presented as picks.

**Never lower the threshold to lengthen a list.** If only three names reach 4.5, the answer is
three names plus `CONFIG.shortfall` explaining what the rest failed on. If none do, the answer is
two empty lists, the reasons, and the per-sector top 5 as context. Padding a screen with weak
names is the exact failure the method exists to prevent — and so is quietly re-baselining the cut
until something shows up.

The **grade is not the verdict.** A name can clear 4.5 on C, A and L and still be a WATCH
because N fails. Fill `verdict` on every pick (BUY-RANGE / WATCH / AVOID) — the dashboard's
self-audit rejects a report where the two disagree, where a buy point sits more than 10% below
the 52-week high, or where a stop is not 7-8% below the entry.

---

## Step 6 — Fallbacks when TradingView is unavailable

Gating is per-endpoint and often intermittent: keep whatever a source *does* answer and fill only
the gaps from the next rung — never drop a letter because one call failed.

| Need | Fallback order |
|---|---|
| Sector top performers | FMP `search-company-screener` (ranks by market cap, not performance — re-rank yourself from quotes) → IBKR `search_investment_topics` + `get_theme_details` → web new-high/leaders lists |
| Bars / RS / base | Massive Market Data `/v2/aggs` (**throttle to 5 calls/min**) → IBKR `get_price_history` (`period: "TWO_YEARS"`, `step: "ONE_DAY"`) |
| Live last price | FMP `batch-quote` → IBKR `get_price_snapshot` |
| C / A fundamentals | Daloopa → bigdata.com → LSEG → SEC EDGAR via `securities-filings-lookup` → FMP → web |
| I sponsorship | FMP `form13F` → `securities-filings-lookup` → web |

Whatever you fall back to, name it in `CONFIG.dataProvenance`, add a `CONFIG.sourceMap` row for
it, and set `CONFIG.dataWarning` to say what was gated or stale and what filled the gap.

---

## Guardrails

- **Read-only market data.** Never call TradingView's portfolio-write or delete tools, and never
  call IBKR order or account tools (balances, positions, orders, trades, summary, PA analytics),
  even if asked mid-run. Trading and account access are out of scope for this skill.
- **Never display or store** contract IDs, account numbers, or any account-bound data. Present
  stocks by symbol and name only.
- Timestamp everything and flag approximations: RS here is a **proxy** (window performance vs
  SPY), not a full-market 1-99 rating, and fundamentals can lag the latest quarter.
- Paraphrase research; short quotes only.
