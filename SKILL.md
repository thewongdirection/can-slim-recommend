---
name: can-slim-recommend
description: >-
  Sweep the whole market sector by sector and return TWO ranked recommendation lists, graded with
  the CAN SLIM growth-investing methodology. Pulls the top 10 performers in EVERY sector from
  TradingView, grades each one with the sister skill `can-slim-grader` (pass/partial/fail per
  letter, out of 7), then returns (1) every sector's leaders graded 4.5 or better and (2) the
  overall top 10 market-wide. Use whenever the user wants stock ideas, picks, or a screen -
  "recommend some stocks", "what should I buy", "find me growth stocks", "screen for CAN SLIM
  stocks", "best names in each sector", "top sector performers", "what to add to my watchlist",
  "build me a shortlist" - or a themed/scoped set ("recommend AI stocks", "just the top 5
  sectors") - even if they don't name CAN SLIM. This is the LIST/screener lens; to judge ONE named
  ticker (a C-A-N-S-L-I-M scorecard with a BUY-RANGE/WATCH/AVOID verdict) use `can-slim-grader`.
  Output: a white-themed A4 PDF report by default (the dark interactive HTML on request). Analysis and
  decision support only - never personalized investment advice and never trading.
---

# can-slim-recommend — CAN SLIM sector sweep over TradingView

Sweeps **every sector** for its top performers, grades each survivor against CAN SLIM with the
same rubric the sister skill uses, and delivers **two recommendation lists**:

1. **Sector leaders** — every top-of-sector performer graded **4.5 or better out of 7**, grouped
   by sector.
2. **Overall top 10** — the highest-graded names market-wide, regardless of sector.

Both come with a per-name CAN-SLIM-only rationale, a buy point where one legitimately exists, and
the 7-8% loss-cutting stop. The deliverable is a **white-themed A4 PDF report by default** (the
interactive HTML on request) — **not investment advice, and never an order.**

> **Sister skill — `can-slim-grader`.** This skill is the **LIST / screener** lens: the whole
> market → two ranked lists. Its sister, **`can-slim-grader`**, is the **single-ticker GRADER**:
> one ticker in → a C·A·N·S·L·I·M scorecard with a BUY-RANGE / WATCH / AVOID verdict. This skill
> **calls that one** to grade every candidate, so a 4.5 here means exactly what a 4.5 means
> there. If the user names one ticker and wants it judged, hand off to `can-slim-grader`; if they
> want ideas/picks/a screen, stay here. (For a data-rich single-stock dashboard, use
> `ibkr-review-ticker`.)

## Operating stance — a highly experienced professional's judgment
Run this the way a seasoned professional trader would: **disciplined, risk-first, evidence-driven,
and opinionated about conviction.** Bring the price/valuation discipline of a veteran value
investor to CAN SLIM's growth/momentum engine — i.e. still buy leaders breaking out of sound
bases, but refuse to justify a name on multiple-expansion or hype alone, and flag when a leader
is discounting implausible growth. Go **beyond the original 1988 book** and factor in modern,
up-to-date market knowledge — refresh it with web research each run rather than relying on memory:
- **Market structure that didn't exist in O'Neil's era** — passive / ETF flows and index
  rebalances, sector rotation, options positioning (dealer gamma, 0DTE, max-pain), and how they
  amplify or fade moves; concentration in mega-cap leadership; liquidity/volatility regime (VIX).
- **Event & macro overlay** — Fed path and CPI/jobs prints, earnings-season dispersion, and
  geopolitics/commodity shocks that reprice sectors intraday. Let these shape the M read and stops.
- **Factor evidence** — the momentum and quality factors (Fama-French/Jegadeesh-Titman momentum,
  AQR quality-minus-junk) that later research validated as the engine behind CAN SLIM's edge;
  use them to sanity-check that a "leader" is a genuine momentum+quality name, not a junk rip.
- **Modern risk management** — position sizing to a fixed % account risk, the 7-8% stop (tighter
  when M is under pressure), pyramiding into strength, taking partial gains, and never averaging
  down. State plainly what would invalidate each idea.
Be direct and professional in the write-up: lead with the read, quantify it, and name the risks.

## What CAN SLIM is (the standard this skill enforces)
CAN SLIM is a growth-stock selection framework built on how the market actually behaves
(supply/demand and crowd psychology) rather than on opinion or valuation "cheapness." Each
letter is one of seven traits shared by the biggest winning stocks just before their big
moves:
**C** current quarterly earnings & sales up big and accelerating · **A** annual earnings
growth 3 yrs + high ROE · **N** a new product/management/condition AND a breakout to new
highs from a sound base · **S** supply/demand (volume surge, tight float, buybacks) ·
**L** leader not laggard (high relative strength, #1 in a strong group) · **I** increasing
institutional sponsorship · **M** general market in a confirmed uptrend.

**Read `references/canslim-methodology.md` in full before screening** — it has every threshold,
the chart-base patterns, the sell rules, and the mistake list. **Read
`references/tradingview-sector-sweep.md`** for the exact TradingView call shapes, the sector
taxonomy, the triage filters, and the grader hand-off. `references/ibkr-data-guide.md` is the
**fallback** path plus the shared fundamental-source ladder.

## Prerequisites
- **TradingView (`Trading_View` MCP) — the primary connector, and the proven one.** It is the only
  one here that covers both halves: the sector screener (`run_screener`) *and* the bars and
  earnings that feed the letters (`get_ohlcv`, `get_symbol_data`, `get_financial_history`,
  `get_earnings_history`, `get_financials`). **All six of those endpoints have returned complete
  data in live end-to-end runs of this skill** — prefer them over any alternative that merely
  ought to work, and see the Tier 1 table in `tradingview-sector-sweep.md` for the per-call notes.
  Symbols are `EXCHANGE:TICKER`. Tools are deferred — load with `ToolSearch`.
- **Screen A before spending calls on history.** `get_financials` alone (ROE + TTM EPS growth)
  disqualifies most candidates on **A**, and a name that fails A cannot reach the cut — so pull
  `fq`/`fy` history only for the survivors. This roughly halved the fundamental calls in the live
  run.
- **`can-slim-grader`** — the sister skill that grades each candidate. If it isn't installed,
  say so, prompt the user to add it from **https://github.com/thewongdirection/can-slim-grader**,
  and apply its rubric inline from the shared methodology rather than inventing a different scale.
- **Institutional sponsorship (I)** is the one letter TradingView cannot answer — take it from
  13F/Form 4 (FMP `form13F`, `securities-filings-lookup`) or the web, and say which.
- **Web search** for the market read and the "new" in N.
- **Fallbacks — unverified, use only when the proven path fails:** IBKR MCP, Massive Market Data,
  FMP (commonly plan-gated) — the Tier 2 table in `tradingview-sector-sweep.md`. None has been
  exercised by a live run of this skill, so treat a first call as a test: if it is gated or empty,
  drop to the next rung rather than retrying. Fall through and say so in `dataWarning`; never
  block the run.

## Workflow

Work in order. Scale research depth to the request; keep the user informed as you go.

> **ALWAYS pull fresh data — every run, regardless of prior usage.** Treat every invocation as a
> cold start. Re-run every screener call, re-pull every bar series, re-fetch every financial, and
> re-run the web research **this run**. **Never reuse** a prior run's screener rows, sweep JSON,
> RS values, grades, or an already-filled `CONFIG` — not from earlier in this conversation, not
> from memory, not from a saved output file. Sector leadership rotates and prices go stale within
> minutes during market hours, so a carried-over number can be silently wrong. **A re-check is a
> full re-run** ("run it again", "is that still true?") — never patch one figure into an old
> report. Stamp `generatedAt`, `dataProvenance` and every `sourceMap[].pulled` with the actual
> pull time of *this* run; if a connector hands back a stale or cached snapshot, refetch and, if
> it is still stale, flag it in `dataWarning`.

### 1 — Set the scope
Defaults, applied without asking when the user just said "recommend stocks":
**all ~20 TradingView sectors · top 10 performers each · ranked on 6-month performance ·
grade cut 4.5 of 7 · overall list of 10 · US primary listings.**
Confirm only what the user actually scoped — a theme ("AI", "energy"), a subset of sectors, a
different ranking window ("this year"), a different cut, or their own watchlist. Record whatever
you changed in `CONFIG.sweep.note` so the report says what was swept.

### 2 — Assess market direction (M) — first, and it gates everything
Per `tradingview-sector-sweep.md` Step 0: pull SPY/QQQ daily bars, count distribution days,
check the 50/200-day, cross-check with a web search. Classify **Confirmed uptrend / Under
pressure / Correction** and set `CONFIG.market.mGrade` to `pass` / `partial` / `fail`.
M is graded **once** for the whole market and added to every row's total, so a correction costs
every name a full point and the 4.5 cut correctly gets harder to clear. **Do not loosen the cut
to compensate** — state the market status prominently, switch to higher-risk framing (tighter
3% stops, "bases to watch for the next follow-through day"), and let the lists come out short.
Also record **SPY's performance over the sweep window** — it is the benchmark for every RS figure.

### 3 — Sweep every sector for its top 10 performers (TradingView)
One `run_screener` call per sector, sorted on the ranking window, filtered to US primary
listings with the method's price and liquidity floors. The exact verified call shape — and the
traps that produce wrong answers (`analyze_sector_tool` does not rank by performance;
`average_volume_50d_calc` is silently ignored; OTC tickers poison the ranking without an
`exchange` filter) — are in `tradingview-sector-sweep.md` Step 2. **Always read
`ignored_filters` in each response.**

### 4 — Triage the sweep down (`scripts/sector_screen.py`)
Feed every screener row into the script exactly as it came back — never retype numbers. It
computes % off the 52-week high, RS vs SPY, position vs the 50/200-day EMA, dollar volume, the
**sector ranking**, and a per-name triage verdict against the method's hard disqualifiers (cheap,
illiquid, >25% below the 52-week high, lagging SPY, below the 200-day). Its `grade_queue` is the
list to grade. **Report the funnel** in `CONFIG.sweep` — swept, pulled, triaged, graded — so the
reader can see what was dropped rather than reading the sweep as full coverage.

### 5 — Grade every survivor with `can-slim-grader`
Run the sister skill on each name in the grade queue (or apply its rubric inline if it isn't
installed). Per ticker that is ~five TradingView calls plus `scripts/relative_strength.py`;
`tradingview-sector-sweep.md` Step 4 lists them, along with the two TradingView traps that
misgrade a letter (its `eps` is GAAP — grade **C** on the street figure from
`get_earnings_history`; and TTM growth breaks across a spin-off — use per-period `yoy_pct`).

**Grades follow their evidence.** If the actual you print concedes a miss ("just under 25%",
"hasn't cleared the high"), the letter **cannot be pass** — call it partial. Where a threshold
says *each* ("EPS up **each** of 3 years at >=25%"), every period must clear it. Magnitude of a
beat, backlog, guidance or a big volume day are colour for the `reason`, never grounds to promote
a letter. **Never leave a letter ungraded** — the dashboard's self-audit flags it.

**A pivot needs both a sound base and new-high ground.** A candidate pivot more than ~10% below
the 52-week high is not a pivot; a strong-earnings name with no valid pivot is a **WATCH** with
"None now" plus the condition that would create an entry. Record `high52` on the pick so the
dashboard can check any buy point you name.

When a candidate needs a deeper individual dive, delegate — see "Delegating for deeper
financials" below.

### 6 — Build the two recommendation lists
Put **every fully graded name** in `CONFIG.picks[]` with its sector, sector rank, six letter
grades and verdict. The dashboard derives both lists — **do not hand-build them**:

1. **Sector leaders** — every pick at or above `CONFIG.gradeThreshold` (**4.5 of 7**), grouped by
   sector, best sector first. A sector with no qualifier is a finding about that sector: record
   it in `CONFIG.excluded`, don't drop the cut to fill it.
2. **Overall top N** — the `CONFIG.topCount` (default 10) highest grades market-wide, ties broken
   by RS then proximity to the 52-week high. No sector cap applies, so this list may concentrate
   in one or two leading groups; the dashboard badges the overlap with list 1.

**Both lists only ever hold names at or above the cut.** A name below 4.5 is not a recommendation
just because everything else scored worse, so it never appears in either list — it stays in the
"Every name graded" appendix with its scorecard.

**A sector that produced no qualifier still shows its top 5.** Paste `sector_screen.py`'s `top5`
into `CONFIG.sectors[].top5` for every sector; the dashboard renders it **only** where that
sector's `qualified` count is 0, under an amber "ungraded - not recommendations" banner, with each
row marked whether it even cleared the hard filters. This keeps a sector from being a blank line
in the report without implying the names are picks - they carry no scorecard, no verdict and no
buy point. Set `--fallback N` on the script to surface a different count.

**When nothing clears the cut, list 2 renders as EMPTY with an enumerated "why"** rather than
ranking the least-weak names. The dashboard derives those reasons from the grades themselves —
the M grade and what it costs every row, which letters failed and how often across the graded
pool, the best score actually reached and how far short it fell, how many names the hard filters
removed before grading, and that every sector came back empty. Add anything run-specific the
grades cannot show on their own (an earnings season mid-flight, a connector that was gated for
one letter) via `CONFIG.noQualifierReasons` — the page appends it. Write `CONFIG.shortfall` too;
it carries the same message on list 1.

**Never lower the threshold to lengthen a list.** If only three names reach 4.5, the answer is
three names plus `CONFIG.shortfall` saying what the rest failed on. If none do, the answer is two
empty lists and the reasons. Padding a screen with weak names is the exact failure the method
exists to prevent — and so is quietly re-baselining the cut so that something shows up.

**The grade is not the verdict.** A name can clear 4.5 on C, A and L and still be a WATCH because
N fails. Give every pick a `verdict` (BUY-RANGE / WATCH / AVOID).

**Each pick's `reason` renders as a full-width row under its stats**, not as a column, so it has
the whole table to wrap into — write it as prose of whatever length the evidence needs, and don't
abbreviate to fit. There is no "% off 52-week high" column: state that distance in words inside
the reason (the leadership map still plots it on its y-axis, and the self-audit still checks any
pivot against `high52`).

**The "why" must be expressed *only* in CAN SLIM concepts and rules** — the seven letters; bases /
pivots / handles and the base type; relative strength; new highs off a sound base; volume,
accumulation/distribution; leader-vs-laggard and group leadership; institutional sponsorship;
market direction (distribution days / follow-through). **Do not justify a pick with anything
outside the method** — no generic macro opinions, no analyst price targets, no "it's a good
company," no personal vibe. If a name cannot be defended in CAN SLIM terms, it does not belong on
either list. Keep each reason concrete (cite the actual EPS/sales %, the RS figure, the base and
pivot).

### 7 — Deliver: a white A4 PDF by default (the dark HTML on request)
1. **Fill the report.** Copy `assets/dashboard_template.html` to
   `canslim-recommendations-<date>.html` and fill the `CONFIG` object — the *only* thing you
   edit; the page renders itself. Populate `market` (verdict + tone + **`mGrade`** + implication),
   `sweep` (the funnel — its `graded` count must equal `picks.length`), `sectors[]` (the sector
   ranking from `sector_screen.py`), `picks[]` (every graded name), `gradeThreshold` /
   `topCount`, and — always — **`dataProvenance`** and **`sourceMap[]`**. Add `shortfall`,
   `noQualifierReasons`, `watch[]`, `speculative[]`, `excluded[]`, `rationale[]`,
   `portfolioNote`, `disclaimer`, `sources[]` and `dataWarning` when they apply.
2. **Check the self-audit banner.** The page audits its own CONFIG on render and prints a red
   "Report checks failed" banner for contradictions — an ungraded letter, a buy point with N
   failing, a pivot more than 10% below the 52-week high, a stop that isn't 7-8%, a verdict that
   disagrees with the grade, a `sweep.graded` count that doesn't match `picks[]`, missing
   provenance. **Never ship a report showing that banner** —
   fix the grade or fix the evidence, and do not delete the check. The PDF freezes whatever the
   page says, so verify before exporting.
3. **Render the PDF — this is the default deliverable.**
   `python scripts/html_to_pdf.py canslim-recommendations-<date>.html`
   (headless Chrome/Chromium/Edge → Playwright → WeasyPrint → wkhtmltopdf; it prints the engine
   used). The template declares `@page{size:A4 landscape; margin:15mm}` — A4 landscape because
   the pick tables are wide, and 15mm on every edge as the committed print inset. The script
   reads **both** the size and the margin out of that rule and passes them to whichever fallback
   engine it uses, so every engine produces the same page. The print stylesheet also **forces the
   white palette**, so the PDF comes out white even though the HTML file itself is dark. Hand over
   the PDF. If no PDF engine is available, say so and hand over the HTML instead — never block the
   run on the export.
4. **HTML on request only, and it is dark.** Give the `.html` when the user asks for the HTML, an
   interactive version, sortable columns, or the clickable per-ticker report modal — those flatten
   in the PDF. The template ships `<html data-theme="dark">`, so the HTML deliverable is dark on
   screen; the PDF is unaffected. Switch that attribute to `"light"` only if someone asks for a
   light HTML.
5. Keep the chat reply short: the market read, how many cleared 4.5 and from which sectors, the
   headline names, and why the count is what it is.

**Built-in visuals (auto-rendered from CONFIG, no extra work):**
- **Funnel tiles** — sectors swept → top performers pulled → cleared triage → fully graded →
  graded ≥ the cut. Built from `CONFIG.sweep` plus the picks.
- **Leadership map** — a scatter plotting every graded name by **RS (x)** vs **% off 52-week high
  (y, 0% at top)**, straight from each pick's `rs` and `offHigh`. Leaders cluster **top-right** in
  a shaded "buyable leaders" zone (RS ≥ 0, within ~8% of the high); names at or above the cut are
  drawn in the leader colour. Shows only when ≥ 2 picks have numeric `rs` + `offHigh`.
- **Sector sweep table** — the sector ranking behind the lists, from `CONFIG.sectors`.
- **No-qualifier fallback** — for each sector with zero qualifiers, its top 5 in the screener's own
  ranking, from `CONFIG.sectors[].top5`, banner-marked as ungraded and not recommendations.
- **Data sources & freshness table** — from `CONFIG.sourceMap`.
- **Acronym glossary** — the standard CAN SLIM + finance terms; extend via `CONFIG.glossary`.

**Per-ticker deep dive (clickable ticker → in-page report window):** give a pick a `reviewUrl`
and its ticker becomes a link that opens that report in a modal iframe. Save each
`can-slim-grader` (or `ibkr-review-ticker`) report next to the dashboard as
`reviews/<SYM>-canslim.html` and set `reviewUrl:"reviews/<SYM>-canslim.html"`. Because the modal
loads via an iframe, the review files must be **same-origin** with the dashboard (same folder,
served locally) — a full `https://` URL also works. Omit `reviewUrl` and the ticker is plain text.
These links are HTML-only; they flatten in the PDF.

**Data sources are not optional.** Every dashboard must carry `dataProvenance` (one line naming
which sources actually contributed and which letters came from where) **and** `sourceMap[]` (one
row per class of figure: what, source, pulled-at, note), plus `dataWarning` whenever any source
was gated, throttled or stale and the analysis leaned on a fallback. The page prints a red check
banner if either is missing.

**Scoring — pass/partial/fail, /7 total (incl. M):** grade each of C·A·N·S·L·I as `pass` (1.0),
`partial` (0.5) or `fail` (0), and grade **M once for the whole market** via
`CONFIG.market.mGrade`. The template renders the six per-stock letters plus a dashed **M cell**
(identical on every row) and a **/7 total**. M is scored once because market direction is a single
market-wide gate — it contributes equally to every name rather than being re-judged per row. This
is the sister skill's exact scale, which is what makes the **4.5 cut** portable between the two.

### As-of / historical mode (optional) — "run it as of <past date>"
If the user asks for the sweep **as of a past date** ("what did CAN SLIM flag in Jan 2023"),
switch to **point-in-time reconstruction**. This is a **best-effort historical view, NOT a
survivorship-bias-free backtest** — say so, and stamp the output as a reconstruction.

- **Pick the as-of date.** A bare month → its **last trading day** (e.g. "Jan 2023" →
  2023-01-31). Everything is computed as it would have looked at that date's close.
- **Still re-issue every call this run** (the fresh-data rule holds), but reconstruct as of the
  date. TradingView `get_ohlcv` and IBKR `get_price_history` always end *now*, so pull a long
  series and **use only bars dated ≤ the as-of date**; Massive Market Data is the clean path here
  because its Custom Bars take an explicit range (`/v2/aggs/ticker/{T}/range/1/day/{from}/{to}`
  with `to` = the as-of date), giving native point-in-time OHLC. Live snapshots and
  `get_quotes_batch` are **live-only — do not use them for history**; take price, the 52-week
  high and % off-high from the in-window bars. Pass the cutoff to `scripts/relative_strength.py`
  via `--asof <cutoff>` so RS / base / breakout use only in-window bars.
- **M, N, S, L** reconstruct cleanly from the truncated SPY/QQQ + candidate bars.
- **C, A, I (avoid look-ahead):** use only the most recent quarter/annual **reported ON OR BEFORE
  the as-of date** — e.g. for Jan 2023 that is **Q3 2022** (filed Oct–Nov 2022), **not** Q4 2022
  (filed Feb 2023). Confirm the filing date is ≤ the as-of date before using a figure; if you
  cannot confirm it, drop to "n/a" rather than risk look-ahead.
- **The screener is the real limit:** `run_screener` ranks on **today's** performance columns, so
  the sector sweep itself cannot be reconstructed natively — and screening only today's listed
  tickers drops names that later delisted or merged (**survivorship bias**). Prefer a universe
  the user supplies for the date, or a fixed broad list, and **flag** that sector membership and
  leadership are present-day.
- **Output:** set `CONFIG.asOf` to the date (renders an "AS OF … - historical reconstruction"
  badge), set `generatedAt` to the as-of date, and make `dataWarning` state the biases plainly —
  **survivorship**, **look-ahead**, that the sector ranking is present-day, and that prices are
  bar-derived. Keep the standard "not advice / no orders" disclaimer.

## Delegating for deeper financials & required companion skills
This skill screens breadth; for depth on a single name, hand off to a specialized skill rather
than doing a shallow web dig:

- **`can-slim-grader`** — **required**: it produces the per-ticker grade this skill's lists are
  built from. Its report also makes a good `reviewUrl` target for the clickable tickers.
- **`ibkr-review-ticker`** — the fullest single-stock dashboard (fundamentals vs. peers,
  valuation, options/volatility positioning, probability outlook). Invoke it for a candidate that
  needs an individual financial review before it earns a spot on either list.
- **`securities-filings-lookup`** — the official filing **PDFs** (10-K / 10-Q / 20-F / annual
  reports) from the right regulator. Use it for the ground-truth statements behind **C**/**A**,
  and for 13F/Form 4 data for **I**.

**If a companion skill you need is not installed**, do not silently fall back — tell the user it's
missing and prompt them to install it from its GitHub repo, then continue with the best available
source (the connector ladder in `tradingview-sector-sweep.md`, or web search):
- `can-slim-grader` → **https://github.com/thewongdirection/can-slim-grader**
- `ibkr-review-ticker` → **https://github.com/thewongdirection/ibkr-review-ticker**
- `securities-filings-lookup` → **https://github.com/thewongdirection/securities-filings-lookup**

(Example prompt: *"I'd normally grade each candidate with the `can-slim-grader` skill so the 4.5
cut matches its scale, but it isn't installed. You can add it from
https://github.com/thewongdirection/can-slim-grader — install it and I'll re-run. For now I'll
apply the same rubric inline from the shared methodology."*)

## Guardrails
- **Read-only, market data only.** TradingView: `search_symbols`, `run_screener`, `get_ohlcv`,
  `get_symbol_data`, `get_quotes_batch`, `get_technicals`, `get_financials`,
  `get_financial_history`, `get_earnings_history`, `get_news`, and the user's own watchlists if
  they ask. **Never** call the portfolio-write or delete tools. IBKR (fallback):
  `search_contracts`, `get_price_snapshot`, `get_price_history`, `search_investment_topics`,
  `get_theme_details`, `get_company_themes`, and `get_watchlists`/`get_watchlist` on request —
  **never** order tools or account tools (balances, positions, orders, trades, summary, PA
  analytics), even if asked mid-run. Trading and account access are out of scope.
- **Never** display or store contract IDs, expiration IDs, account numbers, or any account-bound
  data — the report may be shared. Present stocks by symbol/name only.
- **No personalized advice or directives.** Give the factual CAN SLIM setup and let the user
  decide. If asked "should I buy X", present the scorecard and risks, not a yes/no.
- Timestamp everything; flag approximations (RS is a proxy — window performance vs SPY, not a
  full-market 1-99 rating; fundamentals may lag). Obey copyright in research (paraphrase; short
  quotes only).
- The methodology is a probability edge, not a guarantee — always pair a recommendation with its
  exit rule.

## Files in this skill
- `references/canslim-methodology.md` — the full CAN SLIM rules, thresholds, base patterns, sell
  rules, money management, and mistake list. **Shared verbatim with `can-slim-grader`** — any
  material change to the method has to land on both sides. Read before screening.
- `references/tradingview-sector-sweep.md` — **the primary data guide**: the verified TradingView
  call shapes, the sector taxonomy, the triage filters, the grader hand-off, and how the two
  lists are built. Read before gathering data.
- `references/ibkr-data-guide.md` — the fallback path (IBKR / Massive / FMP) plus the shared
  fundamental source ladder.
- `scripts/sector_screen.py` — turns the per-sector `run_screener` rows into % off the 52-week
  high, RS vs SPY, EMA position, dollar volume, the sector ranking and the triage verdict, and
  emits the grade queue plus each sector's `top5` fallback. Pure standard library.
- `scripts/relative_strength.py` — computes the RS proxy, % off 52-week high, base depth/length
  and breakout volume from OHLCV bars (TradingView / IBKR / Polygon shapes). Shared with
  `can-slim-grader`. Feed it the collected bars rather than eyeballing charts.
- `scripts/html_to_pdf.py` — renders the filled dashboard to the default PDF deliverable
  (Chrome → Playwright → WeasyPrint → wkhtmltopdf; honours the template's `@page` size). Shared
  with `can-slim-grader`.
- `assets/dashboard_template.html` — the report (full behavior in Step 7): a self-contained,
  print-optimized, pure-ASCII dashboard that is **dark on screen and white in print** (A4
  landscape, 15mm margins),
  driven by a `CONFIG` object. Derives both recommendation lists from one `picks[]` array (both
  gated at the grade cut, with an enumerated empty state when nothing clears it), self-audits its
  own CONFIG, and renders the funnel tiles, leadership map, sector sweep table, data-sources
  table and glossary automatically.
