# CAN SLIM Sector Recommendations - portable skill bundle

This is a **complete, self-contained copy** of the `can-slim-recommend` skill, packaged so it can
be used with an assistant other than Claude Code. Everything the skill is - its workflow, its
methodology reference, its data guides, its Python helpers and its self-auditing report template -
is inlined verbatim below.

Source of truth: <https://github.com/thewongdirection/can-slim-recommend>

---

## What the skill does

It sweeps every market sector for its top performers, grades each one against the **CAN SLIM**
growth-investing methodology, and returns **two ranked recommendation lists** as a report:

1. **Sector leaders** - every top-of-sector performer scoring **4.5 or better out of 7**, grouped
   by sector.
2. **Overall top 10** - the highest-graded names market-wide, no sector cap.

Both lists hold only names at or above the cut. When nothing clears it, the lists come out empty
with an enumerated, evidence-based "why" - never padded, never with the bar quietly lowered.

---

## How to use this file with another assistant

**Gemini, ChatGPT, or any long-context chat model**

1. Upload this file (or paste it) at the start of a conversation.
2. Say: *"Follow the workflow in this skill. Run it and produce the report."*
3. The model reads `SKILL.md` as its instructions and the rest as its references.

**A custom assistant (Gemini Gem, Custom GPT, an agent framework)**

Use the accompanying `.zip` instead and upload the files individually - `SKILL.md` as the system
instruction, the rest as knowledge files. That keeps each reference retrievable on its own rather
than competing for attention inside one long document.

**Another Claude Code / agent-with-a-filesystem install**

Unzip into the skills directory and it works as a native skill. Reconstitute the layout from the
file manifest below if you only have this Markdown file.

---

## IMPORTANT: what this skill needs from its host

The skill is **not** self-powering. It needs three capabilities, and its output is only as good as
what it is given. Read this before running it anywhere.

### 1. Live market data (required)

The reference guides describe a specific **TradingView MCP connector**, because that is what the
skill was built and verified against. **Any other assistant almost certainly does not have it.**
That is fine - the connector is an implementation detail. What the workflow actually needs is:

| Step | What it needs | Any source that provides it |
|---|---|---|
| Sector sweep | Top N stocks per sector ranked on trailing 6-month price performance, with price, market cap, average volume, 52-week high/low, EMA position | A stock screener API (FMP, EODHD, Polygon, Finnhub, Alpha Vantage, Norgate, a broker API), or a screener the user runs and pastes in |
| Triage + N/S/L | Daily OHLCV bars, ~90-300 sessions per candidate | Any bars/candles endpoint |
| C (current quarter) | Quarterly revenue and EPS with year-over-year change, 6+ quarters | Any fundamentals endpoint, or SEC EDGAR / the company's filings |
| A (annual) | Annual EPS for 3-4 fiscal years, ROE, debt/equity | Same |
| I (sponsorship) | Institutional ownership **trend** across quarters | SEC 13F filings, or a data vendor. Frequently unavailable - see below |
| M (market) | Daily bars for a broad index ETF and a growth index ETF | Any bars endpoint |

**Substituting a source is expected and legitimate.** What is *not* legitimate is inventing the
numbers. If a datum cannot be obtained, the skill's own rules apply: attempt it, report the
failure in the report, and grade the letter on what remains.

### 2. A way to run Python (recommended, not required)

`scripts/sector_screen.py` and `scripts/relative_strength.py` are plain Python 3 with **no
third-party dependencies** - they do arithmetic over data you supply as JSON. An assistant with a
code interpreter should run them; without one, the model must do the same arithmetic by hand,
which is slower and more error-prone but produces the same result. Read the scripts: the formulas
are the specification.

`scripts/html_to_pdf.py` needs a browser or a PDF library on the machine. Without one, hand over
the HTML - the report is complete either way.

### 3. A way to save and render an HTML file (for the report)

The deliverable is `assets/dashboard_template.html` with its `CONFIG` object filled in. It is a
single self-contained file with no external assets. An assistant that can write files produces it
directly; one that cannot should emit the filled `CONFIG` object and tell the user to paste it
into the template.

---

## Non-negotiable rules, wherever this runs

These are the parts most likely to be lost in translation to another model. They are what make the
output trustworthy rather than merely plausible.

1. **Never invent a number.** Every figure in the report traces to a source that was actually
   called in that run. If a source fails, say so in the report - the template has a dedicated
   freshness block and refuses to render a clean report without it.
2. **Always attempt fresh data, every run.** Never start from a previous run's screener rows,
   grades, or filled report. If a fresh pull fails, retry, try a fallback source, and only then
   reuse older data - and only where the older figure is still applicable. A quarterly financial
   from last week usually is; a price, 52-week high, RS reading or distribution-day count usually
   is not, because those move and a stale one changes grades.
3. **Always date the data.** Two separate dates: when the report was built, and what date the
   market data is as of. Per source: when the call was made, and what date the figure is from.
4. **Never lower the bar to fill a list.** 4.5 out of 7 is the cut. If three names clear it, the
   list has three names. If none do, both lists are empty and the report enumerates why. A short
   list in a weak market is the correct answer, not a failure.
5. **Grade M once, market-wide,** and apply it to every row. A weak market lowers every score at
   once - that is the point of the letter.
6. **Every rationale in CAN SLIM terms only.** The seven letters, bases and pivots, relative
   strength, new highs, volume and accumulation, leadership, sponsorship, market direction. No
   analyst price targets, no macro commentary, no valuation arguments - those are other methods.
7. **Every pick carries its exit.** A buy point only where a valid pivot exists, and the 7-8%
   loss-cutting stop, always.
8. **Read-only, and never advice.** This is informational decision support. It places no orders,
   touches no account data, and gives no personalized buy/sell directives. Keep that framing in
   whatever the model produces.

---

## A note on what the grades mean

CAN SLIM is a probability edge drawn from the traits of past big winners - not a guarantee, not a
valuation model, and not a forecast. A 5.0 out of 7 means a name matches the historical pattern on
five of seven dimensions **as of the data date**, nothing more. Markets carry risk of loss. This
bundle is an independent implementation of a publicly known investing framework and reproduces no
third-party copyrighted text.

---

## File manifest

To reconstitute the skill as a directory, create these paths with the contents of the
correspondingly-titled sections below:

```
can-slim-recommend/
  SKILL.md
  README.md
  references/canslim-methodology.md
  references/tradingview-sector-sweep.md
  references/ibkr-data-guide.md
  scripts/sector_screen.py
  scripts/relative_strength.py
  scripts/build_report.py
  scripts/html_to_pdf.py
  assets/dashboard_template.html
```

---


## `SKILL.md`

The skill itself: when it activates and the full workflow, step by step.

````md
---
name: can-slim-recommend
description: >-
  Sweep the whole market sector by sector with TradingView and return TWO ranked recommendation
  lists graded with the CAN SLIM growth-investing methodology: (1) every sector's
  leaders scoring 4.5 or better out of 7, and (2) the overall top 10 market-wide. Use whenever the
  user wants stock ideas, picks, or a screen - "recommend some stocks", "what should I buy", "find
  me growth stocks", "screen for CAN SLIM stocks", "best names in each sector", "top sector
  performers", "what to add to my watchlist", "build me a shortlist" - or a themed/scoped set
  ("recommend AI stocks", "just the top 5 sectors") - even if they don't name CAN SLIM. This is the
  LIST/screener lens; to judge ONE named ticker (a C-A-N-S-L-I-M scorecard with a
  BUY-RANGE/WATCH/AVOID verdict) use `can-slim-grader`. Output: a white-themed A4 PDF by default
  (the dark interactive HTML on request). Analysis and decision support only - never personalized
  investment advice and never trading.
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
  settles **A** for one call, which is what re-cuts the ceiling and eliminates names before the
  expensive `fq`/`fy` history — see step 4a. Run it on **every** triage survivor: it is the
  cheapest letter that can eliminate, and skipping it is what forces a run to guess which names
  are worth grading.
- **`can-slim-grader`** — the sister skill that grades each candidate. If it isn't installed,
  say so, prompt the user to add it from **https://github.com/thewongdirection/can-slim-grader**,
  and apply its rubric inline from the shared methodology rather than inventing a different scale.
- **Institutional sponsorship (I)** is the one letter TradingView cannot answer. Run
  `scripts/institutional_cache.py` ONCE PER QUARTER (after each 13F deadline: mid-Feb/May/Aug/Nov)
  to build `data/i-cache.json` from SEC Form 13F, then pass it to every run with `--known`. It
  falls open to `scripts/accumulation.py`, which reads institutional buying pressure from the
  up/down volume footprint — a proxy, and its reason strings say so. Only if BOTH are unavailable
  does I fall back to a blanket `--i-grade partial`. Record which source graded it in
  `CONFIG.sourceMap`; the cache carries `detail[ticker].source` per name.
- **Web search** for the market read and the "new" in N.
- **Fallbacks — unverified, use only when the proven path fails:** IBKR MCP, Massive Market Data,
  FMP (commonly plan-gated) — the Tier 2 table in `tradingview-sector-sweep.md`. None has been
  exercised by a live run of this skill, so treat a first call as a test: if it is gated or empty,
  drop to the next rung rather than retrying. Fall through and say so in `dataWarning`; never
  block the run.

## Workflow

Work in order. Scale research depth to the request; keep the user informed as you go.

### 0 — Check this copy of the skill is current, BEFORE anything else

**Run this first, every invocation, before the market read, before a single data call:**

```
python scripts/check_for_updates.py --update
```

A stale checkout is the one failure mode that leaves no trace: it produces a confident,
well-formatted report built by superseded rules, and nothing in the output says so. The check
costs one `git fetch`.

**What an update can and cannot fix mid-run** — the script reports two groups for this reason,
and the distinction has to be passed on honestly rather than collapsed into "it updated":

| | when it is read | effect of updating mid-run |
|---|---|---|
| `scripts/`, `assets/` | from disk, each time they run | **takes effect immediately** — the new `sector_screen.py` and the new template are what actually execute this run |
| `SKILL.md`, `references/` | into context when the skill is invoked | **does NOT take effect this run** — these instructions were loaded before step 0 ran |

So when the script reports changes under *"Instructions that changed"*, the update landed on
disk but this run is still following the previous instructions. **Say so, and offer to re-invoke
the skill** so the new ones are loaded. Never imply the run picked them up.

**The check never blocks a run.** No git, no network, a private remote, a zip export with no
repo at all — the script says what it could not verify and exits 0. Continue on the copy you
have and record it: put the reason in `CONFIG.dataWarning` and a `freshness.failures` entry with
`item: "skill version"`, exactly as you would for a data source that could not be reached. An
unverifiable version is a caveat on the report, not a reason to refuse one.

**It also never pulls over your work.** `--update` fast-forwards only on a clean tree that has
not diverged; against uncommitted changes or a diverged branch it refuses, explains, and leaves
the decision to the user. If it refuses, do not work around it — report it and carry on.

> **ALWAYS ATTEMPT FRESH DATA — every run, every source, regardless of prior usage.** Treat every
> invocation as a cold start. Re-run every screener call, re-pull every bar series, re-fetch every
> financial, and re-run the web research **this run**. Never *start* from a prior run's screener
> rows, sweep JSON, RS values, grades, or an already-filled `CONFIG` — not from earlier in this
> conversation, not from memory, not from a saved output file. Sector leadership rotates and prices
> go stale within minutes during market hours, so a carried-over number can be silently wrong.
> **A re-check is a full re-run** ("run it again", "is that still true?") — never patch one figure
> into an old report.

#### When a fresh pull fails

The attempt is mandatory; success is not always available. A connector can be down, gated,
throttled, or hand back nothing. When that happens, **report it — never paper over it, and never
let it silently become a fresh-looking number.** In order:

1. **Retry once**, and try the documented fallback source for that datum
   (`references/tradingview-sector-sweep.md` step 6, then `references/ibkr-data-guide.md`).
2. **If a fallback source works, that row is still `fresh`** — it just names a different source.
3. **If nothing fresh can be had, you may reuse previously pulled data — but only if it is still
   applicable** to what is being asked, and only after the attempt failed. A quarterly financial
   from last week is usually still applicable; a price, a 52-week high, an RS reading or a
   distribution-day count from a previous session usually is **not** — those move, and a stale one
   changes grades. When the older figure is not applicable, drop the datum, grade the letter on
   what remains, and say so, rather than reusing something that is no longer true.
4. **Record it in `CONFIG.freshness.failures`** — one entry per source, each naming the `item`,
   the `source` attempted, the `error` (why it failed), the `fallback` used, and the
   **`fallbackDate`** (the date the reused data is from). Set `freshness.allFresh: false`.
5. **Mark the row** in `sourceMap[]` as `status:"reused"` (older data used) or
   `status:"unavailable"` (no data at all), with its `asOf` date.
6. **Say it in `dataWarning`** too, in plain language, when it changes how the report should be
   read — a capped letter, a missing grade, a gap worked around.

The template enforces all of this: the page renders an amber callout enumerating every failure
with its fallback date, and the self-audit **refuses the report** if `freshness` is missing, if a
failure has no `error`, if reused data has no date, or if a `reused`/`unavailable` row in the
sources table has no matching entry in `freshness.failures`. A silent reuse cannot ship.

#### Always date the data

Two dates, always, and never merged into one string:
- **`generatedAt`** — when the report was built.
- **`dataDate`** — **what date the market data is as of** (the newest bar the run actually saw,
  e.g. `"2026-08-21 close"`). Required; the self-audit rejects a report without it. A run on a
  Sunday reads Friday's close, and the reader has to be able to tell.

Per source, `sourceMap[]` carries both `pulled` (when *this run* made the call) and `asOf` (what
date the figure underneath is from) — a source pulled today can still hand back last week's
number. Every row needs `pulled`; a reused row also needs `asOf`. Also set
`freshness.attemptedAt` to when the run tried its sources, so "fresh" has a timestamp behind it.

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

Pass the run's **M grade** and the best **I** any name can reach, because both are known before a
single name is graded and both bound every row:

```
python scripts/sector_screen.py sweep.json --m-grade partial --i-grade partial --md
```

### 4a — The ceiling: which names MUST be graded
You cannot know a name clears 4.5 until you grade it — the score *is* the output of grading. So
the coverage rule runs the other way, on the **ceiling**: the highest score a name could still
reach. `sector_screen.py` computes it for every triage survivor from what is already known —

| letter | bounded by | cap |
|---|---|---|
| **M** | graded once market-wide, before any name | the run's actual M |
| **I** | routinely unsourceable; never guessed | `--i-grade` (usually partial) |
| **N** | % below the 52-week high | >10% below → partial (no pivot); >20% → fail |
| **S** | relative volume | <1.0x → partial; <0.8x → fail (drying up, not accumulating) |
| **L** | sector rank from this sweep | bottom-half sector → partial (leader of a laggard group) |
| **C**, **A** | not yet pulled | assumed **pass** until a real grade says otherwise |

> **THE RULE: grade every name whose ceiling reaches `gradeThreshold`. No exceptions, and never
> a judgment call about which names "look promising".** Because every entry above is an *upper*
> bound, a ceiling below the cut means no combination of unseen fundamentals could get that name
> there — it is eliminated by arithmetic. A ceiling at or above the cut means the opposite: the
> name might qualify, so not grading it could hide a qualifier. `CONFIG.sweep.mustGrade` carries
> that count and **the dashboard's self-audit refuses a report that graded fewer**.

**Two stages, because the A-screen is where the pruning actually happens.** With M and I both at
partial the stage-1 floor is exactly 4.5 (1+1+0.5+0.5+0.5+0.5+0.5), so the screener alone
eliminates almost nobody — that is arithmetic, not a weak filter. Spend one `get_financials` call
per survivor to settle **A**, write the results to a JSON map, and re-cut the ceiling:

```
python scripts/sector_screen.py sweep.json --m-grade partial --i-grade partial \
       --known a-screen.json --md          # {"NASDAQ:OKTA": {"A": "fail"}, ...}
```

Everything that now falls below the cut is eliminated **without spending the C call on it**.
Grade the rest in the order the queue gives them (highest ceiling first), so an interrupted run
has still found the strongest qualifiers.

**If the must-grade count is more than the run can afford, tighten the funnel — never the
coverage.** Raise `--threshold`, or tighten triage (`--max-off-high 15`, a higher
`--min-dollar-vol`). Both shrink the must-grade set *provably* and both are recorded in
`CONFIG.sweep`. Silently grading a subset is the one thing that is not allowed, because it makes
the two lists a sample while the report reads as a sweep.

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
"Every name graded" appendix with its scorecard. **The report says this in its own words**: the
dashboard renders a note under list 1 stating that only names scoring >=4.5/7 are listed, and —
from `CONFIG.sweep.mustGrade` / `eliminatedByCeiling` — that every survivor which could still have
reached the cut was graded. Fill both fields from `sector_screen.py`'s `must_grade` and
`eliminated_by_ceiling` or that sentence cannot be made.

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

### 7 — Deliver: PDF by default, HTML on request (`--format` decides)
1. **Fill the report.** Copy `assets/dashboard_template.html` to
   `canslim-recommendations-{date}.html` and fill the `CONFIG` object — the *only* thing you
   edit; the page renders itself. Populate `market` (verdict + tone + **`mGrade`** + implication),
   `sweep` (the funnel — its `graded` count must equal `picks.length`), `sectors[]` (the sector
   ranking from `sector_screen.py`), `picks[]` (every graded name), `gradeThreshold` /
   `topCount`, and — always — **`dataDate`**, **`freshness`**, **`dataProvenance`** and
   **`sourceMap[]`** (every row with `pulled`, `asOf` and `status`). Add `shortfall`,
   `noQualifierReasons`, `watch[]`, `speculative[]`, `excluded[]`, `rationale[]`,
   `portfolioNote`, `disclaimer`, `sources[]` and `dataWarning` when they apply.
2. **Check the self-audit banner.** The page audits its own CONFIG on render and prints a red
   "Report checks failed" banner for contradictions — an ungraded letter, a buy point with N
   failing, a pivot more than 10% below the 52-week high, a stop that isn't 7-8%, a verdict that
   disagrees with the grade, a `sweep.graded` count that doesn't match `picks[]`, missing
   provenance, a missing `dataDate`, an undated source row, or reused data the `freshness` block
   does not declare. **Never ship a report showing that banner** —
   fix the grade or fix the evidence, and do not delete the check. The PDF freezes whatever the
   page says, so verify before exporting.
3. **Build the deliverable — one command, and the format is an argument.**
   ```
   python scripts/build_report.py canslim-recommendations-{date}.html [--format pdf|html|both]
   ```
   **`--format` defaults to `pdf`**, so plain `build_report.py {file}` is the default run. Pass
   `--format html` when the user asks for HTML, `--format both` when they want each. Read the
   user's own words: *"as a PDF"*, *"send me the HTML"*, *"both"* — and if they said nothing about
   format, produce the PDF. Add `--theme light` only if someone wants a light HTML; the PDF is
   white regardless.

   What the script does for you, so none of it depends on remembering:
   - **Enforces the self-audit.** It renders the page headlessly, reads the banner, and
     **refuses to emit anything** while the report is failing its own checks (exit 1, listing
     each failure). `--no-check` overrides it for inspection only. With no browser available the
     check is skipped *with a warning* rather than silently passing.
   - **Runs the same engine chain** as `html_to_pdf.py` (Chrome/Chromium/Edge → Playwright →
     WeasyPrint → wkhtmltopdf) and names the one it used.
   - **Never blocks the run on the export.** If `--format pdf` was asked for and no engine
     exists, it writes the HTML instead and says why — hand that over and repeat the reason.

   The template declares `@page{size:A4 landscape; margin:15mm}` — A4 landscape because the pick
   tables are wide, 15mm on every edge as the committed print inset — and the print stylesheet
   forces the white palette, so the PDF is white even though the HTML is dark. `html_to_pdf.py`
   remains usable directly if you only want the PDF and nothing else.
4. **What differs between the two formats.** Only presentation: the same filled `CONFIG` drives
   both. The **HTML** is dark, has sortable columns and clickable tickers that open each name's
   per-ticker report in a modal — all of which flatten in print. The **PDF** is white, A4
   landscape, paginated. Neither contains a figure the other does not.
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
- **Data date stamp** — `CONFIG.dataDate` beside `generatedAt`, at the top of the page.
- **Freshness banner** — from `CONFIG.freshness`: a green line when every source came back fresh,
  or an amber callout enumerating each failure, its cause, what was used instead and that
  fallback's date.
- **Data sources & freshness table** — from `CONFIG.sourceMap`: what, source, pulled, data-as-of,
  a FRESH / REUSED / UNAVAILABLE status chip, and the note.
- **Acronym glossary** — the standard CAN SLIM + finance terms; extend via `CONFIG.glossary`.

**Per-ticker deep dive (clickable ticker → in-page report window):** give a pick a `reviewUrl`
and its ticker becomes a link that opens that report in a modal iframe. Save each
`can-slim-grader` (or `ibkr-review-ticker`) report next to the dashboard as
`reviews/{SYM}-canslim.html` and set `reviewUrl:"reviews/{SYM}-canslim.html"`. Because the modal
loads via an iframe, the review files must be **same-origin** with the dashboard (same folder,
served locally) — a full `https://` URL also works. Omit `reviewUrl` and the ticker is plain text.
These links are HTML-only; they flatten in the PDF.

**Data sources and dates are not optional.** Every dashboard must carry `dataProvenance` (one line
naming which sources actually contributed and which letters came from where), `sourceMap[]` (one
row per class of figure: what, source, `pulled`, `asOf`, `status`, note), `dataDate` (the date the
market data is as of) and `freshness` (whether this run's fresh pull succeeded, and what failed if
it did not) — plus `dataWarning` whenever a gap changes how the report should be read. The page
prints a red check banner if any of them is missing, and refuses a report whose sources table
admits reused data that `freshness.failures` does not declare.

**Scoring — pass/partial/fail, /7 total (incl. M):** grade each of C·A·N·S·L·I as `pass` (1.0),
`partial` (0.5) or `fail` (0), and grade **M once for the whole market** via
`CONFIG.market.mGrade`. The template renders the six per-stock letters plus a dashed **M cell**
(identical on every row) and a **/7 total**. M is scored once because market direction is a single
market-wide gate — it contributes equally to every name rather than being re-judged per row. This
is the sister skill's exact scale, which is what makes the **4.5 cut** portable between the two.

### As-of / historical mode (optional) — "run it as of {past date}"
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
  via `--asof {cutoff}` so RS / base / breakout use only in-window bars.
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
  rules, money management, and mistake list. **Shared with `can-slim-grader`** — any material
  change to the method has to land on both sides. Read before screening.
  **Not currently byte-identical, and this copy is the newer one:** it carries the
  *"pass / partial / fail grading rubric"* section (the per-letter PASS/PARTIAL/FAIL anchors and
  the total read bands), which the sister's copy does not yet have. The port owed therefore runs
  *from here to the sister*, not the other way. **There is exactly one scale in this skill:**
  seven letters, each pass 1.0 / partial 0.5 / fail 0, totalling out of **7**. Any other scale
  you may meet in an older copy of either skill, or in the sister's parity note, is dead — do not
  reintroduce it, and do not grade a letter on anything but pass / partial / fail.
- `references/tradingview-sector-sweep.md` — **the primary data guide**: the verified TradingView
  call shapes, the sector taxonomy, the triage filters, the grader hand-off, and how the two
  lists are built. Read before gathering data.
- `references/ibkr-data-guide.md` — the fallback path (IBKR / Massive / FMP) plus the shared
  fundamental source ladder.
- `scripts/check_for_updates.py` — step 0. Compares this checkout against its remote and splits
  what changed into code (takes effect this run) and instructions (next run). Fails open on
  every can't-check case; `--update` fast-forwards only when the tree is clean and undiverged.
- `scripts/sector_screen.py` — turns the per-sector `run_screener` rows into % off the 52-week
  high, RS vs SPY, EMA position, dollar volume, the sector ranking and the triage verdict, and
  emits the grade queue plus each sector's `top5` fallback. Pure standard library.
- `scripts/relative_strength.py` — computes the RS proxy, % off 52-week high, base depth/length
  and breakout volume from OHLCV bars (TradingView / IBKR / Polygon shapes). Shared with
  `can-slim-grader`. Feed it the collected bars rather than eyeballing charts.
- `scripts/build_report.py` — **the step-7 entry point.** Produces the PDF (default), the HTML,
  or both from one filled dashboard; enforces the self-audit before emitting anything; falls back
  to the HTML when no PDF engine exists.
- `scripts/html_to_pdf.py` — the PDF engine chain behind it (Chrome → Playwright → WeasyPrint →
  wkhtmltopdf; honours the template's `@page` size and margin). Usable directly, and shared
  with `can-slim-grader`.
- `assets/dashboard_template.html` — the report (full behavior in Step 7): a self-contained,
  print-optimized, pure-ASCII dashboard that is **dark on screen and white in print** (A4
  landscape, 15mm margins),
  driven by a `CONFIG` object. Derives both recommendation lists from one `picks[]` array (both
  gated at the grade cut, with an enumerated empty state when nothing clears it), self-audits its
  own CONFIG, and renders the funnel tiles, leadership map, sector sweep table, data-sources
  table and glossary automatically.
````


## `README.md`

Human-facing overview: what it produces and the CAN SLIM ideas behind it.

````md
# can-slim-recommend

A Claude skill that sweeps **every market sector** for its top performers, grades each one against
the **CAN SLIM** growth-investing methodology using live **TradingView** data, and returns **two
ranked recommendation lists** as a white-themed A4 PDF report.

It activates when you ask for stock ideas — *"recommend some stocks"*, *"what should I buy"*,
*"give me a list of growth stocks"*, *"best names in each sector"*, *"top sector performers"*,
*"screen for CAN SLIM names"*, *"recommend AI stocks"*.

## What it produces

Two lists, both built from the same graded pool:

1. **Sector leaders** — every top-of-sector performer that scored **4.5 or better out of 7** on
   the CAN SLIM scorecard, grouped by sector, best sector first.
2. **Overall top 10** — the highest-graded names market-wide, no sector cap.

Both lists hold **only** names at or above the cut. A name that scores 4.0 is not a
recommendation because everything else scored worse — it stays in the appendix with its
scorecard. When nothing clears 4.5, list 2 renders as **empty with an enumerated "why"**, derived
from the grades themselves: the market grade and what it costs every row, which letters failed
and how often, the best score actually reached, and how many names the hard filters removed
before grading.

A sector that produced no qualifier is not left blank — the report shows that sector's **top 5 in
the screener's own ranking**, banner-marked as ungraded and explicitly not recommendations, with
each row noting whether it even cleared the hard filters. Context to pick up the thread manually,
never a substitute for a grade.

Each name carries a letter-by-letter scorecard, a BUY-RANGE / WATCH / AVOID verdict, a rationale
expressed **only** in CAN SLIM terms, a buy point where a valid pivot exists, and the 7-8%
loss-cutting stop.

## How it works

0. **Version check first** — `scripts/check_for_updates.py` compares this checkout against its
   remote before any market call. Code updates (`scripts/`, `assets/`) take effect on the spot;
   instruction updates (`SKILL.md`, `references/`) were already loaded and land on the next
   invocation, so the run reports which it got. It never blocks a run and never pulls over
   uncommitted work.
1. **M first** — market direction from SPY/QQQ bars (distribution days, 50/200-day trend), graded
   once and applied to every row. In a correction the lists come out short rather than the cut
   coming down.
2. **Sector sweep** — one TradingView `run_screener` call per sector pulls that sector's **top 10
   performers** over the ranking window (6-month by default), restricted to US primary listings
   above the method's price and liquidity floors.
3. **Triage** — `scripts/sector_screen.py` computes % off the 52-week high, RS vs SPY, EMA
   position and dollar volume for all ~200 names, and drops the ones the method disqualifies
   outright (cheap, illiquid, >25% below the 52-week high, lagging SPY, below the 200-day).
4. **Grade** — every survivor goes through the sister skill **`can-slim-grader`**: C·A·N·S·L·I·M
   scored pass (1.0) / partial (0.5) / fail (0), out of 7. Same rubric, so a 4.5 here means what a
   4.5 means there.
5. **Two lists** — derived from the grades, never hand-built. If only three names reach 4.5, you
   get three names and an explanation. If none do, you get two empty lists and the reasons —
   never a padded list, and never a quietly lowered bar.

## Core concepts & critical ideas

CAN SLIM is a rules-based framework for finding **growth stocks poised for a big advance**. It is
built on how the market actually behaves — supply, demand, and crowd psychology — rather than on
valuation "cheapness," forecasts, dividends, or opinion. The whole approach rests on a handful of
critical ideas:

- **The seven factors (CAN SLIM).** Each letter is a trait the biggest historical winners shared
  *just before* their major moves:
  - **C — Current quarterly earnings & sales** up sharply (≥25%, ideally far more) versus the
    same quarter a year ago, and *accelerating*.
  - **A — Annual earnings** growing (≥25%/yr over 3 years) with a high return on equity (≥17%).
  - **N — Something new** (product, management, or industry condition) **and** the stock breaking
    out to **new highs from a sound price base** — the key entry trigger.
  - **S — Supply & demand** — a big volume surge on the breakout, a manageable share float,
    buybacks, low debt.
  - **L — Leader, not laggard** — high relative price strength; the #1 or #2 name in a strong
    industry group, not the cheap also-ran.
  - **I — Institutional sponsorship** — increasing ownership by high-quality funds.
  - **M — Market direction** — the general market must be in a confirmed uptrend.
- **"M" gates everything.** Roughly three of four stocks follow the general market, so the
  market's direction is assessed *first*. A market top is spotted through **distribution days**
  (heavy-volume down days); a new uptrend is confirmed by a **follow-through day**. You don't buy
  breakouts in a downtrend — and because M is one of the seven graded letters, a weak market
  lowers every score at once.
- **Buy high to sell higher (the "Great Paradox").** What looks too high to the crowd tends to go
  higher; what looks cheap tends to go lower. You buy **strength emerging from a base near new
  highs**, never a falling "bargain."
- **Bases and pivots.** Winners consolidate into recognizable patterns (cup-with-handle,
  double-bottom, flat base) before advancing. You buy at the **pivot** as the stock breaks out on
  volume ≥40–50% above average — and never chase it more than ~5% past that point. A candidate
  pivot more than ~10% below the 52-week high is **not** a pivot.
- **Defense first — cut losses at 7–8%, no exceptions.** Every large loss began as a small one.
  You take losses quickly and profits slowly, **average up, never down**, and take many 20–25%
  gains while letting the strongest leaders run.
- **Leadership & groups.** About half of a stock's move comes from its industry group and sector,
  which is exactly why this skill screens sector by sector rather than scanning a flat universe.
- **Concentration over diversification.** The method favors owning just a handful of the very best
  names (4–6) — so both lists are a **research shortlist to narrow down**, not positions to hold
  at once.

`references/canslim-methodology.md` contains the full rule set, thresholds, base patterns, sell
rules, and the classic mistakes to avoid.

## Output

One command produces either format, and the format is an argument rather than a convention:

```
python scripts/build_report.py canslim-recommendations-{date}.html [--format pdf|html|both]
```

`--format` **defaults to `pdf`**. The script also enforces the dashboard's self-audit — it renders
the page and refuses to emit anything while the report is failing its own checks — and falls back
to the HTML, with a reason, if no PDF engine is installed.

- **Default: a white-themed PDF report** (`scripts/build_report.py`), A4 landscape with a 15mm
  margin on every edge, so the
  pick tables fit. Each pick's CAN SLIM rationale runs as a full-width row beneath its stats
  rather than squeezed into a column, so it always has the whole table to wrap into. It includes the market verdict, the screening funnel, a leadership
  map (RS vs distance below the 52-week high), both recommendation lists, the sector sweep
  ranking, a **data sources & freshness table**, the portfolio/loss-cutting note, the disclaimer
  and an acronym glossary.
- **On request: the interactive HTML** — same report plus sortable columns and clickable tickers
  that open each name's per-ticker report in an in-page window. The HTML deliverable is **dark**;
  the PDF stays white regardless, because the print stylesheet forces the light palette. Set
  `data-theme="light"` on `<html>` if you want a light HTML instead.
- The dashboard **audits its own CONFIG** on render and prints a red banner for contradictions —
  an ungraded letter, a buy point with N failing, a pivot below new-high ground, a stop that isn't
  7-8%, a verdict that disagrees with the grade, or missing data provenance.

## Fresh data, every run — and an honest report when it isn't

Every run attempts a fresh pull of every source. Screener rows, bars, financials and grades are
never *started* from an earlier run, an earlier session, or earlier in the same conversation — a
re-check is a full re-run.

When a fresh pull fails — a connector down, gated, throttled, or returning nothing — the run
retries, tries the documented fallback source, and only then may fall back to previously pulled
data, and only where that older figure is still applicable (a quarterly financial usually is; a
price, 52-week high or distribution-day count usually is not). **Whatever happens is reported in
the dashboard**, not buried: a banner enumerates each source that did not come back fresh, why,
what was used instead, and the date that fallback data is from, and the sources table carries a
FRESH / REUSED / UNAVAILABLE chip per row.

**Every report is dated twice** — `generatedAt` (when the report was built) and `dataDate` (what
date the market data is as of), plus, per source, both when the call was made and what date the
figure underneath is from. The dashboard's self-audit refuses to ship a report that is missing its
data date, has an undated source row, or admits reused data the freshness block does not declare.

## Using it with a non-Claude assistant

`python scripts/export_portable.py` bundles the whole skill into two artifacts under `dist/`:

- **`can-slim-recommend-portable.md`** — one self-contained Markdown file: a portability preamble
  followed by every file of the skill inlined verbatim. Paste or upload it into Gemini, ChatGPT,
  or any long-context assistant and tell it to follow the workflow. This file is committed, so
  there is a stable link to hand someone.
- **`can-slim-recommend.zip`** — the raw directory, for a host that takes a folder (a Gemini Gem,
  a Custom GPT's knowledge files, another agent install).

The preamble is the important part. The reference guides describe a specific TradingView MCP
connector because that is what the skill was verified against, and no other assistant will have
it — so the preamble restates the requirement **tool-agnostically**: a screener ranked on 6-month
performance, daily OHLCV bars, quarterly and annual fundamentals, index bars for the market grade.
Any source that provides those works. It also carries the rules most likely to be lost in
translation — never invent a number, always attempt fresh data, always date it, never lower the
bar to fill a list.

Re-run the script after changing the skill; a stale bundle is worse than none.

## Contents
- `SKILL.md` — activation + the full workflow.
- `references/canslim-methodology.md` — the distilled CAN SLIM rule set: the seven criteria and
  thresholds, chart-base patterns, buy/sell rules, money management, and the costly mistakes.
  Shared with `can-slim-grader`; this copy additionally carries the pass/partial/fail grading
  rubric, which the sister's copy does not yet have. Both skills score a scorecard out of **7** —
  seven letters, each pass 1.0 / partial 0.5 / fail 0.
- `references/tradingview-sector-sweep.md` — the primary data guide: verified TradingView call
  shapes, the sector taxonomy, triage filters, the grader hand-off, and how the two lists are
  built.
- `references/ibkr-data-guide.md` — the fallback path (IBKR / Massive / FMP) plus the shared
  fundamental-source ladder.
- `scripts/check_for_updates.py` — step 0: is this copy current? Fails open when it cannot
  check; `--update` fast-forwards only on a clean, undiverged tree.
- `scripts/sector_screen.py` — sector sweep arithmetic + CAN SLIM triage over the screener rows.
- `scripts/relative_strength.py` — RS proxy, % off 52-week high, base depth/length, breakout
  volume from OHLCV bars. Shared with `can-slim-grader`.
- `scripts/institutional_cache.py` — grades **I** from SEC Form 13F, aggregated once per quarter
  and cached so a run spends no network on it. Fails open to the proxy below.
- `scripts/accumulation.py` — the **I** fallback: institutional buying pressure read from the
  up/down volume footprint. A proxy, and every reason string says so.
- `scripts/build_report.py` — produces the PDF (default), the HTML, or both, and enforces the
  self-audit before emitting.
- `scripts/html_to_pdf.py` — the PDF engine chain behind it. Shared with `can-slim-grader`.
- `scripts/export_portable.py` — bundles the skill for use with a non-Claude assistant.
- `assets/dashboard_template.html` — the self-contained report template: dark on screen, white
  on paper.
- `tests/test_regression.py` — the regression suite (see below).

## Tests
```
python tests/test_regression.py        # all of it, ~2s
python tests/test_regression.py -v     # name every passing check
python tests/test_regression.py ceiling   # only suites matching a substring
```
Pure standard library — no pytest, no network, no MCP connector. Run it after touching anything
under `scripts/` or `assets/`.

The load-bearing check is the ceiling's **soundness**: a ceiling that sits too high only wastes
API calls, but one that sits too low drops a qualifying name and leaves no trace in the report.
Two tests pin it from opposite directions — a brute force over the whole grade space against an
independently written copy of the rubric, and every grade the 2026-09-12 run actually awarded,
asserting no real score exceeded its own ceiling. The rest cover triage (a missing column must be
skipped, never failed), `@page` margin parsing, the dashboard's self-audit rules, and the full
`check_for_updates` git matrix including that it fails open and refuses to pull over a dirty tree.

## Requirements
- **TradingView MCP connector** (primary). Falls back to IBKR / Massive Market Data / FMP / web.
- **`can-slim-grader`** — the sister skill that grades each candidate:
  https://github.com/thewongdirection/can-slim-grader
- Web search available in the session.
- A PDF engine for the default deliverable (Chrome/Chromium/Edge, Playwright, WeasyPrint or
  wkhtmltopdf) — without one you still get the HTML.

## Disclaimer
This skill is **informational decision support, not investment advice.** It never places orders
and never gives personalized buy/sell directives. CAN SLIM is a probability edge, not a guarantee;
every recommendation is paired with its loss-cutting exit rule. Markets carry risk of loss. It is
an independent implementation of a publicly known investing framework and reproduces no
third-party copyrighted text.
````


## `references/canslim-methodology.md`

The distilled CAN SLIM rule set - the seven criteria, thresholds, base patterns, buy/sell rules.

```md
# CAN SLIM Methodology — the rule set this skill enforces

This is the complete rule set the `can-slim-recommend` skill applies — a growth-stock
selection framework distilled from decades of study of the market's biggest winners. Read
it fully before screening. The numbers below are the established thresholds of the method;
do not invent softer ones.

The core thesis: the greatest winning stocks of the last ~125 years shared **seven
common traits at the moment just before their biggest advances.** CAN SLIM names those
seven. It is a system built on *how the market actually behaves* (supply/demand + crowd
psychology), not opinion, forecasts, P/E "value," dividends, or book value — which
historically had little predictive value for the biggest winners.

Two ideas underpin everything:
- **The Great Paradox:** what looks too high and risky to the crowd usually goes higher;
  what looks cheap usually goes lower. Buy strength emerging from a sound base near new
  highs — never "bargains" on the way down.
- **History repeats** because human nature doesn't change. The same base patterns and
  topping signals recur cycle after cycle.

---

## The seven CAN SLIM criteria (BUY side)

### C — Current Quarterly Earnings & Sales
- **EPS (most recent quarter) up ≥ 25%** vs. the *same quarter a year ago* (never vs. the
  prior quarter — avoids seasonality). Absolute minimum floor is 18–20%; the method prefers
  concentrating on **40%–500%+** in bull markets. The higher, the better.
- Insist ideally on **two consecutive** quarters of strong gains.
- **Earnings acceleration** matters as much as the level: the growth *rate* should be
  improving over recent quarters (e.g., 15% → 40% → 100%). Deceleration for **two
  straight quarters** (a drop of ~2/3 from the prior rate, e.g. 100%→30%) is a red flag.
- **Sales up ≥ 25%** in the latest quarter, OR sales-growth rate accelerating over the
  last three quarters. Earnings without sales support (cost-cutting) are not sustainable.
- **After-tax profit margins** improving and near the company's peak / best-in-industry.
- Exclude **one-time / nonrecurring gains** (asset sales) from EPS.
- Cross-check: at least one *other* stock in the same industry group should also show
  strong earnings; if not, you may have the wrong name.

### A — Annual Earnings Increases
- **Annual EPS up in each of the last 3 years**, growth rate **25%–50%+** (median of big
  winners at emergence was ~36%). Prefer no down year; one down year is acceptable only if
  the next year makes a new EPS high.
- Each year's EPS should be meaningfully higher than the last (e.g., 0.70 → 1.15 → 1.85 →
  2.65 → 4.00). Beware "recovery" that is still below the prior peak.
- **Return on Equity (ROE) ≥ 17%** (the best show 25%–50%). If ROE is low, pretax margin
  must be strong.
- Optional quality marks: **annual cash flow per share ≥ 20% above EPS**; stable, straight
  earnings line on a log chart (low deviation from trend).
- Next-year consensus estimate should also be up (but estimates are opinions; actuals are
  facts).
- **P/E is NOT a selection or rejection factor.** Big winners typically began at P/Es of
  25–50 and expanded 100%+. A low P/E is usually low for a good reason. Never skip a
  leader because its P/E "looks high," and never buy junk because its P/E "looks cheap."

### N — New (Products, Management, Conditions) + New Highs off a proper base
- **95%+ of big winners** had something *new*: a new product/service driving accelerating
  earnings, new management, or new industry conditions (shortages, price rises, new
  technology, regulatory change).
- Favor **"New America" entrepreneurial companies** — IPO within the last ~8–10 years,
  fastest growth typically between years 5 and 10. Avoid tired "old America" laggards run
  by "caretaker/maintainer" management.
- **The timing half of N — this is the single most actionable buy trigger:** buy as the
  stock **breaks out to a new high price out of a sound, properly formed base**, on a
  volume surge. Do NOT buy extended >5–10% past the pivot. See "Chart bases & buy points."

### S — Supply & Demand
- **Smaller share supply usually outperforms** (easier to move); but any capitalization is
  acceptable if all other CAN SLIM traits are present. Small caps are more volatile both
  ways.
- Prefer meaningful **management ownership** (≥1–3% in large companies, more in small).
- **Companies buying back their own stock** (5–10%+) over time is a plus (shrinks supply,
  lifts EPS).
- **Low debt-to-equity** is safer; a company *reducing* its debt/equity over 2–3 years is
  attractive. Watch for dilution from convertibles / excessive stock splits (stocks often
  top around the 2nd–3rd split).
- **Demand is read through volume:** on the breakout, day volume should be **≥ 40–50% above
  average** (often +100% to +1000% on true leaders). In the base, look for **volume
  dry-ups** near the lows (selling exhausted) and up-weeks on above-average volume
  outnumbering down-weeks.

### L — Leader or Laggard
- Buy the **#1 or #2/#3 company in a strong group** — defined by best EPS & sales growth,
  highest ROE, widest margins, strongest price action and product — *not* the biggest or
  most familiar name.
- **Relative Strength (RS):** buy stocks whose 12-month price performance beats **≥ 80%**
  (ideally 90%+) of the market. Big winners averaged an **RS ~87** before their major run.
  **Do not buy RS below ~70.** (This skill computes an RS *proxy* from price history — see
  ibkr-data-guide.md — since a true full-market 1–99 RS rating needs the whole market.)
- **Avoid "sympathy plays"** — the cheaper laggard in the same group that never performs
  like the leader. "The first man gets the oyster; the second, the shell."
- **Never buy on the way down** because it "looks cheap" (Cisco $82→$8, Crocs $75→$1, BofA
  $55→$6 examples). In a market correction, the growth stocks that **fall the least** are
  your best forward leaders; the ones down most are weakest.
- Look for **abnormal strength on a weak market day** (up strongly on heavy volume while
  the market is down) — a tell of a genuine leader.
- The best new leaders break out in the **first ~13 weeks** (especially first 3–4) of a new
  bull market — don't miss that window.

### I — Institutional Sponsorship
- Want **several** institutional owners (≥ a handful), with the **number increasing** over
  recent quarters — and especially **new positions** taken by top-performing funds in the
  latest quarter.
- **Quality over quantity:** a couple of A-rated / top-performing fund managers owning it
  beats hundreds of mediocre holders.
- Beware **"over-owned"** stocks (owned by 1,000s of institutions) — that's future selling
  pressure; by the time ownership is universal, "the heart is out of the watermelon."
- Sponsorship also provides **liquidity** when you need to sell.

### M — Market Direction (the make-or-break filter)
- **3 of 4 stocks follow the general market.** You can be right on C-A-N-S-L-I and still
  lose if M is down. Assess the market **first**.
- **Read the major indexes daily** (S&P 500, Nasdaq Composite, Dow, NYSE Composite) — price
  + volume. Don't rely on secondary indicators, economists, newsletters, or opinions.
- **Distribution days = topping signal:** a day where the index closes **down > 0.2% on
  higher volume than the prior day** (or heavy volume with stalling/no price progress).
  **4–5 distribution days over 4–5 weeks** almost always tips the market into a decline.
  When you see them: raise cash, get off margin.
- **Follow-through day = new uptrend confirmation (bottoms):** after a decline, a rally
  attempt begins on the day an index closes up (Day 1). Then, on **Day 4–7 of the attempt**,
  look for a **big gain (~1.5%+, decisively) on volume higher than the prior day and above
  average.** No new bull market has ever started without one. A follow-through is the green
  light to start buying breakouts — not a signal to buy with abandon.
- **The big money is made in the first 1–2 years** of a new bull market.
- Late-cycle tells: laggards/low-quality/defensive stocks (gold, utilities, tobacco, food)
  leading; leaders breaking out of wide, loose, late-stage (3rd/4th) bases; leaders
  climaxing. When the leaders break, the market is near a top.

---

## Chart bases & buy points (the "how" behind N and S)

A **base** is a price correction/consolidation after a prior uptrend. Requirements: a
prior uptrend of **≥ 30%**, improving RS, and prior volume. Buy the breakout through the
**pivot / "line of least resistance."** ~80–90% of bases form during general-market
corrections.

**Sound base patterns (in rough order of reliability):**
- **Cup with handle** — the most common. U-shaped (not sharp V), lasts 7–65 wks (usually
  3–6 months), depth typically 12–15% up to ~33% (occasionally 40–50% in volatile leaders
  or deep corrections). **Handle**: forms in the **upper half** of the base and above the
  10-week MA, drifts **down** (a shakeout), depth 8–12% (up to 20–30% only at bear-market
  bottoms), on light volume. **Pivot buy point** ≈ handle high (usually a bit below the
  base's absolute peak). Breakout volume ≥ 40–50% above average.
- **Cup without handle** — works but slightly higher failure rate.
- **Saucer with handle** — like a cup but shallower and longer.
- **Double bottom (W)** — 2nd low should undercut the 1st (shakeout). Pivot = the middle
  peak of the W (or handle high if it has one). Points: A start, B first low, C middle
  peak (buy), D second low, E/F handle top/low.
- **Flat base** — a 2nd-stage base after a ≥20% advance; sideways ≥ 5–6 weeks, corrects
  ≤ 10–15%. Good second-chance entry.
- **Square box** — 4–7 weeks, ~10–15% correction, boxy look.
- **Ascending base** — 3 pullbacks of 10–20%, each low higher than the last.
- **Base-on-base** — a base built on top of a prior base during a market decline; springs
  hard when the market turns.
- **High, tight flag** — RARE and strongest but riskiest: a **100–120% move in 4–8 weeks**,
  then a tight **10–25% sideways** flag for 3–5 weeks. Big moves follow; hard to interpret.

**Faulty / avoid patterns:** wide-and-loose and erratic bases; V-bottoms straight into new
highs with no handle; **wedging handles** (drifting *up* along the lows — no shakeout);
handles in the **lower half** of the base or below the 10-week line; late-stage (3rd/4th)
bases; triangles, coils, pennants, triple bottoms, head-and-shoulders *bottoms* (all weak);
bases with heavy adverse volume or every week's spread wide. **Minimum ~7–8 weeks** for
most valid bases (except flat base 5–6 wks, square box 4–7 wks, high-tight-flag). One-,
two-, three-week bases are risky — avoid.

**Overhead supply:** prior buyers underwater above the current price create resistance
("get me out even" sellers). Avoid stocks with heavy recent overhead supply; a stock at an
all-time new high has none — an advantage. Supply >2 years old matters less.

---

## SELL rules (defense) — needed even for a recommendation list

Recommendations must ship with an exit plan — you can't win big without a strong defense.

**The absolute loss rule (never optional):**
- **Cut every loss at 7–8% below your purchase price. No exceptions, ever.** If bought
  exactly at the pivot, winners rarely fall 8%. In a bear market, tighten to **3%**.
- Every 50% loss began as a 10–20% loss. A 33% loss needs a 50% gain to recover; a 50% loss
  needs 100%. "Take losses quickly and profits slowly." Average **up, never down.**

**Taking profits:**
- Default: **take gains at 20–25%** (compounding a few 20–25% wins beats waiting).
- **Exception — hold the big leaders:** a stock that jumps **20% in ≤ 1–3 weeks** from the
  pivot should be **held ≥ 8 weeks** (it may be a huge winner). Don't take profits in the
  first 8 weeks unless it's in serious trouble.
- Keep a **3:1** ratio of profit-taking to loss-cutting.
- Never let a **20%+ gain turn back into a loss.**

**Technical topping / sell signals** (many appear while earnings still look great — the
smart money sells before the fundamentals turn):
- **Climax top:** rapid run-up 2–3 weeks after a long advance; largest daily/weekly price
  spread and gain of the whole move; heaviest volume day; **exhaustion gap** up.
- New highs on **declining volume**; repeated closes at the day's low; **stock split**
  euphoria (25–50% pop); breaking the **upper channel line**; 70–100%+ above the 200-day MA.
- **3rd/4th-stage base breakouts** (as much as 80% fail).
- Breaking the **long-term uptrend line** on heavy volume; greatest one-day drop of the
  move; living below the **10-week MA** for 8–9 weeks; 200-day MA turns down.
- **RS rating drops below 70**; no confirming strength from any other stock in the group.
- Two consecutive quarters of major earnings **deceleration**.
- Sell into obvious good news / cover stories / universal optimism ("bulls and bears make
  money, pigs get slaughtered").

---

## Money management & portfolio construction

- **Concentration, not wide diversification.** The method holds that most investors should
  own **4–6** well-chosen stocks (fewer for small accounts; even $1M+ needs only 6–7);
  broad diversification is treated as a hedge for ignorance. **Force-feed** money from
  laggards into your best performers (pyramid up 2–2.5% above the first buy, smaller
  add-ons, never past ~5% extended).
  → *This skill outputs a longer ranked, sector-diversified watchlist; it explicitly tells
  the user the methodology would concentrate into the top few names.*
- Sector matters: **~37% of a stock's move is its industry group, +12% its sector ≈ half.**
  Buy leaders in **top-ranked groups** (top ~20 of 197 / top 6 sectors on the new-high
  list); avoid the bottom groups. **60%+ of big winners** were part of a group move.
  Confirmation: require **at least one other strong stock in the same group**.
- Group tells: "wash-over effect" (weakness in one leader spreads to the group), "follow-on
  effect," "cousin stock" (suppliers to a hot group).
- Margin only for experienced investors and only in the first 1–2 years of a bull market;
  off margin the moment a bear market begins.
- Don't day-trade; don't over-worry taxes/commissions; keep it simple (avoid options-heavy,
  foreign, bonds, commodities as distractions).
- Price/liquidity filters: favor **NYSE $20–$300 / Nasdaq $15–$300**; most super stocks
  emerge from **$30+** bases; **avoid sub-$10 "junk pile."** Average daily volume should be
  at least several hundred thousand shares.

---

## The 21 costly mistakes (what to screen OUT / warn about)

1. Holding small losses until they get big. 2. Buying on the way down. 3. Averaging down.
4. Not using charts / fearing new highs. 5. Poor selection criteria (buying 4th-rate
stocks). 6. No general-market rules. 7. Not following your own rules. 8. No sell plan.
9. Ignoring institutional sponsorship & charts. 10. Buying more shares of cheap stocks
instead of fewer of quality ones. 11. Buying on tips/rumors/news/opinions. 12. Picking
stocks for dividends or low P/E. 13. Wanting a quick, easy buck. 14. Buying familiar old
names. 15. Can't recognize good info/advice. 16. Cashing small profits while holding
losers. 17. Over-worrying taxes/commissions. 18. Over-speculating in options/futures.
19. Using limit orders and quibbling over eighths instead of transacting at market.
20. Can't make decisions (no rules). 21. Not looking at stocks objectively (hope/ego).

**Why people miss big winners:** disbelief/unfamiliarity with new names; P/E bias; not
understanding leaders start big moves at *new highs* not new lows; selling too soon (or too
late by not cutting losses).

---

## The master buy checklist (Chapter 20, condensed)

A candidate should satisfy as many as possible:
1. Price not cheap (NYSE ≥ $20 / Nasdaq ≥ $15; prefer $30+ bases; avoid < $10).
2. Annual EPS up ≥ 25% each of last 3 yrs; next-year estimate up ≥ 25%; cash flow ≥ 20%
   above EPS a plus.
3. Last 2–3 quarters' EPS up big (≥ 25–30% min; 40–500% in bull markets).
4. Last 3 quarters' sales accelerating, or latest sales ≥ 25%.
5. ROE ≥ 17% (great ones 25–50%).
6. Recent after-tax margins improving / near peak.
7. In a top ~6 sector / top 10% industry group.
8. Bought for leadership (earnings, sales, ROE, margins, product), NOT dividend/P/E.
9. **RS ≥ 85** (proxy ≥ 80).
10. Adequate average daily volume (several hundred thousand+ shares).
11. Emerging from a sound base at a proper pivot, breakout volume ≥ 50% above normal;
    not extended > 5–10% past the pivot.
12. Average up, never down; cut losses at 7–8% (3% in bear markets).
13. Written sell rules for taking profits.
14. Increasing institutional sponsorship; ≥ 1–2 top-performing funds recently added.
15. Excellent new/superior product with a big repeat-sale market.
16. **General market in a confirmed uptrend.**
17. Don't over-diversify or dabble in options/foreign/bonds/commodities.
18. Management ownership.
19. "New America" entrepreneurial company (IPO within ~8–10 yrs) over old laggards.
20. Forget ego; the market is always right.
21. Read the market daily; know tops and bottoms.
22. Watch for buybacks (5–10%+) and new management.
23. Don't buy at the bottom / on the way down / average down.

## The pass / partial / fail grading rubric (how to score each letter)
Grade every letter **pass (1.0) / partial (0.5) / fail (0)**. Seven letters, so a scorecard totals
out of **7**. Both `can-slim-recommend` and `can-slim-grader` use this one scale, which is what
makes a score portable between a screen and a single-ticker report.

**A grade follows mechanically from the threshold and the actual printed beside it.** If the
evidence concedes a miss ("just under the 25% mark", "hasn't cleared the high"), the letter cannot
be pass — call it partial. Where a threshold says **each** ("EPS up each of the last 3 yrs at
>=25%"), every period must clear it: one strong year among three below-bar years is a PARTIAL.
Magnitude of a beat, backlog, guidance or a big volume day are colour for the write-up, never
grounds to promote a letter.

- **C — current quarterly EPS & sales:** PASS = EPS and sales both up >=25% vs the year-ago
  quarter, accelerating rather than decelerating. PARTIAL = one of the two clears the bar, or both
  are up but short of 25%, or growth is decelerating. FAIL = flat, negative, or a loss. Downgrade
  if sales lag EPS (buyback-driven) or margins are falling.
- **A — annual earnings & ROE:** PASS = EPS up **each** of the last 3 years at >=25% **and** ROE
  >=17%. PARTIAL = a broadly rising multi-year record that misses one leg (a year below the bar,
  or ROE under 17%). FAIL = declining EPS, no annual profit, or an ROE far below the bar. A newly
  public company without three years of record cannot exceed PARTIAL on A.
- **N — new + new high off a base:** PASS = a genuine new driver **and** a sound base with the
  stock at a proper pivot, no more than ~5% extended past it. PARTIAL = at or near new-high ground
  but with no valid pivot to buy (base incomplete, or already extended beyond it). FAIL = no new
  driver, more than ~10% below the 52-week high (a lower high is not a pivot), or a wide-and-loose
  / late-stage base. Extension far above the 50-day (roughly >25%) after a climax run is a FAIL,
  not a partial — there is no entry there.
- **S — supply & demand:** PASS = breakout volume >=40-50% above the 50-day average, manageable
  float, buybacks, low debt. PARTIAL = institutional-grade liquidity and a constructive trend but
  no demand surge. FAIL = heavy distribution, dilution, illiquidity, or below the 200-day.
- **L — leader not laggard:** PASS = clearly outperforming the benchmark over the window **and**
  the #1 or #2 name in a strong group. PARTIAL = outperforming but mid-pack within its own group,
  or leading a group that itself lags. FAIL = in line with or behind the benchmark.
- **I — institutional sponsorship:** PASS = ownership **rising** over recent quarters with
  quality funds adding, and not so over-owned that new sponsorship is impossible. PARTIAL =
  adequate ownership whose trend you could not verify, or flat sponsorship. FAIL = thin, neglected,
  or funds distributing. Verify the trend before awarding a pass — a high ownership *level* alone
  is a PARTIAL.
- **M — market direction (scored ONCE for the whole market, applied to every row via
  `CONFIG.market.mGrade`):** PASS = confirmed uptrend, few distribution days, broad leadership.
  PARTIAL = uptrend under pressure — distribution days building (4-5+), leadership narrowing, an
  index slipping below its 50-day. FAIL = confirmed correction or downtrend. M is scored once
  because market direction is a single market-wide gate: it moves every total together, so a weak
  tape correctly makes any cut harder to clear. Never loosen the cut to compensate.

Rough total read: **6.0-7.0** = table-pounding leader in a strong tape; **4.5-5.5** = qualifies,
buyable when N gives a pivot; **3.5-4.0** = watch (needs the market or a letter to improve);
**< 3.5** = pass on it.

## Modern refinements & professional practice (beyond the 1988 book)
CAN SLIM's core is durable, but apply it with current, professionally-informed judgment — and
refresh the specifics with web research each run rather than from memory:
- **Why it works (factor evidence):** the edge is the *momentum* factor (Jegadeesh-Titman;
  6-12 mo cross-sectional relative strength) combined with *quality* (profitability/ROE — Fama-
  French RMW, AQR "quality-minus-junk"). A genuine leader is a momentum+quality name, not a
  low-quality junk rip — down-weight L/S when the strength is purely speculative.
- **Market structure O'Neil didn't have:** passive/ETF flows, index add/deletes and quarterly
  rebalances, and dealer options positioning (gamma, 0DTE, max-pain) can extend or reverse moves
  fast; mega-cap concentration means the index (M) can mask narrow leadership — check breadth
  (advance/decline, % of stocks above their 50-day), not just the index level.
- **Macro & event overlay:** Fed path, CPI/jobs prints, earnings-season dispersion, and
  commodity/geopolitical shocks reprice whole sectors intraday — reflect them in the M score and
  in stop width.
- **Volatility regime & sizing:** in high-VIX / under-pressure tapes, cut size, tighten stops
  toward 3-5%, demand cleaner bases, and require a follow-through day before buying breakouts.
- **Valuation-sanity overlay (the value-investor lens):** CAN SLIM ignores P/E on purpose, but a
  professional still flags a leader discounting implausible growth (extreme EV/Sales or P/E vs. its
  own history and peers) as elevated risk — never *reject* on valuation alone, but note it.
- **Data hygiene:** prefer as-reported / GAAP-reconciled figures; treat heavily-adjusted non-GAAP,
  one-time gains, and buyback-inflated EPS skeptically (that is the C/A quality check).

Keep every pick's written reason in CAN SLIM terms; use these refinements to grade more accurately
and to frame risk, not to smuggle in off-method rationale.
```


## `references/tradingview-sector-sweep.md`

The primary data guide: verified call shapes, sector taxonomy, triage filters, list construction.

````md
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
  "sectors": { "Electronic Technology": [ {row}, {row}, ... ], "Health Technology": [ ... ] } }
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
`scripts/institutional_cache.py` (SEC 13F, built once a quarter), falling open to
`scripts/accumulation.py` (volume proxy). Record which in `CONFIG.sourceMap` — the cache carries
`detail[ticker].source` per name. Never leave I ungraded: the dashboard's self-audit flags it.

**Two routes that do NOT work for I, both checked rather than assumed.** FMP `form13F` needs the
Ultimate/Enterprise plan and returned ACCESS DENIED on a free tier (Sept 2026). And the
`securities-filings-lookup` skill cannot answer it either, for a structural reason worth
understanding: it resolves ticker → CIK → *that company's own* filings, but a 13F is filed by the
FUND, so an issuer lookup returns nothing — NVIDIA files no 13Fs. Sponsorship is an aggregation
across every filer in the quarter, which is a bulk-dataset job, not a per-company fetch. Use that
skill for what it is good at: the official **C/A** filing PDFs.

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

Write each `reason` as prose of whatever length the evidence needs — it renders as a full-width
row under the pick, not as a column. There is no "% off 52-week high" column in the report, so
state that distance in words in the reason itself.

The **grade is not the verdict.** A name can clear 4.5 on C, A and L and still be a WATCH
because N fails. Fill `verdict` on every pick (BUY-RANGE / WATCH / AVOID) — the dashboard's
self-audit rejects a report where the two disagree, where a buy point sits more than 10% below
the 52-week high, or where a stop is not 7-8% below the entry.

---

## Step 6 — Source priority: what is proven, and what to fall back to

**Reach for the proven path first.** The ladder below is ordered by what has actually returned
usable data in live runs of this skill, not by what looks best on paper. Prefer a call that is
known to work over one that merely should.

### Tier 1 — verified working (use these by default)

Every one of these returned complete, correct data in live end-to-end runs:

| Need | Call | Notes from live use |
|---|---|---|
| Sector top performers | `run_screener` sorted on a `Perf.*` column | 20/20 sectors returned rows; the filter shape in Step 2 is the verified one |
| Price, 52-wk range, EMA50/200, rel. volume, liquidity, industry, next earnings | `run_screener` columns | all populated; `EMA200` is `null` for names with under ~200 sessions (recent listings) - treat as unknown, don't infer |
| Index bars for M | `get_ohlcv` (`1D`, ~28 bars is enough for a distribution-day count) | exact OHLCV; count 300 also fine but wasteful |
| Benchmark window performance | `get_symbol_data("AMEX:SPY", ["Perf.6M", ...])` | one small call; cheaper than deriving it from bars |
| C - quarterly revenue & EPS with YoY | `get_financial_history` `period="fq"` | per-period `yoy_pct` is the field to grade on |
| A - annual EPS record | `get_financial_history` `period="fy"` | 4 fiscal years back |
| A - ROE, margins, debt, TTM growth | `get_financials` | the fastest way to screen A before spending calls on history |
| C cross-check - street EPS vs consensus | `get_earnings_history` | grade C on `eps_actual`, not the GAAP `eps` |
| I - institutional sponsorship | `scripts/institutional_cache.py` (SEC Form 13F, cached quarterly) -> `scripts/accumulation.py` (volume proxy) | 13F is filed by MANAGER not by issuer, so "who owns X" is an aggregation, not a lookup - which is why the cache exists and why it is built once a quarter, not once a run. Web search returns the ownership **level** reliably but not the **trend**, which is the half that grades the letter |

**A cheap ordering that saves calls:** run `get_financials` on every candidate first. ROE and TTM
EPS growth alone disqualify most names on **A**, and a name that cannot pass A cannot reach the
cut - so only pull `fq`/`fy` history for the ones still alive. In the live run this cut the
fundamental calls roughly in half.

### Tier 2 — unverified in this environment (fall back only, and say so)

These have **not** been exercised by a live run of this skill. They may work; treat a first call
as a test, and if it is gated or empty, drop to the next rung rather than retrying:

| Need | Fallback order |
|---|---|
| Sector top performers | FMP `search-company-screener` (ranks by market cap, not performance - re-rank yourself) → IBKR `search_investment_topics` + `get_theme_details` → web new-high/leaders lists |
| Bars / RS / base | Massive Market Data `/v2/aggs` (**throttle to 5 calls/min**) → IBKR `get_price_history` (`period:"TWO_YEARS"`, `step:"ONE_DAY"`) |
| Live last price | FMP `batch-quote` → IBKR `get_price_snapshot` |
| C / A fundamentals | Daloopa → bigdata.com → LSEG → SEC EDGAR via `securities-filings-lookup` → FMP → web |
| I sponsorship trend | `institutional_cache.py` (SEC 13F bulk, free, no key) → `accumulation.py` (volume proxy) → FMP `form13F` (**verified plan-gated**: ACCESS DENIED on a free tier, Sept 2026) → web |

FMP in particular has been **plan-gated** in past checks of the sister skill (`statements` and
`quote` returned ACCESS DENIED in an August-2026 check), which is why it sits low on every rung.

Gating is per-endpoint and often intermittent: keep whatever a source *does* answer and fill only
the gaps from the next rung - never drop a letter because one call failed. Whatever you fall back
to, name it in `CONFIG.dataProvenance`, add a `CONFIG.sourceMap` row for it, and set
`CONFIG.dataWarning` to say what was gated or stale and what filled the gap.

## Guardrails

- **Read-only market data.** Never call TradingView's portfolio-write or delete tools, and never
  call IBKR order or account tools (balances, positions, orders, trades, summary, PA analytics),
  even if asked mid-run. Trading and account access are out of scope for this skill.
- **Never display or store** contract IDs, account numbers, or any account-bound data. Present
  stocks by symbol and name only.
- Timestamp everything and flag approximations: RS here is a **proxy** (window performance vs
  SPY), not a full-market 1-99 rating, and fundamentals can lag the latest quarter.
- Paraphrase research; short quotes only.
````


## `references/ibkr-data-guide.md`

The fallback data path plus the shared fundamental-source ladder.

```md
# IBKR data guide — the fallback path (and the shared fundamental ladder)

> **Read `tradingview-sector-sweep.md` first — it is the primary path.** This skill's main
> workflow sweeps every sector's top performers with the **TradingView** connector and grades
> them with `can-slim-grader`. This document is the **fallback** for when TradingView is not
> connected or an endpoint is gated, plus the **fundamental source ladder** (Step 3) that both
> paths share. The candidate-generation strategy below (IBKR themes + web leaders lists) is the
> alternative to the TradingView sector sweep, not a second run alongside it.

It maps the methodology in `canslim-methodology.md` to concrete IBKR connector calls plus
targeted web research, and gives the candidate-generation strategy. The IBKR connector here exposes **live price/volume, 52-week stats, and
sector/theme groupings — but NOT company fundamentals** (EPS growth, ROE, margins, annual
earnings, institutional ownership). So:

- **Massive Market Data** (Polygon-style; preferred for **price history & RS**) and/or **IBKR**
  cover the technical/positioning letters: **N** (new highs, bases), **S** (volume/liquidity),
  **L** (relative strength, leadership/groups), **M** (market direction).
- **Fundamental-data connectors** (preferred) or web research cover the fundamental letters:
  **C** (quarterly EPS & sales), **A** (annual EPS, ROE, margins), and the ownership half of
  **I**. Prefer connected financial sources over generic web search — see Step 3 for the
  source-priority ladder (Daloopa → bigdata.com → LSEG → SEC EDGAR → FMP → web; FMP is the
  lowest-priority connector because it is commonly gated/throttled) and when to delegate
  to the `ibkr-review-ticker` / `securities-filings-lookup` skills.

Load IBKR tools with `ToolSearch` (query e.g. `"search contracts price history price
snapshot investment topics company themes"`) before use — they are deferred. This skill is
**strictly read-only market data**: only `search_contracts`, `get_price_snapshot`,
`get_price_history`, `search_investment_topics`, `get_theme_details`, `get_company_themes`,
and optionally `get_watchlists`/`get_watchlist`. **Never** call order tools or account
tools (balances, positions, orders, trades, summary, PA analytics) — trading and account
access are entirely out of scope, even if asked mid-run.

### Massive Market Data connector (preferred for price history / RS / MAs)
A Polygon.io-style market-data MCP (tools `mcp__Massive_Market_Data__search_endpoints` /
`call_api` / `query_data`; deferred — load with `ToolSearch` first). It is **ticker-based (no
`contract_id` resolution)** and gives clean, deterministic OHLC — the best source here for the
technical letters. Use `search_endpoints` (`market` must be capitalized, e.g. `"Stocks"`) to
discover paths, then `call_api`:
- **Custom Bars (OHLC)** — `/v2/aggs/ticker/{TICKER}/range/1/day/{from}/{to}` → feed daily
  closes to `scripts/relative_strength.py` for a **true 12-month RS** (point-to-point return vs
  SPY over the same window) and the base shape. This is materially better than a 200-day-MA
  proxy — e.g. a name that round-tripped through a base can show a weak 200-day proxy yet a
  strong true 12-mo RS. Pull ~14 months (or `2025-...`→today) for candidate **and SPY**.
- **SMA / EMA / MACD** — `/v1/indicators/sma/{TICKER}?timespan=day&window=50` (and `window=200`)
  → 50/200-day MAs directly (matches other feeds to the cent), for the N/S trend gate.
- **Grouped daily** — `/v2/aggs/grouped/locale/us/market/stocks/{date}` → all US stocks' OHLC
  for one date in a single call (bulk breadth / candidate generation).
- **`store_as` + `query_data`** — save a pull as an in-memory table and run SQL (returns, %
  off high, ranking) across many names without dumping raw bars into context.
- **Rate limit — throttle to AT MOST 5 Massive calls per minute.** Space them out (~12s apart);
  do not fire large parallel bursts. Design the run to need few calls: prefer **grouped-daily**
  (all US stocks for a date in ONE call) + **`store_as`/`query_data`** over per-ticker pulls —
  e.g. two grouped-daily calls (year-ago + latest) cover the entire universe's RS. If you must
  pull many per-ticker series, batch the work across minutes and stay under the cap.
- **Plan boundary (this account):** historical **aggregates + indicators WORK**; the
  **real-time snapshot** endpoints (`/v2/snapshot/...`, `/v3/snapshot`) return **403
  NOT_AUTHORIZED**. Daily aggregates also lag live by up to one session. So: use **Massive for
  history / RS / MAs**, and get the **live last price** from **FMP `batch-quote`** or **IBKR
  `get_price_snapshot`**. If a Massive call 403s, fall through to IBKR/FMP for that datum.

---

**Freshness (applies to every step below): always pull fresh.** Re-issue every IBKR / FMP /
web call on each run — do not reuse quotes, bars, `contract_id`s, RS, or candidate lists from a
previous run, from earlier in the conversation, from memory, or from a cached output file. IBKR
`get_price_history` responses carry an `expires` field; if it is already in the past, or a
snapshot's timestamp is stale, refetch. Timestamp the output with the actual pull time.

**As-of / point-in-time mode (optional):** when the user wants the screen *as of a past date*,
still re-issue every call this run, but reconstruct as of that date (see SKILL.md "As-of /
historical mode"). **Massive** does this natively — its Custom Bars take an explicit range
(`/v2/aggs/ticker/{T}/range/1/day/{from}/{to}` with `to` = the as-of date), so no truncation is
needed. **IBKR** `get_price_history` has **no as-of parameter** and always ends now, so pull
`period: "FIVE_YEARS"` (it spans the date) and use only bars dated **≤ the as-of date**;
`get_price_snapshot` / FMP `batch-quote` are **live-only — skip them** and take price / 52-wk
high / % off-high from the in-window bars. Feed the cutoff to `scripts/relative_strength.py` with `--asof {cutoff}` (same
units as the bar timestamps; a bare `YYYY-MM-DD` is inclusive of that day) so RS, base, and
breakout are computed only from in-window bars. For **C/A/I**, use only filings dated **on/before**
the as-of date (no look-ahead), and remember `get_theme_details` / web "current leaders" are
**present-day** — flag the survivorship/look-ahead limits in `dataWarning`.

## Step 0 — Candidate generation (the hardest part)

The **IBKR** connector has no bulk market screener, so build a candidate universe from
several sources, then filter it down. Aim to *start* with 60–120 names so ~20 survive.
**FMP does have a screener** (`search` → `search-company-screener`: filter by market cap,
price, volume, sector, country, `isEtf`/`isFund`/`isActivelyTrading`) — use it to pull a
liquid starting universe by sector, but note it ranks by market cap, not growth/RS, so it
surfaces mega-caps first and still needs the near-high + earnings filter below. In practice
the most CAN-SLIM-aligned candidates come from **web new-high/leaders lists + IBKR leading
themes**, with the FMP screener as a breadth cross-check.

1. **Leading themes/groups (primary, most CAN-SLIM-aligned).** The user may name a theme,
   or you infer the current leading areas. For each leading trend/sector:
   - `search_investment_topics { query: "{singular root noun}", max: 5 }` — use short
     singular keywords ("battery", "robot", "solar", "nuclear", "obesity", "cyber", "ai",
     "datacenter"). Retry with a synonym if empty.
   - `get_theme_details { key, max: 25 }` — returns companies **relevance-ranked** (rank 1 =
     most central), each with a `contract_id` you can reuse directly. This surfaces group
     leaders without needing symbols up front.
2. **Web research for current leaders.** Search for names currently showing CAN SLIM traits:
   recent-quarter EPS up big, near 52-week highs, top-ranked industry groups, strong RS,
   breaking out of bases. Good queries: "stocks breaking out to new highs [current month
   year]", "leading growth stocks strong earnings [quarter]", "top growth-stock leaderboards
   current leaders", "top performing S&P sectors this quarter". This keeps the universe
   current.
3. **User's own watchlists (optional):** if the user asks to screen their lists, `get_watchlists`
   → `get_watchlist { id }`. (Read-only; never write.)
4. Deduplicate; resolve every symbol to a `contract_id` via `search_contracts` (exact
   `symbol` match, US primary listing, `sections` include `STK`; ignore leveraged/yield ETFs
   that merely contain the symbol).

---

## Step 1 — M: assess general market direction FIRST (gates everything)

Do this before deep candidate work — it sets risk posture and the message to the user.

- Pull daily bars for broad indexes/ETFs: `search_contracts` for **SPY** and **QQQ** (or
  index `IND`), then `get_price_history { contract_id, security_type: "STK", step: "ONE_DAY",
  period: "THREE_MONTHS", outside_rth: false }`.
- Assess trend and count **distribution days** (close down > 0.2% on volume higher than the
  prior day) over the last 4–5 weeks. **4–5+ distribution days → market under pressure.**
- Check whether price is above/below the 50-day and 200-day moving averages and making
  higher highs/lows (uptrend) vs. lower highs/lows (correction).
- Cross-check with a web search for current market status ("stock market uptrend or
  correction today", follow-through day / distribution-day count from market-analysis sources).
- Classify as one of: **Confirmed uptrend** / **Uptrend under pressure** / **Correction /
  downtrend**. Per user preference, the skill **still delivers** the list in a correction
  but states the status prominently and switches to higher-risk framing (tighter 3% stops,
  "watchlist to buy on the next follow-through" tone).

---

## Step 2 — Per-candidate technical data (IBKR)

For each candidate `contract_id`:

**a) `get_price_snapshot`** — request fields incl. `last`, `change`, `year_to_date_change`,
`misc_statistics` (52-week + 13/26-week high/low), and any average-volume fields. Response
keys are **hyphenated**; vol values are fractions (×100 for %). From this:
- **% off 52-week high** = `(52wk_high − last) / 52wk_high`. Near a new high (within ~0–15%)
  is what N wants; a stock near its 52-week *low* is disqualified (avoid the new-low list).
- Price-range filter (≥ $15 Nasdaq / $20 NYSE; flag < $10).

**b) `get_price_history`** for the technical work:
- **Weekly, one year+** (`step: "ONE_WEEK", period: "ONE_YEAR"` or `TWO_YEARS`) → base
  detection: identify the most recent consolidation, its depth (peak-to-trough %), length
  (weeks), whether price is emerging near the top of it, and whether the pattern is tight vs.
  wide-and-loose. Map to the base types in `canslim-methodology.md`.
- **Daily, ~14 months** (`step: "ONE_DAY", step_count: ~300`, or `period: "TWO_YEARS"`) —
  **not** `SIX_MONTHS`/`ONE_YEAR`. The **pivot/breakout check** only reads the recent tail —
  **breakout volume** (latest up-day volume vs. ~50-day average; want ≥ +40–50%), volume
  dry-ups near base lows, and distance past any pivot (avoid > 5–10% extended) — but the RS
  proxy below needs a full 12 months of bars, so pull one longer daily series and reuse it.
- **Relative Strength proxy** (see script): compute the candidate's price return over 3, 6,
  and 12 months and compare to SPY over the same windows. **The 12-month leg needs > 252 daily
  bars**, so `SIX_MONTHS` (~126) silently nulls the 6- *and* 12-month legs, and `ONE_YEAR`
  (~251) falls just short of the 12-month window — pull ~14 months (`step_count ~300`) for
  **both** the candidate **and SPY**. A true full-market 1–99 RS needs the whole
  market; instead **rank candidates against each other** on 12-month (weighted toward
  recent) relative return, and keep the top performers (target the equivalent of RS ≥ 80:
  clearly outperforming SPY and in the top tier of the candidate set). Reject names lagging
  SPY over 6–12 months. If `rs_relative_return.12m` comes back `null`, you pulled too few daily
  bars — refetch with more history before ranking.

Use `scripts/relative_strength.py` to turn the OHLCV JSON into these metrics deterministically
rather than eyeballing bars. **Prefer the Massive connector's `/v2/aggs` daily bars (by ticker,
no `contract_id`) as the RS input** — it yields a true point-to-point 12-month RS; the 200-day-MA
ratio some quote feeds expose is only a rough proxy and can badly understate a leader that
round-tripped through a base (e.g. ANET measured +47 true vs +18 on the proxy). See the Massive
subsection above.

---

## Step 3 — Per-candidate fundamentals (prefer data connectors over web search)

The fundamental letters — **C** (quarterly EPS & sales), **A** (annual EPS, ROE, margins),
and the ownership half of **I** — need real reported financials. IBKR does not supply these,
so use the best source that is actually connected, **in this order of preference**. Only fall
back to generic web search when none of the better sources are available. Do the deep
research only for finalists that already survived the technical cut.

**Fundamental source priority (use the highest one that's connected):**

1. **Daloopa** (`daloopa:*` skills, e.g. `daloopa:tearsheet`, `daloopa:industry`, the model
   builders) — audited, model-ready quarterly & annual financials plus operating KPIs. Best
   for the exact EPS / sales / margin / ROE growth figures and the multi-year history behind
   **C** and **A**.
2. **bigdata.com** (`bigdata-com:*`, e.g. `company-brief`, `earnings-digest`,
   `earnings-quality-screen`, `valuation-snapshot`) — latest-quarter beat / acceleration /
   guidance for **C**, an earnings-quality read that catches the "earnings up but sales flat /
   weak cash conversion" trap, and the **N** story.
3. **LSEG** (`lseg:*`, e.g. `lseg:equity-research`) — analyst **consensus estimates** and
   fundamentals: next-year EPS estimate (part of **A**), plus estimate revisions and surprise
   history (the acceleration signal in **C**).
4. **SEC EDGAR / official filings** — the authoritative primary statements (10-K / 10-Q /
   20-F / annual reports). Reach them via the **`securities-filings-lookup`** skill, which
   resolves the ticker's exchange/regulator and pulls the official filing (also covers non-US
   listings: HKEX, CNINFO, TWSE, LSE, EDINET, Frankfurt). Use for ground-truth income
   statement / balance sheet / cash flow, and for **I** (13F institutional ownership, Form 4
   management ownership).
5. **Financial Modeling Prep (FMP)** — a structured fundamentals MCP (deferred; load its tools
   with `ToolSearch`). **Deliberately the lowest-priority connector:** on lower-tier plans it is
   heavily gated *and* throttled — bursts of calls return `ACCESS DENIED ... requires a higher
   plan` even for endpoints that worked moments earlier — so it is unreliable as a primary
   fundamentals source. Prefer the higher rungs above; reach for FMP mainly as a **cheap breadth
   cross-check** or when the higher rungs are not connected. Probe cheaply and drop to web (rung
   6) for whatever's gated. What tends to work on lower tiers, and how to use it:
   - **`quote` → `batch-quote`** (the workhorse): one call takes a symbol array and returns, per
     name, `price`, `yearHigh`/`yearLow`, `priceAvg50`/`priceAvg200`, `volume`, `marketCap`.
     That single call gives you **% off 52-wk high** and **50/200-day trend** for a whole
     candidate list — a very token-efficient first-pass screen (compute off-high = `(yearHigh -
     price)/yearHigh`; require price above both MAs). Use it before spending per-name IBKR calls.
   - **`search` → `search-company-screener`** — the sector/size/liquidity screener (see Step 0).
   - **`company` → `profile-symbol`** — sector, industry, **IPO date** (New America / **N**),
     employees, market cap, business description (the **N** story). Usually available.
   - **`quote` → `quote-change`** — 1M/3M/6M/1Y/… performance windows; when available this is a
     cheap RS input (compare each name's 6-/12-mo change to SPY's). **Often premium-gated** — if
     denied, get RS from IBKR weekly/daily bars via `scripts/relative_strength.py` instead.
   - **Premium / commonly gated:** `statements` (income / growth / ratios), `analyst`
     (estimates, grades, targets), `form13F` + `insiderTrades`, `earningsTranscript`,
     `discountedCashFlow`. When these are gated, the **C**/**A** earnings figures and **I**
     ownership come from the official filings (rung 4) or web research (rung 6) instead.
   IBKR tickers vs FMP symbols line up for US names; IBKR name-search is unreliable, so resolve
   IBKR `contract_id`s by **ticker**, not company name.
6. **General web search** — the universal fallback when the connected sources above cannot
   answer (gated, throttled, or not connected).

**Handling gated / throttled / unavailable sources — fall through the ladder, never abandon a
letter.** These connectors (Daloopa, bigdata.com, LSEG, FMP) only work if the user has
authorized/keyed them, and access is frequently **partial** (some endpoints only) or
**intermittent** (throttling). Treat **any** of the following as "this source cannot answer
*this* call right now" and immediately try the **next source down the ladder** for that same
data point — do not stop at the first gate:
- **explicit gating** — `ACCESS DENIED ... requires a higher plan`, `unauthorized`, `not
  entitled`, or any upgrade prompt;
- **throttling / rate-limiting** — the *same* call fails right after succeeding, or a burst of
  parallel calls mostly fails. On FMP this often surfaces as the *same* "requires a higher
  plan" message, so treat a wave of denials as possible throttling: space the calls out and
  retry once before concluding the endpoint is truly gated;
- **empty / `null` / timeout / obviously stale** responses.

Rules for falling through:
1. **Gating is per-endpoint and per-source, not all-or-nothing.** One FMP endpoint being gated
   (e.g. `statements`, `analyst`) does not mean `quote`/`profile` are — keep using whatever a
   source *does* answer and fill only the gaps from lower rungs. Probe the cheap endpoints first.
2. **Fall through for every letter independently.** If Daloopa/bigdata are absent and FMP
   `statements` is gated, get **C**/**A** from SEC EDGAR (via `securities-filings-lookup`) or web
   rather than skipping them. If FMP `quote-change`/`batch-quote` is gated, get RS and % off high
   from IBKR bars via `scripts/relative_strength.py` (the default technical path anyway).
3. **Never block the run or leave a letter blank because the top source is gated.** Walk the
   ladder all the way down to general web search; only if *every* rung fails do you mark the
   field `n/a` and lower confidence for that name.
4. **Always record which source each figure came from and timestamp it** (sources differ in lag
   and revision). Obey copyright (paraphrase; short quotes only).

**Deep single-ticker dive.** When a candidate is borderline, a sell-off needs explaining, or
the user asks to look closer at one name, delegate to the **`ibkr-review-ticker`** skill — it
builds a full single-stock dashboard (fundamentals vs. peers, valuation, options/vol,
probability outlook) and pulls the official financials for further analysis. For the raw
filing **PDFs**, use `securities-filings-lookup`. **If a companion skill you need is not
installed, don't silently skip it** — tell the user and point them to its GitHub repo to
install (see SKILL.md "Delegating for deeper financials & required companion skills" for the
repo URLs and an example prompt), then continue with the best available source.

Whichever source you use, gather:
- **C:** last 2–3 quarters' **EPS growth YoY** and **sales growth YoY**; is growth
  accelerating? margins improving? Exclude one-time items.
- **A:** **annual EPS** last 3 years (up each year? growth rate?), **ROE**, profit margins,
  next-year consensus estimate.
- **N:** the "new" story — product/service, new management, new industry conditions; IPO
  recency (New America).
- **I:** number/trend of institutional owners; any top-tier funds adding; over-owned?
  (institutional ownership %, recent 13F buying).
- **S extras:** shares outstanding / float, buybacks, debt/equity, management ownership.

If data is unavailable from every source, mark the field "n/a" and lower confidence rather
than guessing.

---

## Step 4 — Score, filter, diversify

1. **Hard filters (disqualify):** price < $10; near 52-week low / RS lagging SPY; annual or
   quarterly EPS declining; no earnings; wide-loose/late-stage-only base; illiquid.
2. **CAN SLIM score:** rate each of C, A, N, S, L, I against the thresholds in
   `canslim-methodology.md` (e.g., pass/partial/fail), plus the M context. Rank by how many
   criteria are strongly met, weighting C, A (earnings) and L (RS/leadership) most heavily —
   these are the method's most predictive factors.
3. **Sector non-overlap:** use `get_company_themes { contract_id }` to get each finalist's
   sectors/trends. Enforce diversification: **cap how many names share the same industry
   group/sector** (aim ≤ 2–3 per group for a 20-name list) so the watchlist isn't, e.g., 15
   semiconductors. Keep the highest-scoring name(s) per group and drop weaker duplicates.
4. Produce the requested count (default 20). **If fewer than requested qualify, return
   fewer and explain** — never pad with weak names (user preference; faithful to "buy only
   the best merchandise").

---

## Notes & guardrails
- **Never** display or store contract IDs, expiration IDs, account numbers, positions, or
  any account-bound data. Present stocks by symbol/name only.
- Market-data entitlements follow the account; delayed data is fine — **timestamp** the
  output.
- If IBKR tools are missing/unauthorized/time out, fall back to web-sourced figures for that
  candidate and say so; don't block the whole run.
- This is **decision support, not advice.** No order placement, no personalized
  buy/sell/allocation directives.
```


## `scripts/check_for_updates.py`

Step 0: is this copy current? Compares the checkout against its remote, separates code (effective this run) from instructions (effective next run), and fails open when it cannot check.

```python
#!/usr/bin/env python3
"""
check_for_updates.py - step 0: is this copy of the skill current?

The skill is iterated on constantly, and a stale checkout fails SILENTLY - it produces a
plausible-looking report built by last month's rules. So every run starts here.

WHAT AN UPDATE CAN AND CANNOT FIX MID-RUN. This is the whole reason the script reports two
groups rather than one number:

  scripts/ and assets/   READ FROM DISK when they run. Updating them takes effect THIS RUN -
                         the new sector_screen.py and the new dashboard template are what
                         actually execute.
  SKILL.md, references/  READ INTO CONTEXT when the skill is invoked, before this script runs.
                         Updating the files on disk does NOT replace the instructions already
                         guiding this run; those land on the NEXT invocation.

So "always use the newest version" is achievable for the code and only partly for the
instructions. When the instructions are the part that moved, the honest move is to say so and
let the user decide whether to re-invoke - never to imply the run picked them up.

FAILS OPEN, ALWAYS. No git, no network, no remote, a fetch that times out - none of these stop
a run. The script says what it could not check and exits 0. A skill that refuses to work
offline is worse than one that works on a possibly-stale copy and says so.

NEVER AUTO-PULLS OVER YOUR WORK. `--update` refuses to touch a dirty tree or a diverged branch;
it reports and leaves the decision to you. Uncommitted local changes are someone's work in
progress, not garbage to be overwritten.

Usage:
  python scripts/check_for_updates.py              # report only (what step 0 runs)
  python scripts/check_for_updates.py --update     # also fast-forward when it is safe to
  python scripts/check_for_updates.py --json       # machine-readable verdict
  python scripts/check_for_updates.py --timeout 20 # network patience, seconds (default 15)

Exit status is 0 for "current", "behind", and every can't-check case - the run continues either
way. It is 1 only when --update was asked for and the update itself failed.
Pure standard library.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Which half of the skill a changed path belongs to - see the module docstring.
LIVE_PREFIXES = ("scripts/", "assets/")


def git(*args, **kw):
    """Run a git command in the skill root. Returns (ok, output). Never raises.

    On failure the output is git's STDERR - git writes "could not resolve host", "repository not
    found" and every other diagnosis there, and a failure message that cannot say why is useless
    to whoever has to fix it.
    """
    try:
        p = subprocess.run(("git", "-C", ROOT) + args, capture_output=True, text=True,
                           timeout=kw.get("timeout", 15))
        if p.returncode == 0:
            return True, (p.stdout or "").strip()
        return False, ((p.stderr or "") + (p.stdout or "")).strip()
    except FileNotFoundError:
        return False, "git is not installed on this host"
    except subprocess.TimeoutExpired:
        return False, "git timed out after %ss" % kw.get("timeout", 15)
    except Exception as e:                      # anything else - still never raise
        return False, str(e)


def classify(paths):
    """Split changed paths into what this run will actually pick up and what it will not."""
    live = sorted(p for p in paths if p.startswith(LIVE_PREFIXES))
    ctx = sorted(p for p in paths if not p.startswith(LIVE_PREFIXES))
    return live, ctx


def check(timeout):
    """Return a verdict dict. `status` is one of:
       current | behind | ahead | diverged | no-upstream | not-a-repo | unreachable | no-git
    """
    out = {"status": "unknown", "branch": None, "behind": 0, "ahead": 0,
           "changed_live": [], "changed_context": [], "detail": "", "can_fast_forward": False,
           "dirty": False}

    ok, why = git("rev-parse", "--git-dir")
    if not ok:
        # Two very different situations that must not share a message: git absent (the copy may
        # be perfectly current, we simply cannot look) vs. a real non-checkout (a zip export).
        if "not installed" in why or "not found" in why or "No such file" in why:
            out["status"] = "no-git"
            out["detail"] = ("git is not available on this host, so the version cannot be checked "
                             "- this copy may or may not be current. Continue, and say in the "
                             "report that the version could not be verified.")
        else:
            out["status"] = "not-a-repo"
            out["detail"] = ("this copy of the skill is not a git checkout (a zip export, a "
                             "vendored copy, or another assistant's upload), so there is nothing "
                             "to compare against. Continue, and say in the report that the "
                             "version could not be verified.")
        return out

    ok, branch = git("rev-parse", "--abbrev-ref", "HEAD")
    out["branch"] = branch if ok else None

    ok, st = git("status", "--porcelain")
    out["dirty"] = bool(ok and st)

    ok, upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if not ok or not upstream:
        out["status"] = "no-upstream"
        out["detail"] = ("the current branch tracks no remote, so there is no newer version to "
                         "compare against. Continue.")
        return out

    remote = upstream.split("/", 1)[0]
    ok, err = git("fetch", "--quiet", remote, timeout=timeout)
    if not ok:
        out["status"] = "unreachable"
        out["detail"] = ("could not reach '%s' (%s). The network may be down or the remote may be "
                         "private to another host. Continue on this copy and say in the report "
                         "that the version could not be verified." % (remote, err.splitlines()[0] if err else "no detail"))
        return out

    ok, counts = git("rev-list", "--left-right", "--count", "HEAD...@{u}")
    if not ok:
        out["status"] = "unreachable"
        out["detail"] = "fetched, but could not compare against %s. Continue." % upstream
        return out
    try:
        ahead, behind = (int(x) for x in counts.split())
    except ValueError:
        ahead = behind = 0
    out["ahead"], out["behind"] = ahead, behind

    # Only list files when there is something INCOMING. `git diff HEAD @{u}` is symmetric, so on
    # an "ahead" branch it would list the run's own unpushed edits under a heading promising new
    # upstream code - the opposite of what is true.
    if behind:
        ok, names = git("diff", "--name-only", "HEAD", "@{u}")
        paths = [p for p in names.splitlines() if p.strip()] if ok else []
        out["changed_live"], out["changed_context"] = classify(paths)

    if behind and ahead:
        out["status"] = "diverged"
        out["detail"] = ("local and %s have both moved on (%d local commit(s), %d remote). A "
                         "fast-forward is not possible; this needs a human to merge or rebase. "
                         "Continue on this copy and say so in the report." % (upstream, ahead, behind))
    elif behind:
        out["status"] = "behind"
        out["can_fast_forward"] = not out["dirty"]
        out["detail"] = "%d commit(s) behind %s." % (behind, upstream)
        if out["dirty"]:
            out["detail"] += (" The working tree has uncommitted changes, so this will NOT be "
                              "updated automatically - that would overwrite someone's work. "
                              "Commit or stash first.")
    elif ahead:
        out["status"] = "ahead"
        out["detail"] = ("%d local commit(s) not yet pushed. This copy is newer than the remote; "
                         "nothing to pull." % ahead)
    else:
        out["status"] = "current"
        out["detail"] = "up to date with %s." % upstream
    return out


def do_update(v, timeout):
    """Fast-forward only, and only when check() already said it is safe. Returns (ok, message)."""
    if v["status"] != "behind":
        return True, "nothing to update (%s)" % v["status"]
    if v["dirty"]:
        return False, ("refused: the working tree has uncommitted changes. Commit or stash them, "
                       "then re-run. Pulling over local work is never the right default.")
    ok, out = git("merge", "--ff-only", "@{u}", timeout=timeout)
    if not ok:
        return False, "fast-forward failed: %s" % (out.splitlines()[0] if out else "no detail")
    return True, "fast-forwarded %d commit(s)." % v["behind"]


def render(v, updated=None):
    L = []
    head = {"current": "Skill is current",
            "behind": "Skill is OUT OF DATE",
            "ahead": "Skill is ahead of the remote",
            "diverged": "Skill has DIVERGED from the remote",
            "no-upstream": "Version not verified - no upstream",
            "not-a-repo": "Version not verified - not a git checkout",
            "unreachable": "Version not verified - remote unreachable",
            "no-git": "Version not verified - git unavailable",
            }.get(v["status"], "Version check inconclusive")
    L.append("%s%s" % (head, (" (%s)" % v["branch"]) if v["branch"] else ""))
    L.append("  " + v["detail"])

    if v["changed_live"]:
        L.append("  Code that changed - THIS RUN WILL USE THE NEW VERSION once updated:")
        for p in v["changed_live"]:
            L.append("      %s" % p)
    if v["changed_context"]:
        L.append("  Instructions that changed - ALREADY LOADED, so this run keeps the OLD ones:")
        for p in v["changed_context"]:
            L.append("      %s" % p)
        L.append("      -> re-invoke the skill after updating to pick these up, or tell the user "
                 "the run used the previous instructions.")
    if updated is not None:
        L.append("  Update: %s" % updated)
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update", action="store_true",
                    help="fast-forward to the remote when it is safe (clean tree, not diverged)")
    ap.add_argument("--json", action="store_true", help="machine-readable verdict")
    ap.add_argument("--timeout", type=float, default=15.0,
                    help="seconds to wait on the network (default %(default)s)")
    a = ap.parse_args()

    v = check(a.timeout)
    msg = None
    if a.update:
        ok, msg = do_update(v, a.timeout)
        if ok and v["status"] == "behind" and not v["dirty"]:
            # Re-read so the verdict reflects the update. Keep the fresh detail ("up to date
            # with ...") - the fast-forward itself is reported once, on the Update line.
            v = check(a.timeout)
    if a.json:
        v["update_message"] = msg
        print(json.dumps(v, indent=2))
    else:
        print(render(v, msg))
    # Fail open: only an update that was asked for and did not work is an error.
    return 1 if (a.update and msg and msg.startswith(("refused", "fast-forward failed"))) else 0


if __name__ == "__main__":
    sys.exit(main())
```


## `scripts/sector_screen.py`

Sector-sweep arithmetic and CAN SLIM triage over the screener rows.

```python
#!/usr/bin/env python3
"""
sector_screen.py - turn TradingView `run_screener` rows into the sector sweep + CAN SLIM triage.

Stage B/C1 of the skill runs one `run_screener` call per sector (top N performers over the
chosen window) and feeds every returned row straight into this script. It does the arithmetic
deterministically so a run never eyeballs percentages:

  - % off the 52-week high         (N wants new-high ground; a deep discount is overhead supply)
  - RS vs the benchmark            (L: window performance minus SPY's over the SAME window)
  - price vs the 50/200-day EMA    (N/L trend gate)
  - average dollar volume          (S: institutional-grade liquidity)
  - a per-name TRIAGE verdict      - `grade` (send to can-slim-grader) or `drop` + the reasons
  - a per-sector RANK              - by the median window performance of its top-N members,
    with the count that survived triage (this is what "top sector" means downstream)

It never invents data: a field the screener did not return comes back `null` and any check
that depends on it is skipped (and named in `checks_skipped`), so a missing column can never
silently pass or fail a name.

INPUT: a JSON file (or stdin) shaped like:
{
  "asOf":   "2026-08-21 (close)",            # optional, echoed through
  "window": "Perf.6M",                       # the ranking column used in the screener calls
  "benchmark": {"symbol": "AMEX:SPY", "perf": {"Perf.6M": 12.4, "Perf.Y": 18.0}},
  "sectors": {
    "Electronic Technology": [ <run_screener row>, <run_screener row>, ... ],
    "Health Technology":     [ ... ]
  }
}
`sectors` may also be a list of {"sector": "...", "rows": [...]}. Each row is a raw
TradingView screener row - pass it through untouched; the keys used are `symbol`/`name`,
`description`, `close`, the window column, `price_52_week_high`, `EMA50`, `EMA200`,
`average_volume_10d_calc` (or `average_volume_90d_calc`), `relative_volume_10d_calc`,
`market_cap_basic`, `industry` and `earnings_release_next_date`.

OUTPUT: JSON to stdout - `sectors` (ranked, each with its scored members) plus a flat
`grade_queue` (every name that survived triage, strongest RS first) which is the exact list
to hand to `can-slim-grader`. `--md` prints a compact markdown view instead.

Usage:
  python sector_screen.py sweep.json
  python sector_screen.py sweep.json --md
  cat sweep.json | python sector_screen.py --top 10 --min-price 15 --min-dollar-vol 20e6
Pure standard library.
"""
import argparse
import json
import statistics
import sys

# CAN SLIM hard filters (methodology defaults; override on the command line).
DEFAULTS = {
    "top": 10,              # members kept per sector - "the top 10 performers in each sector"
    "fallback": 5,          # names surfaced for a sector that produced no qualifier
    "min_price": 15.0,      # no cheap stock; the method's price floor
    "min_dollar_vol": 20e6, # average daily $ volume - institutions need liquidity (S)
    "min_market_cap": 1e9,  # skip microcaps the method's sponsorship test can't clear
    "max_off_high": 25.0,   # % below the 52-week high beyond which there is no new-high ground
    "min_rs": 0.0,          # must beat the benchmark over the window (L: leader not laggard)
    "threshold": 4.5,       # the recommendation cut, out of 7 - the ceiling is measured against it
    "m_grade": "partial",   # M is graded ONCE market-wide, before any name; it bounds every row
    "i_grade": "partial",   # I is routinely unavailable, which caps every row - say so, never guess
    "pivot_band": 10.0,     # % below the 52-week high beyond which there is no pivot, so N <= partial
    "thin_vol": 0.8,        # relative volume under this is drying up, not accumulating, so S = fail
}

WEIGHT = {"pass": 1.0, "partial": 0.5, "fail": 0.0}

VOL_KEYS = ("average_volume_10d_calc", "average_volume_90d_calc", "average_volume_30d_calc",
            "average_volume_60d_calc", "volume")


def f(row, *keys):
    """First present, numeric value among `keys`; None when absent/blank/non-numeric."""
    for k in keys:
        v = row.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def money(v):
    """$1.2B / $250M / $400k - so a $1e9 floor never prints as "$1000M"."""
    v = float(v)
    for unit, size in (("B", 1e9), ("M", 1e6), ("k", 1e3)):
        if abs(v) >= size:
            n = v / size
            return "$%.0f%s" % (n, unit) if abs(n) >= 10 or n == int(n) else "$%.1f%s" % (n, unit)
    return "$%.0f" % v


def pct_off_high(close, high):
    if close is None or not high:
        return None
    return (close / high - 1.0) * 100.0


def pct_vs(close, level):
    if close is None or not level:
        return None
    return (close / level - 1.0) * 100.0


def score_row(row, window, bench_perf, cfg):
    """Compute the derived metrics + triage verdict for one screener row."""
    sym = row.get("symbol") or row.get("name") or "?"
    close = f(row, "close", "price")
    perf = f(row, window)
    high52 = f(row, "price_52_week_high", "High.All")
    low52 = f(row, "price_52_week_low")
    ema50 = f(row, "EMA50")
    ema200 = f(row, "EMA200")
    avgvol = f(row, *VOL_KEYS)
    mcap = f(row, "market_cap_basic")

    off_high = pct_off_high(close, high52)
    dollar_vol = close * avgvol if (close is not None and avgvol is not None) else None
    rs = (perf - bench_perf) if (perf is not None and bench_perf is not None) else None

    out = {
        "symbol": sym,
        "ticker": (row.get("name") or str(sym).split(":")[-1]),
        "company": row.get("description") or "",
        "sector": row.get("sector") or "",
        "industry": row.get("industry") or "",
        "close": close,
        "window": window,
        "window_perf_pct": perf,
        "bench_perf_pct": bench_perf,
        "rs_vs_bench_pts": rs,
        "high_52w": high52,
        "low_52w": low52,
        "off_high_pct": off_high,
        "vs_ema50_pct": pct_vs(close, ema50),
        "vs_ema200_pct": pct_vs(close, ema200),
        "avg_volume": avgvol,
        "avg_dollar_volume": dollar_vol,
        "rel_volume_10d": f(row, "relative_volume_10d_calc"),
        "market_cap": mcap,
        "next_earnings": row.get("earnings_release_next_date"),
    }

    # --- triage: the method's hard disqualifiers, each only applied when its data exists ---
    drops, flags, skipped = [], [], []

    def check(value, name, fail, reason):
        if value is None:
            skipped.append(name)
        elif fail:
            drops.append(reason)

    check(close, "price", close is not None and close < cfg["min_price"],
          "price below the %.0f floor (cheap stock)" % cfg["min_price"])
    check(dollar_vol, "liquidity", dollar_vol is not None and dollar_vol < cfg["min_dollar_vol"],
          "average dollar volume under %s - too thin for institutional sponsorship (S)"
          % money(cfg["min_dollar_vol"]))
    check(mcap, "market_cap", mcap is not None and mcap < cfg["min_market_cap"],
          "market cap under %s" % money(cfg["min_market_cap"]))
    # off_high is negative below the high; print its magnitude or the text reads "-33% below".
    check(off_high, "off_high", off_high is not None and off_high < -cfg["max_off_high"],
          "%.0f%% below the 52-week high - no new-high ground, overhead supply (N)"
          % abs(off_high or 0))
    check(rs, "rs", rs is not None and rs <= cfg["min_rs"],
          "window performance lags the benchmark - laggard, not leader (L)")
    v200 = out["vs_ema200_pct"]
    check(v200, "ema200", v200 is not None and v200 < 0,
          "trading below the 200-day EMA - downtrend (N/L)")

    # --- flags: context for the grader, never a pass/fail on their own ---
    if off_high is not None and off_high >= -8.0:
        flags.append("within 8% of the 52-week high - new-high ground")
    if out["vs_ema50_pct"] is not None and out["vs_ema50_pct"] > 25.0:
        flags.append("more than 25% above the 50-day EMA - extended, likely past a pivot")
    if out["rel_volume_10d"] is not None and out["rel_volume_10d"] >= 1.4:
        flags.append("relative volume %.1fx - accumulation (S)" % out["rel_volume_10d"])
    if out["vs_ema50_pct"] is not None and out["vs_ema200_pct"] is not None \
            and out["vs_ema50_pct"] > 0 and out["vs_ema200_pct"] > 0:
        flags.append("above both the 50- and 200-day EMA")

    out["triage"] = "drop" if drops else "grade"
    out["drop_reasons"] = drops
    out["flags"] = flags
    out["checks_skipped"] = skipped
    return out


def ceiling(out, cfg, known=None):
    """The HIGHEST score this name could still reach - so a name can be eliminated without
    grading it, and one that cannot be eliminated is provably worth the calls.

    The rule the whole two-stage process rests on: grade every candidate whose ceiling reaches
    the cut. Because each letter here is an UPPER bound, a ceiling below the cut means no
    combination of unseen fundamentals could get the name there - it is eliminated by
    arithmetic, not by judgment. Erring high is safe (it only costs calls); erring low would
    silently drop a qualifier, so every cap below is one the grader would actually apply.

    M and I are known before any name is graded - M is graded once market-wide and I is
    routinely unsourceable - so both bound every row from the start. N, S and L are capped
    from screener columns. C and A are assumed PASS until a real grade says otherwise, which
    is what `known` supplies: pass {"A": "fail"} after the A-screen and the ceiling drops
    again, usually far enough to skip the C call entirely.
    """
    known = known or {}
    # Normalise up front: the default M/I reasons below must not be emitted for a letter a real
    # grade is about to replace, or a row whose sponsorship WAS sourced still reads "sponsorship
    # not sourceable this run" next to the grade that sourced it.
    graded = {str(k).strip().upper(): str(v).strip().lower() for k, v in known.items()}
    graded = {k: v for k, v in graded.items() if v in WEIGHT}
    caps, why = {}, []

    # N - no pivot without new-high ground. The 10% band mirrors the dashboard's own audit
    # rule, which rejects a buy point more than 10% under the 52-week high as "a lower high,
    # not a pivot". Past twice that band there is no new-high ground left to grade at all, so
    # the cap is FAIL rather than partial - the grade this run would actually give.
    oh = out["off_high_pct"]
    band = cfg["pivot_band"]
    if oh is None:
        caps["N"] = "pass"
    elif oh < -2 * band:
        caps["N"] = "fail"
        why.append("N = fail: %.0f%% below the 52-week high - no new-high ground at all" % abs(oh))
    elif oh < -band:
        caps["N"] = "partial"
        why.append("N <= partial: %.0f%% below the 52-week high, so there is no pivot" % abs(oh))
    else:
        caps["N"] = "pass"

    # S - relative volume is the accumulation test. At its own norm or better the letter is
    # still open; below it demand is absent, and materially below it (the `thin_vol` floor)
    # the price is rising on drying volume, which is the opposite of what S asks for.
    rv = out["rel_volume_10d"]
    if rv is None:
        caps["S"] = "pass"
    elif rv < cfg["thin_vol"]:
        caps["S"] = "fail"
        why.append("S = fail: relative volume %.2fx - volume drying up under the price" % rv)
    elif rv < 1.0:
        caps["S"] = "partial"
        why.append("S <= partial: relative volume %.2fx - under its own norm, no accumulation" % rv)
    else:
        caps["S"] = "pass"

    # L - a leader of a laggard group is not a leader. Sector rank comes from the sweep, so
    # this is only known once every sector has been ranked.
    sr = out.get("sector_rank_overall")
    tot = out.get("sector_count") or 0
    if sr and tot and sr > tot / 2.0:
        caps["L"] = "partial"
        why.append("L <= partial: sector ranks #%d of %d - leader of a laggard group" % (sr, tot))
    else:
        caps["L"] = "pass"

    caps["C"] = "pass"   # unknown until the quarter is pulled
    caps["A"] = "pass"   # unknown until get_financials is pulled
    caps["M"] = cfg["m_grade"]
    caps["I"] = cfg["i_grade"]
    if cfg["m_grade"] != "pass" and "M" not in graded:
        why.append("M = %s: graded once market-wide, so it bounds every row" % cfg["m_grade"])
    if cfg["i_grade"] != "pass" and "I" not in graded:
        why.append("I <= %s: sponsorship not sourceable this run" % cfg["i_grade"])

    # a real grade always overrides the assumption
    for k, v in graded.items():
        if k in caps:
            # Recorded even when the grade MATCHES the assumption it replaces. "I = partial
            # (graded)" and "I <= partial: sponsorship not sourceable" are the same number and
            # completely different evidence - one was measured, the other is an admission - and
            # the report has to be able to tell them apart.
            why.append("%s = %s (graded)" % (k, v))
            caps[k] = v

    total = round(sum(WEIGHT[caps[k]] for k in ("C", "A", "N", "S", "L", "I", "M")) * 2) / 2.0
    out["ceiling"] = total
    out["ceiling_caps"] = caps
    out["ceiling_reasons"] = why
    out["ceiling_known"] = {k.upper(): str(v).lower() for k, v in known.items()}
    out["grade_required"] = total >= cfg["threshold"]
    return out


def normalize_sectors(blob):
    """Accept either {"sectors": {name: [rows]}} or {"sectors": [{"sector","rows"}]}."""
    sec = blob.get("sectors") or {}
    if isinstance(sec, dict):
        return [(k, v or []) for k, v in sec.items()]
    return [(s.get("sector") or s.get("name") or "?", s.get("rows") or s.get("results") or [])
            for s in sec]


def run(blob, cfg, known=None):
    window = blob.get("window") or "Perf.6M"
    bench = blob.get("benchmark") or {}
    bench_perf = None
    bp = bench.get("perf")
    if isinstance(bp, dict):
        bench_perf = bp.get(window)
    elif bp is not None:
        bench_perf = bp
    try:
        bench_perf = float(bench_perf) if bench_perf is not None else None
    except (TypeError, ValueError):
        bench_perf = None

    sectors = []
    for name, rows in normalize_sectors(blob):
        # the screener already sorted by the window column, but re-sort so a hand-assembled
        # or re-ordered payload still yields the true top N performers.
        scored = [score_row(r, window, bench_perf, cfg) for r in rows]
        scored.sort(key=lambda d: (d["window_perf_pct"] is None, -(d["window_perf_pct"] or 0)))
        members = scored[:cfg["top"]]
        for i, m in enumerate(members, 1):
            m["sector_rank"] = i
        perfs = [m["window_perf_pct"] for m in members if m["window_perf_pct"] is not None]
        keep = [m for m in members if m["triage"] == "grade"]
        sectors.append({
            "sector": name,
            "members_considered": len(scored),
            "members": members,
            "median_perf_pct": statistics.median(perfs) if perfs else None,
            "mean_perf_pct": statistics.mean(perfs) if perfs else None,
            "breadth_pass_pct": (100.0 * len(keep) / len(members)) if members else None,
            "survivors": len(keep),
            # The sector's top `fallback` names in the screener's own ranking, ready to paste into
            # CONFIG.sectors[].top5. The dashboard shows these ONLY for a sector that produced no
            # qualifier, so a reader still sees what led the group - clearly marked as an ungraded
            # performance ranking, never as a recommendation.
            "top5": [{
                "symbol": m["symbol"], "ticker": m["ticker"], "company": m["company"],
                "sectorRank": m["sector_rank"], "perf": m["window_perf_pct"],
                "rs": m["rs_vs_bench_pts"], "offHigh": m["off_high_pct"],
                "triage": m["triage"],
                "note": ("cleared triage" if m["triage"] == "grade"
                         else "dropped: " + "; ".join(m["drop_reasons"])),
            } for m in members[:cfg["fallback"]]],
        })

    sectors.sort(key=lambda s: (s["median_perf_pct"] is None, -(s["median_perf_pct"] or 0)))
    for i, s in enumerate(sectors, 1):
        s["rank"] = i
        for m in s["members"]:
            m["sector_rank_overall"] = i

    # The ceiling needs the finished sector ranking (L depends on group strength), so it runs
    # only once every sector has been placed - never inside score_row.
    known = known or {}
    for s in sectors:
        for m in s["members"]:
            m["sector_count"] = len(sectors)
            if m["triage"] == "grade":
                ceiling(m, cfg, known.get(m["symbol"]) or known.get(m["ticker"]))
            else:                       # already disqualified; a ceiling would only confuse
                m["ceiling"] = None
                m["grade_required"] = False
        s["must_grade"] = sum(1 for m in s["members"] if m.get("grade_required"))

    queue = [m for s in sectors for m in s["members"] if m["triage"] == "grade"]
    # Highest ceiling first, then RS - the order that finds qualifiers soonest if a run is
    # interrupted, and the order the coverage rule expects the calls to be spent in.
    queue.sort(key=lambda d: (-(d.get("ceiling") or 0),
                              d["rs_vs_bench_pts"] is None, -(d["rs_vs_bench_pts"] or 0)))
    must = [m for m in queue if m.get("grade_required")]

    return {
        "asOf": blob.get("asOf"),
        "window": window,
        "benchmark": {"symbol": bench.get("symbol"), "perf_pct": bench_perf},
        "filters": cfg,
        "sector_count": len(sectors),
        "graded_candidates": len(queue),
        "dropped": sum(len(s["members"]) for s in sectors) - len(queue),
        # The coverage contract, in three numbers the report has to echo: how many survivors
        # could still reach the cut (every one of these MUST be graded), how many the ceiling
        # ruled out, and what the cut is. A run that grades fewer than must_grade has not
        # finished, and the dashboard's self-audit refuses it.
        "threshold": cfg["threshold"],
        "must_grade": len(must),
        "eliminated_by_ceiling": len(queue) - len(must),
        "ceiling_basis": {"M": cfg["m_grade"], "I": cfg["i_grade"],
                          "pivot_band_pct": cfg["pivot_band"],
                          "thin_vol": cfg["thin_vol"]},
        "sectors": sectors,
        "grade_queue": [{"symbol": m["symbol"], "ticker": m["ticker"], "sector": m["sector"] or "",
                         "sector_rank": m["sector_rank"], "rs_vs_bench_pts": m["rs_vs_bench_pts"],
                         "off_high_pct": m["off_high_pct"], "ceiling": m.get("ceiling"),
                         "grade_required": m.get("grade_required"),
                         "ceiling_reasons": m.get("ceiling_reasons") or [],
                         "flags": m["flags"]} for m in queue],
    }


def load_known(paths):
    """Merge one or more graded-letter files into the {symbol: {letter: grade}} map run() wants.

    Accepts the bare map AND the {"meta", "known", "detail"} wrapper that institutional_cache.py
    and accumulation.py emit - without the unwrap, passing an I-cache here would look like it
    worked and grade nothing, because every lookup would miss. Later files win on a conflict, so
    the A-screen result can be layered over a quarterly I-cache.
    """
    merged = {}
    for path in paths or []:
        blob = json.loads(open(path, encoding="utf-8").read())
        if isinstance(blob.get("known"), dict):
            blob = blob["known"]
        for sym, letters in blob.items():
            if isinstance(letters, dict):
                merged.setdefault(sym, {}).update(letters)
    return merged


def n(v, dp=1, suffix=""):
    return "-" if v is None else ("%.*f%s" % (dp, v, suffix))


def to_markdown(res):
    L = []
    L.append("# Sector sweep - top %d performers per sector (%s)" % (res["filters"]["top"], res["window"]))
    L.append("")
    L.append("As of %s | benchmark %s %s over the window | %d sectors | %d to grade, %d dropped"
             % (res.get("asOf") or "n/a", res["benchmark"].get("symbol") or "n/a",
                n(res["benchmark"].get("perf_pct"), 1, "%"), res["sector_count"],
                res["graded_candidates"], res["dropped"]))
    L.append("")
    cb = res.get("ceiling_basis") or {}
    L.append("**Grading coverage** - %d of the %d survivors can still reach %s/7 and MUST be graded; "
             "%d are eliminated by ceiling (no combination of unseen fundamentals reaches the cut). "
             "Ceiling assumes M=%s, I<=%s, and C/A pass until graded."
             % (res.get("must_grade", 0), res["graded_candidates"], n(res.get("threshold"), 1),
                res.get("eliminated_by_ceiling", 0), cb.get("M", "?"), cb.get("I", "?")))
    L.append("")
    L.append("| # | Sector | Median perf | Survived triage | Must grade |")
    L.append("|---|---|---:|---:|---:|")
    for s in res["sectors"]:
        L.append("| %d | %s | %s | %d/%d | %d |" % (s["rank"], s["sector"], n(s["median_perf_pct"], 1, "%"),
                                                    s["survivors"], len(s["members"]), s.get("must_grade", 0)))
    L.append("")
    must = [m for m in res["grade_queue"] if m.get("grade_required")]
    if must:
        L.append("## Must grade - %d names, highest ceiling first" % len(must))
        L.append("")
        L.append("| # | Symbol | Sector | Ceiling | RS vs bench | Off 52w high |")
        L.append("|---|---|---|---:|---:|---:|")
        for i, m in enumerate(must, 1):
            L.append("| %d | %s | %s | %s | %s | %s |" % (
                i, m["ticker"], m["sector"], n(m.get("ceiling"), 1),
                n(m["rs_vs_bench_pts"], 1, " pts"), n(m["off_high_pct"], 1, "%")))
        L.append("")
    skip = [m for m in res["grade_queue"] if not m.get("grade_required")]
    if skip:
        L.append("## Eliminated by ceiling - %d names, not graded and why" % len(skip))
        L.append("")
        L.append("| Symbol | Sector | Ceiling | Why it cannot reach the cut |")
        L.append("|---|---|---:|---|")
        for m in skip:
            L.append("| %s | %s | %s | %s |" % (m["ticker"], m["sector"], n(m.get("ceiling"), 1),
                                                "; ".join(m.get("ceiling_reasons") or []) or "-"))
        L.append("")
    for s in res["sectors"]:
        L.append("## %d. %s" % (s["rank"], s["sector"]))
        L.append("")
        L.append("| # | Symbol | Company | Price | Perf | RS vs bench | Off 52w high | vs 50d | vs 200d | Triage |")
        L.append("|---|---|---|---:|---:|---:|---:|---:|---:|---|")
        for m in s["members"]:
            note = "grade" if m["triage"] == "grade" else "drop - " + "; ".join(m["drop_reasons"])
            L.append("| %d | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                m["sector_rank"], m["ticker"], (m["company"] or "")[:34], n(m["close"], 2),
                n(m["window_perf_pct"], 1, "%"), n(m["rs_vs_bench_pts"], 1, " pts"),
                n(m["off_high_pct"], 1, "%"), n(m["vs_ema50_pct"], 1, "%"),
                n(m["vs_ema200_pct"], 1, "%"), note))
        L.append("")
    dry = [s for s in res["sectors"] if not s["survivors"]]
    if dry:
        L.append("## Sectors with no triage survivor - top %d by screener rank (ungraded)" % res["filters"]["fallback"])
        L.append("")
        for s in dry:
            L.append("**%s** - %s" % (s["sector"], ", ".join(
                "%s (%s)" % (t["ticker"], n(t["perf"], 0, "%")) for t in s["top5"])))
        L.append("")
    L.append("## Grade queue (hand these to can-slim-grader, strongest RS first)")
    L.append("")
    L.append(", ".join(q["symbol"] for q in res["grade_queue"]) or "(none survived triage)")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", help="sweep JSON (default: stdin)")
    ap.add_argument("--top", type=int, default=DEFAULTS["top"],
                    help="members kept per sector (default %(default)s)")
    ap.add_argument("--fallback", type=int, default=DEFAULTS["fallback"],
                    help="names per sector emitted as the no-qualifier fallback (default %(default)s)")
    ap.add_argument("--min-price", type=float, default=DEFAULTS["min_price"])
    ap.add_argument("--min-dollar-vol", type=float, default=DEFAULTS["min_dollar_vol"])
    ap.add_argument("--min-market-cap", type=float, default=DEFAULTS["min_market_cap"])
    ap.add_argument("--max-off-high", type=float, default=DEFAULTS["max_off_high"],
                    help="max %% below the 52-week high before a name is dropped (default %(default)s)")
    ap.add_argument("--min-rs", type=float, default=DEFAULTS["min_rs"],
                    help="minimum window performance over the benchmark, in points")
    ap.add_argument("--threshold", type=float, default=DEFAULTS["threshold"],
                    help="the recommendation cut out of 7 (default %(default)s)")
    ap.add_argument("--m-grade", choices=("pass", "partial", "fail"), default=DEFAULTS["m_grade"],
                    help="this run's market grade - graded ONCE and applied to every row, so it "
                         "bounds every ceiling (default %(default)s)")
    ap.add_argument("--i-grade", choices=("pass", "partial", "fail"), default=DEFAULTS["i_grade"],
                    help="the best I any name can reach this run; sponsorship data is routinely "
                         "unavailable, and the cap belongs in the ceiling (default %(default)s)")
    ap.add_argument("--pivot-band", type=float, default=DEFAULTS["pivot_band"],
                    help="%% below the 52-week high past which N cannot pass; past twice it, "
                         "N cannot even reach partial (default %(default)s)")
    ap.add_argument("--thin-vol", type=float, default=DEFAULTS["thin_vol"],
                    help="relative volume under which S cannot pass at all (default %(default)s)")
    ap.add_argument("--known", metavar="FILE", action="append",
                    help='letters already graded, so the ceiling can be re-cut: '
                         '{"NASDAQ:OKTA": {"A": "fail"}}. Re-run with this after the A-screen - '
                         'every name that drops below the threshold is eliminated without '
                         'spending the C call on it. Also takes an I-cache from '
                         'institutional_cache.py or accumulation.py (their {"meta","known",...} '
                         'wrapper is unwrapped automatically). Repeatable; later files win.')
    ap.add_argument("--md", action="store_true", help="print markdown instead of JSON")
    a = ap.parse_args()

    raw = open(a.input).read() if a.input else sys.stdin.read()
    blob = json.loads(raw)
    known = load_known(a.known)
    cfg = {"top": a.top, "fallback": a.fallback, "min_price": a.min_price,
           "min_dollar_vol": a.min_dollar_vol, "min_market_cap": a.min_market_cap,
           "max_off_high": a.max_off_high, "min_rs": a.min_rs, "threshold": a.threshold,
           "m_grade": a.m_grade, "i_grade": a.i_grade, "pivot_band": a.pivot_band,
           "thin_vol": a.thin_vol}
    res = run(blob, cfg, known)
    print(to_markdown(res) if a.md else json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
```


## `scripts/relative_strength.py`

RS proxy, % off the 52-week high, base depth/length, breakout volume, from OHLCV bars.

```python
#!/usr/bin/env python3
"""
relative_strength.py — turn IBKR price-history bars into the technical CAN SLIM metrics.

Computes, deterministically (so every run doesn't re-derive it by eyeballing bars):
  - Relative-strength proxy vs. a benchmark (SPY/QQQ) over 3/6/12 months, and a blended
    RS score weighted toward recent performance.
  - % off the 52-week high (N wants near new highs; reject near new lows).
  - Most-recent base depth & length (weekly bars) and a wide/loose flag.
  - Latest-day breakout volume vs. average (want >= +40-50% on a breakout).

INPUT: a JSON file (or stdin) shaped like:
{
  "benchmark": {"symbol": "SPY", "daily": [[t, o, h, l, c, v], ...]},
  "candidates": [
     {"symbol": "NVDA",
      "daily":  [[t,o,h,l,c,v], ...],   # ~6-12 months of ONE_DAY bars, oldest first
      "weekly": [[t,o,h,l,c,v], ...]},  # ~1-2 years of ONE_WEEK bars, oldest first
     ...
  ]
}
Each bar is [timestamp, open, high, low, close, volume]. `t` may be any monotonic value;
only ordering is used. Missing `weekly` disables base metrics for that name.

OUTPUT: JSON to stdout — per-candidate metrics plus a candidate-set RS rank (1 = strongest).

Usage:
  python relative_strength.py bars.json
  cat bars.json | python relative_strength.py
Pure standard library. If IBKR returns bars in a different shape, adapt the loader; the
math below only needs ordered (close, volume) series.
"""
import json
import sys


def closes(bars):
    return [float(b[4]) for b in bars if b and b[4] is not None]


def volumes(bars):
    return [float(b[5]) for b in bars if b and b[5] is not None]


def _le(t, asof):
    """Is bar-timestamp `t` on/before the as-of cutoff? Numeric when both parse as numbers;
    otherwise ISO-date-aware string compare - a bare YYYY-MM-DD cutoff matches by date prefix so
    the whole as-of day is inclusive (e.g. '2023-01-31T20:00Z' <= '2023-01-31')."""
    try:
        return float(t) <= float(asof)
    except (TypeError, ValueError):
        ts, a = str(t), str(asof)
        return (ts[:10] <= a) if len(a) <= 10 else (ts <= a)


def truncate_asof(bars, asof):
    """Point-in-time: keep only bars dated on/before `asof` (same units as the bar timestamp).
    `asof=None` (the default) keeps everything - i.e. the normal 'as of now' run."""
    if asof is None:
        return bars
    return [b for b in bars if b and _le(b[0], asof)]


def ret_over(series, lookback):
    """Return fractional price change over the last `lookback` bars (e.g. ~63=3mo daily)."""
    if len(series) <= lookback or series[-lookback - 1] == 0:
        return None
    return series[-1] / series[-lookback - 1] - 1.0


def rs_proxy(cand_daily, bench_daily):
    """3/6/12-month relative return vs benchmark + a recency-weighted blend."""
    c, b = closes(cand_daily), closes(bench_daily)
    windows = {"3m": 63, "6m": 126, "12m": 252}
    rel = {}
    for name, lb in windows.items():
        cr, br = ret_over(c, lb), ret_over(b, lb)
        rel[name] = None if cr is None or br is None else round(cr - br, 4)
    # Blend: weight recent more (relative-strength ratings weight the most recent quarter). Skip missing.
    weights = {"3m": 0.40, "6m": 0.35, "12m": 0.25}
    num = sum(weights[k] * rel[k] for k in weights if rel[k] is not None)
    den = sum(weights[k] for k in weights if rel[k] is not None)
    blend = round(num / den, 4) if den else None
    return rel, blend


def pct_off_52w_high(daily):
    c = closes(daily)
    if not c:
        return None
    window = c[-252:] if len(c) >= 252 else c
    hi = max(window)
    if hi == 0:
        return None
    return round((hi - c[-1]) / hi, 4)  # 0.0 = at new high; 0.20 = 20% below


def base_metrics(weekly):
    """Rough most-recent consolidation: scan back from the last bar for the local peak,
    then the trough after it, to estimate depth% and length(weeks). Heuristic, not a
    full pattern classifier — use with the pattern rules in canslim-methodology.md."""
    c = closes(weekly)
    if len(c) < 6:
        return None
    last = c[-1]
    # find highest close in the trailing ~65 weeks that precedes current price action
    look = c[-65:] if len(c) >= 65 else c
    peak_idx = max(range(len(look)), key=lambda i: look[i])
    peak = look[peak_idx]
    trough = min(look[peak_idx:]) if peak_idx < len(look) else last
    depth = round((peak - trough) / peak, 4) if peak else None
    length_weeks = len(look) - peak_idx
    near_high = round((peak - last) / peak, 4) if peak else None
    # wide/loose warning: base deeper than ~35% is suspect (bull-market context)
    wide_loose = depth is not None and depth > 0.35
    return {
        "base_depth_pct": depth,
        "base_length_weeks": length_weeks,
        "pct_below_base_peak": near_high,
        "wide_and_loose_flag": wide_loose,
    }


def breakout_volume(daily, avg_window=50):
    v = volumes(daily)
    if len(v) < avg_window + 1:
        return None
    avg = sum(v[-avg_window - 1:-1]) / avg_window
    if avg == 0:
        return None
    latest = v[-1]
    return round(latest / avg - 1.0, 4)  # 0.5 = +50% above average


def analyze(data):
    # Point-in-time cutoff (optional): compute every metric as of this date, ignoring later bars.
    asof = data.get("asof")
    bench = truncate_asof(data.get("benchmark", {}).get("daily", []), asof)
    out = []
    for cand in data.get("candidates", []):
        daily = truncate_asof(cand.get("daily", []), asof)
        weekly = truncate_asof(cand.get("weekly", []), asof)
        rel, blend = rs_proxy(daily, bench) if bench and daily else ({}, None)
        out.append({
            "symbol": cand.get("symbol"),
            "rs_relative_return": rel,
            "rs_blended": blend,
            "pct_off_52w_high": pct_off_52w_high(daily),
            "breakout_vol_vs_avg": breakout_volume(daily),
            "base": base_metrics(weekly) if weekly else None,
        })
    # rank by blended RS (strongest first); None sorts last
    ranked = sorted(out, key=lambda r: (r["rs_blended"] is None, -(r["rs_blended"] or 0)))
    for i, r in enumerate(ranked, 1):
        r["rs_rank"] = i
    return {"candidates": ranked, "count": len(ranked)}


def main():
    # Optional: --asof <cutoff> for a point-in-time (historical) run. The cutoff must be in the
    # same units as the bar timestamps (epoch, or an ISO date/datetime); a bare YYYY-MM-DD is
    # inclusive of that whole day. Overrides any "asof" key already in the input JSON.
    args = sys.argv[1:]
    asof = None
    path = None
    i = 0
    while i < len(args):
        if args[i] == "--asof" and i + 1 < len(args):
            asof = args[i + 1]
            i += 2
        else:
            path = args[i]
            i += 1
    if path:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)
    if asof is not None:
        data["asof"] = asof
    json.dump(analyze(data), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
```


## `scripts/institutional_cache.py`

Grades I (institutional sponsorship) from SEC Form 13F, aggregated once per quarter and cached. 13F is filed by manager, not by issuer, so this is the aggregation that makes 'who owns it' answerable at all. Fails open to the volume proxy.

```python
#!/usr/bin/env python3
"""
institutional_cache.py - grade I (institutional sponsorship) from SEC Form 13F, cached quarterly.

THE PROBLEM THIS SOLVES. 13F is filed by MANAGER, not by issuer. EDGAR indexes a filing under the
CIK of the fund that filed it, so "who owns NVDA" is not an endpoint anywhere - it is an
aggregation across every filer in the quarter. That is the entire reason ownership data is sold
rather than looked up, and the reason this skill graded I=partial for every name in every run.

THE SHAPE THAT MAKES IT CHEAP. 13F updates four times a year, so paying the aggregation cost once
per quarter and caching the result turns a per-run impossibility into a file read. Run this after
each 13F deadline (45 days past quarter-end: mid-Feb, mid-May, mid-Aug, mid-Nov); the sweep then
reads the cache and spends no network at all on I.

WHAT IT COMPUTES. For every issuer, in two consecutive quarters: the number of distinct managers
holding it, and the total shares they hold. The quarter-over-quarter change in BOTH is what the
rubric actually asks for - "ownership rising over recent quarters", not merely "institutionally
owned". The level alone is free everywhere; this trend is the part that is hard, and it is the
part that grades the letter.

THE CUSIP PROBLEM, STATED HONESTLY. INFOTABLE identifies holdings by CUSIP and issuer NAME - not
by ticker - and there is no free authoritative CUSIP-to-ticker map. So this script resolves
tickers two ways, in order: an explicit map you supply (--cusip-map), then normalised issuer-name
matching against the candidate list from the sweep (--universe). Names that resolve neither way
are reported in `unresolved` rather than silently dropped, because a name missing from the cache
must fall through to the proxy, not be graded on absent data.

FAILS OPEN, ALWAYS. No network, a moved URL, a corrupt zip - none of these stop a run. The script
says what it could not do and exits 0 with an empty cache, and `--fallback` merges in
accumulation.py's volume proxy for every ticker 13F could not answer. Provenance is recorded per
ticker in `detail[t]["source"]`, so the report can say which evidence graded each letter.

Usage:
  # once per quarter, after the 13F deadline
  python institutional_cache.py --quarter 2026Q2 --prior 2026Q1 -o data/i-cache.json
  # resolve tickers using the sweep's own candidate list, and fill gaps with the volume proxy
  python institutional_cache.py --quarter 2026Q2 --prior 2026Q1 \\
      --universe sweep.json --fallback accum.json -o data/i-cache.json
  # then, per run:
  python sector_screen.py sweep.json --known data/i-cache.json --md

OUTPUT: the same three-part shape accumulation.py emits - meta / known / detail - so either can
feed `sector_screen.py --known`.
Pure standard library.
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
import zipfile

DEFAULTS = {
    "thin_holders": 20,     # fewer managers than this is a neglected name, not a sponsored one
    "rising_pct": 2.0,      # shares held must move more than this to count as a real change
    "over_owned_pct": 95.0, # institutions holding more than this of the float leaves no new buyer
}

# The bulk files have lived under two prefixes over the years. Both are tried, in order, and the
# one that answers is recorded in meta - guessing a single URL and reporting "unreachable" when
# it 404s would blame the network for a moved file.
URL_PATTERNS = [
    "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/{q}_form13f.zip",
    "https://www.sec.gov/files/dera/data/form-13f-data-sets/{q}_form13f.zip",
]

# SEC requires a declared User-Agent with contact details and returns 403 without one. This is
# their stated access policy, not an obstacle to route around.
UA = "can-slim-recommend/1.0 (contact: set --contact)"

STOP = re.compile(r"\b(inc|corp|corporation|co|company|ltd|limited|plc|holdings?|group|the|"
                  r"cl|class|a|b|com|common|stock|shs|sa|nv|ag|lp|llc|trust|reit)\b")


def norm_name(s):
    """Normalise an issuer name for matching: case, punctuation and the corporate-suffix noise
    that differs between EDGAR ('NVIDIA CORPORATION') and a screener ('NVIDIA Corp')."""
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = STOP.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def fetch(quarter, contact, timeout, cache_dir=None):
    """Download one quarter's zip. Returns (bytes, url) or (None, why). Never raises."""
    q = quarter.lower()
    if cache_dir:
        local = os.path.join(cache_dir, "%s_form13f.zip" % q)
        if os.path.exists(local) and os.path.getsize(local) > 1000:
            return open(local, "rb").read(), "file://" + local
    why = []
    for pat in URL_PATTERNS:
        url = pat.format(q=q)
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "can-slim-recommend/1.0 (contact: %s)" % contact if contact else UA,
                "Accept-Encoding": "gzip, deflate"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if len(data) < 1000:
                why.append("%s returned %d bytes" % (url, len(data)))
                continue
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
                open(os.path.join(cache_dir, "%s_form13f.zip" % q), "wb").write(data)
            return data, url
        except urllib.error.HTTPError as e:
            why.append("%s -> HTTP %s" % (url, e.code))
        except Exception as e:                       # network down, DNS, TLS, egress policy
            why.append("%s -> %s" % (url, e))
    return None, "; ".join(why)


def _member(z, want):
    """Find a table inside the zip regardless of casing or an added directory level."""
    for n in z.namelist():
        base = n.rsplit("/", 1)[-1].lower()
        if base in (want + ".tsv", want + ".txt"):
            return n
    return None


def aggregate(zbytes):
    """Aggregate one quarter's holdings by CUSIP. Returns ({cusip: {...}}, note).

    Streamed row by row on purpose: INFOTABLE runs to millions of rows per quarter and reading it
    into memory is the difference between this working on a laptop and not. Only the per-CUSIP
    totals are retained.

    Two filters matter for correctness. SSHPRNAMTTYPE must be 'SH' - a 'PRN' row is a principal
    amount of debt, not a share count, and summing the two together produces nonsense. And a row
    with PUTCALL set is an option position, not ownership of the stock; counting it would credit
    a fund that is short the name via puts as a sponsor.
    """
    try:
        z = zipfile.ZipFile(io.BytesIO(zbytes))
    except Exception as e:
        return None, "not a readable zip (%s)" % e
    cover, info = _member(z, "coverpage"), _member(z, "infotable")
    if not info:
        return None, "no INFOTABLE in the archive (members: %s)" % ", ".join(z.namelist()[:8])

    # accession -> filer CIK, so "holders" counts distinct MANAGERS rather than distinct filings
    acc_cik = {}
    if cover:
        with z.open(cover) as f:
            for row in csv.DictReader(io.TextIOWrapper(f, "utf-8", errors="replace"),
                                      delimiter="\t"):
                a = (row.get("ACCESSION_NUMBER") or "").strip()
                c = (row.get("CIK") or "").strip()
                if a:
                    acc_cik[a] = c or a

    out = {}
    rows = kept = 0
    with z.open(info) as f:
        for row in csv.DictReader(io.TextIOWrapper(f, "utf-8", errors="replace"), delimiter="\t"):
            rows += 1
            if (row.get("PUTCALL") or "").strip():
                continue                                  # an option, not ownership
            if (row.get("SSHPRNAMTTYPE") or "SH").strip().upper() != "SH":
                continue                                  # principal amount, not shares
            cusip = (row.get("CUSIP") or "").strip().upper()
            if not cusip:
                continue
            try:
                sh = float(row.get("SSHPRNAMT") or 0)
            except ValueError:
                continue
            acc = (row.get("ACCESSION_NUMBER") or "").strip()
            e = out.setdefault(cusip, {"name": (row.get("NAMEOFISSUER") or "").strip(),
                                       "shares": 0.0, "value": 0.0, "filers": set()})
            e["shares"] += sh
            try:
                e["value"] += float(row.get("VALUE") or 0)
            except ValueError:
                pass
            e["filers"].add(acc_cik.get(acc, acc))
            kept += 1
    for e in out.values():
        e["holders"] = len(e["filers"])
        del e["filers"]
    return out, "%d rows read, %d share positions kept, %d issuers" % (rows, kept, len(out))


def resolve_tickers(agg, cusip_map, universe):
    """cusip -> ticker, via an explicit map first and normalised issuer names second.

    Ambiguity is dropped rather than guessed: if two issuers normalise to the same name, neither
    is matched. A wrong ticker here attaches one company's sponsorship to another's scorecard,
    which is far worse than leaving the letter to the proxy.
    """
    by_ticker, unresolved = {}, []
    name_to_tick = {}
    dupes = set()
    for tick, comp in (universe or {}).items():
        k = norm_name(comp)
        if not k:
            continue
        if k in name_to_tick and name_to_tick[k] != tick:
            dupes.add(k)
        name_to_tick[k] = tick
    for k in dupes:
        name_to_tick.pop(k, None)

    for cusip, e in agg.items():
        tick = (cusip_map or {}).get(cusip) or name_to_tick.get(norm_name(e["name"]))
        if not tick:
            unresolved.append({"cusip": cusip, "name": e["name"], "holders": e["holders"]})
            continue
        # Two CUSIPs (share classes) can map to one ticker - sum them.
        cur = by_ticker.setdefault(tick, {"name": e["name"], "shares": 0.0, "holders": 0,
                                          "value": 0.0, "cusips": []})
        cur["shares"] += e["shares"]
        cur["value"] += e["value"]
        cur["holders"] = max(cur["holders"], e["holders"])
        cur["cusips"].append(cusip)
    unresolved.sort(key=lambda d: -d["holders"])
    return by_ticker, unresolved


def grade(now, prior, cfg, float_shares=None):
    """Grade I from the two quarters. Returns (grade, reason, metrics).

    Follows the rubric in references/canslim-methodology.md: PASS is ownership RISING with a real
    base of holders and room left for new buyers; PARTIAL is adequate ownership whose trend is
    flat or unverifiable; FAIL is thin, neglected, or declining.
    """
    h, sh = now["holders"], now["shares"]
    m = {"holders": h, "shares": sh, "holders_prior": None, "shares_prior": None,
         "holders_delta": None, "shares_delta_pct": None, "pct_of_float": None}

    if float_shares:
        try:
            m["pct_of_float"] = round(100.0 * sh / float(float_shares), 1)
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    if h < cfg["thin_holders"]:
        return ("fail", "I: only %d institutional holders - thin and neglected, below the "
                        "sponsorship test" % h, m)

    if not prior:
        return ("partial", "I: %d institutional holders (%.1fM shares), but no prior quarter to "
                           "compare - the trend is unverified" % (h, sh / 1e6), m)

    m["holders_prior"], m["shares_prior"] = prior["holders"], prior["shares"]
    m["holders_delta"] = h - prior["holders"]
    if prior["shares"]:
        m["shares_delta_pct"] = round(100.0 * (sh - prior["shares"]) / prior["shares"], 1)

    dh, ds = m["holders_delta"], (m["shares_delta_pct"] or 0.0)
    over = m["pct_of_float"] is not None and m["pct_of_float"] >= cfg["over_owned_pct"]

    if dh > 0 and ds > cfg["rising_pct"]:
        if over:
            return ("partial", "I: sponsorship rising (%+d holders to %d, shares %+.1f%%) but "
                               "institutions already hold %.1f%% of the float - little room for "
                               "new sponsorship" % (dh, h, ds, m["pct_of_float"]), m)
        return ("pass", "I: %d institutional holders, %+d on the quarter, shares held %+.1f%% - "
                        "sponsorship is increasing (SEC 13F)" % (h, dh, ds), m)
    if dh < 0 and ds < -cfg["rising_pct"]:
        return ("fail", "I: sponsorship declining - %d holders (%+d) and shares held %+.1f%% "
                        "(SEC 13F)" % (h, dh, ds), m)
    return ("partial", "I: %d institutional holders (%+d, shares %+.1f%%) - adequate ownership "
                       "but the trend is flat (SEC 13F)" % (h, dh, ds), m)


def build(args, cfg):
    meta = {"source": "sec-13f", "is_proxy": False, "quarter": args.quarter, "prior": args.prior,
            "thresholds": dict(cfg), "urls": {}, "notes": [], "ok": False}
    known, detail = {}, {}

    universe, cusip_map, floats = {}, {}, {}
    if args.universe:
        blob = json.load(open(args.universe, encoding="utf-8"))
        for _, rows in (blob.get("sectors") or {}).items() if isinstance(
                blob.get("sectors"), dict) else []:
            for r in rows or []:
                t = (r.get("symbol") or "").split(":")[-1]
                if t:
                    universe[t] = r.get("description") or r.get("name") or ""
                    if r.get("float_shares_outstanding_current"):
                        floats[t] = r["float_shares_outstanding_current"]
        meta["notes"].append("universe: %d tickers from %s" % (len(universe), args.universe))
    if args.cusip_map:
        cusip_map = {k.strip().upper(): v for k, v in
                     json.load(open(args.cusip_map, encoding="utf-8")).items()}
        meta["notes"].append("cusip map: %d entries" % len(cusip_map))

    aggs = {}
    for label, q in (("quarter", args.quarter), ("prior", args.prior)):
        if not q:
            continue
        data, where = fetch(q, args.contact, args.timeout, args.cache_dir)
        meta["urls"][q] = where
        if data is None:
            meta["notes"].append("%s %s could not be fetched: %s" % (label, q, where))
            continue
        agg, note = aggregate(data)
        meta["notes"].append("%s %s: %s" % (label, q, note))
        if agg:
            aggs[label] = agg

    if "quarter" not in aggs:
        meta["notes"].append("no 13F data for the current quarter - every ticker falls through "
                             "to the fallback, if one was given")
        return meta, known, detail, []

    now_t, unresolved = resolve_tickers(aggs["quarter"], cusip_map, universe)
    prior_t = resolve_tickers(aggs["prior"], cusip_map, universe)[0] if "prior" in aggs else {}
    meta["ok"] = True
    meta["notes"].append("resolved %d tickers; %d issuers unresolved" % (len(now_t), len(unresolved)))

    for tick, e in now_t.items():
        g, why, m = grade(e, prior_t.get(tick), cfg, floats.get(tick))
        known[tick] = {"I": g}
        detail[tick] = dict(m, grade=g, ceiling_cap=g, reason=why, source="sec-13f",
                            issuer=e["name"], cusips=e["cusips"])
    return meta, known, detail, unresolved


def merge_fallback(meta, known, detail, path):
    """Fill every ticker 13F could not answer from accumulation.py's volume proxy.

    Only gaps are filled - a real 13F grade is never overwritten by a proxy. Each entry keeps its
    own `source`, so the report can say which evidence graded which name instead of implying the
    whole column came from one place.
    """
    try:
        fb = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        meta["notes"].append("fallback %s could not be read: %s" % (path, e))
        return 0
    n = 0
    for tick, v in (fb.get("known") or {}).items():
        if tick in known:
            continue
        known[tick] = v
        d = (fb.get("detail") or {}).get(tick) or {}
        detail[tick] = dict(d, source=(fb.get("meta") or {}).get("source", "accumulation-proxy"))
        n += 1
    meta["notes"].append("fallback filled %d ticker(s) 13F did not cover" % n)
    meta["fallback"] = {"path": path, "source": (fb.get("meta") or {}).get("source"), "filled": n}
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quarter", required=True, help="e.g. 2026Q2 (the latest 13F deadline past)")
    ap.add_argument("--prior", help="the quarter before it, e.g. 2026Q1 - needed for the TREND")
    ap.add_argument("--universe", metavar="FILE",
                    help="the sweep JSON, used to resolve CUSIPs by issuer name")
    ap.add_argument("--cusip-map", metavar="FILE", help='{"67066G104": "NVDA", ...}')
    ap.add_argument("--fallback", metavar="FILE",
                    help="accumulation.py output, used for tickers 13F could not answer")
    ap.add_argument("--cache-dir", default="data/13f", help="keep the zips (default %(default)s)")
    ap.add_argument("--contact", default="", help="contact address for SEC's User-Agent policy")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--thin-holders", type=int, default=DEFAULTS["thin_holders"])
    ap.add_argument("-o", "--out", metavar="FILE", help="write here (default: stdout)")
    ap.add_argument("--known-only", action="store_true", help="print just the --known map")
    a = ap.parse_args()

    cfg = dict(DEFAULTS, thin_holders=a.thin_holders)
    meta, known, detail, unresolved = build(a, cfg)
    if a.fallback:
        merge_fallback(meta, known, detail, a.fallback)
    meta["graded"] = len(known)

    res = {"meta": meta, "known": known, "detail": detail,
           "unresolved": unresolved[:200]}
    text = json.dumps(known if a.known_only else res, indent=2)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        open(a.out, "w", encoding="utf-8").write(text + "\n")
        print("%s: %d ticker(s) graded%s" % (a.out, len(known),
              "" if meta["ok"] else " - 13F UNAVAILABLE, see meta.notes"), file=sys.stderr)
        for nte in meta["notes"]:
            print("  " + nte, file=sys.stderr)
    else:
        print(text)
    return 0        # fails open: a run continues on the proxy, or on I=partial


if __name__ == "__main__":
    sys.exit(main())
```


## `scripts/accumulation.py`

The I fallback: reads institutional buying pressure from the up/down volume footprint when 13F ownership is unavailable. A proxy, and every reason string says so.

```python
#!/usr/bin/env python3
"""
accumulation.py - grade I (institutional sponsorship) from the volume footprint, when 13F
ownership is unavailable.

WHY THIS EXISTS. I is the letter this skill routinely cannot source. 13F is filed by MANAGER,
not by issuer, so "who owns NVDA" is not an endpoint anywhere - it is an aggregation over every
filer - and the vendors that pre-compute it charge for it. The result was that every name in
every run scored I=partial by default, which is an admission, not a grade.

WHAT THIS MEASURES INSTEAD. Institutions cannot accumulate a position quietly: buying millions of
shares leaves a footprint in the tape, and that footprint is readable from bars this skill already
pulls. The up/down volume ratio - volume on advancing days over volume on declining days - is the
standard reading of it (IBD publishes the same idea as its Accumulation/Distribution Rating).
Above ~1.25 the stock is being accumulated; below ~0.9 it is under distribution, and a stock under
distribution is not one whose sponsorship is increasing, whatever last quarter's 13F said.

WHAT IT IS NOT. This is a PROXY and the output says so in every reason string. It reads buying
PRESSURE, not ownership: it cannot tell you the number of holders, whether the buyers are quality
funds, or whether the name is already so over-owned that new sponsorship is impossible - all three
of which the real rubric asks about. Prefer `institutional_cache.py` (SEC 13F) whenever it has
data; use this when it does not.

THE ASYMMETRY THAT DRIVES THE DEFAULT. The ceiling in sector_screen.py is an UPPER bound, and its
soundness depends on never being too low: a ceiling above the truth only wastes API calls, but a
ceiling below it silently drops a name that would have qualified. A proxy that reports "pass"
is therefore safe to feed the ceiling. A proxy that reports "fail" is not - it would be asserting,
from volume alone, that no amount of real ownership data could lift the letter. So by default a
proxy FAIL caps the ceiling at `partial`, never at `fail`; `--strict` lets it cap at fail for
anyone who would rather prune harder and accept the risk. The report grade is unaffected either
way - `detail` always carries the honest estimate.

INPUT: the same JSON `relative_strength.py` takes -
  {"candidates": [{"symbol": "NVDA", "daily": [[t,o,h,l,c,v], ...]}, ...]}
Bars are oldest-first; ~3 months (65 bars) is the minimum and ~1 year is comfortable.

OUTPUT: JSON with three parts -
  meta    what was measured and under which thresholds
  known   {ticker: {"I": grade}} - the CEILING-SAFE cap, ready for `sector_screen.py --known`
  detail  {ticker: {...}} - the honest estimate, the numbers behind it, and the reason string
          the report should print

Usage:
  python accumulation.py bars.json
  python accumulation.py bars.json --window 50 --strict
  cat bars.json | python accumulation.py --known-only > known.json
Pure standard library.
"""
import argparse
import json
import sys

DEFAULTS = {
    "window": 50,        # trading days of tape to read; ~10 weeks, IBD's usual U/D lookback
    "accumulate": 1.25,  # U/D at or above this is accumulation
    "distribute": 0.90,  # U/D below this is distribution
    "big_vol": 1.40,     # a day at >= this multiple of average volume is an institutional print
    "min_prints": 3,     # ... and a pass wants at least this many of them in the window
    "min_bars": 30,      # below this there is not enough tape to say anything
}

ORDER = {"fail": 0, "partial": 1, "pass": 2}


def _rows(bars):
    """(close, volume) pairs, skipping bars with either value missing.

    Accepts BOTH bar shapes in use here: the positional [t,o,h,l,c,v] that relative_strength.py
    documents, and the {"t":..,"c":..,"v":..} dicts the TradingView connector actually returns from
    get_ohlcv. Taking the native shape removes a hand-conversion step between the two, and a
    hand-conversion step between a connector and a grader is exactly where a column silently
    shifts by one.
    """
    out = []
    for b in bars or []:
        try:
            if isinstance(b, dict):
                c, v = float(b["c"]), float(b["v"])
            else:
                c, v = float(b[4]), float(b[5])
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        out.append((c, v))
    return out


def up_down_volume(bars, window):
    """Volume on advancing days over volume on declining days, across the last `window` days.

    Unchanged closes are excluded rather than assigned to either side: a flat day carries no
    directional information, and bucketing it with the buyers is how this ratio gets quietly
    inflated on thin names that print the same close repeatedly.
    """
    r = _rows(bars)
    if len(r) < 2:
        return None
    seg = r[-(window + 1):] if len(r) > window else r
    up = dn = 0.0
    for i in range(1, len(seg)):
        prev, cur = seg[i - 1][0], seg[i][0]
        vol = seg[i][1]
        if cur > prev:
            up += vol
        elif cur < prev:
            dn += vol
    if dn == 0:
        return None if up == 0 else float("inf")   # nothing but up days: no ratio, but not weak
    return up / dn


def big_volume_up_days(bars, window, mult):
    """Advancing days on volume at least `mult` times the window average.

    This is the part that separates accumulation from drift. A U/D ratio a little over 1 can come
    from many small up days; institutions buying size leave a handful of conspicuously heavy ones,
    and requiring a few of those keeps a quiet uptrend from reading as sponsorship.
    """
    r = _rows(bars)
    if len(r) < 2:
        return None
    seg = r[-(window + 1):] if len(r) > window else r
    vols = [v for _, v in seg[1:]]
    if not vols:
        return None
    avg = sum(vols) / len(vols)
    if avg <= 0:
        return None
    n = 0
    for i in range(1, len(seg)):
        if seg[i][0] > seg[i - 1][0] and seg[i][1] >= mult * avg:
            n += 1
    return n


def grade(bars, cfg):
    """Return (grade, ceiling_cap, reason, metrics). `grade` is the honest estimate for the
    report; `ceiling_cap` is what is safe to hand the ceiling - see the module docstring."""
    r = _rows(bars)
    if len(r) < cfg["min_bars"]:
        return ("partial", "partial",
                "I: not graded - only %d usable bars, too little tape to read accumulation "
                "(no 13F data either)" % len(r),
                {"bars": len(r), "ud_ratio": None, "big_up_days": None})

    ud = up_down_volume(bars, cfg["window"])
    prints = big_volume_up_days(bars, cfg["window"], cfg["big_vol"])
    m = {"bars": len(r), "ud_ratio": (None if ud is None else
                                      (None if ud == float("inf") else round(ud, 2))),
         "all_up_days": ud == float("inf"),
         "big_up_days": prints, "window": cfg["window"]}

    if ud is None:
        return ("partial", "partial",
                "I: not graded - no directional volume in the last %d days (proxy; no 13F data)"
                % cfg["window"], m)

    strong = ud == float("inf") or ud >= cfg["accumulate"]
    weak = ud != float("inf") and ud < cfg["distribute"]
    shown = "all advancing days" if ud == float("inf") else "%.2fx" % ud

    if strong and (prints or 0) >= cfg["min_prints"]:
        return ("pass", "pass",
                "I: up/down volume %s over %d days with %d heavy accumulation days - "
                "institutional buying pressure (proxy: volume footprint, not 13F ownership)"
                % (shown, cfg["window"], prints or 0), m)
    if weak:
        return ("fail", "partial",
                "I: up/down volume %s over %d days - under distribution, sponsorship is not "
                "building (proxy: volume footprint, not 13F ownership)" % (shown, cfg["window"]), m)
    return ("partial", "partial",
            "I: up/down volume %s over %d days with %d heavy days - no clear accumulation either "
            "way (proxy: volume footprint, not 13F ownership)"
            % (shown, cfg["window"], prints or 0), m)


def analyze(data, cfg, strict=False):
    known, detail = {}, {}
    for cand in data.get("candidates") or []:
        sym = cand.get("symbol") or ""
        tick = sym.split(":")[-1] if sym else ""
        if not tick:
            continue
        g, cap, why, m = grade(cand.get("daily") or [], cfg)
        if strict:
            cap = g                      # let a proxy fail prune; see the module docstring
        known[tick] = {"I": cap}
        detail[tick] = dict(m, symbol=sym, grade=g, ceiling_cap=cap, reason=why)
    return {
        "meta": {
            "source": "accumulation-proxy",
            "measures": "up/down volume ratio and heavy accumulation days",
            "is_proxy": True,
            "caveat": ("Volume footprint, NOT 13F ownership. It reads institutional buying "
                       "PRESSURE; it cannot count holders, identify quality funds, or detect an "
                       "over-owned name. Prefer institutional_cache.py when it has data."),
            "ceiling_policy": ("proxy fail caps the ceiling at partial" if not strict
                               else "STRICT: proxy fail caps the ceiling at fail"),
            "thresholds": dict(cfg),
            "graded": len(known),
        },
        "known": known,
        "detail": detail,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", help="bars JSON (default: stdin)")
    ap.add_argument("--window", type=int, default=DEFAULTS["window"],
                    help="trading days of tape to read (default %(default)s)")
    ap.add_argument("--accumulate", type=float, default=DEFAULTS["accumulate"],
                    help="U/D at or above this is accumulation (default %(default)s)")
    ap.add_argument("--distribute", type=float, default=DEFAULTS["distribute"],
                    help="U/D below this is distribution (default %(default)s)")
    ap.add_argument("--big-vol", type=float, default=DEFAULTS["big_vol"],
                    help="volume multiple that marks an institutional print (default %(default)s)")
    ap.add_argument("--min-prints", type=int, default=DEFAULTS["min_prints"],
                    help="heavy up days a pass requires (default %(default)s)")
    ap.add_argument("--strict", action="store_true",
                    help="let a proxy FAIL cap the ceiling at fail rather than partial - prunes "
                         "harder, at the risk of dropping a name real 13F data would have kept")
    ap.add_argument("--known-only", action="store_true",
                    help="print just the --known map, ready for sector_screen.py")
    a = ap.parse_args()

    cfg = dict(DEFAULTS)
    cfg.update({"window": a.window, "accumulate": a.accumulate, "distribute": a.distribute,
                "big_vol": a.big_vol, "min_prints": a.min_prints})
    data = json.load(open(a.input, encoding="utf-8")) if a.input else json.load(sys.stdin)
    res = analyze(data, cfg, strict=a.strict)
    json.dump(res["known"] if a.known_only else res, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
```


## `scripts/build_report.py`

The step-7 entry point: produces the PDF (default), the HTML, or both, and refuses to emit a report that is failing its own self-audit.

```python
#!/usr/bin/env python3
"""
build_report.py - turn a filled dashboard into the deliverable(s) the user asked for.

This is the single entry point for step 7. It exists so "PDF by default, HTML on request"
is a resolved argument rather than a convention someone has to remember:

    python scripts/build_report.py canslim-recommendations-<date>.html                 -> PDF
    python scripts/build_report.py canslim-recommendations-<date>.html --format html   -> HTML
    python scripts/build_report.py canslim-recommendations-<date>.html --format both   -> both

`--format` defaults to `pdf`. Nothing else about the report changes with the format: the same
filled CONFIG drives both, the HTML renders dark on screen, and the print stylesheet forces the
white palette so the PDF is white either way (see the template's THEME note). `--theme` flips
the on-screen look of the HTML deliverable; it has no effect on the PDF.

THE SELF-AUDIT IS ENFORCED HERE. The template audits its own CONFIG on render and prints a red
"Report checks failed" banner when the run contradicts itself. Shipping a report showing that
banner is the one thing the skill must never do, so this script renders the page in a headless
browser and REFUSES to emit anything when the banner is present. If no browser is available the
check is skipped with a warning rather than silently passing.

Exit codes: 0 = deliverables written; 1 = nothing written (audit failed, or no PDF engine and
--format pdf was required); 2 = bad usage.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import html_to_pdf  # noqa: E402  - same directory, shared engine chain


def apply_theme(path, theme):
    """Rewrite the document element's data-theme. Returns True if the file changed.

    Anchored to the doctype on purpose: the template's own header comment TALKS about
    `<html data-theme="dark">`, and a naive "first <html" match rewrites that prose instead of
    the real element, leaving the page's theme untouched while reporting success.
    """
    src = open(path, encoding="utf-8").read()
    doctype = re.search(r"<!doctype\s+html[^>]*>", src, re.I)
    start = doctype.end() if doctype else 0
    tag = re.search(r"<html\b[^>]*>", src[start:], re.I)
    if not tag:
        return False
    lo, hi = start + tag.start(), start + tag.end()
    old_tag = src[lo:hi]
    if 'data-theme="%s"' % theme in old_tag:
        return False
    new_tag, n = re.subn(r'\s*data-theme="[^"]*"', ' data-theme="%s"' % theme, old_tag, count=1)
    if not n:
        new_tag = old_tag[:-1].rstrip() + ' data-theme="%s">' % theme
    open(path, "w", encoding="utf-8").write(src[:lo] + new_tag + src[hi:])
    return True


# Wall-clock ceiling on any single headless-render subprocess. A render that has not
# finished by now is wedged, not slow - the engine gives up and the caller falls through
# to the next one in the chain.
RENDER_TIMEOUT = 240


def audit(path):
    """Render the page headlessly and read its self-audit banner.

    Returns (ok, detail): ok is True when the report is clean OR the check could not run
    (detail says which). ok is False only when the banner is actually present.
    """
    exe = html_to_pdf.find_browser()
    if not exe:
        return True, "SKIPPED - no headless browser found, so the self-audit could not be read"
    url = "file:///" + os.path.abspath(path).replace("\\", "/")
    for head in ("--headless=new", "--headless"):
        try:
            out = subprocess.run(
                [exe, head, "--disable-gpu", "--no-sandbox", "--virtual-time-budget=6000",
                 "--dump-dom", url],
                check=True, timeout=RENDER_TIMEOUT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            ).stdout.decode("utf-8", "replace")
        except Exception:
            continue
        m = re.search(r'<div id="checks"[^>]*>(.*?)(?=<div id="freshness")', out, re.S)
        body = m.group(1) if m else ""
        if "Report checks failed" not in body:
            return True, "clean"
        items = re.findall(r"<li>(.*?)</li>", body, re.S)
        items = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", i)).strip() for i in items]
        return False, "\n".join("    - " + i for i in items) or "    - (banner present)"
    return True, "SKIPPED - the browser failed to render the page, so the audit could not be read"


def main():
    ap = argparse.ArgumentParser(description="Produce the PDF and/or HTML deliverable.")
    ap.add_argument("input", help="the filled canslim-recommendations-<date>.html")
    ap.add_argument("--format", "-f", choices=("pdf", "html", "both"), default="pdf",
                    help="which deliverable to produce (default: pdf)")
    ap.add_argument("--theme", choices=("dark", "light"),
                    help="on-screen theme of the HTML deliverable; the PDF is white regardless")
    ap.add_argument("--out", "-o", help="directory to write into (default: alongside the input)")
    ap.add_argument("--no-check", action="store_true",
                    help="emit even if the self-audit banner is showing (use only to inspect a failure)")
    a = ap.parse_args()

    if not os.path.isfile(a.input):
        print("no such file: " + a.input, file=sys.stderr)
        sys.exit(2)

    outdir = a.out or os.path.dirname(os.path.abspath(a.input)) or "."
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(a.input))[0]

    if a.theme and apply_theme(a.input, a.theme):
        print("theme -> %s" % a.theme)

    ok, detail = audit(a.input)
    if not ok:
        print("REFUSED: the report's self-audit is failing - do not ship it.\n" + detail,
              file=sys.stderr)
        if not a.no_check:
            print("\nFix the CONFIG (or re-run with --no-check to emit it anyway for inspection).",
                  file=sys.stderr)
            sys.exit(1)
        print("--no-check given; emitting anyway.", file=sys.stderr)
    elif detail != "clean":
        print("self-audit %s" % detail)
    else:
        print("self-audit clean")

    written = []
    if a.format in ("html", "both"):
        dest = os.path.join(outdir, stem + ".html")
        if os.path.abspath(dest) != os.path.abspath(a.input):
            shutil.copyfile(a.input, dest)
        written.append(dest)

    if a.format in ("pdf", "both"):
        dest = os.path.join(outdir, stem + ".pdf")
        made = False
        for name, fn in (("chrome", html_to_pdf.via_chrome),
                         ("playwright", html_to_pdf.via_playwright),
                         ("weasyprint", html_to_pdf.via_weasyprint),
                         ("wkhtmltopdf", html_to_pdf.via_wkhtmltopdf)):
            if fn(a.input, dest):
                print("PDF via %s" % name)
                written.append(dest)
                made = True
                break
        if not made:
            # Never block the run on the export: fall back to the HTML and say why.
            print("no PDF engine available (install Chrome/Chromium/Edge, playwright, weasyprint "
                  "or wkhtmltopdf)", file=sys.stderr)
            if a.format == "pdf":
                fallback = os.path.join(outdir, stem + ".html")
                if os.path.abspath(fallback) != os.path.abspath(a.input):
                    shutil.copyfile(a.input, fallback)
                written.append(fallback)
                print("falling back to the HTML deliverable - hand it over and say why there is "
                      "no PDF.", file=sys.stderr)

    for p in written:
        print("%8.1f KB  %s" % (os.path.getsize(p) / 1024.0, p))
    sys.exit(0 if written else 1)


if __name__ == "__main__":
    main()
```


## `scripts/html_to_pdf.py`

The PDF engine chain behind it; reads page size and margin from the document's @page rule.

```python
#!/usr/bin/env python3
"""
html_to_pdf.py - render the filled CAN SLIM recommendations HTML to PDF.

The PDF is this skill's DEFAULT deliverable: the filled canslim-recommendations-<date>.html
is the working file, and this turns it into the report the user gets. The dashboard template
is print-optimized (A4, print-color-adjust:exact) and its print stylesheet forces the white
palette, so the PDF comes out white even when the HTML itself is rendered dark. This script
tries several engines so it works across environments, and prints the engine it used.

Page size AND margin are read out of the document's own `@page` rule (see css_page_size and
css_page_margin) and passed to whichever engine runs, so every engine produces the same page
rather than each applying its own default.

Shared with the sister skill `can-slim-grader` (same file, same behaviour) - keep the two in
step if you change it.

Usage:
    python html_to_pdf.py <input.html> [output.pdf]
If output is omitted it is the input path with a .pdf extension.

Engine order: headless Chrome/Chromium/Edge (--print-to-pdf) -> Playwright -> WeasyPrint ->
wkhtmltopdf. Exits non-zero (with guidance) if none is available - in that case hand over the
HTML instead and say why.
"""
import os
import re
import sys
import shutil
import subprocess


def css_page_size(path):
    """Read the document's `@page { size: ... }` rule, if it declares one.

    Chrome's --print-to-pdf honours @page on its own, but Playwright and wkhtmltopdf do not
    unless told, so a landscape report (like the recommend skill's wide screening table) would
    silently clip on those engines. Returns the raw size value lowercased, or None.
    """
    try:
        head = open(path, encoding="utf-8", errors="replace").read(200000)
    except OSError:
        return None
    m = re.search(r"@page[^{]*\{[^}]*?\bsize\s*:\s*([^;}]+)", head, re.I | re.S)
    return m.group(1).strip().lower() if m else None


DEFAULT_MARGIN = "12mm"


def css_page_margin(path, default=DEFAULT_MARGIN):
    """Read the document's `@page { margin: ... }` rule as a single CSS length.

    Same reason as css_page_size: Chrome honours @page itself, but Playwright and wkhtmltopdf
    take margins as arguments, so without this a document that asks for a 15mm inset gets
    whatever the engine defaults to. Only a uniform (one-value) margin is read - that is what
    both templates declare, and a multi-value rule is left to `default` rather than guessed at.
    Returns a CSS length string such as "15mm", or `default` when there is no usable rule.
    """
    try:
        head = open(path, encoding="utf-8", errors="replace").read(200000)
    except OSError:
        return default
    m = re.search(r"@page[^{]*\{[^}]*?\bmargin\s*:\s*([^;}]+)", head, re.I | re.S)
    if not m:
        return default
    val = m.group(1).strip().lower()
    # one value only, and it must be a length we can hand to another engine verbatim
    return val if re.fullmatch(r"\d+(?:\.\d+)?(?:mm|cm|in|px|pt)", val) else default


def _abs(p):
    return os.path.abspath(p)


def find_browser():
    """Return a path to a Chromium-family executable, or None."""
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "chrome", "msedge", "microsoft-edge"):
        p = shutil.which(name)
        if p:
            return p
    cands = []
    # Agent sandboxes often ship a Playwright-managed Chromium that is not on PATH.
    pw = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if pw:
        cands += [os.path.join(pw, "chromium"),
                  os.path.join(pw, "chrome-linux", "chrome")]
    cands += [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


# Wall-clock ceiling on any single render subprocess, shared by every engine in the chain
# so none of them can be the odd one out. Playwright otherwise defaults to 30s, which was
# the tightest limit here and the only one not written down.
RENDER_TIMEOUT = 240


def via_chrome(inp, out):
    exe = find_browser()
    if not exe:
        return False
    url = "file:///" + _abs(inp).replace("\\", "/")
    common = [exe, "--disable-gpu", "--no-sandbox",
              "--run-all-compositor-stages-before-draw", "--virtual-time-budget=4000",
              f"--print-to-pdf={_abs(out)}", url]
    # Prefer suppressing Chrome's date/title/URL/page-number header & footer; fall back to
    # plain print if a given Chrome build doesn't accept the flag. Try new then classic headless.
    for head in ("--headless=new", "--headless"):
        for extra in (["--no-pdf-header-footer"], []):
            try:
                if os.path.exists(out):
                    os.remove(out)
            except Exception:
                pass
            try:
                subprocess.run([exe, head] + extra + common[1:], check=True, timeout=RENDER_TIMEOUT,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(out) and os.path.getsize(out) > 1000:
                    return True
            except Exception:
                continue
    return False


def via_playwright(inp, out):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return False
    try:
        url = "file:///" + _abs(inp).replace("\\", "/")
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            pg.goto(url, wait_until="networkidle", timeout=RENDER_TIMEOUT * 1000)
            mg = css_page_margin(inp)
            kw = dict(path=_abs(out), print_background=True,
                      margin={"top": mg, "bottom": mg, "left": mg, "right": mg})
            if css_page_size(inp):
                kw["prefer_css_page_size"] = True   # the document declares its own page
            else:
                kw["format"] = "A4"
            pg.pdf(**kw)
            b.close()
        return os.path.exists(out) and os.path.getsize(out) > 1000
    except Exception:
        return False


def via_weasyprint(inp, out):
    try:
        from weasyprint import HTML
    except Exception:
        return False
    try:
        HTML(_abs(inp)).write_pdf(_abs(out))
        return os.path.exists(out) and os.path.getsize(out) > 1000
    except Exception:
        return False


def via_wkhtmltopdf(inp, out):
    exe = shutil.which("wkhtmltopdf")
    if not exe:
        return False
    try:
        size = css_page_size(inp) or ""
        orient = ["-O", "Landscape"] if "landscape" in size else []
        mg = css_page_margin(inp)
        margins = ["-T", mg, "-B", mg, "-L", mg, "-R", mg]
        subprocess.run([exe, "--enable-local-file-access", "--print-media-type"] + orient +
                       margins + [_abs(inp), _abs(out)], check=True, timeout=RENDER_TIMEOUT,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return os.path.exists(out) and os.path.getsize(out) > 1000
    except Exception:
        return False


def main():
    if len(sys.argv) < 2:
        print("usage: html_to_pdf.py <input.html> [output.pdf]", file=sys.stderr)
        sys.exit(2)
    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(inp)[0] + ".pdf"
    for name, fn in (("chrome", via_chrome), ("playwright", via_playwright),
                     ("weasyprint", via_weasyprint), ("wkhtmltopdf", via_wkhtmltopdf)):
        if fn(inp, out):
            print(f"OK {out} (via {name})")
            return
    print("FAILED: no PDF engine available. Install Google Chrome/Chromium/Edge, or "
          "`pip install playwright weasyprint`, or wkhtmltopdf.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
```


## `assets/dashboard_template.html`

The report template. Fill its CONFIG object and it renders itself, audits itself, and refuses to ship a self-contradicting report.

```html
<!--
  can-slim-recommend - CAN SLIM sector-sweep dashboard template.

  HOW TO USE (per run):
    1. Copy this file to the output location, e.g. canslim-recommendations-<date>.html
    2. Fill the CONFIG object below with the run's results. That is the ONLY thing you
       edit - the page renders itself from CONFIG. Do not hand-edit the DOM.
    3. Render the PDF (the DEFAULT deliverable):
         python scripts/html_to_pdf.py canslim-recommendations-<date>.html
       Hand over the HTML itself only when the user asks for it.

  WHAT THE PAGE BUILDS FOR YOU - fill ONE list, get BOTH recommendation lists:
    You fill `picks[]` with EVERY name that was fully graded (each carrying its sector, its
    rank inside that sector, and its C-A-N-S-L-I grades). The page then derives:
      1. "Sector leaders" - every pick whose grade reaches CONFIG.gradeThreshold (default 4.5
         of 7), grouped by sector, best sector first.
      2. "Overall top N"  - the CONFIG.topCount (default 10) highest-graded names market-wide,
         regardless of sector. Overlap with list 1 is expected and is badged, not hidden.
    Both lists only hold names at/above the cut. When nothing clears it, list 2 renders as
    EMPTY with an enumerated, evidence-based "why" (derived from the grades themselves) rather
    than ranking the least-weak names - a sub-cut name is not a recommendation just because
    others scored worse. Never hand-build those two lists - if a name is missing from one, its
    grade is the reason.

  RULES THE TEMPLATE ENFORCES BY CONVENTION:
    - Every pick MUST carry a `reason` expressed ONLY in CAN SLIM terms (the seven letters,
      bases/pivots, relative strength, new highs, volume/accumulation, leadership,
      institutional sponsorship, market direction). No generic market chatter, no analyst
      targets, no non-method rationale. If a name can't be justified in CAN SLIM terms, it
      does not belong here.
    - `scores` grades each of C,A,N,S,L,I as "pass" | "partial" | "fail" - the SAME rubric the
      sister skill `can-slim-grader` applies, so a grade means the same thing in both reports.
    - `reason` renders as a FULL-WIDTH row under each pick, not as a column, so it always has the
      whole table to wrap into. Write it as prose of any length. `offHigh` is not a column - state
      the distance from the 52-week high inside the reason (the map still plots it).
    - M (market direction) is graded ONCE for the whole market via CONFIG.market.mGrade and
      applied to every row, so each scorecard shows C,A,N,S,L,I + a dashed M cell.
      Total = pass 1 + partial 0.5 + fail 0, out of 7. The 4.5 cut lives on that scale.
    - Every pick needs a `verdict` - BUY-RANGE / WATCH / AVOID, exactly as can-slim-grader
      issues it. The verdict is NOT the grade: a name can clear the 4.5 cut on C/A/L and still
      be a WATCH because N fails (no sound base at new-high ground, so no pivot to buy).
    - Data sources are NOT optional: fill `dataProvenance` AND `sourceMap[]`. The page prints
      a red check banner if provenance is missing - never ship a report showing that banner.
    - Never put account-bound data (IDs, balances, positions) anywhere in CONFIG.

  THEME - the two deliverables deliberately differ:
    - The PDF (the default deliverable) is WHITE. The print stylesheet redeclares the light
      tokens, so it stays white no matter what data-theme the file carries. It targets A4
      landscape with a 15mm margin on all four edges.
    - The HTML (handed over on request) is DARK - <html data-theme="dark"> is set below.
      Switch that attribute to "light" if someone wants a light HTML instead; the PDF is
      unaffected either way.

  ENCODING: keep CONFIG text ASCII where practical (use "-" not an em-dash, "vs" not a
    special glyph). The page is UTF-8, but ASCII content is bulletproof across viewers/PDF.

  VISUALS (auto-rendered from CONFIG, no extra work):
    - Leadership map: a scatter of RS (x) vs % off 52-wk high (y, 0 at top) built from each
      pick's `rs` and `offHigh` - leaders cluster top-right in the shaded zone. That zone marks
      high RS on new-high ground only; it does NOT test for a pivot, so do not read a dot inside
      it as buyable. Marks are coloured AND shaped by `verdict` (BUY-RANGE / WATCH / AVOID) with
      a legend; ticker labels are placed by a collision solver, so they never overlap. Shows only
      when >=2 picks have numeric rs+offHigh; otherwise it hides itself.
    - Sector sweep table: rendered from `sectors[]` - the sector ranking behind the sweep.

  PER-TICKER DEEP DIVE: give a pick a `reviewUrl` (path/URL to that symbol's can-slim-grader
    or ibkr-review-ticker HTML, saved next to this file). The ticker then becomes a link that
    opens the report in an in-page window (modal iframe). Omit it and the ticker is plain
    text. The links are interactive-HTML only - they flatten in the PDF.
-->
<!doctype html>
<!-- data-theme="dark" is the HTML deliverable's committed look. The print
     stylesheet forces the light palette back on, so the PDF stays white. To hand over a
     light-on-screen HTML instead, change this to data-theme="light". -->
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CAN SLIM Sector Recommendations</title>
<style>
  /* White/light is the committed design of this dashboard (screen AND the default PDF).
     A dark palette remains available via <html data-theme="dark"> for anyone who wants it. */
  :root{
    --bg:#ffffff; --panel:#fbfcfd; --ink:#14181f; --muted:#5b6472; --line:#e3e7ec;
    --accent:#1c5fd8; --accent-soft:#eaf1fe;
    --pass:#0f7a45; --pass-bg:#e4f4ea; --partial:#a76300; --partial-bg:#fdf0dc;
    --fail:#b4231f; --fail-bg:#fbe7e5; --chip:#eef1f5;
    --mono:'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    --sans:'Inter',system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
  }
  :root[data-theme="light"]{--bg:#ffffff;--panel:#fbfcfd;--ink:#14181f;--muted:#5b6472;--line:#e3e7ec;
      --accent:#1c5fd8;--accent-soft:#eaf1fe;--pass:#0f7a45;--pass-bg:#e4f4ea;--partial:#a76300;
      --partial-bg:#fdf0dc;--fail:#b4231f;--fail-bg:#fbe7e5;--chip:#eef1f5;}
  :root[data-theme="dark"]{--bg:#0d1017;--panel:#161b23;--ink:#e8ebf1;--muted:#9aa4b2;--line:#273040;
      --accent:#6ea0ff;--accent-soft:#182236;--pass:#3ddc91;--pass-bg:#0f2f22;--partial:#e6b04a;
      --partial-bg:#332711;--fail:#ff6d64;--fail-bg:#3a1613;--chip:#1e2632;}

  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.5;
    -webkit-font-smoothing:antialiased}
  .wrap{max-width:1180px;margin:0 auto;padding:28px 22px 60px}
  header.top{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:14px;
    border-bottom:2px solid var(--line);padding-bottom:16px}
  h1{font-size:26px;margin:0 0 4px;letter-spacing:-.01em}
  .sub{color:var(--muted);font-size:16px}
  .meta{font-family:var(--mono);font-size:14px;color:var(--muted);text-align:right}

  .market{display:flex;flex-wrap:wrap;align-items:center;gap:14px;margin:18px 0 6px;
    background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
  .verdict{font-weight:700;font-size:17px;padding:6px 12px;border-radius:999px;white-space:nowrap}
  .verdict.up{background:var(--pass-bg);color:var(--pass)}
  .verdict.pressure{background:var(--partial-bg);color:var(--partial)}
  .verdict.down{background:var(--fail-bg);color:var(--fail)}
  .market .imp{font-size:16px;color:var(--ink);flex:1;min-width:240px}
  /* The distribution-day line is one long mono string, so left in the same flex row it claims
     its full width as its base size and squeezes the implication - the paragraph that actually
     matters - into whatever is left. Give it its own row instead. */
  .dd{font-family:var(--mono);font-size:14px;color:var(--muted)}
  .market .dd{flex-basis:100%}

  .section-title{font-size:16px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
    color:var(--muted);margin:26px 0 10px}
  .section-title .n{font-weight:400;text-transform:none;letter-spacing:0;color:var(--muted)}
  .legend{display:flex;gap:14px;flex-wrap:wrap;font-size:14px;color:var(--muted);margin:2px 0 10px;align-items:center}
  .legend span{display:inline-flex;align-items:center;gap:6px}
  .legend span.note{display:block;flex-basis:100%;align-items:initial}
  .dot{width:10px;height:10px;border-radius:3px;display:inline-block}
  .dot.pass{background:var(--pass)} .dot.partial{background:var(--partial)} .dot.fail{background:var(--fail)}
  .hint{font-size:14px;color:var(--muted);font-style:italic}

  .funnel{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 4px}
  .fstep{flex:1;min-width:150px;background:var(--panel);border:1px solid var(--line);border-radius:12px;
    padding:11px 14px}
  .fstep .v{font-family:var(--mono);font-size:22px;font-weight:700;color:var(--ink)}
  .fstep .k{font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
  .fstep .s{font-size:13px;color:var(--muted);margin-top:2px}

  .tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel)}
  table{border-collapse:collapse;width:100%;min-width:820px;font-size:16px}
  table.compact{min-width:520px;font-size:15px}
  thead th{text-align:left;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);
    padding:11px 10px;border-bottom:1px solid var(--line);white-space:nowrap;background:var(--panel);position:sticky;top:0}
  thead th.sortable{cursor:pointer;user-select:none}
  thead th.sortable:hover{color:var(--ink)}
  th .arrow{opacity:.35;font-size:12px;margin-left:3px}
  th.sorted .arrow{opacity:1;color:var(--accent)}
  th.num{text-align:right}
  tbody td{padding:11px 10px;border-bottom:1px solid var(--line);vertical-align:top}
  td.stock{min-width:132px}
  td.grp{min-width:150px}
  tbody tr:last-child td{border-bottom:none}
  tr.grouphead td{background:var(--chip);font-size:13px;text-transform:uppercase;letter-spacing:.05em;
    font-weight:700;color:var(--ink);padding:8px 10px}
  tr.grouphead .gmeta{font-weight:400;text-transform:none;letter-spacing:0;color:var(--muted)}
  .rk{font-family:var(--mono);color:var(--muted)}
  .sym{font-family:var(--mono);font-weight:700;font-size:17px}
  a.sym{color:var(--accent);text-decoration:none;cursor:pointer;border-bottom:1px dotted var(--accent)}
  a.sym:hover{border-bottom-style:solid}
  .co{color:var(--muted);font-size:14px}
  .grp{font-size:14px}
  td.num{font-family:var(--mono);white-space:nowrap;text-align:right}
  .pos{color:var(--pass)} .neg{color:var(--fail)}
  .badge{display:inline-block;font-size:11px;font-family:var(--mono);font-weight:700;padding:1px 6px;
    border-radius:999px;background:var(--accent-soft);color:var(--accent);margin-left:6px;vertical-align:1px}
  .badge.warn{background:var(--partial-bg);color:var(--partial)}
  .vd{display:inline-block;font-family:var(--mono);font-size:12px;font-weight:700;white-space:nowrap;
    padding:3px 8px;border-radius:999px}
  .vd-buy{background:var(--pass-bg);color:var(--pass)}
  .vd-watch{background:var(--partial-bg);color:var(--partial)}
  .vd-avoid{background:var(--fail-bg);color:var(--fail)}
  .scorecells{white-space:nowrap}
  .sc{display:inline-flex;flex-direction:column;align-items:center;width:22px;margin-right:2px}
  .sc .lab{font-size:11px;color:var(--muted);font-family:var(--mono)}
  .sc .mk{width:21px;height:21px;border-radius:6px;display:flex;align-items:center;justify-content:center;
    font-size:12px;font-weight:700;margin-top:2px;font-family:var(--mono)}
  .mk.g-pass{background:var(--pass-bg);color:var(--pass)}
  .mk.g-partial{background:var(--partial-bg);color:var(--partial)}
  .mk.g-fail{background:var(--fail-bg);color:var(--fail)}
  .sc.mcol .mk{outline:1px dashed var(--line);outline-offset:-1px}   /* M = market-wide component */
  /* ONE span, value first: "4.5 / 7". It used to be a stacked "/7" label above the value, which
     looked fine but flattened to "/74.5" in copy-paste, PDF text extraction and screen readers -
     i.e. it read as a score out of 70. Never split a value from its denominator across elements. */
  .sc-total{display:inline-block;margin-left:9px;padding-top:13px;vertical-align:top;white-space:nowrap;
    font-family:var(--mono);font-weight:700;font-size:15px;color:var(--ink);font-variant-numeric:tabular-nums}
  .sc-total.hit{color:var(--pass)}
  /* Carries text that must survive flattening but must not be seen. */
  .vh{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;
    clip-path:inset(50%);white-space:nowrap;border:0}
  /* The CAN SLIM read spans the whole table rather than living in a column, so it always has
     the full width to wrap into and is never truncated or squeezed to one word per line. */
  tr.whyrow td{border-bottom:1px solid var(--line);padding:0 10px 11px 10px}
  tr.pickrow td{border-bottom:none;padding-bottom:5px}
  .reason{font-size:15px;line-height:1.5;color:var(--ink);width:100%;max-width:none;
    white-space:normal;overflow-wrap:anywhere;word-break:break-word;hyphens:auto}
  .reason .wlab{display:inline-block;font-family:var(--mono);font-size:11px;text-transform:uppercase;
    letter-spacing:.05em;color:var(--muted);margin-right:8px;white-space:nowrap}

  .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 15px}
  .card h3{margin:0 0 2px;font-size:18px;font-family:var(--mono)}
  .card .co{margin-bottom:8px}
  .card p{margin:0;font-size:16px}

  .fbsec{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 15px;margin-bottom:10px}
  .fbsec h4{margin:0 0 8px;font-size:15px;display:flex;flex-wrap:wrap;gap:8px;align-items:baseline}
  .fbsec h4 .rk{font-family:var(--mono);color:var(--muted);font-weight:400}
  .fbsec h4 .meta{font-weight:400;font-size:13px;color:var(--muted)}
  .fbrow{display:grid;grid-template-columns:22px 62px 1fr 74px 66px 74px;gap:6px 10px;align-items:baseline;
    font-size:14px;padding:5px 0;border-top:1px solid var(--line)}
  .fbrow:first-of-type{border-top:none}
  .fbrow .n{font-family:var(--mono);color:var(--muted);font-size:12px}
  .fbrow .sym{font-family:var(--mono);font-weight:700;font-size:15px}
  .fbrow .co{color:var(--muted);font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .fbrow .num{font-family:var(--mono);text-align:right;white-space:nowrap}
  .fbrow .st{font-size:12px;color:var(--muted);white-space:nowrap}
  .fbrow .st.ok{color:var(--pass)}
  .fbnote{font-size:13px;color:var(--muted);margin-top:8px}
  @media (max-width:640px){.fbrow{grid-template-columns:20px 58px 1fr;}.fbrow .num,.fbrow .st{display:none}}
  .tier{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 15px;margin-bottom:10px}
  .tier b{font-family:var(--mono)}
  .tier .why{color:var(--muted);font-size:15px}

  .callout{background:var(--accent-soft);border:1px solid var(--line);border-left:3px solid var(--accent);
    border-radius:8px;padding:12px 15px;font-size:16px;margin:14px 0}
  .callout.warn{background:var(--partial-bg);border-left-color:var(--partial)}
  .callout.bad{background:var(--fail-bg);border-left-color:var(--fail);color:var(--fail)}
  .callout.bad b{color:var(--fail)}
  .callout.bad ul{margin:6px 0 0 18px;padding:0}
  ol.reasons{margin:12px 0 14px;padding-left:26px;font-size:16px}
  ol.reasons li{margin:0 0 8px;padding-left:4px}
  ol.reasons li::marker{font-family:var(--mono);font-weight:700;color:var(--accent)}
  .provenance{font-family:var(--mono);font-size:14px;color:var(--muted);margin:10px 0 2px}
  .provenance b{color:var(--ink)}
  /* historical / point-in-time badge */
  /* Per-source freshness chips in the data-sources table, and the data-date stamp. */
  /* A date that wraps to "2026-\A 08-23" is unreadable - the two date columns never break. */
  td.when{white-space:nowrap}
  .fchip{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:700;
    letter-spacing:.03em;white-space:nowrap}
  .fchip.fresh{background:var(--pass-bg);color:var(--pass)}
  .fchip.reused{background:var(--partial-bg);color:var(--partial)}
  .fchip.unavailable{background:var(--fail-bg);color:var(--fail)}
  .datestamp{display:inline-flex;align-items:center;gap:7px;margin:14px 0 0;padding:7px 13px;
    border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:8px;
    background:var(--panel);font-family:var(--mono);font-size:13px;color:var(--ink)}
  .datestamp b{font-family:var(--sans);letter-spacing:.03em;text-transform:uppercase;font-size:11px;
    color:var(--muted)}
  .asof-badge{display:inline-flex;align-items:center;gap:8px;margin:14px 0 0;padding:8px 14px;
    border-radius:10px;background:var(--partial-bg);color:var(--partial);border:1px solid var(--line);
    font-weight:700;font-size:14px}
  .asof-badge .sub2{font-weight:400;color:var(--muted)}

  /* glossary of acronyms (auto-rendered at the end) */
  .glossary{display:grid;grid-template-columns:max-content 1fr;gap:7px 18px;font-size:16px;margin-top:4px}
  .glossary .gterm{font-family:var(--mono);font-weight:700;color:var(--ink);white-space:nowrap}
  .glossary .gdef{color:var(--muted)}
  @media (max-width:560px){.glossary{grid-template-columns:1fr;gap:2px 0}.glossary .gterm{margin-top:8px}}
  footer{margin-top:28px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:14px}
  footer a{color:var(--accent)}
  .sources a{margin-right:12px;white-space:nowrap}

  /* modal window for the per-ticker report */
  .modal{position:fixed;inset:0;background:rgba(10,14,20,.5);display:none;z-index:50;
    align-items:center;justify-content:center;padding:24px}
  .modal.open{display:flex}
  .modal-box{background:var(--panel);border:1px solid var(--line);border-radius:12px;width:min(1200px,96vw);
    height:min(88vh,900px);display:flex;flex-direction:column;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.25)}
  .modal-bar{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 14px;
    border-bottom:1px solid var(--line)}
  .modal-bar .t{font-family:var(--mono);font-weight:700}
  .modal-bar .acts a,.modal-bar .acts button{font-size:14px;margin-left:12px;color:var(--accent);
    background:none;border:none;cursor:pointer;text-decoration:none}
  .modal iframe{border:0;width:100%;height:100%;background:#fff}

  /* leadership map (RS vs % off 52-wk high scatter) */
  .leadmap{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 12px 6px}
  .leadmap svg{display:block;width:100%;height:auto}
  .lm-axis{stroke:var(--line);stroke-width:1}
  .lm-grid{stroke:var(--line);stroke-width:1;opacity:.55}
  .lm-ref{stroke:var(--muted);stroke-width:1;stroke-dasharray:4 4;opacity:.65}
  .lm-zone{fill:var(--accent-soft);opacity:.7}
  .lm-zone-lab{fill:var(--accent);font-size:11.5px;font-family:var(--mono);opacity:.9}
  .lm-axlab{fill:var(--muted);font-size:12.5px;font-family:var(--sans)}
  .lm-tick{fill:var(--muted);font-size:11px;font-family:var(--mono)}
  /* one hue per VERDICT, not per stock - a scatter can only carry a few all-pairs-safe hues.
     Shape repeats the split so the encoding survives colourblindness and greyscale print. */
  .lm-mark{stroke:var(--panel);stroke-width:2}          /* 2px surface ring on overlap */
  .v-buy   .lm-mark{fill:var(--pass)}
  .v-watch .lm-mark{fill:var(--partial)}
  .v-avoid .lm-mark{fill:var(--fail)}
  .v-none  .lm-mark{fill:var(--muted)}
  .lm-leader{stroke:var(--muted);stroke-width:1;opacity:.55}
  .lm-lab{fill:var(--ink);font-size:11.5px;font-family:var(--mono);font-weight:700}
  .lm-legend{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;padding:10px 4px 6px;
    font-size:13px;color:var(--muted)}
  .lm-key{display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);font-size:12.5px;
    color:var(--ink)}
  .lm-legend .hint{font-family:var(--sans);font-style:italic}
  .lm-zonekey{color:var(--muted)}
  .lm-swatch{width:16px;height:12px;border-radius:3px;background:var(--accent-soft);
    border:1px solid var(--accent);opacity:.9;display:inline-block}

  /* the PDF is the default deliverable - keep the white design and the colour chips exact */
  html,body{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  @media print{
    /* The PDF is a WHITE report even when the HTML deliverable is rendered dark. The theme
       tokens are redeclared here so <html data-theme="dark"> prints light rather than laying
       a dark page down on paper. Keep these in step with the :root block above. */
    :root,:root[data-theme="dark"],:root[data-theme="light"]{
      --bg:#ffffff;--panel:#fbfcfd;--ink:#14181f;--muted:#5b6472;--line:#e3e7ec;
      --accent:#1c5fd8;--accent-soft:#eaf1fe;--pass:#0f7a45;--pass-bg:#e4f4ea;--partial:#a76300;
      --partial-bg:#fdf0dc;--fail:#b4231f;--fail-bg:#fbe7e5;--chip:#eef1f5;}
    html,body{background:#fff;color:var(--ink)}
    /* The page inset is owned by @page (15mm on all four edges) - the wrap adds none of its
       own, or the two would stack and the wide pick table would lose the width it needs. */
    .wrap{max-width:none;padding:0}
    .card,.tier,.market,.leadmap,.funnel,#leadmapWrap{break-inside:avoid}
    tbody tr{break-inside:avoid}
    tr.pickrow{break-after:avoid}          /* keep a pick with its CAN SLIM reason */
    tr.grouphead{break-after:avoid}
    .section-title{break-after:avoid}
    thead th{position:static}
    thead{display:table-header-group}
    .tablewrap{overflow:visible}
    table,table.compact{min-width:0;width:100%;table-layout:auto;font-size:13px}
    tbody td{padding:7px 7px}
    thead th{padding:8px 7px;font-size:11px}
    td.stock,td.grp{min-width:0}
    .reason{font-size:13px;line-height:1.45;max-width:none}
    .sc{width:19px;margin-right:1px}
    .sc .mk{width:18px;height:18px;font-size:11px}
    .hint,th .arrow{display:none}
    a{color:var(--accent);text-decoration:none}
    .modal{display:none !important}
    /* A4, landscape: the pick tables are ~10 columns wide and portrait clips them. 15mm of
       margin on every edge is the report's committed print inset - scripts/html_to_pdf.py
       reads both the size and the margin out of this rule and passes them to whichever
       fallback engine it ends up using, so every engine produces the same page. */
    @page{size:A4 landscape;margin:15mm}
  }
</style>
</head>
<body>

<div class="wrap">
  <header class="top">
    <div>
      <h1 id="title">CAN SLIM Sector Recommendations</h1>
      <div class="sub" id="subtitle">Top performers per sector, graded against CAN SLIM</div>
    </div>
    <div class="meta" id="meta"></div>
  </header>

  <div id="asof"></div>
  <div id="datestamp"></div>
  <div class="market" id="market"></div>
  <div id="checks"></div>
  <div id="freshness"></div>
  <div id="dataWarning"></div>
  <div id="dataProvenance"></div>
  <div class="funnel" id="funnel"></div>
  <div id="shortfall"></div>

  <div id="leadmapWrap" style="display:none">
    <div class="section-title">Leadership map <span class="n">- relative strength vs. distance below the 52-week high; leaders cluster top-right. Each mark is one graded name, coloured <b>and</b> shaped by its verdict. The shaded zone marks high RS on new-high ground only - it does <b>not</b> test for a pivot, so a name can sit inside it and still be extended well past any buy point.</span></div>
    <div class="leadmap" id="leadmap"></div>
    <div class="lm-legend" id="leadmapLegend"></div>
  </div>

  <!-- ===================== LIST 1: sector leaders at/above the grade cut ===================== -->
  <div class="section-title" id="leadersTitle">Recommendation 1 &mdash; sector leaders</div>
  <div id="gradeScopeNote"></div>
  <div id="leadersIntro"></div>
  <div class="legend" id="scoreLegend"></div>
  <div class="legend"><span class="hint">Click a column header to sort (sorting flattens the sector grouping). Click a ticker to open its per-name report.</span></div>
  <div class="tablewrap">
    <table>
      <thead><tr id="leadersHead"></tr></thead>
      <tbody id="leadersRows"></tbody>
    </table>
  </div>
  <div id="leadersEmpty"></div>

  <!-- ===================== LIST 2: overall top N by grade ===================== -->
  <div class="section-title" id="topTitle">Recommendation 2 &mdash; overall top performers</div>
  <div id="topIntro"></div>
  <div class="tablewrap" id="topTable">
    <table>
      <thead><tr id="topHead"></tr></thead>
      <tbody id="topRows"></tbody>
    </table>
  </div>

  <!-- ===================== the sweep behind the lists ===================== -->
  <div id="sweepWrap" style="display:none">
    <div class="section-title">Sector sweep <span class="n" id="sweepNote"></span></div>
    <div class="tablewrap">
      <table class="compact">
        <thead><tr id="sweepHead"></tr></thead>
        <tbody id="sweepRows"></tbody>
      </table>
    </div>
  </div>

  <div id="fallbackWrap" style="display:none">
    <div class="section-title" id="fallbackTitle"></div>
    <div id="fallbackIntro"></div>
    <div id="fallback"></div>
  </div>

  <div id="allWrap" style="display:none">
    <div class="section-title">Every name graded <span class="n" id="allNote"></span></div>
    <div class="tablewrap">
      <table>
        <thead><tr id="allHead"></tr></thead>
        <tbody id="allRows"></tbody>
      </table>
    </div>
  </div>

  <div id="rationaleWrap" style="display:none">
    <div class="section-title">Per-name detail</div>
    <div class="cards" id="cards"></div>
  </div>

  <div id="watchWrap" style="display:none">
    <div class="section-title">Watch &mdash; leaders repairing bases (not yet buyable)</div>
    <div id="watch"></div>
  </div>

  <div id="specWrap" style="display:none">
    <div class="section-title">Strong charts that fail the earnings test &mdash; avoid (per method)</div>
    <div id="spec"></div>
  </div>

  <div id="exclWrap" style="display:none">
    <div class="section-title">Sectors excluded (no leaders cleared the sweep)</div>
    <div id="excl"></div>
  </div>

  <div class="callout" id="portfolio"></div>

  <!-- ===================== data sources (always shown) ===================== -->
  <div class="section-title">Data sources &amp; freshness <span class="n" id="srcSub"></span></div>
  <div class="tablewrap">
    <table class="compact">
      <thead><tr id="srcHead"></tr></thead>
      <tbody id="srcRows"></tbody>
    </table>
  </div>

  <div class="section-title">Glossary <span class="n">- acronyms used in this dashboard</span></div>
  <div class="glossary" id="glossary"></div>

  <footer>
    <div id="disclaimer"></div>
    <div class="sources" id="sources" style="margin-top:8px"></div>
    <div style="margin-top:8px">Methodology: CAN SLIM (C &mdash; current quarterly earnings &amp; sales &middot; A &mdash; annual earnings &amp; ROE &middot; N &mdash; new products/management/highs off a base &middot; S &mdash; supply/demand &amp; volume &middot; L &mdash; leader not laggard / relative strength &middot; I &mdash; institutional sponsorship &middot; M &mdash; market direction). Reasons are expressed only in these terms. Letter grades use the same pass/partial/fail rubric as the sister skill <b>can-slim-grader</b>.</div>
  </footer>
</div>

<!-- per-ticker report window -->
<div class="modal" id="modal" role="dialog" aria-modal="true">
  <div class="modal-box">
    <div class="modal-bar">
      <span class="t" id="modalTitle"></span>
      <span class="acts">
        <a id="modalOpen" target="_blank" rel="noopener">Open in new tab</a>
        <button id="modalClose" type="button">Close &times;</button>
      </span>
    </div>
    <iframe id="modalFrame" title="per-ticker CAN SLIM report"></iframe>
  </div>
</div>

<script>
/* ============================ FILL THIS PER RUN ============================ */
const CONFIG = {
  title: "CAN SLIM Sector Recommendations",
  subtitle: "Top 10 performers per sector (TradingView), each graded against CAN SLIM",
  // WHEN THE REPORT WAS BUILT. Not the same thing as when the market data is from - a run on a
  // Sunday reads Friday's close. Both are printed, and never merged into one string.
  generatedAt: "2026-08-23",
  // WHAT DATE THE MARKET DATA IS AS OF - REQUIRED, and the page prints a red check banner
  // without it. This is the newest bar/filing the run actually saw, e.g. "2026-08-21 close".
  // Every reader question that starts "how old is this?" is answered by this field.
  dataDate: "",
  dataSource: "TradingView screener + bars/financials; sponsorship from filings/web",
  // Historical / point-in-time mode: set to a past date (e.g. "2023-01-31") to mark the whole
  // page as an as-of reconstruction (renders an "AS OF ..." badge). Leave "" for a live run.
  asOf: "",

  /* --- FRESHNESS: every run attempts a fresh pull of every source; this is where the run says
     whether it got one. REQUIRED. The page renders a green line when everything came back
     fresh and an amber callout enumerating each failure when it did not - and the self-audit
     refuses a report whose sourceMap admits reused data that is not declared here.

     Reuse is a fallback, never a shortcut: only after a fresh pull was ATTEMPTED and failed,
     and only when the older figure is still applicable to the question being asked. Say so
     here, with the date of what was reused, so nothing stale is ever passed off as current. */
  freshness: {
    attemptedAt: "",        // when this run tried the sources, e.g. "2026-08-23 13:40 UTC"
    allFresh: true,         // false if ANY source fell back to older data or came back empty
    // One entry per source that did not come back fresh. Leave [] when allFresh is true.
    failures: [
      // { item:"I - institutional sponsorship",       // which class of figure
      //   source:"TradingView get_symbol_data",       // what was attempted
      //   error:"ownership columns returned null for every symbol queried; I is capped at "+
      //         "partial for every name rather than guessed",   // why, and what it costs
      //   fallback:"",                                // what OLDER data was reused, if any.
      //                                               // Leave "" when nothing was reused - the
      //                                               // page then says the gap was worked around.
      //   fallbackDate:"" }                           // REQUIRED whenever `fallback` is set:
      //                                               // the date the reused data is from.
    ]
  },

  // --- the two recommendation lists are DERIVED from picks[] using these knobs ---
  gradeThreshold: 4.5,   // list 1 = every graded name at/above this score out of 7
  topCount: 10,          // list 2 = the N highest-graded names market-wide
  // Both lists only ever contain names at/above the cut, so list 2 goes EMPTY (with an
  // enumerated why) rather than ranking sub-cut names. Set false only if you deliberately want
  // list 2 to rank the top N by grade regardless - sub-cut rows are then badged "below cut".
  topRequiresThreshold: true,
  // Optional run-specific reasons appended to list 2's empty state. The page already derives
  // the evidence-based ones (the M grade, which letters failed and how often, the best score
  // reached, what the hard filters removed, how many sectors came back empty) - add only what
  // the grades cannot show on their own, e.g. "Earnings season is mid-flight: 14 of the 38
  // graded names report within 10 sessions, so C is provisional across the sweep."
  noQualifierReasons: [],

  // One line naming which data sources ACTUALLY contributed to this run (renders as a
  // "Data sources used:" line under the market banner). Be specific about which letters came
  // from where, e.g. "TradingView run_screener (sector sweep) + get_ohlcv/get_financial_history
  // /get_earnings_history (C/A/N/S/L/M); I from SEC 13F via securities-filings-lookup".
  // REQUIRED - the page prints a red check banner if this is empty.
  dataProvenance: "",
  // Set a short warning whenever any source was STALE or GATED and the analysis leaned on a
  // fallback (renders an amber caveat banner). Say what was gated/stale and what filled the
  // gap. Leave "" if everything resolved from the preferred sources with fresh data.
  dataWarning: "",

  /* Per-datum provenance, rendered as the "Data sources & freshness" table. REQUIRED - one row
     per class of figure in the report. Every row needs BOTH dates and a status:
       item    - which class of figure this row covers
       source  - the tool / feed it came from
       pulled  - WHEN THE CALL WAS MADE (required; the audit rejects a row without it)
       asOf    - WHAT DATE THE DATA ITSELF IS FROM (newest bar, filed quarter, ...). Required
                 for a reused row; strongly preferred everywhere, since "pulled today" says
                 nothing about whether the figure underneath is a week old.
       status  - "fresh"       pulled successfully in THIS run (the default when omitted)
                 "reused"      a fresh pull was attempted and failed, so older data was used
                 "unavailable" no data at all - the report works around the gap and says how
       note    - anything a reader needs to judge the figure
     A "reused" or "unavailable" row MUST have a matching entry in freshness.failures, or the
     self-audit refuses the report. */
  sourceMap: [
    // { item:"Sector sweep (top 10 per sector)", source:"TradingView run_screener, Perf.6M",
    //   pulled:"2026-08-23 14:05 UTC", asOf:"2026-08-21 close", status:"fresh",
    //   note:"20 sectors, US primary listings, >$20M avg $ volume" },
    // { item:"C - quarterly EPS & sales", source:"TradingView get_financial_history (fq)",
    //   pulled:"2026-08-23 14:12 UTC", asOf:"Q2/2026 as filed", status:"fresh", note:"" },
    // { item:"I - institutional sponsorship", source:"SEC 13F via securities-filings-lookup",
    //   pulled:"-", asOf:"", status:"unavailable", note:"gated this run; I capped at partial" }
  ],

  // The screening funnel - the numbers that make the sweep auditable. Rendered as stat tiles.
  sweep: {
    windowLabel: "6-month price performance",   // the ranking window used for "top performers"
    benchmark: "SPY +11.2% over the same window",
    sectorsScanned: 0,
    perSector: 10,
    screened: 0,        // sectors x perSector
    triaged: 0,         // survived the CAN SLIM hard filters (sector_screen.py)
    graded: 0,          // fully graded with can-slim-grader
    /* THE COVERAGE CONTRACT. `mustGrade` is sector_screen.py's `must_grade`: the number of
       triage survivors whose CEILING - the highest score still reachable once M, I and the
       screener-known N/S/L are fixed and C/A are assumed to pass - reaches gradeThreshold.
       Every one of those MUST be fully graded, because no combination of unseen fundamentals
       could lift the others to the cut. Grading fewer is an incomplete run and the self-audit
       refuses it, so a qualifier can never be missed merely because the run stopped early.
       `eliminatedByCeiling` is the rest of the survivors: not graded, but provably unable to
       reach the cut - eliminated by arithmetic, never by judgment. */
    mustGrade: 0,
    eliminatedByCeiling: 0,
    note: ""            // e.g. "Universe: US primary listings, price >$15, avg $ volume >$20M."
  },

  market: {
    verdict: "Confirmed uptrend - narrow & selective",   // badge text
    tone: "pressure",                                     // "up" | "pressure" | "down"
    mGrade: "partial",                                    // "pass" | "partial" | "fail" - graded ONCE, applied to every row
    distributionDays: "SPY 5 / QQQ 7 over ~5 weeks",
    implication: "Indices near highs above the 50-day, but leadership is narrow (M intact but late-stage). Buy only genuine leaders emerging from sound bases; normal 7-8% stops."
  },

  // Set when the grade cut leaves fewer names than the user hoped for (never pad).
  shortfall: "",

  // EVERY fully graded name goes here - the page derives BOTH recommendation lists from it.
  // scores = pass|partial|fail per letter (M comes from market.mGrade). reason = CAN SLIM terms ONLY.
  // Optional: high52 (enables the pivot check), verdict, reviewUrl (makes the ticker clickable).
  picks: [
    // {
    //   symbol:"ANET", company:"Arista Networks", sector:"Electronic Technology",
    //   group:"AI networking", sectorRank:2,
    //   price:"186.96", rs:"+51", offHigh:"2%", high52:"190.80",
    //   buyPoint:"178.40", stop:"164.50", verdict:"BUY-RANGE",
    //   scores:{C:"pass", A:"pass", N:"pass", S:"partial", L:"pass", I:"pass"},
    //   reason:"C: Q EPS +32% / sales +35%, accelerating. A: EPS up each of 3 yrs at >25% with ROE 31%. N: new AI-cluster product, breaking out of an 8-week flat base at a new high. S: breakout volume +62% vs the 50-day average. L: RS +51 vs SPY, #1 of its group's top-10. I: fund ownership up 4 quarters running.",
    //   reviewUrl:"reviews/ANET-canslim.html"
    // }
  ],

  rationale: [ /* { symbol, company, text } */ ],
  watch: [ /* { symbol, company, sector, offHigh, note } */ ],
  speculative: [ /* { symbol, company, reason } */ ],
  excluded: [ /* { group, names, reason } */ ],

  // The sector sweep ranking behind the lists (straight from sector_screen.py output).
  // `top5` is the sector's highest-ranked names in the SCREENER's own order - paste it from
  // sector_screen.py's `top5`. It renders ONLY for a sector whose `qualified` count is 0, under a
  // clearly-marked "ungraded, not recommendations" banner, so a sector that produced nothing is
  // not a blank page. Omit it and such a sector simply shows nothing.
  sectors: [
    // { rank:1, sector:"Electronic Technology", medianPerf:"+34.2%", survivors:6, considered:10,
    //   qualified:3, leaders:"ANET, AVGO, VRT", note:"Group leadership intact; three at new highs.",
    //   top5:[ {sectorRank:1, ticker:"BLZE", company:"Backblaze", perf:"+275.9%", rs:"+264",
    //           triage:"drop", note:"dropped: 32% below the 52-week high"} ] }
  ],

  showAllGraded: true,   // render the "Every name graded" appendix table

  // A glossary of the standard CAN SLIM + finance acronyms auto-renders at the end of the page
  // (see DEFAULT_GLOSSARY in the script). Add run-specific terms here to EXTEND it - each entry
  // is { term, def }; anything whose term matches a default is ignored. Leave [] to use defaults.
  glossary: [ /* { term:"XYZ", def:"..." } */ ],

  portfolioNote: "The method favors concentration (4-6 names), so treat both lists as a research shortlist to narrow, not a buy-all list. Cut every loss at 7-8% (no exceptions), average up never down, take many 20-25% gains but let a powerful leader run if it jumps 20%+ in 1-3 weeks. Re-check M - if distribution days keep building, raise cash.",
  disclaimer: "Informational decision support, not investment advice; not a financial advisor. Figures are as-of the timestamp; RS is a relative-strength proxy (window performance vs SPY), not a full-market 1-99 rating; fundamentals may lag the latest quarter. Nothing here is an order; no orders were or will be placed.",
  sources: [ /* { label, url } */ ]
};
/* ========================================================================== */

const $ = (id)=>document.getElementById(id);
const esc = (s)=> (s==null?"":String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const rsClass = (v)=> /^[-\u2212]/.test(String(v).trim()) ? "neg" : "pos";
// parse a messy numeric string ("+51","-14%","1,188",">1,220 breakout","~178 pivot") -> number|NaN
const num = (s)=>{ if(s==null) return NaN; const m=String(s).replace(/,/g,'').match(/-?\d+(\.\d+)?/); return m?parseFloat(m[0]):NaN; };

/* ---- grading: pass/partial/fail per letter; total = C+A+N+S+L+I + M, out of 7 ----
   Identical rubric and arithmetic to the sister skill can-slim-grader, so a 4.5 here and a
   4.5 there mean the same thing. */
const WEIGHT = {pass:1, partial:0.5, fail:0};
const LETTERS6 = ["C","A","N","S","L","I"];
const isGrade = (v)=> WEIGHT.hasOwnProperty(String(v==null?"":v).trim().toLowerCase());
const gradeOf = (v)=>{ const g=String(v==null?"":v).trim().toLowerCase(); return WEIGHT.hasOwnProperty(g)?g:"fail"; };
const mGrade = ()=> gradeOf((CONFIG.market||{}).mGrade);
const scoreTotal = (p)=> LETTERS6.reduce((n,k)=> n+WEIGHT[gradeOf((p.scores||{})[k])], 0) + WEIGHT[mGrade()];
const fmtScore = (v)=> (Math.round(v*2)/2).toFixed(1).replace(/\.0$/,"");
const THRESHOLD = Number(CONFIG.gradeThreshold)||4.5;
const TOPN = Number(CONFIG.topCount)||10;

document.title = CONFIG.title || "CAN SLIM Sector Recommendations";
$("title").textContent = CONFIG.title || document.title;
if (CONFIG.subtitle) $("subtitle").textContent = CONFIG.subtitle;
$("meta").innerHTML = "Generated " + esc(CONFIG.generatedAt||"") + "<br>" + esc(CONFIG.dataSource||"");

/* ---- the data date, stamped where nobody can miss it ----
   generatedAt says when the report was built; dataDate says how old the market data underneath
   it is. They are different questions and a report that answers only the first is misleading,
   so this is rendered on its own line and the self-audit requires it. ---- */
(function(){
  const dd = CONFIG.dataDate;
  $("datestamp").innerHTML = dd
    ? '<div class="datestamp"><b>Data as of</b> ' + esc(dd) +
      (CONFIG.generatedAt ? ' <span style="color:var(--muted)">&middot; report generated ' +
        esc(CONFIG.generatedAt) + '</span>' : '') + '</div>'
    : '';
})();

/* ---- freshness: did this run actually get fresh data? ----
   Every run attempts a fresh pull of every source. This block reports the outcome either way -
   a green line when everything came back fresh, an enumerated amber callout when something did
   not, naming what failed, why, what was used instead, and THAT fallback's date. Silence is
   never an option: the audit below rejects a sourceMap that admits reuse this block does not
   declare. ---- */
(function(){
  const f = CONFIG.freshness || {};
  const fails = Array.isArray(f.failures) ? f.failures : [];
  const when = f.attemptedAt ? ' on ' + esc(f.attemptedAt) : '';
  if (!fails.length && f.allFresh !== false){
    $("freshness").innerHTML = '<div class="callout"><b>&#10003; Fresh data:</b> every source in the '+
      'table below was pulled fresh for this run' + when + '. Nothing was carried over from an '+
      'earlier run or an earlier point in this conversation.</div>';
    return;
  }
  const li = fails.map(x=>{
    const used = x.fallback
      ? ' <b>Used instead:</b> ' + esc(x.fallback) +
        (x.fallbackDate ? ' <b>(data dated ' + esc(x.fallbackDate) + ')</b>' : ' <b>(no date given)</b>')
      : ' <b>Used instead:</b> nothing - the report works around the gap.';
    return '<li><b>' + esc(x.item||'(unnamed source)') + '</b> via ' + esc(x.source||'(source not named)') +
           ' &mdash; ' + esc(x.error||'fresh pull failed') + '.' + used + '</li>';
  }).join('');
  $("freshness").innerHTML = '<div class="callout warn"><b>&#9888; Not all data is fresh.</b> A fresh '+
    'pull was attempted for every source' + when + '. ' + fails.length + ' did not come back fresh:'+
    '<ul style="margin:6px 0 0 18px;padding:0">' + (li ||
      '<li>freshness.allFresh is false but no failures are listed - the run must say what was not fresh.</li>') +
    '</ul></div>';
})();

if (CONFIG.asOf){
  $("asof").innerHTML = '<div class="asof-badge">&#9203; AS OF ' + esc(CONFIG.asOf) +
    ' <span class="sub2">- historical reconstruction (point-in-time), not a survivorship-free backtest</span></div>';
}

const m = CONFIG.market||{};
const M_LABEL = {pass:"PASS", partial:"PART", fail:"FAIL"};
$("market").innerHTML =
  '<span class="verdict '+esc(m.tone||'up')+'">'+esc(m.verdict||'')+'</span>'+
  '<div class="imp"><b>M &mdash; market direction ('+M_LABEL[mGrade()]+'):</b> '+esc(m.implication||'')+'</div>'+
  (m.distributionDays?'<div class="dd">Distribution days: '+esc(m.distributionDays)+'</div>':'');

// data provenance (which sources actually contributed) + a warning when any is stale/gated.
const prov = CONFIG.dataProvenance || CONFIG.dataSource;
if (prov){
  $("dataProvenance").innerHTML = '<div class="provenance"><b>Data sources used:</b> '+esc(prov)+'</div>';
}
if (CONFIG.dataWarning){
  $("dataWarning").innerHTML = '<div class="callout warn">&#9888; <b>Data caveat:</b> '+esc(CONFIG.dataWarning)+'</div>';
}

// ---- the screening funnel ----
(function(){
  const s = CONFIG.sweep||{};
  const tiles = [
    {k:"Sectors swept", v:s.sectorsScanned, s:s.windowLabel||""},
    {k:"Top performers pulled", v:s.screened, s:(s.perSector? s.perSector+" per sector":"")},
    {k:"Cleared triage", v:s.triaged, s:"CAN SLIM hard filters"},
    {k:"Could still reach the cut", v:s.mustGrade||null,
     s:(s.eliminatedByCeiling? s.eliminatedByCeiling+" ruled out by ceiling":"ceiling test")},
    {k:"Fully graded", v:s.graded, s:"can-slim-grader rubric"},
    /* No "7" anywhere in this tile. Its value is a COUNT of names, and the label sits directly
       above it while the sub-label sits directly below - so either one ending or starting with
       "7" makes the count read as a score ("2 of 7", "out of 72"). The /7 scale is stated in the
       table legend, where it belongs. */
    {id:"qualified", k:"Graded &ge;"+fmtScore(THRESHOLD), v:null, s:"names at or above the cut"}
  ];
  window.__tiles = tiles;   // count filled in after picks are scored
})();

// ---- score every pick once, then DERIVE both lists ----
const allPicks = (CONFIG.picks||[]).map(p=>{
  const t = scoreTotal(p);
  return Object.assign({}, p, {_total:t, _rs:num(p.rs), _off:num(p.offHigh)});
});
// strongest first: grade, then RS, then nearest the 52-week high
const byGrade = (a,b)=> (b._total-a._total)
  || ((isNaN(b._rs)?-1e9:b._rs)-(isNaN(a._rs)?-1e9:a._rs))
  || ((isNaN(a._off)?1e9:Math.abs(a._off))-(isNaN(b._off)?1e9:Math.abs(b._off)));

const qualified = allPicks.filter(p=> p._total >= THRESHOLD).sort(byGrade);   // list 1 pool
// List 2 is the best of the SAME qualifying pool - a name below the cut is not a
// recommendation just because others scored worse, so it never appears here. Set
// CONFIG.topRequiresThreshold = false to get the old ungated "top N by grade" ranking instead.
const TOP_GATED = CONFIG.topRequiresThreshold !== false;
const topOverall = (TOP_GATED ? qualified : allPicks).slice().sort(byGrade).slice(0, TOPN);
const topSet = new Set(topOverall.map(p=>p.symbol));
const qualSet = new Set(qualified.map(p=>p.symbol));

// sector order for list 1: follow CONFIG.sectors ranking when given, else best grade first
const sectorOrder = new Map((CONFIG.sectors||[]).map((s,i)=>[s.sector, (s.rank!=null?Number(s.rank):i+1)]));
function sectorKey(p){ return p.sector || p.group || "Unclassified"; }
const groupedLeaders = (()=>{
  const g = new Map();
  qualified.forEach(p=>{ const k=sectorKey(p); if(!g.has(k)) g.set(k,[]); g.get(k).push(p); });
  const keys = Array.from(g.keys()).sort((a,b)=>{
    const ra = sectorOrder.has(a)?sectorOrder.get(a):9e3, rb = sectorOrder.has(b)?sectorOrder.get(b):9e3;
    if (ra!==rb) return ra-rb;
    return Math.max(...g.get(b).map(p=>p._total)) - Math.max(...g.get(a).map(p=>p._total));
  });
  return keys.map(k=>({sector:k, rows:g.get(k).sort(byGrade)}));
})();

// funnel tiles (now that the grade count is known)
(function(){
  // Address the tile by identity, never by index - inserting a tile above it used to
  // silently write the qualifier count into whichever tile had drifted into slot 4.
  const tiles = window.__tiles;
  const qt = tiles.find(t=>t.id==="qualified"); if (qt) qt.v = qualified.length;
  $("funnel").innerHTML = tiles.map(t=>
    '<div class="fstep"><div class="k">'+t.k+'</div><div class="v">'+
    (t.v==null||t.v===""?"-":esc(t.v))+'</div>'+(t.s?'<div class="s">'+esc(t.s)+'</div>':'')+'</div>').join('');
})();

// ---- table plumbing shared by all three pick tables ----
/* `offHigh` is deliberately NOT a column - it still feeds the leadership map's y-axis, the
   grade tiebreaker and the pivot self-audit, and every pick's `reason` states it in words.
   Dropping the column buys the width back for the scorecard, verdict and price fields. */
const COLS = [
  {key:"rank",   label:"#",            type:"num",  cls:"",     get:(p,i)=>i+1, noSort:true},
  {key:"symbol", label:"Stock",        type:"text", cls:"",     get:p=>(p.symbol||"")},
  {key:"sector", label:"Sector / group",type:"text",cls:"",     get:p=>sectorKey(p)},
  {key:"price",  label:"Price",        type:"num",  cls:"num",  get:p=>num(p.price)},
  {key:"rs",     label:"RS",           type:"num",  cls:"num",  get:p=>p._rs},
  {key:"score",  label:"C&middot;A&middot;N&middot;S&middot;L&middot;I&middot;M &mdash; total out of 7", type:"num", cls:"", get:p=>p._total},
  {key:"verdict",label:"Verdict",      type:"text", cls:"",     get:p=>(p.verdict||"")},
  {key:"buyPoint",label:"Buy point",   type:"text", cls:"num",  get:p=>(p.buyPoint||""), noSort:true},
  {key:"stop",   label:"Stop",         type:"text", cls:"num",  get:p=>(p.stop||""),      noSort:true},
];
// The CAN SLIM reason is NOT a column - it is a full-width sub-row under each pick, so it stays
// readable instead of being squeezed into a 400px cell (and so the table fits an A4 page).

function headHtml(){
  return COLS.map(c=>{
    const sortable = !c.noSort;
    return '<th class="'+c.cls+(sortable?' sortable':'')+'" data-key="'+c.key+'">'+c.label+
      (sortable?' <span class="arrow">&#9662;</span>':'')+'</th>';
  }).join('');
}

function scoreCells(p){
  const ms = mGrade(), LAB = {pass:"P", partial:"~", fail:"X"};
  const t = p._total;
  /* Each letter carries a visually-hidden ":grade " so the cell still reads correctly once the
     markup is flattened. Without it the inline spans fuse into "CPAPN~SXLPI~M~". */
  const cell = (k,g,extra,title)=>
    '<span class="sc'+extra+'" title="'+title+'"><span class="lab">'+k+'</span>'+
    '<span class="mk g-'+g+'">'+LAB[g]+'</span></span><span class="vh">:'+g+' </span>';
  return LETTERS6.map(k=>{ const g=gradeOf((p.scores||{})[k]); return cell(k,g,'',k+': '+g); }).join('')
    + cell('M', ms, ' mcol', 'M = market direction (same for every row): '+ms)
    /* Value THEN denominator, in one span - the exact form the sister skill can-slim-grader
       prints ("4.5 / 7"), so a score means and reads the same in both reports. */
    + '<span class="sc-total'+(t>=THRESHOLD?' hit':'')+'" title="total out of 7">'
    + fmtScore(t)+' / 7</span>';
}

/* BUY-RANGE / WATCH / AVOID - the same three verdicts can-slim-grader issues. It is NOT the
   grade: a name can clear 4.5/7 on C/A/L and still have no valid pivot (N fail), which is a
   WATCH, not a buy. Showing both stops the grade being read as an entry signal. */
function verdictChip(p){
  const v = String(p.verdict||"").toUpperCase();
  if (!v) return '<span class="co">-</span>';
  const cls = v.indexOf("BUY")===0 ? "vd-buy" : (v.indexOf("AVOID")===0 ? "vd-avoid" : "vd-watch");
  return '<span class="vd '+cls+'">'+esc(v)+'</span>';
}

function rowHtml(p, i, opts){
  opts = opts||{};
  const tk = p.reviewUrl
    ? '<a class="sym" data-review="'+esc(p.reviewUrl)+'" data-sym="'+esc(p.symbol)+'">'+esc(p.symbol)+'</a>'
    : '<span class="sym">'+esc(p.symbol)+'</span>';
  let badge = "";
  if (opts.markTop && topSet.has(p.symbol)) badge = '<span class="badge" title="also in the overall top '+TOPN+'">TOP '+TOPN+'</span>';
  if (opts.markQual) badge = qualSet.has(p.symbol)
    ? '<span class="badge" title="also a sector leader at or above the grade cut">&ge;'+fmtScore(THRESHOLD)+'</span>'
    : '<span class="badge warn" title="in the overall top '+TOPN+' by grade but below the '+fmtScore(THRESHOLD)+' cut">below cut</span>';
  const sect = esc(sectorKey(p)) + (p.sectorRank? ' <span class="co">#'+esc(p.sectorRank)+' in sector</span>' : '');
  return '<tr class="pickrow">'+
    '<td class="rk">'+(i+1)+'</td>'+
    '<td class="stock">'+tk+badge+'<div class="co">'+esc(p.company)+'</div></td>'+
    '<td class="grp">'+sect+(p.group&&p.group!==p.sector?'<div class="co">'+esc(p.group)+'</div>':'')+'</td>'+
    '<td class="num">'+esc(p.price)+'</td>'+
    '<td class="num '+rsClass(p.rs)+'">'+esc(p.rs)+'</td>'+
    '<td class="scorecells">'+scoreCells(p)+'</td>'+
    '<td>'+verdictChip(p)+'</td>'+
    '<td class="num">'+esc(p.buyPoint)+'</td>'+
    '<td class="num">'+esc(p.stop)+'</td>'+
  '</tr>'+
  '<tr class="whyrow"><td colspan="'+COLS.length+'" class="reason">'+
    '<span class="wlab">Why (CAN SLIM read)</span>'+esc(p.reason)+'</td></tr>';
}

function emptyRow(msg){
  return '<tr><td colspan="'+COLS.length+'" style="padding:18px;color:var(--muted)">'+esc(msg)+'</td></tr>';
}

/* A sortable table. `groups` (optional) renders sector group headers; sorting flattens them. */
function makeTable(headId, bodyId, flatList, opts){
  opts = opts||{};
  $(headId).innerHTML = headHtml();
  const state = {key:null, dir:1};
  function renderGrouped(){
    if (!flatList.length){ $(bodyId).innerHTML = emptyRow(opts.emptyMsg||"No names qualified."); return; }
    let i = 0, html = "";
    opts.groups.forEach(g=>{
      const meta = (CONFIG.sectors||[]).find(s=>s.sector===g.sector) || {};
      html += '<tr class="grouphead"><td colspan="'+COLS.length+'">'+esc(g.sector)+
        ' <span class="gmeta">- '+g.rows.length+' at or above '+fmtScore(THRESHOLD)+'/7'+
        (meta.rank?' &middot; sector rank #'+esc(meta.rank):'')+
        (meta.medianPerf?' &middot; median '+esc(meta.medianPerf):'')+'</span></td></tr>';
      g.rows.forEach(p=>{ html += rowHtml(p, i++, opts); });
    });
    $(bodyId).innerHTML = html;
  }
  function renderFlat(list){
    $(bodyId).innerHTML = list.map((p,i)=>rowHtml(p,i,opts)).join('') || emptyRow(opts.emptyMsg||"No names qualified.");
  }
  function draw(){
    if (state.key===null && opts.groups) renderGrouped();
    else {
      const col = COLS.find(c=>c.key===state.key);
      const list = col ? flatList.slice().sort((a,b)=>{
        let va=col.get(a,0), vb=col.get(b,0);
        if(col.type==="num"){ const na=isNaN(va), nb=isNaN(vb); if(na&&nb)return 0; if(na)return 1; if(nb)return -1; return (va-vb)*state.dir; }
        return String(va).localeCompare(String(vb),undefined,{sensitivity:'base'})*state.dir;
      }) : flatList;
      renderFlat(list);
    }
    Array.from($(headId).children).forEach(th=>{
      th.classList.toggle('sorted', th.dataset.key===state.key);
      const ar=th.querySelector('.arrow'); if(ar) ar.innerHTML = th.dataset.key===state.key ? (state.dir>0?'&#9652;':'&#9662;') : '&#9662;';
    });
  }
  $(headId).addEventListener('click', e=>{
    const th=e.target.closest('th'); if(!th||!th.dataset.key) return;
    const col=COLS.find(c=>c.key===th.dataset.key); if(!col||col.noSort) return;
    state.dir = (state.key===th.dataset.key) ? -state.dir : (col.type==="num" ? -1 : 1);
    state.key = th.dataset.key;
    draw();
  });
  draw();
}

// ---- legend ----
$("scoreLegend").innerHTML =
  '<span><span class="dot pass"></span>P = pass (1.0)</span>'+
  '<span><span class="dot partial"></span>~ = partial (0.5)</span>'+
  '<span><span class="dot fail"></span>X = fail (0)</span>'+
  '<span class="note" style="color:var(--muted)">Total = C&middot;A&middot;N&middot;S&middot;L&middot;I + <b>M</b> (market, same for every row) out of <b>7</b> - the same scale the sister skill <b>can-slim-grader</b> uses. RS = window performance vs SPY. '+
  'The <b>verdict</b> is separate from the grade: a name can clear '+fmtScore(THRESHOLD)+'/7 on earnings and leadership and still be a <b>WATCH</b> because it has no valid pivot (N).</span>';

// ---- LIST 1: sector leaders at/above the cut ----
// Say plainly what the lists do and do not contain. A reader must never take a name's
// absence for a judgment on it when it was simply never graded - or, conversely, take the
// listed names for the whole market when the cut is what selected them.
(function(){
  const sw = CONFIG.sweep||{};
  let t = "Both lists contain ONLY names that scored "+fmtScore(THRESHOLD)+"/7 or better. "+
          "A name graded below the cut is not listed as a recommendation.";
  if (sw.mustGrade && sw.graded)
    t += " Coverage: every one of the "+sw.mustGrade+" triage survivors that could still reach "+
         fmtScore(THRESHOLD)+"/7 was graded ("+sw.graded+" graded in total)"+
         (sw.eliminatedByCeiling? "; the other "+sw.eliminatedByCeiling+" were eliminated without "+
          "a grade because their best reachable score was below the cut" : "")+".";
  const el = $("gradeScopeNote"); if (el) el.innerHTML = '<div class="callout">&#9432; '+t+'</div>';
})();

$("leadersTitle").innerHTML = 'Recommendation 1 &mdash; sector leaders graded &ge;'+fmtScore(THRESHOLD)+
  '/7 <span class="n">- '+qualified.length+' name'+(qualified.length===1?'':'s')+' across '+
  groupedLeaders.length+' sector'+(groupedLeaders.length===1?'':'s')+'</span>';
$("leadersIntro").innerHTML = '<div class="callout">Every top-of-sector performer that reached <b>'+
  fmtScore(THRESHOLD)+' of 7</b> on the CAN SLIM scorecard, grouped by sector and ordered by grade. '+
  'A sector missing from this list had no name clear the cut - that is a finding about the sector, not an omission.</div>';
makeTable("leadersHead","leadersRows", qualified, {groups:groupedLeaders, markTop:true,
  emptyMsg:"No name from any sector's top performers reached "+fmtScore(THRESHOLD)+"/7 in this market. Per the method, that is the answer - nothing is padded in."});
if (!qualified.length && CONFIG.shortfall){
  $("leadersEmpty").innerHTML = '<div class="callout warn">'+esc(CONFIG.shortfall)+'</div>';
} else if (CONFIG.shortfall){
  $("shortfall").innerHTML = '<div class="callout">'+esc(CONFIG.shortfall)+'</div>';
}

// ---- LIST 2: overall top N ----
/* Every entry here is a recommendation, so the list is EMPTY when nothing clears the cut - and
   an empty list has to say why. The reasons are derived from the graded pool itself (the market
   grade, which letters actually failed, the best score reached, what the hard filters removed)
   so they are evidence, not narration; CONFIG.noQualifierReasons is appended for anything
   run-specific the grades cannot show on their own. */
function noQualifierReasons(){
  const R = [], sw = CONFIG.sweep||{}, mkt = CONFIG.market||{};
  const NAMES = {C:"C - current quarterly earnings & sales", A:"A - annual earnings & ROE",
                 N:"N - new highs from a sound base", S:"S - supply & demand / volume",
                 L:"L - leader, not laggard", I:"I - institutional sponsorship"};

  if (!allPicks.length){
    R.push("Nothing reached the grading stage" +
      (sw.screened ? " - of the " + sw.screened + " top performers pulled, none cleared the CAN SLIM hard filters" +
        " (price floor, dollar volume, within 25% of the 52-week high, ahead of SPY, above the 200-day)." : "."));
    return R.concat(CONFIG.noQualifierReasons||[]);
  }

  const mg = mGrade();
  if (mg !== "pass"){
    R.push("M - market direction is " + (mkt.verdict||"not a confirmed uptrend") + ", graded " +
      (mg==="fail" ? "FAIL" : "PARTIAL") + ". M is one of the seven letters and is scored once for the whole " +
      "market, so every name in the sweep starts " + (mg==="fail" ? "a full point" : "half a point") +
      " short of 7" + (mkt.distributionDays ? " (" + mkt.distributionDays + ")" : "") +
      ". The method does not buy breakouts into this.");
  }

  // which letters actually did the damage, worst first
  const tally = {};
  LETTERS6.forEach(k=>{ tally[k]={pass:0, partial:0, fail:0}; });
  allPicks.forEach(p=> LETTERS6.forEach(k=>{ tally[k][gradeOf((p.scores||{})[k])]++; }));
  LETTERS6.slice()
    .sort((a,b)=> (tally[b].fail - tally[a].fail) || (tally[b].partial - tally[a].partial))
    .filter(k=> tally[k].fail || tally[k].partial)
    .slice(0,3)
    .forEach(k=>{
      const t = tally[k], bits = [];
      if (t.fail) bits.push(t.fail + " FAIL");
      if (t.partial) bits.push(t.partial + " PARTIAL");
      R.push(NAMES[k] + " - " + bits.join(" and ") + " of the " + allPicks.length +
        " names graded" + (t.pass ? " (only " + t.pass + " passed)" : " (none passed)") + ".");
    });

  const best = allPicks.slice().sort(byGrade)[0];
  R.push("The strongest scorecard in the whole sweep was " + (best.symbol||"?") + " at " +
    fmtScore(best._total) + "/7 - still " + fmtScore(THRESHOLD - best._total) +
    " points short of the " + fmtScore(THRESHOLD) + " cut.");

  // Two different reasons a pulled name never got a grade - the hard filters and a grading cap.
  // Never merge them: "dropped on the filters" said of a name that was simply not reached is false.
  if (sw.screened && sw.triaged && sw.screened > sw.triaged){
    R.push((sw.screened - sw.triaged) + " of the " + sw.screened + " top performers pulled were dropped by the " +
      "hard filters before grading (below the price floor, too thin, more than 25% below the 52-week high, " +
      "lagging SPY, or under the 200-day).");
  }
  if (sw.triaged && sw.graded && sw.triaged > sw.graded){
    R.push((sw.triaged - sw.graded) + " further names cleared triage but were never graded in this run - they are " +
      "absent from both lists because they were not reached, not because they failed. Coverage is " +
      sw.graded + " of " + sw.triaged + ".");
  } else if (!sw.triaged && sw.screened && sw.graded && sw.screened > sw.graded){
    R.push((sw.screened - sw.graded) + " of the " + sw.screened + " top performers pulled never reached grading - " +
      "dropped on the hard filters (below the price floor, too thin, more than 25% below the 52-week high, " +
      "lagging SPY, or under the 200-day).");
  }

  // Prefer the funnel's own count: CONFIG.sectors may list only the sectors worth tabulating,
  // and disagreeing with the "Sectors swept" tile directly above is worse than saying nothing.
  const secs = Number(sw.sectorsScanned) || (CONFIG.sectors||[]).length;
  if (secs) R.push("All " + secs + " sectors swept produced zero qualifiers - this is a market-wide read, not one weak group.");

  return R.concat(CONFIG.noQualifierReasons||[]);
}

const topEmpty = !topOverall.length;
$("topTitle").innerHTML = 'Recommendation 2 &mdash; overall top '+TOPN+
  (topEmpty ? ' <span class="n">- <b>empty</b>: no name in the sweep qualifies</span>'
            : ' <span class="n">- highest CAN SLIM grades market-wide, any sector</span>');

if (topEmpty){
  $("topTable").style.display = 'none';
  $("topIntro").innerHTML =
    '<div class="callout bad"><b>Empty - no recommendations.</b> '+
    (allPicks.length
      ? 'None of the '+allPicks.length+' graded names reached '+fmtScore(THRESHOLD)+' of 7, so there is nothing to rank here. '
      : 'Nothing in the sweep was gradeable, so there is nothing to rank here. ')+
    'Per the method that is the answer - the list is not backfilled with the least-weak names. '+
    'The reasons, from the grades themselves:</div>'+
    '<ol class="reasons">'+noQualifierReasons().map(r=>'<li>'+esc(r)+'</li>').join('')+'</ol>'+
    '<div class="callout">What would refill this list: M returning to a confirmed uptrend on a follow-through day, '+
    'and leaders finishing sound bases into new-high ground with the earnings letters intact. '+
    'Until then the method\'s position is cash, not a lower bar. '+
    'Every name that was graded is still listed in the appendix below, with its scorecard.</div>';
} else {
  $("topIntro").innerHTML = '<div class="callout">The '+topOverall.length+' highest-graded names from the whole sweep'+
    (TOP_GATED ? ' that cleared '+fmtScore(THRESHOLD)+' of 7' : '')+
    ', ranked by grade, then relative strength, then proximity to the 52-week high. Sector caps do <b>not</b> apply here, '+
    'so this list can concentrate in one or two leading groups - check it against list 1 before sizing anything.</div>'+
    (topOverall.length < TOPN
      ? '<div class="callout warn">&#9888; Only '+topOverall.length+' of a possible '+TOPN+' qualified. '+
        'The list is short because the market is, not because the sweep was narrow - it is not padded out to '+TOPN+'.</div>'
      : '')+
    (!TOP_GATED && topOverall.filter(p=>p._total<THRESHOLD).length
      ? '<div class="callout warn">&#9888; '+topOverall.filter(p=>p._total<THRESHOLD).length+' of these are <b>below the '+
        fmtScore(THRESHOLD)+'/7 cut</b> (badged "below cut") - they rank here on grade alone and are not recommendations.</div>'
      : '');
  makeTable("topHead","topRows", topOverall, {markQual:!TOP_GATED,
    emptyMsg:"No names were graded in this run."});
}

// ---- sector sweep table ----
(function(){
  const rows = CONFIG.sectors||[];
  if (!rows.length) return;
  $("sweepWrap").style.display='block';
  const s = CONFIG.sweep||{};
  $("sweepNote").textContent = '- ranked by ' + (s.windowLabel||"window performance") +
    (s.benchmark? ' (benchmark: '+s.benchmark+')':'') + (s.note? ' ' + s.note : '');
  const cols = ["#","Sector","Median perf","Cleared triage","Graded &ge;"+fmtScore(THRESHOLD),"Leaders","Note"];
  $("sweepHead").innerHTML = cols.map((c,i)=>'<th'+(i>=2&&i<=4?' class="num"':'')+'>'+c+'</th>').join('');
  $("sweepRows").innerHTML = rows.map(r=>{
    const q = (r.qualified!=null) ? r.qualified
      : qualified.filter(p=>sectorKey(p)===r.sector).length;
    return '<tr>'+
      '<td class="rk">'+esc(r.rank)+'</td>'+
      '<td><b>'+esc(r.sector)+'</b></td>'+
      '<td class="num">'+esc(r.medianPerf)+'</td>'+
      '<td class="num">'+esc(r.survivors)+(r.considered?' / '+esc(r.considered):'')+'</td>'+
      '<td class="num">'+q+'</td>'+
      '<td class="grp">'+esc(r.leaders||'')+'</td>'+
      '<td class="grp">'+esc(r.note||'')+'</td>'+
    '</tr>';
  }).join('');
})();

/* ---- Sectors that produced no qualifier: show what actually led the group ----
   A sector with nothing at or above the cut would otherwise be a blank in this report. These are
   the screener's OWN top names for the ranking window - raw performance, NOT graded and NOT
   recommendations. They are shown so the reader can see where the strength sat and pick up the
   thread manually, and each row carries whether it even cleared the CAN SLIM hard filters. */
(function(){
  const rows = (CONFIG.sectors||[]).filter(r=>{
    const q = (r.qualified!=null) ? Number(r.qualified) : qualified.filter(p=>sectorKey(p)===r.sector).length;
    return !q && (r.top5||[]).length;
  });
  if (!rows.length) return;
  $("fallbackWrap").style.display='block';
  const lens = rows.map(r=>r.top5.length);
  const lo = Math.min(...lens), hi = Math.max(...lens);
  const n = (lo===hi) ? String(hi) : (lo+"-"+hi);   // sectors can return fewer than the cap
  $("fallbackTitle").innerHTML = 'Sectors with no qualifier &mdash; top '+n+' by screener rank '+
    '<span class="n">- '+rows.length+' of '+(CONFIG.sectors||[]).length+' sectors produced nothing at or above '+
    fmtScore(THRESHOLD)+'/7</span>';
  $("fallbackIntro").innerHTML = '<div class="callout warn">&#9888; <b>Ungraded - not recommendations.</b> '+
    'These are simply the names the TradingView screener ranked highest in each sector over '+
    esc((CONFIG.sweep||{}).windowLabel || 'the sweep window')+'. They carry <b>no CAN SLIM scorecard</b>, '+
    'no verdict and no buy point, and several did not even clear the hard filters (each row says which). '+
    'They are here so a sector that produced no qualifier is not a blank page - use them as a starting '+
    'point to research, never as a substitute for a grade.</div>';
  $("fallback").innerHTML = rows.map(r=>{
    const body = r.top5.map((t,i)=>{
      const ok = String(t.triage||'').toLowerCase()==='grade';
      return '<div class="fbrow">'+
        '<span class="n">'+(t.sectorRank||i+1)+'</span>'+
        '<span class="sym">'+esc(t.ticker||t.symbol)+'</span>'+
        '<span class="co" title="'+esc(t.company||'')+'">'+esc(t.company||'')+'</span>'+
        '<span class="num">'+esc(t.perf)+'</span>'+
        '<span class="num '+rsClass(t.rs)+'">'+esc(t.rs)+'</span>'+
        '<span class="st'+(ok?' ok':'')+'" title="'+esc(t.note||'')+'">'+(ok?'cleared triage':'dropped')+'</span>'+
      '</div>';
    }).join('');
    return '<div class="fbsec"><h4><span class="rk">#'+esc(r.rank)+'</span>'+esc(r.sector)+
      '<span class="meta">median '+esc(r.medianPerf)+' &middot; '+esc(r.survivors)+' of '+esc(r.considered)+
      ' cleared triage &middot; 0 graded &ge;'+fmtScore(THRESHOLD)+'</span></h4>'+body+
      (r.note?'<div class="fbnote">'+esc(r.note)+'</div>':'')+'</div>';
  }).join('');
})();

// ---- appendix: every name graded ----
if (CONFIG.showAllGraded !== false && allPicks.length){
  $("allWrap").style.display='block';
  $("allNote").textContent = '- all '+allPicks.length+' names that were fully graded, including those below the '+
    fmtScore(THRESHOLD)+'/7 cut';
  makeTable("allHead","allRows", allPicks.slice().sort(byGrade), {emptyMsg:"Nothing graded."});
}

// ---- leadership map: RS (x) vs % off 52-wk high (y, 0 at top) ----
/* Colour encodes the VERDICT (three groups), not one hue per stock: a scatter cannot carry eight
   arbitrary hues and stay colourblind-safe, and verdict is the split a reader actually needs.
   Marker SHAPE repeats the same split as secondary encoding, the ticker beside each dot carries
   identity, and labels wear the ink token rather than the series colour. Labels are placed by a
   collision solver - candidate offsets around the dot, first non-overlapping in-bounds slot wins,
   with a leader line when a label had to move off its dot. */
const VERDICT_STYLE = {
  buy:   {cls:"v-buy",   shape:"circle",   label:"BUY-RANGE"},
  watch: {cls:"v-watch", shape:"diamond",  label:"WATCH"},
  avoid: {cls:"v-avoid", shape:"triangle", label:"AVOID"},
  none:  {cls:"v-none",  shape:"circle",   label:"ungraded verdict"}
};
function verdictKey(p){
  const v = String(p.verdict||"").toUpperCase();
  if (v.indexOf("BUY")===0) return "buy";
  if (v.indexOf("AVOID")===0) return "avoid";
  if (v) return "watch";
  return "none";
}
function markPath(shape, cxIn, cyIn, r){
  // Coerce first: callers pass toFixed() strings, and "539.4"+6.3 concatenates into junk path data.
  const cx=Number(cxIn), cy=Number(cyIn), n=(v)=>v.toFixed(2);
  if (shape==="diamond")
    return '<path class="lm-mark" d="M'+n(cx)+' '+n(cy-r*1.15)+'L'+n(cx+r*1.15)+' '+n(cy)+
           'L'+n(cx)+' '+n(cy+r*1.15)+'L'+n(cx-r*1.15)+' '+n(cy)+'Z"/>';
  if (shape==="triangle")
    return '<path class="lm-mark" d="M'+n(cx)+' '+n(cy-r*1.25)+'L'+n(cx+r*1.2)+' '+n(cy+r*0.9)+
           'L'+n(cx-r*1.2)+' '+n(cy+r*0.9)+'Z"/>';
  return '<circle class="lm-mark" cx="'+n(cx)+'" cy="'+n(cy)+'" r="'+r+'"/>';
}

function buildLeadMap(){
  const pts = allPicks.map(p=>({sym:p.symbol, x:p._rs, y:Math.abs(p._off), vk:verdictKey(p)}))
                      .filter(d=> isFinite(d.x) && isFinite(d.y));
  if (pts.length < 2) return;   // nothing meaningful to plot
  $("leadmapWrap").style.display='block';

  const W=760, H=400, mL=54, mR=22, mT=24, mB=54;
  const pw=W-mL-mR, ph=H-mT-mB;
  // signed-sqrt x-scale so one extreme-RS outlier doesn't compress the rest of the field
  const tx=(v)=> Math.sign(v)*Math.sqrt(Math.abs(v));
  const xsR=pts.map(d=>d.x), ys=pts.map(d=>d.y);
  let xMinR=Math.min(...xsR,0), xMaxR=Math.max(...xsR,0);
  let yMin=0, yMax=Math.max(...ys, 8);
  const xPadR=(xMaxR-xMinR||1)*0.10, ypad=(yMax-yMin||1)*0.12;
  xMinR-=xPadR; xMaxR+=xPadR; yMax+=ypad;              // yMin stays 0 (at the high)
  const txMin=tx(xMinR), txMax=tx(xMaxR);
  const X=(v)=> mL + (tx(v)-txMin)/((txMax-txMin)||1)*pw;
  const Y=(v)=> mT + (v-yMin)/((yMax-yMin)||1)*ph;      // 0% -> top

  const buyBand=8;                                     // within 8% of high = new-high ground
  const yBuy=Y(Math.min(buyBand,yMax)), xZero=X(Math.max(0,xMinR));
  let svg='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Relative strength versus percent below the 52-week high, one mark per graded name, coloured by verdict">';

  // zone: high RS on new-high ground (NOT a pivot test - see the caption)
  if (xMaxR>0){
    svg+='<rect class="lm-zone" x="'+xZero.toFixed(1)+'" y="'+mT+'" '+
         'width="'+(mL+pw-xZero).toFixed(1)+'" height="'+(yBuy-mT).toFixed(1)+'"/>';
  }
  // y gridlines at each tick
  const yTicks=[0, 4, 8, 12, 16, 20, 25, 30].filter(t=>t<=yMax);
  if (yTicks[yTicks.length-1] < yMax-2) yTicks.push(Math.round(yMax));
  /* Keep every tick label's box - the x-axis ticks below are checked against these so the two
     axes never clip each other in the bottom-left corner. ~6.7px/char at the 11px tick size. */
  const TCH=6.7, tickBoxes=[];
  yTicks.forEach(t=>{
    const ty=Y(t)+4, lab=t+'%', tw=lab.length*TCH;
    tickBoxes.push({x1:mL-8-tw, x2:mL-8, y1:ty-9, y2:ty+3});
    svg+='<line class="lm-grid" x1="'+mL+'" y1="'+Y(t).toFixed(1)+'" x2="'+(mL+pw)+'" y2="'+Y(t).toFixed(1)+'"/>'+
         '<text class="lm-tick" x="'+(mL-8)+'" y="'+ty.toFixed(1)+'" text-anchor="end">'+lab+'</text>';
  });
  // axes + reference lines
  svg+='<line class="lm-axis" x1="'+mL+'" y1="'+(mT+ph)+'" x2="'+(mL+pw)+'" y2="'+(mT+ph)+'"/>'+
       '<line class="lm-axis" x1="'+mL+'" y1="'+mT+'" x2="'+mL+'" y2="'+(mT+ph)+'"/>';
  if (xMinR<0 && xMaxR>0) svg+='<line class="lm-ref" x1="'+X(0).toFixed(1)+'" y1="'+mT+'" x2="'+X(0).toFixed(1)+'" y2="'+(mT+ph)+'"/>';
  if (buyBand<yMax) svg+='<line class="lm-ref" x1="'+mL+'" y1="'+yBuy.toFixed(1)+'" x2="'+(mL+pw)+'" y2="'+yBuy.toFixed(1)+'"/>';
  // axis titles
  svg+='<text class="lm-axlab" x="'+(mL+pw/2)+'" y="'+(H-10)+'" text-anchor="middle">Relative strength vs SPY over the window (points, sqrt scale) &#8594; stronger</text>'+
       '<text class="lm-axlab" transform="translate(15,'+(mT+ph/2)+') rotate(-90)" text-anchor="middle">&#8592; nearer the 52-wk high (% below)</text>';
  // x ticks: evenly spaced in transformed space, labelled with the actual (nonlinear) RS value
  const xTickY=mT+ph+26;   // clear of the y-axis tick column; the skip below is a backstop
  for(let i=0;i<=4;i++){ const txv=txMin+i/4*(txMax-txMin), raw=Math.sign(txv)*txv*txv, px=mL+i/4*pw;
    const lab=(raw>0?'+':'')+Math.round(raw), lw=lab.length*TCH;
    const box={x1:px-lw/2-2, x2:px+lw/2+2, y1:xTickY-9, y2:xTickY+3};
    // Drop a tick label rather than let it clip a y-axis label - the axis line still marks the spot.
    if (tickBoxes.some(b=> !(box.x2<b.x1 || b.x2<box.x1 || box.y2<b.y1 || b.y2<box.y1))) continue;
    tickBoxes.push(box);
    svg+='<text class="lm-tick" x="'+px.toFixed(1)+'" y="'+xTickY+'" text-anchor="middle">'+lab+'</text>';
  }

  /* ---- label placement: try offsets around the dot, take the first that collides with nothing
     already placed and stays inside the plot. Falls back to the least-bad slot, and draws a
     leader line whenever the label is not in its default position beside the dot. ---- */
  const R=5.5, CH=6.7, LH=13, PAD=2.5;                 // mono ~6.7px/char at 11.5px
  const marks=[], labels=[];
  const OFFS=[[10,4],[-10,4],[10,-8],[-10,-8],[10,16],[-10,16],[0,-14],[0,21],[18,11],[-18,11],[0,-23],[0,30]];
  const hit=(a,b)=> !(a.x2<b.x1 || b.x2<a.x1 || a.y2<b.y1 || b.y2<a.y1);
  const inPlot=(b)=> b.x1>=mL-2 && b.x2<=mL+pw+2 && b.y1>=mT-2 && b.y2<=mT+ph+2;

  const nodes = pts.map(d=>({d, cx:X(d.x), cy:Y(d.y)}))
                   .sort((a,b)=> a.cy-b.cy || a.cx-b.cx);   // top-down keeps placement stable
  /* EVERY mark is an obstacle from the start - reserving a mark only once its own label is
     placed lets an early label land on a dot that is drawn later. `own` is skipped so a label
     may still sit beside its own mark. */
  const markBoxes = nodes.map(({cx,cy})=>({x1:cx-R-1.5, x2:cx+R+1.5, y1:cy-R-1.5, y2:cy+R+1.5}));
  const placed = [];

  nodes.forEach(({d,cx,cy}, idx)=>{
    const w=d.sym.length*CH, best={score:Infinity};
    const obstacles = placed.concat(markBoxes.filter((_,i)=> i!==idx));
    for (let i=0;i<OFFS.length;i++){
      const [ox,oy]=OFFS[i], anchor = ox<0 ? "end" : (ox===0 ? "middle" : "start");
      const lx = cx+ox, ly = cy+oy;
      const x1 = anchor==="end" ? lx-w : (anchor==="middle" ? lx-w/2 : lx);
      const box = {x1:x1-PAD, x2:x1+w+PAD, y1:ly-LH+3-PAD, y2:ly+3+PAD};
      const clash = obstacles.filter(b=>hit(box,b)).length;
      const score = clash*100 + (inPlot(box)?0:50) + i;   // prefer earlier offsets
      if (score < best.score) Object.assign(best,{score, box, lx, ly, anchor, moved:i>1});
      if (score===i) break;                              // clean + in-bounds + first choice
    }
    placed.push(best.box);
    const st = VERDICT_STYLE[d.vk];
    marks.push('<g class="'+st.cls+'">'+markPath(st.shape, cx.toFixed(1), cy.toFixed(1), R)+'</g>');
    if (best.moved)
      labels.push('<line class="lm-leader" x1="'+cx.toFixed(1)+'" y1="'+cy.toFixed(1)+
                  '" x2="'+best.lx.toFixed(1)+'" y2="'+(best.ly-3).toFixed(1)+'"/>');
    labels.push('<text class="lm-lab" text-anchor="'+best.anchor+'" x="'+best.lx.toFixed(1)+
                '" y="'+best.ly.toFixed(1)+'">'+esc(d.sym)+'</text>');
  });
  svg += labels.join('') + marks.join('') + '</svg>';   // marks over leader lines
  $("leadmap").innerHTML=svg;

  // legend - identity is never colour alone (shape + text label + the ticker beside each mark)
  const present=["buy","watch","avoid","none"].filter(k=>pts.some(d=>d.vk===k));
  $("leadmapLegend").innerHTML = present.map(k=>{
    const st=VERDICT_STYLE[k];
    return '<span class="lm-key"><svg class="'+st.cls+'" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">'+
      markPath(st.shape, 8, 8, 5)+'</svg>'+esc(st.label)+' ('+pts.filter(d=>d.vk===k).length+')</span>';
  }).join('') +
    '<span class="lm-key lm-zonekey"><span class="lm-swatch"></span>shaded: RS &gt; 0 and within '+buyBand+'% of the 52-wk high</span>' +
    '<span class="hint">Marks are coloured and shaped by verdict; the ticker beside each mark gives identity.</span>';
}
buildLeadMap();

// ---- per-ticker report modal ----
function openReview(url, sym){
  $("modalTitle").textContent = (sym?sym+" - ":"") + "CAN SLIM report";
  $("modalOpen").href = url;
  $("modalFrame").src = url;
  $("modal").classList.add('open');
}
function closeReview(){ $("modal").classList.remove('open'); $("modalFrame").src="about:blank"; }
document.addEventListener('click', e=>{
  const a=e.target.closest('a[data-review]'); if(!a) return;
  e.preventDefault(); openReview(a.dataset.review, a.dataset.sym);
});
$("modalClose").addEventListener('click', closeReview);
$("modal").addEventListener('click', e=>{ if(e.target.id==='modal') closeReview(); });
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeReview(); });

// ---- optional sections ----
if ((CONFIG.rationale||[]).length){
  $("rationaleWrap").style.display='block';
  $("cards").innerHTML = CONFIG.rationale.map(r=>
    '<div class="card"><h3>'+esc(r.symbol)+'</h3><div class="co">'+esc(r.company||'')+'</div><p>'+esc(r.text)+'</p></div>').join('');
}
if ((CONFIG.watch||[]).length){
  $("watchWrap").style.display='block';
  $("watch").innerHTML = CONFIG.watch.map(w=>
    '<div class="tier"><b>'+esc(w.symbol)+'</b> '+esc(w.company||'')+' &middot; '+esc(w.sector||w.group||'')+' &middot; <span class="num neg">'+esc(w.offHigh||'')+'</span><div class="why">'+esc(w.note||'')+'</div></div>').join('');
}
if ((CONFIG.speculative||[]).length){
  $("specWrap").style.display='block';
  $("spec").innerHTML = CONFIG.speculative.map(s=>
    '<div class="tier"><b>'+esc(s.symbol)+'</b> '+esc(s.company||'')+'<div class="why">'+esc(s.reason||'')+'</div></div>').join('');
}
if ((CONFIG.excluded||[]).length){
  $("exclWrap").style.display='block';
  $("excl").innerHTML = CONFIG.excluded.map(x=>
    '<div class="tier"><b>'+esc(x.group)+'</b> <span class="why">- '+esc(x.names||'')+'</span><div class="why">'+esc(x.reason||'')+'</div></div>').join('');
}
$("portfolio").innerHTML = '<b>Portfolio &amp; risk (per the method):</b> '+esc(CONFIG.portfolioNote||'');

// ---- data sources & freshness table (always rendered; never let a report ship sourceless) ----
(function(){
  const rows = CONFIG.sourceMap||[];
  /* Two dates, deliberately: `pulled` is when this run made the call, `asOf` is how old the
     figure underneath is. A source pulled today can still hand back last week's number. */
  $("srcHead").innerHTML = ["What","Source (tool / feed)","Pulled","Data as of","Status","Note"]
    .map(c=>'<th>'+c+'</th>').join('');
  const STATUS = {fresh:"FRESH", reused:"REUSED", unavailable:"UNAVAILABLE"};
  $("srcRows").innerHTML = rows.length
    ? rows.map(r=>{
        const st = String(r.status||"fresh").trim().toLowerCase();
        const cls = STATUS.hasOwnProperty(st) ? st : "unavailable";
        const lab = STATUS[st] || String(r.status).toUpperCase();
        return '<tr><td><b>'+esc(r.item)+'</b></td><td class="grp">'+esc(r.source)+
          '</td><td class="grp when">'+esc(r.pulled||'')+
          '</td><td class="grp">'+esc(r.asOf||'')+
          '</td><td><span class="fchip '+cls+'">'+esc(lab)+'</span></td>'+
          '<td class="grp">'+esc(r.note||'')+'</td></tr>';
      }).join('')
    : '<tr><td colspan="6" style="padding:16px;color:var(--fail)">CONFIG.sourceMap is empty - fill it before shipping this report.</td></tr>';
  /* The subtitle is derived, never asserted: a run that fell back cannot print "pulled fresh". */
  const nf = rows.filter(r=> String(r.status||"fresh").trim().toLowerCase() !== "fresh").length;
  $("srcSub").textContent = nf
    ? '- every figure traces to one of these; ' + nf + ' of ' + rows.length +
      ' did not come back fresh this run (see the banner above)'
    : '- every figure in this report traces to one of these, all pulled fresh for this run';
})();

/* ---- self-audit: the report checks itself and shouts if CONFIG contradicts itself.
   Never ship a report showing this banner - fix the grade or fix the evidence. ---- */
(function(){
  const errs = [];
  /* The scorecard maxes at 7 - seven letters at pass=1. A threshold carried over from some other
     scale (45, 70, a percentage) is not a loud failure: THRESHOLD just exceeds every possible
     total, both lists come out empty, and the empty-state text explains it as a weak market. */
  const thr = Number(CONFIG.gradeThreshold);
  if (CONFIG.gradeThreshold != null && (!isFinite(thr) || thr <= 0 || thr > 7))
    errs.push('CONFIG.gradeThreshold is "'+CONFIG.gradeThreshold+'", which is off the scale - a '+
      'scorecard is seven letters at pass 1 / partial 0.5 / fail 0, so it totals at most 7 and the '+
      'cut must sit between 0 and 7 (the default is 4.5). A value above 7 empties both lists and '+
      'reads as a weak market rather than as a mis-set threshold.');
  /* The checks above police CONFIG's structured fields. Prose is the remaining hole: a reason
     that says "scores 45/70" renders exactly as written, contradicting the /7 scorecard beside
     it. Match ONLY the dead scales by name - a general "denominator that isn't 7" rule fires on
     ordinary prose ("52-week high of 514", "#1 of the ten"), and an audit that cries wolf is
     worse than no audit, because the banner is meant to stop a shipment. */
  (function(){
    const DEAD = /\/\s*(?:70|10)\b|\bout of\s+(?:70|10)\b|\b0\s*-\s*10\s+(?:rubric|scale|scoring)\b/i;
    const texts = [];
    const add = (label, v)=>{ if (typeof v === "string" && v) texts.push([label, v]); };
    add("market.implication", (CONFIG.market||{}).implication);
    add("shortfall", CONFIG.shortfall); add("dataWarning", CONFIG.dataWarning);
    add("portfolioNote", CONFIG.portfolioNote); add("dataProvenance", CONFIG.dataProvenance);
    (CONFIG.picks||[]).forEach(p=> add((p.symbol||"a pick")+".reason", p.reason));
    (CONFIG.noQualifierReasons||[]).forEach((r,i)=> add("noQualifierReasons["+i+"]", r));
    (CONFIG.sourceMap||[]).forEach((r,i)=> add("sourceMap["+i+"].note", r.note));
    texts.forEach(([label, v])=>{
      const hit = v.match(DEAD);
      if (hit) errs.push(label+' says "'+hit[0].trim()+'" - that is a scoring scale this skill '+
        'does not use. A scorecard is seven letters at pass 1 / partial 0.5 / fail 0, totalling '+
        'out of 7. Rewrite the sentence on the /7 scale.');
    });
  })();
  if (!CONFIG.dataProvenance) errs.push("CONFIG.dataProvenance is empty - the report must name the data sources it used.");
  if (!(CONFIG.sourceMap||[]).length) errs.push("CONFIG.sourceMap is empty - fill one row per class of figure (what, source, pulled).");

  /* ---- freshness contract ----
     Every run attempts fresh data; the report must say what it got. These checks make silence
     impossible: no data date, an undated source, or reuse that the freshness block does not
     declare all stop the report here. */
  if (!CONFIG.dataDate)
    errs.push("CONFIG.dataDate is empty - every report must state the date its market data is as of. "+
      "generatedAt (when the report was built) does not answer that question.");
  const fr = CONFIG.freshness;
  if (!fr || typeof fr !== "object")
    errs.push("CONFIG.freshness is missing - every run must record whether its fresh pull succeeded, "+
      "even when it did (freshness:{attemptedAt:'...', allFresh:true, failures:[]}).");
  else {
    const fails = Array.isArray(fr.failures) ? fr.failures : [];
    if (!fr.attemptedAt)
      errs.push("CONFIG.freshness.attemptedAt is empty - state when this run attempted its data pull.");
    if (fr.allFresh === false && !fails.length)
      errs.push("CONFIG.freshness.allFresh is false but freshness.failures is empty - name what did not "+
        "come back fresh, why, and what was used instead.");
    if (fr.allFresh !== false && fails.length)
      errs.push("CONFIG.freshness lists "+fails.length+" failure(s) but allFresh is not false - "+
        "the banner would tell the reader everything was fresh.");
    fails.forEach((x,i)=>{
      const who = x.item || ("failures["+i+"]");
      if (!x.item)   errs.push("freshness.failures["+i+"] has no `item` - name which class of figure failed.");
      if (!x.error)  errs.push(who+": freshness failure has no `error` - say why the fresh pull did not work.");
      if (x.fallback && !x.fallbackDate)
        errs.push(who+': fell back to "'+x.fallback+'" with no fallbackDate - reused data must carry '+
          "the date it is from, or the reader cannot tell how stale it is.");
    });
    // every reused/unavailable source has to be declared up top, not just chipped in the table
    const declared = new Set(fails.map(x=>String(x.item||"").trim().toLowerCase()).filter(Boolean));
    (CONFIG.sourceMap||[]).forEach((r,i)=>{
      const where = r.item || ("sourceMap["+i+"]");
      const st = String(r.status||"fresh").trim().toLowerCase();
      if (["fresh","reused","unavailable"].indexOf(st) < 0)
        errs.push(where+': status "'+r.status+'" is not fresh/reused/unavailable - it renders as UNAVAILABLE.');
      if (!r.pulled)
        errs.push(where+": no `pulled` date - every source row must say when this run called it "+
          '(use "-" only for a source that returned nothing, and mark it unavailable).');
      if (st === "reused" && !r.asOf)
        errs.push(where+": reused data with no `asOf` date - reused figures must say what date they are from.");
      if ((st === "reused" || st === "unavailable") && !declared.has(String(r.item||"").trim().toLowerCase()))
        errs.push(where+' is marked '+st.toUpperCase()+' in the sources table but has no matching entry in '+
          "CONFIG.freshness.failures - a source that was not pulled fresh must be reported at the top of "+
          "the report, not only in the table.");
    });
  }
  if (!allPicks.length) errs.push("CONFIG.picks is empty - nothing was graded, so neither recommendation list can be built.");
  const swGraded = Number((CONFIG.sweep||{}).graded);
  if (isFinite(swGraded) && swGraded && swGraded !== allPicks.length)
    errs.push("CONFIG.sweep.graded says "+swGraded+" names were graded but CONFIG.picks holds "+allPicks.length+
      " - the funnel and the lists must count the same run.");
  // The coverage contract: a run that graded fewer names than could still reach the cut has
  // not finished, and might be hiding a qualifier among the names it never reached.
  const swMust = Number((CONFIG.sweep||{}).mustGrade);
  if (isFinite(swMust) && swMust > 0 && allPicks.length < swMust)
    errs.push("CONFIG.sweep.mustGrade says "+swMust+" survivors could still reach "+fmtScore(THRESHOLD)+
      "/7, but only "+allPicks.length+" names were graded - the run is incomplete and a qualifier may be "+
      "missing. Grade every name whose ceiling reaches the cut, or raise the cut.");
  allPicks.forEach(p=>{
    const sc = p.scores||{};
    LETTERS6.forEach(k=>{
      if (sc[k]==null) errs.push(p.symbol+": letter "+k+" has no grade (defaults to fail).");
      else if (!isGrade(sc[k])) errs.push(p.symbol+": letter "+k+' is "'+sc[k]+
        '", which is not pass/partial/fail - it scores as FAIL. Every letter takes exactly "pass" (1.0), "partial" (0.5) or "fail" (0); a bare number is not a grade on any scale this skill uses and silently zeroes the letter.');
    });
    if (!isGrade((CONFIG.market||{}).mGrade))
      errs.push('CONFIG.market.mGrade is "'+((CONFIG.market||{}).mGrade)+
        '", not pass/partial/fail - M scores as FAIL for every row.');
    const bp = num(p.buyPoint), hi = num(p.high52), st = num(p.stop);
    if (isFinite(bp) && gradeOf(sc.N)==="fail")
      errs.push(p.symbol+": a buy point is named but N is FAIL - the method has no entry without a sound base at new-high ground.");
    if (isFinite(bp) && isFinite(hi) && bp < hi*0.90)
      errs.push(p.symbol+": buy point "+p.buyPoint+" is more than 10% below the 52-week high ("+p.high52+") - that is a lower high, not a pivot.");
    if (isFinite(bp) && isFinite(st)){
      const d = (bp-st)/bp;
      if (d < 0.025 || d > 0.09)
        errs.push(p.symbol+": stop "+p.stop+" is "+(d*100).toFixed(1)+"% below the buy point - the rule is 7-8% (3% when M is a correction).");
    }
    const vd = String(p.verdict||"").toUpperCase();
    if (vd==="AVOID" && p._total>=THRESHOLD)
      errs.push(p.symbol+": verdict AVOID but the scorecard totals "+fmtScore(p._total)+"/7 - grade and verdict disagree.");
    if (vd.indexOf("BUY")===0 && !isFinite(bp))
      errs.push(p.symbol+": verdict BUY-RANGE but no buy point is given - name the pivot or downgrade to WATCH.");
    if (vd.indexOf("BUY")===0 && gradeOf(sc.N)==="fail")
      errs.push(p.symbol+": verdict BUY-RANGE with N FAIL - no sound base at new-high ground means no entry.");
    if (!vd) errs.push(p.symbol+": no verdict - every graded name needs BUY-RANGE, WATCH or AVOID so the grade is not read as an entry signal.");
  });
  if (errs.length){
    $("checks").innerHTML = '<div class="callout bad"><b>&#9888; Report checks failed ('+errs.length+
      ') - do not ship this report:</b><ul>'+errs.map(e=>'<li>'+esc(e)+'</li>').join('')+'</ul></div>';
  }
})();

// ---- glossary of acronyms (default set; extend via CONFIG.glossary = [{term,def}, ...]) ----
const DEFAULT_GLOSSARY = [
  {term:"CAN SLIM", def:"Growth-stock selection framework - the seven traits (below) shared by big market winners just before their major advances."},
  {term:"C", def:"Current quarterly earnings & sales - up sharply vs the year-ago quarter and accelerating."},
  {term:"A", def:"Annual earnings - multi-year EPS growth with a high return on equity."},
  {term:"N", def:"New - a new product / management / industry condition AND a breakout to new highs from a sound base."},
  {term:"S", def:"Supply & demand - a volume surge on the breakout, a manageable float, buybacks."},
  {term:"L", def:"Leader, not laggard - high relative strength; the #1 or #2 name in a strong group."},
  {term:"I", def:"Institutional sponsorship - increasing ownership by high-quality funds."},
  {term:"M", def:"Market direction - the general market must be in a confirmed uptrend (shown in the banner at the top)."},
  {term:"P / ~ / X", def:"Letter grades - pass (1.0), partial (0.5), fail (0). Seven letters, so a scorecard totals out of 7."},
  {term:"RS", def:"Relative strength - price performance vs the S&P 500 over the sweep window. A proxy, not a full-market 1-99 rating."},
  {term:"Pivot / buy point", def:"The price at the top of a sound base where the breakout is bought - valid only at or very near new-high ground."},
  {term:"Base", def:"A price consolidation (cup-with-handle, flat base, double bottom, square box) formed after a prior advance."},
  {term:"Distribution day", def:"An index day closing down >=0.2% on heavier volume than the session before - institutional selling."},
  {term:"Follow-through day", def:"A decisive high-volume index rally day that confirms a new uptrend after a correction."},
  {term:"EPS", def:"Earnings per share."},
  {term:"YoY", def:"Year over year - vs the same period one year earlier."},
  {term:"ROE", def:"Return on equity - profit as a percentage of shareholders' equity."},
  {term:"FCF", def:"Free cash flow - operating cash flow minus capital expenditures."},
  {term:"ARR", def:"Annual recurring revenue - the annualized run-rate of subscription revenue."},
  {term:"EBITDA", def:"Earnings before interest, taxes, depreciation & amortization."},
  {term:"GAAP / non-GAAP", def:"Standardized accounting results vs company-adjusted (non-standard) results."},
  {term:"EMA (50-/200-day)", def:"Exponential moving average of price - the 50- and 200-day trend lines."},
  {term:"bps", def:"Basis points - 1 bp = 0.01% (100 bps = 1%)."},
  {term:"13F", def:"The quarterly SEC filing in which large institutions disclose their holdings - the source for I."},
  {term:"ETF", def:"Exchange-traded fund (e.g. SPY = S&P 500, QQQ = Nasdaq-100)."}
];
(function(){
  const el = document.getElementById("glossary"); if(!el) return;
  const extra = Array.isArray(CONFIG.glossary) ? CONFIG.glossary : [];
  const seen = new Set(DEFAULT_GLOSSARY.map(g=>String(g.term).toLowerCase()));
  const all = DEFAULT_GLOSSARY.concat(extra.filter(g=>g&&g.term&&!seen.has(String(g.term).toLowerCase())));
  el.innerHTML = all.map(g=>'<div class="gterm">'+esc(g.term)+'</div><div class="gdef">'+esc(g.def)+'</div>').join('');
})();
$("disclaimer").textContent = CONFIG.disclaimer||'';
if ((CONFIG.sources||[]).length){
  $("sources").innerHTML = "Sources: " + CONFIG.sources.map(s=>'<a href="'+esc(s.url)+'">'+esc(s.label)+'</a>').join('');
}
</script>
</body>
</html>
```


## `tests/test_regression.py`

The regression suite - pure stdlib, no pytest, no network. Run it after porting or editing anything: the ceiling's soundness is the one property whose failure is invisible in the output, so it is pinned twice over.

`````python
#!/usr/bin/env python3
"""
Regression suite for can-slim-recommend. Pure standard library, no pytest needed.

    python tests/test_regression.py            # all suites
    python tests/test_regression.py ceiling    # only suites whose name contains "ceiling"
    python tests/test_regression.py -v         # show every passing assertion

WHAT THIS GUARDS. Every test here exists because the behaviour it pins is one a future edit
could plausibly break without any other signal:

  * the ceiling must never sit BELOW a score a name could actually earn - an unsound ceiling
    silently drops qualifiers, which is invisible in the output
  * triage must skip a check whose data is missing rather than fail it - a null column must
    never masquerade as a disqualification
  * check_for_updates must fail OPEN and must never pull over uncommitted work
  * the dashboard's self-audit must actually refuse the contradictions it claims to catch
  * @page margin/size parsing must reject what it cannot hand to another engine verbatim

Tests are plain functions named check_*; each returns None and raises AssertionError on failure.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import sector_screen as ss                                  # noqa: E402
import relative_strength as rs                              # noqa: E402
import html_to_pdf as h2p                                   # noqa: E402
import build_report as br                                   # noqa: E402
import check_for_updates as cfu                             # noqa: E402
import accumulation as acc                                  # noqa: E402
import institutional_cache as ic                            # noqa: E402

W = {"pass": 1.0, "partial": 0.5, "fail": 0.0}
CFG = dict(ss.DEFAULTS)


def row(**kw):
    """A screener row that clears every hard filter unless a test overrides a field."""
    d = {"symbol": "NYSE:TEST", "name": "TEST", "description": "Test Co", "close": 100.0,
         "Perf.6M": 50.0, "market_cap_basic": 5e9, "average_volume_10d_calc": 1e6,
         "relative_volume_10d_calc": 1.5, "sector": "Energy Minerals", "industry": "Oil",
         "price_52_week_high": 101.0, "price_52_week_low": 40.0,
         "EMA50": 90.0, "EMA200": 80.0, "exchange": "NYSE",
         "earnings_release_next_date": "2026-11-01"}
    d.update(kw)
    return d


def sweep(rows_by_sector, bench=10.0):
    return {"asOf": "test", "window": "Perf.6M",
            "benchmark": {"symbol": "AMEX:SPY", "perf": {"Perf.6M": bench}},
            "sectors": rows_by_sector}


# ---------------------------------------------------------------- sector_screen: arithmetic

def check_triage_keeps_a_clean_row():
    r = ss.score_row(row(), "Perf.6M", 10.0, CFG)
    assert r["triage"] == "grade", r["drop_reasons"]
    assert abs(r["off_high_pct"] - (100/101 - 1) * 100) < 1e-9
    assert abs(r["rs_vs_bench_pts"] - 40.0) < 1e-9
    assert r["avg_dollar_volume"] == 100.0 * 1e6


def check_triage_drops_each_hard_filter():
    cases = [
        (dict(close=9.0), "price below"),
        (dict(average_volume_10d_calc=1e4), "average dollar volume under"),
        (dict(market_cap_basic=5e8), "market cap under"),
        (dict(close=60.0, price_52_week_high=101.0), "below the 52-week high"),
        (dict(**{"Perf.6M": 5.0}), "lags the benchmark"),
        (dict(close=79.0, EMA200=80.0, price_52_week_high=80.0), "below the 200-day"),
    ]
    for over, frag in cases:
        r = ss.score_row(row(**over), "Perf.6M", 10.0, CFG)
        assert r["triage"] == "drop", "%s should have dropped" % over
        assert any(frag in x for x in r["drop_reasons"]), (frag, r["drop_reasons"])


def check_missing_data_is_skipped_never_failed():
    """A null column must be recorded as skipped, not silently treated as a disqualification."""
    r = ss.score_row(row(market_cap_basic=None, EMA200=None, relative_volume_10d_calc=None),
                     "Perf.6M", 10.0, CFG)
    assert "market_cap" in r["checks_skipped"], r["checks_skipped"]
    assert "ema200" in r["checks_skipped"], r["checks_skipped"]
    assert r["triage"] == "grade", r["drop_reasons"]


def check_money_formatting():
    assert ss.money(1e9) == "$1B" and ss.money(2.5e7) == "$25M"
    assert ss.money(2e7) == "$20M" and ss.money(400e3) == "$400k"


def check_f_helper_prefers_first_present_numeric():
    assert ss.f({"a": None, "b": "3.5"}, "a", "b") == 3.5
    assert ss.f({"a": "not-a-number"}, "a") is None
    assert ss.f({}, "missing") is None


# ---------------------------------------------------------------- sector_screen: the ceiling

def _ceiling_of(**over):
    out = ss.score_row(row(**over), "Perf.6M", 10.0, CFG)
    out["sector_rank_overall"], out["sector_count"] = 1, 20
    ss.ceiling(out, CFG)
    return out


def check_ceiling_floor_is_exactly_the_cut_when_M_and_I_are_partial():
    """The documented result the two-stage design rests on: with M and I both partial, the
    worst possible ceiling is 4.5, so stage 1 can never eliminate anybody. If a future edit
    changes a cap and this floor moves, the SKILL.md explanation is wrong and must change too."""
    out = _ceiling_of(close=85.0, price_52_week_high=101.0,       # N capped to partial (>10% off)
                      relative_volume_10d_calc=0.9)              # S capped to partial
    out["sector_rank_overall"], out["sector_count"] = 20, 20     # L capped to partial
    ss.ceiling(out, CFG)
    assert out["ceiling"] == 4.5, out["ceiling"]
    assert out["grade_required"] is True


def check_ceiling_caps_N_by_distance_from_the_high():
    assert _ceiling_of(close=100.0, price_52_week_high=101.0)["ceiling_caps"]["N"] == "pass"
    assert _ceiling_of(close=85.0, price_52_week_high=101.0)["ceiling_caps"]["N"] == "partial"
    assert _ceiling_of(close=78.0, price_52_week_high=101.0)["ceiling_caps"]["N"] == "fail"


def check_ceiling_caps_S_by_relative_volume():
    assert _ceiling_of(relative_volume_10d_calc=1.5)["ceiling_caps"]["S"] == "pass"
    assert _ceiling_of(relative_volume_10d_calc=0.9)["ceiling_caps"]["S"] == "partial"
    assert _ceiling_of(relative_volume_10d_calc=0.7)["ceiling_caps"]["S"] == "fail"


def check_ceiling_caps_L_in_a_bottom_half_sector():
    out = _ceiling_of()
    out["sector_rank_overall"], out["sector_count"] = 15, 20
    ss.ceiling(out, CFG)
    assert out["ceiling_caps"]["L"] == "partial"


def check_a_real_grade_overrides_the_screener_cap_in_both_directions():
    """`known` carries grades that were actually awarded, so it REPLACES the screener's guess
    rather than being bounded by it. Downward is the case the two-stage design runs on: an
    A-screen result drops the ceiling and usually saves the C call. Upward is rarer but must also
    hold - a screener column is a proxy, and when a real grade contradicts it the real grade wins.
    """
    out = _ceiling_of()
    base = out["ceiling"]
    ss.ceiling(out, CFG, {"A": "fail"})
    assert out["ceiling"] == base - 1.0, (base, out["ceiling"])
    ss.ceiling(out, CFG, {"A": "partial", "C": "fail"})       # re-graded: caps recompute from scratch
    assert out["ceiling"] == base - 1.5, (base, out["ceiling"])

    thin = _ceiling_of(relative_volume_10d_calc=0.7)          # S capped at fail by the screener
    capped = thin["ceiling"]
    ss.ceiling(thin, CFG, {"S": "pass"})
    assert thin["ceiling_caps"]["S"] == "pass"
    assert thin["ceiling"] == capped + 1.0, (capped, thin["ceiling"])

    # keys are matched case- and whitespace-insensitively; junk is ignored, not crashed on
    loose = _ceiling_of()
    ss.ceiling(loose, CFG, {" a ": "FAIL", "Z": "pass", "C": "nonsense"})
    assert loose["ceiling_caps"]["A"] == "fail" and loose["ceiling_caps"]["C"] == "pass"


def _best_grade_the_rubric_allows(oh, rv, rank, tot, cfg):
    """An INDEPENDENT statement of the same caps, written from the rubric rather than read back
    out of ceiling(). The distinction matters: the first version of this test filtered its grade
    space using ceiling()'s own `ceiling_caps`, which made it circular - it proved the ceiling
    agreed with itself, and a cap set too TIGHT (the failure mode that silently drops qualifiers)
    passed unnoticed. Two implementations that must agree is the point; if you change a band,
    change it here too, deliberately.
    """
    band = cfg["pivot_band"]
    if oh is None or oh >= -band:
        n = "pass"
    elif oh >= -2 * band:
        n = "partial"
    else:
        n = "fail"
    if rv is None or rv >= 1.0:
        sg = "pass"
    elif rv >= cfg["thin_vol"]:
        sg = "partial"
    else:
        sg = "fail"
    l = "partial" if (rank and tot and rank > tot / 2.0) else "pass"
    # C and A are unknown until the fundamentals are pulled, so the rubric allows a full pass.
    return {"C": "pass", "A": "pass", "N": n, "S": sg, "L": l}


def check_ceiling_is_sound_against_every_reachable_grade():
    """THE load-bearing property: no grade a grader could actually award may exceed the ceiling.
    A ceiling that is too HIGH only wastes API calls; one that is too LOW drops a qualifier and
    leaves no trace in the output, so this brute-forces the whole 3^5 grade space against the
    independent rubric above, over every combination of the three screener facts that cap it."""
    import itertools
    for oh, rv, rank in itertools.product([-1.0, -15.0, -22.0], [1.5, 0.9, 0.7], [1, 18]):
        close = 101.0 * (1 + oh / 100.0)
        out = ss.score_row(row(close=close, price_52_week_high=101.0,
                               relative_volume_10d_calc=rv, EMA50=close * 0.9, EMA200=close * 0.8,
                               **{"Perf.6M": 50.0}), "Perf.6M", 10.0, CFG)
        out["sector_rank_overall"], out["sector_count"] = rank, 20
        ss.ceiling(out, CFG)
        best = _best_grade_the_rubric_allows(oh, rv, rank, 20, CFG)
        for combo in itertools.product(["pass", "partial", "fail"], repeat=5):
            g = dict(zip("CANSL", combo))
            if any(W[g[k]] > W[best[k]] for k in "CANSL"):
                continue                       # not a grade this row could earn
            total = sum(W[v] for v in g.values()) + W[CFG["i_grade"]] + W[CFG["m_grade"]]
            assert total <= out["ceiling"] + 1e-9, (g, total, out["ceiling"], out["ceiling_caps"])


# Every name the 2026-09-12 run actually graded, as (symbol, % off the 52-week high, sector rank,
# the six letters awarded as C-A-N-S-L-I where P=pass H=partial F=fail). Real grader output, not
# constructed cases: it is the only evidence here that the caps match what the rubric DOES rather
# than what a second copy of the rubric says it should. Run outputs are gitignored, so the extract
# is pinned in-file; M was graded "partial" market-wide and 20 sectors were swept.
REAL_RUN_2026_09_12 = [
    ("INSW",   2.9,  7, "PPPPPH"),
    ("TNK",   0.1,  6, "PPPPPH"),
    ("CMBT",   2.1,  5, "PPPHPH"),
    ("DELL",   0.1,  2, "PPPHPH"),
    ("ECO",   0.1,  3, "PPPHPH"),
    ("FRO",   0.7,  4, "PPPHPH"),
    ("GEO",   5.0,  1, "HPPPPH"),
    ("OSCR",   4.3,  1, "PHPPPH"),
    ("TRMD",   2.4,  8, "PPPHPH"),
    ("AYA",   8.0,  1, "PPPHHH"),
    ("CON",   2.6,  6, "HPPHPH"),
    ("DINO",   3.9,  2, "PHPHPH"),
    ("DK",   3.0,  4, "PFPPPH"),
    ("GRDN",   7.2, 10, "HPPPHH"),
    ("HPE",   3.4,  4, "PHPHPH"),
    ("LPG",   0.6,  1, "PHPHPH"),
    ("MPC",   3.2,  6, "PHPHPH"),
    ("OII",   5.8,  5, "HHPPPH"),
    ("PARR",   2.7,  8, "PPPFPH"),
    ("PBF",   5.2,  3, "PHPHPH"),
    ("PSX",   2.2, 10, "PHPHPH"),
    ("SBLK",   5.2, 10, "PHPHPH"),
    ("VG",  10.3,  4, "PPHPHH"),
    ("VLO",   2.2,  7, "PHPHPH"),
    ("WT",   7.6,  6, "PPPFPH"),
    ("AAMI",   7.6,  4, "PHPFPH"),
    ("AMD",  11.7,  6, "PHHHPH"),
    ("ARMK",   6.5, 10, "HFPPPH"),
    ("ARW",   3.8,  4, "PFPPHH"),
    ("AVT",   0.4,  3, "PFPPHH"),
    ("CGAU",   7.7,  9, "HPPHHH"),
    ("CNC",   4.2,  5, "PFPHPH"),
    ("CXW",   1.0,  4, "HFPPPH"),
    ("IMAX",   6.3,  3, "HHPPHH"),
    ("MU",  22.3, 10, "PPFHPH"),
    ("NESR",   9.2,  1, "PHPHHH"),
    ("SM",   2.2,  9, "PFPHPH"),
    ("VCTR",  10.7,  5, "PHHHPH"),
    ("BTSG",  20.4,  8, "PHFHPH"),
    ("EAT",  16.7,  8, "HHHHPH"),
    ("MSM",   7.6,  9, "HHPHHH"),
    ("SNX",   9.2,  1, "PFPHHH"),
    ("STT",   1.3,  8, "HFPHPH"),
    ("SUNC",   2.8,  7, "PFPHHH"),
]


def check_ceiling_covers_every_grade_the_last_real_run_awarded():
    """No name in a completed run may have scored above its own ceiling. Relative volume is not
    carried in the report, so S is left unknown here - that only makes the ceiling more generous,
    and the check still binds on N and L, the two caps the real grades can contradict."""
    for sym, off_high, rank, awarded in REAL_RUN_2026_09_12:
        close = 101.0 * (1 - off_high / 100.0)
        out = ss.score_row(row(symbol=sym, close=close, price_52_week_high=101.0,
                               EMA50=close * 0.9, EMA200=close * 0.8, **{"Perf.6M": 50.0}),
                           "Perf.6M", 10.0, CFG)
        out["rel_volume_10d"] = None                      # not reported; the generous branch
        out["sector_rank_overall"], out["sector_count"] = rank, 20
        ss.ceiling(out, CFG)
        g = {"P": "pass", "H": "partial", "F": "fail"}
        total = sum(W[g[c]] for c in awarded) + W[CFG["m_grade"]]
        assert total <= out["ceiling"] + 1e-9, (
            "%s scored %.1f but its ceiling was %.1f - the ceiling would have dropped a name the "
            "grader passed (caps %r)" % (sym, total, out["ceiling"], out["ceiling_caps"]))
        # and the N cap must not contradict the N the grader actually awarded
        assert W[g[awarded[2]]] <= W[out["ceiling_caps"]["N"]], (
            "%s: graded N=%s but the ceiling capped N at %s" % (sym, g[awarded[2]],
                                                                out["ceiling_caps"]["N"]))


# ---------------------------------------------------------------- sector_screen: run()

def check_run_ranks_sectors_and_builds_the_queue():
    blob = sweep({"Energy Minerals": [row(**{"Perf.6M": 90.0}), row(symbol="NYSE:B", name="B", **{"Perf.6M": 80.0})],
                  "Utilities": [row(symbol="NYSE:C", name="C", **{"Perf.6M": 20.0})]})
    res = ss.run(blob, CFG)
    assert res["sector_count"] == 2
    assert res["sectors"][0]["sector"] == "Energy Minerals"     # higher median ranks first
    assert res["sectors"][0]["rank"] == 1
    assert res["graded_candidates"] == 3
    assert res["must_grade"] + res["eliminated_by_ceiling"] == res["graded_candidates"]
    assert res["threshold"] == CFG["threshold"]


def check_run_counts_reconcile_with_known_grades():
    blob = sweep({"Energy Minerals": [row(), row(symbol="NYSE:B", name="B")]})
    res = ss.run(blob, CFG, {"NYSE:B": {"A": "fail", "C": "fail"}})
    assert res["must_grade"] + res["eliminated_by_ceiling"] == res["graded_candidates"]
    q = {m["symbol"]: m for m in res["grade_queue"]}
    assert q["NYSE:B"]["ceiling"] < q["NYSE:TEST"]["ceiling"]


def check_dropped_rows_carry_no_ceiling():
    blob = sweep({"Energy Minerals": [row(close=9.0)]})
    res = ss.run(blob, CFG)
    m = res["sectors"][0]["members"][0]
    assert m["triage"] == "drop" and m["ceiling"] is None and m["grade_required"] is False


def check_normalize_accepts_both_sweep_shapes():
    a = ss.normalize_sectors({"sectors": {"X": [row()]}})
    b = ss.normalize_sectors({"sectors": [{"sector": "X", "rows": [row()]}]})
    assert [k for k, _ in a] == [k for k, _ in b] == ["X"]


def check_markdown_renders_without_crashing():
    res = ss.run(sweep({"Energy Minerals": [row()], "Utilities": [row(symbol="NYSE:D", name="D", close=9.0)]}), CFG)
    md = ss.to_markdown(res)
    assert "Grading coverage" in md and "Must grade" in md
    assert "/ 70" not in md and "out of 70" not in md        # the dead scale must never reappear


def check_cli_runs_end_to_end(tmp):
    p = os.path.join(tmp, "sweep.json")
    io.open(p, "w", encoding="utf-8").write(json.dumps(sweep({"Energy Minerals": [row()]})))
    out = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "sector_screen.py"), p,
                          "--m-grade", "partial", "--i-grade", "partial"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    d = json.loads(out.stdout)
    assert d["ceiling_basis"]["M"] == "partial" and d["ceiling_basis"]["I"] == "partial"
    # stdin path
    out2 = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "sector_screen.py"), "--md"],
                          input=json.dumps(sweep({"Energy Minerals": [row()]})),
                          capture_output=True, text=True, timeout=60)
    assert out2.returncode == 0 and "Sector sweep" in out2.stdout


# ---------------------------------------------------------------- relative_strength

def _bars(prices, vols=None):
    vols = vols or [1_000_000] * len(prices)
    return [[i, p, p, p, p, v] for i, (p, v) in enumerate(zip(prices, vols))]


def check_ret_over_and_rs_proxy():
    assert abs(rs.ret_over([100, 110], 1) - 0.1) < 1e-9
    assert rs.ret_over([100], 5) is None                       # not enough history
    assert rs.ret_over([0, 5], 1) is None                      # divide-by-zero guarded
    cand, bench = _bars([100] * 252 + [200]), _bars([100] * 252 + [110])
    rel, blend = rs.rs_proxy(cand, bench)
    assert rel["3m"] > 0 and blend is not None


def check_pct_off_52w_high():
    assert rs.pct_off_52w_high(_bars([100, 50])) == 0.5
    assert rs.pct_off_52w_high(_bars([100])) == 0.0
    assert rs.pct_off_52w_high([]) is None


def check_breakout_volume_excludes_the_latest_bar():
    """The 50-day average must not include the breakout bar itself, or a big day dilutes its
    own signal. 50 bars at 1M then one at 2M is exactly +100%."""
    v = [1_000_000] * 50 + [2_000_000]
    assert rs.breakout_volume(_bars([100] * 51, v), avg_window=50) == 1.0
    assert rs.breakout_volume(_bars([100] * 10), avg_window=50) is None


def check_base_metrics_flags_a_wide_loose_base():
    m = rs.base_metrics(_bars([100] * 10 + [50] + [60] * 5))
    assert m["wide_and_loose_flag"] is True and m["base_depth_pct"] == 0.5
    assert rs.base_metrics(_bars([1, 2])) is None


# ---------------------------------------------------------------- accumulation (I proxy)

def _tape(pattern, vol=None):
    """pattern: 'u'/'d'/'f' per bar (up, down, flat). vol: per-bar multiplier of 1M."""
    bars, price = [], 100.0
    for i, ch in enumerate(pattern):
        price += 1.0 if ch == "u" else (-1.0 if ch == "d" else 0.0)
        v = 1_000_000 * ((vol or [1] * len(pattern))[i])
        bars.append([i, price, price, price, round(price, 2), v])
    return bars


def check_up_down_volume_ignores_flat_days():
    """A flat close carries no directional information. Bucketing it with the buyers is how this
    ratio gets quietly inflated on thin names that reprint the same close."""
    assert acc.up_down_volume(_tape("xuudd"), 50) == 1.0        # 2 up, 2 down, equal volume
    # inserting flat days must not move the ratio
    assert acc.up_down_volume(_tape("xuffuddff"), 50) == 1.0
    assert acc.up_down_volume(_tape("xuuu"), 50) == float("inf")   # nothing to divide by
    assert acc.up_down_volume([], 50) is None


def check_up_down_volume_weights_by_volume_not_by_day_count():
    # one heavy up day outweighs three light down days
    r = acc.up_down_volume(_tape("xuddd", [1, 9, 1, 1, 1]), 50)
    assert abs(r - 3.0) < 1e-9, r


def check_big_volume_up_days_counts_only_heavy_advances():
    v = [1] * 20 + [5]                       # last bar heavy
    assert acc.big_volume_up_days(_tape("x" + "ud" * 10, v), 50, 1.4) >= 0
    up_heavy = acc.big_volume_up_days(_tape("x" + "u" * 20, v), 50, 1.4)
    dn_heavy = acc.big_volume_up_days(_tape("x" + "d" * 20, v), 50, 1.4)
    assert up_heavy == 1 and dn_heavy == 0, (up_heavy, dn_heavy)


def check_accumulation_accepts_both_bar_shapes():
    """get_ohlcv returns dicts; relative_strength.py documents positional lists. A grader that
    took only one would need a hand conversion, which is where a column shifts by one."""
    lists = _tape("xuuddu")
    dicts = [{"t": b[0], "o": b[1], "h": b[2], "l": b[3], "c": b[4], "v": b[5]} for b in lists]
    assert acc.up_down_volume(lists, 50) == acc.up_down_volume(dicts, 50)


def _heavy_on(pattern, ch, mult=4, every=6):
    """Volume derived FROM the pattern, so the heavy days land on the intended side, and heavy
    days stay OCCASIONAL.

    Two fixture mistakes are baked into this helper's shape, both found here rather than in the
    code. Building pattern and volume independently put the accumulation volume on the down days.
    And making every up day heavy scores ZERO heavy days - the count is relative to the window
    average, so a uniformly heavy tape has no spikes to find. That is the right behaviour (if
    every day looks the same you cannot pick out the institutions) but it is not what real
    accumulation looks like, which is ordinary volume punctuated by prints.
    """
    out, n = [], 0
    for c in pattern:
        if c == ch:
            n += 1
            out.append(mult if n % every == 0 else 1)
        else:
            out.append(1)
    return out


def check_accumulation_grades_the_three_regimes():
    cfg = dict(acc.DEFAULTS)
    # accumulation: more up days than down, and the heavy prints are on the up days
    p = "uud" * 27
    g, cap, why, m = acc.grade(_tape(p, _heavy_on(p, "u")), cfg)
    assert (g, cap) == ("pass", "pass"), (g, cap, m)
    assert "proxy" in why and m["ud_ratio"] > cfg["accumulate"]
    # distribution: the heavy prints are on the down days
    q = "ddu" * 27
    g2, cap2, _, m2 = acc.grade(_tape(q, _heavy_on(q, "d")), cfg)
    assert g2 == "fail" and m2["ud_ratio"] < cfg["distribute"], (g2, m2)
    # neutral tape sits between the two and must claim nothing
    r = "ud" * 40
    g3, _, _, _ = acc.grade(_tape(r), cfg)
    assert g3 == "partial", g3


def check_a_proxy_fail_never_caps_the_ceiling_at_fail_by_default():
    """THE safety property for the proxy. The ceiling is an upper bound: too high only wastes API
    calls, too low silently drops a qualifier. Volume alone cannot prove no amount of ownership
    data would lift the letter, so a proxy FAIL caps at partial unless --strict is asked for."""
    cfg = dict(acc.DEFAULTS)
    data = {"candidates": [{"symbol": "NYSE:DIST", "daily": _tape("d" * 60 + "dddu" * 8)}]}
    lenient = acc.analyze(data, cfg)
    assert lenient["detail"]["DIST"]["grade"] == "fail"
    assert lenient["known"]["DIST"]["I"] == "partial", "a proxy fail must not cap at fail"
    strict = acc.analyze(data, cfg, strict=True)
    assert strict["known"]["DIST"]["I"] == "fail", "--strict must let it prune"
    # and no proxy output may ever be worse than its own honest grade
    for out in (lenient, strict):
        for t, k in out["known"].items():
            assert acc.ORDER[k["I"]] >= acc.ORDER[out["detail"][t]["grade"]]


def check_too_little_tape_is_partial_never_fail():
    """Same rule as triage: missing data is skipped, never treated as a disqualification."""
    g, cap, why, m = acc.grade(_tape("ud" * 5), dict(acc.DEFAULTS))
    assert g == "partial" and cap == "partial", (g, cap)
    assert "too little tape" in why


# ---------------------------------------------------------------- institutional_cache (I, 13F)

def _mk13f(path, spec, quarter="06-30-2026"):
    """spec: {cusip: (issuer, n_managers, shares_each)} -> a zip shaped like SEC's data set."""
    import zipfile
    cover = ["ACCESSION_NUMBER\tCIK\tFILINGMANAGER_NAME\tREPORTCALENDARORQUARTER"]
    info = ["ACCESSION_NUMBER\tINFOTABLE_SK\tNAMEOFISSUER\tTITLEOFCLASS\tCUSIP\tVALUE\t"
            "SSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL"]
    seen, k = set(), 0
    for cusip, (name, nf, sh) in spec.items():
        for i in range(nf):
            a = "0001-%s-%03d" % (cusip[:4], i)
            if a not in seen:
                seen.add(a)
                cover.append("%s\t%d\tFUND %d\t%s" % (a, 9000 + i, i, quarter))
            k += 1
            info.append("%s\t%d\t%s\tCOM\t%s\t%d\t%d\tSH\t" % (a, k, name, cusip, sh * 50, sh))
    z = zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED)
    z.writestr("COVERPAGE.tsv", "\n".join(cover))
    z.writestr("INFOTABLE.tsv", "\n".join(info))
    z.close()
    return info


def check_13f_excludes_options_and_principal_rows(tmp):
    """Two filters that are silent if wrong. A PUTCALL row is an option, so counting it credits a
    fund that is SHORT the name via puts as a sponsor. A PRN row is a principal amount of debt,
    and summing it with share counts produces a number that means nothing."""
    import zipfile
    p = os.path.join(tmp, "q.zip")
    _mk13f(p, {"67066G104": ("NVIDIA CORPORATION", 3, 1000)})
    z = zipfile.ZipFile(p, "a")
    rows = z.read("INFOTABLE.tsv").decode()
    rows += ("\n0001-6706-000\t901\tNVIDIA CORPORATION\tCOM\t67066G104\t9\t500000\tSH\tCall"
             "\n0001-6706-000\t902\tNVIDIA CORPORATION\tNOTE\t67066G104\t9\t400000\tPRN\t")
    z.close()
    z2 = zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED)
    z2.writestr("COVERPAGE.tsv", zipfile.ZipFile(os.path.join(tmp, "q.zip.bak"), "r").read(
        "COVERPAGE.tsv").decode() if False else
        "ACCESSION_NUMBER\tCIK\tFILINGMANAGER_NAME\tREPORTCALENDARORQUARTER\n"
        "0001-6706-000\t9000\tFUND 0\t06-30-2026\n0001-6706-001\t9001\tFUND 1\t06-30-2026\n"
        "0001-6706-002\t9002\tFUND 2\t06-30-2026")
    z2.writestr("INFOTABLE.tsv", rows)
    z2.close()
    agg, note = ic.aggregate(io.open(p, "rb").read())
    e = agg["67066G104"]
    assert e["shares"] == 3000, "options/principal leaked into the share count: %s" % e["shares"]
    assert e["holders"] == 3, e["holders"]


def check_13f_counts_distinct_managers_not_filings(tmp):
    """A manager can appear on several accessions. Counting filings would inflate the holder
    count, which is the number the whole grade turns on."""
    import zipfile
    p = os.path.join(tmp, "q.zip")
    z = zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED)
    z.writestr("COVERPAGE.tsv",
               "ACCESSION_NUMBER\tCIK\tFILINGMANAGER_NAME\tREPORTCALENDARORQUARTER\n"
               "A1\t555\tONE FUND\t06-30-2026\nA2\t555\tONE FUND\t06-30-2026\n"
               "A3\t777\tOTHER FUND\t06-30-2026")
    z.writestr("INFOTABLE.tsv",
               "ACCESSION_NUMBER\tINFOTABLE_SK\tNAMEOFISSUER\tTITLEOFCLASS\tCUSIP\tVALUE\t"
               "SSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL\n"
               "A1\t1\tACME CORP\tCOM\tAAA\t1\t100\tSH\t\n"
               "A2\t2\tACME CORP\tCOM\tAAA\t1\t100\tSH\t\n"
               "A3\t3\tACME CORP\tCOM\tAAA\t1\t100\tSH\t")
    z.close()
    agg, _ = ic.aggregate(io.open(p, "rb").read())
    assert agg["AAA"]["holders"] == 2, agg["AAA"]["holders"]
    assert agg["AAA"]["shares"] == 300


def check_issuer_name_matching_and_its_refusal_to_guess():
    assert ic.norm_name("NVIDIA CORPORATION") == ic.norm_name("NVIDIA Corp")
    assert ic.norm_name("Laggard Industries, Inc.") == ic.norm_name("LAGGARD INDUSTRIES INC")
    agg = {"C1": {"name": "AMBIGUOUS HOLDINGS", "shares": 1.0, "holders": 30, "value": 1.0},
           "C2": {"name": "NVIDIA CORPORATION", "shares": 1.0, "holders": 40, "value": 1.0}}
    # two tickers claiming the same normalised name must resolve to NEITHER - a wrong ticker
    # attaches one company's sponsorship to another's scorecard
    by, un = ic.resolve_tickers(agg, {}, {"AMB": "Ambiguous Holdings", "AMB2": "Ambiguous Holdings",
                                          "NVDA": "NVIDIA Corp"})
    assert "NVDA" in by and "AMB" not in by and "AMB2" not in by
    assert [u["cusip"] for u in un] == ["C1"]


def check_share_classes_collapse_onto_one_ticker():
    agg = {"C1": {"name": "DUAL CO", "shares": 100.0, "holders": 30, "value": 1.0},
           "C2": {"name": "DUAL CO", "shares": 50.0, "holders": 25, "value": 1.0}}
    by, _ = ic.resolve_tickers(agg, {"C1": "DUAL", "C2": "DUAL"}, {})
    assert by["DUAL"]["shares"] == 150.0 and by["DUAL"]["holders"] == 30
    assert sorted(by["DUAL"]["cusips"]) == ["C1", "C2"]


def check_13f_grades_follow_the_rubric():
    cfg = dict(ic.DEFAULTS)
    rise = ic.grade({"holders": 60, "shares": 100.0}, {"holders": 52, "shares": 80.0}, cfg)
    assert rise[0] == "pass", rise
    drop = ic.grade({"holders": 30, "shares": 50.0}, {"holders": 38, "shares": 90.0}, cfg)
    assert drop[0] == "fail", drop
    flat = ic.grade({"holders": 40, "shares": 100.0}, {"holders": 40, "shares": 100.1}, cfg)
    assert flat[0] == "partial", flat
    thin = ic.grade({"holders": 5, "shares": 10.0}, {"holders": 4, "shares": 9.0}, cfg)
    assert thin[0] == "fail" and "thin" in thin[1]
    # no prior quarter = the TREND is unverified, which is partial, never a pass
    solo = ic.grade({"holders": 90, "shares": 100.0}, None, cfg)
    assert solo[0] == "partial" and "unverified" in solo[1]
    # rising but already over-owned: no room left for new sponsorship
    over = ic.grade({"holders": 60, "shares": 99.0}, {"holders": 52, "shares": 80.0}, cfg,
                    float_shares=100.0)
    assert over[0] == "partial" and "float" in over[1], over


def check_13f_fails_open_when_it_cannot_fetch(tmp):
    """No network, a moved URL, an egress policy - none of these may stop a run."""
    class A:
        quarter, prior = "2099Q4", "2099Q3"
        universe = cusip_map = None
        cache_dir = os.path.join(tmp, "nope")
        contact, timeout = "", 0.2
    meta, known, detail, un = ic.build(A(), dict(ic.DEFAULTS))
    assert meta["ok"] is False and known == {} and detail == {}
    assert any("could not be fetched" in n for n in meta["notes"]), meta["notes"]


def check_fallback_fills_gaps_and_never_overwrites(tmp):
    meta = {"notes": []}
    known = {"NVDA": {"I": "pass"}}
    detail = {"NVDA": {"grade": "pass", "source": "sec-13f"}}
    fb = os.path.join(tmp, "fb.json")
    io.open(fb, "w", encoding="utf-8").write(json.dumps({
        "meta": {"source": "accumulation-proxy"},
        "known": {"NVDA": {"I": "fail"}, "OTHER": {"I": "partial"}},
        "detail": {"NVDA": {"grade": "fail"}, "OTHER": {"grade": "partial"}}}))
    n = ic.merge_fallback(meta, known, detail, fb)
    assert n == 1
    assert known["NVDA"]["I"] == "pass", "a proxy overwrote a real 13F grade"
    assert detail["NVDA"]["source"] == "sec-13f"
    assert detail["OTHER"]["source"] == "accumulation-proxy"


# ---------------------------------------------------------------- known-file plumbing

def check_load_known_unwraps_the_cache_shape(tmp):
    """Without the unwrap, passing an I-cache to --known looks like it worked and grades nothing:
    every lookup misses, silently, and the run reports I=partial for the whole market."""
    a = os.path.join(tmp, "a.json")
    io.open(a, "w", encoding="utf-8").write(json.dumps({
        "meta": {"source": "sec-13f"}, "known": {"NVDA": {"I": "pass"}}, "detail": {}}))
    assert ss.load_known([a]) == {"NVDA": {"I": "pass"}}
    b = os.path.join(tmp, "b.json")          # the bare shape still works
    io.open(b, "w", encoding="utf-8").write(json.dumps({"NVDA": {"A": "fail"}}))
    merged = ss.load_known([a, b])
    assert merged["NVDA"] == {"I": "pass", "A": "fail"}, merged
    c = os.path.join(tmp, "c.json")          # later file wins on a conflict
    io.open(c, "w", encoding="utf-8").write(json.dumps({"NVDA": {"I": "fail"}}))
    assert ss.load_known([a, c])["NVDA"]["I"] == "fail"


def check_a_sourced_letter_is_distinguishable_from_an_unsourced_one():
    """"I = partial (graded)" and "I <= partial: not sourceable" are the same number and entirely
    different evidence. A report that cannot tell them apart cannot say where the grade came from.
    """
    graded = _ceiling_of()
    ss.ceiling(graded, CFG, {"I": "partial"})
    assert any("I = partial (graded)" in r for r in graded["ceiling_reasons"])
    assert not any("not sourceable" in r for r in graded["ceiling_reasons"])
    bare = _ceiling_of()
    ss.ceiling(bare, CFG)
    assert any("not sourceable" in r for r in bare["ceiling_reasons"])
    assert graded["ceiling"] == bare["ceiling"]      # same number, different provenance


# ---------------------------------------------------------------- html_to_pdf

def check_css_page_size_and_margin(tmp):
    p = os.path.join(tmp, "a.html")
    io.open(p, "w", encoding="utf-8").write("<style>@page{size:A4 landscape;margin:15mm}</style>")
    assert h2p.css_page_size(p) == "a4 landscape"
    assert h2p.css_page_margin(p) == "15mm"


def check_css_margin_rejects_what_it_cannot_forward(tmp):
    """A multi-value or unitless margin cannot be handed to wkhtmltopdf verbatim, so the parser
    must fall back rather than pass through something the engine will misread."""
    for css, want in [("@page{margin:10mm 5mm}", h2p.DEFAULT_MARGIN),
                      ("@page{margin:0}", h2p.DEFAULT_MARGIN),
                      ("@page{margin:1.5cm}", "1.5cm"),
                      ("<style></style>", h2p.DEFAULT_MARGIN)]:
        p = os.path.join(tmp, "b.html")
        io.open(p, "w", encoding="utf-8").write("<style>%s</style>" % css)
        assert h2p.css_page_margin(p) == want, (css, h2p.css_page_margin(p))


def check_css_helpers_survive_a_missing_file():
    assert h2p.css_page_size("/nope/nothing.html") is None
    assert h2p.css_page_margin("/nope/nothing.html") == h2p.DEFAULT_MARGIN


def check_render_timeouts_agree():
    """Every engine in the chain shares one ceiling; a mismatch means one engine is the odd one
    out again, which is the bug the constant was introduced to remove."""
    assert h2p.RENDER_TIMEOUT == br.RENDER_TIMEOUT == 240


# ---------------------------------------------------------------- build_report / the template

TPL = os.path.join(ROOT, "assets", "dashboard_template.html")


def check_apply_theme_targets_the_doctype_not_the_prose(tmp):
    """The template's own header comment TALKS ABOUT <html data-theme="dark">; the rewrite must
    anchor on the real doctype or it edits the comment and leaves the document untouched."""
    p = os.path.join(tmp, "r.html")
    shutil.copy(TPL, p)
    assert br.apply_theme(p, "light") is True
    s = io.open(p, encoding="utf-8").read()
    doc = re.search(r"<!doctype html>(?:\s|<!--.*?-->)*<html[^>]*>", s, re.I | re.S)
    assert doc and 'data-theme="light"' in doc.group(0), doc.group(0) if doc else "no doctype"
    assert s.count('<html lang="en" data-theme="light">') == 1


def check_template_scripts_parse():
    src = io.open(TPL, encoding="utf-8").read()
    js = "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", src, re.S))
    node = shutil.which("node")
    if not node:
        return "skipped - node not installed"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        path = f.name
    try:
        r = subprocess.run([node, "--check", path], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
    finally:
        os.unlink(path)


def _strip_comments(src):
    """Drop HTML comments and CSS/JS block comments - the parts that never reach a reader.

    The template deliberately NAMES the dead scales in two comments: the .sc-total rule explains
    why the value and its denominator must live in one span (a split one flattened to "/74.5",
    "i.e. a score out of 70"), and the audit explains which denominators it matches. Grepping raw
    source would fail on the very comments that document the bug, so strip what does not render
    and check the rest - the same distinction the /70 hunt turned on originally.
    """
    src = re.sub(r"<!--.*?-->", " ", src, flags=re.S)
    return re.sub(r"/\*.*?\*/", " ", src, flags=re.S)


def check_template_has_no_dead_scale():
    src = _strip_comments(io.open(TPL, encoding="utf-8").read())
    for bad in ("/70", "out of 70", "/ 70", "/10", "out of 10"):
        assert bad not in src, "template still mentions %r outside a comment" % bad
    assert "out of 7" in src


def check_template_audit_rules_are_wired():
    """The self-audit is the skill's last line of defence; these are the contradictions it
    promises to catch, each identified by the text it raises."""
    src = io.open(TPL, encoding="utf-8").read()
    for frag in ["CONFIG.sweep.mustGrade says",
                 "verdict AVOID but the scorecard totals",
                 "a buy point is named but N is FAIL",
                 "is more than 10% below the 52-week high",
                 "CONFIG.dataDate is empty",
                 "CONFIG.freshness is missing",
                 "reused data with no `asOf`"]:
        assert frag in src, "audit no longer raises: %s" % frag


def check_funnel_tile_is_addressed_by_identity_not_index():
    """Writing the qualifier count to tiles[4] broke the moment a tile was inserted above it."""
    src = io.open(TPL, encoding="utf-8").read()
    assert 'id:"qualified"' in src and 't.id==="qualified"' in src
    assert "tiles[4]" not in src


# ---------------------------------------------------------------- check_for_updates

def _git(cwd, *a, **kw):
    return subprocess.run(("git",) + a, cwd=cwd, capture_output=True, text=True,
                          timeout=60, **kw)


def _mkrepo(tmp):
    """An origin, a working clone with the script inside it, and a second clone to push from."""
    org = os.path.join(tmp, "origin")
    os.makedirs(org)
    _git(org, "init", "-q", "--bare")
    _git(tmp, "clone", "-q", org, "work")
    work = os.path.join(tmp, "work")
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        _git(work, "config", k, v)
    os.makedirs(os.path.join(work, "scripts"))
    os.makedirs(os.path.join(work, "assets"))
    shutil.copy(os.path.join(ROOT, "scripts", "check_for_updates.py"),
                os.path.join(work, "scripts"))
    for f in ("SKILL.md", "scripts/sector_screen.py", "assets/dashboard_template.html"):
        io.open(os.path.join(work, f), "w", encoding="utf-8").write("v1\n")
    _git(work, "add", "-A"); _git(work, "commit", "-qm", "init")
    br_ = _git(work, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    _git(work, "push", "-q", "-u", "origin", br_)
    _git(tmp, "clone", "-q", org, "other")
    other = os.path.join(tmp, "other")
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        _git(other, "config", k, v)
    return work, other


def _run_cfu(cwd, *args):
    r = subprocess.run([sys.executable, os.path.join(cwd, "scripts", "check_for_updates.py")] + list(args),
                       cwd=cwd, capture_output=True, text=True, timeout=90)
    return r.returncode, r.stdout + r.stderr


def check_updates_reports_current(tmp):
    work, _ = _mkrepo(tmp)
    code, out = _run_cfu(work)
    assert code == 0 and "Skill is current" in out, out


def check_updates_separates_code_from_instructions(tmp):
    """The distinction the whole feature rests on: code updates land now, instruction updates
    land next run, and the report must not merge them."""
    work, other = _mkrepo(tmp)
    for f in ("SKILL.md", "scripts/sector_screen.py"):
        io.open(os.path.join(other, f), "w", encoding="utf-8").write("v2\n")
    _git(other, "add", "-A"); _git(other, "commit", "-qm", "bump"); _git(other, "push", "-q")
    code, out = _run_cfu(work)
    assert code == 0 and "OUT OF DATE" in out, out
    live = out.index("THIS RUN WILL USE THE NEW VERSION")
    ctx = out.index("ALREADY LOADED")
    assert out.index("scripts/sector_screen.py") > live
    assert out.index("SKILL.md", ctx) > ctx
    assert io.open(os.path.join(work, "SKILL.md")).read().strip() == "v1"   # report-only: no pull


def check_updates_refuses_to_pull_over_uncommitted_work(tmp):
    work, other = _mkrepo(tmp)
    io.open(os.path.join(other, "SKILL.md"), "w", encoding="utf-8").write("v2\n")
    _git(other, "commit", "-qam", "bump"); _git(other, "push", "-q")
    mine = os.path.join(work, "scripts", "sector_screen.py")
    io.open(mine, "w", encoding="utf-8").write("MY UNCOMMITTED WORK\n")
    code, out = _run_cfu(work, "--update")
    assert code == 1, out
    assert "refused" in out
    assert io.open(mine).read() == "MY UNCOMMITTED WORK\n", "local work was clobbered"
    assert io.open(os.path.join(work, "SKILL.md")).read().strip() == "v1"


def check_updates_fast_forwards_a_clean_tree(tmp):
    work, other = _mkrepo(tmp)
    io.open(os.path.join(other, "scripts", "sector_screen.py"), "w", encoding="utf-8").write("v2\n")
    _git(other, "commit", "-qam", "bump"); _git(other, "push", "-q")
    code, out = _run_cfu(work, "--update")
    assert code == 0 and "fast-forwarded" in out, out
    assert io.open(os.path.join(work, "scripts", "sector_screen.py")).read().strip() == "v2"
    assert out.count("fast-forwarded") == 1, "the update message is duplicated"
    code2, out2 = _run_cfu(work, "--update")                 # idempotent
    assert code2 == 0 and "nothing to update" in out2


def check_updates_ahead_does_not_claim_incoming_code(tmp):
    """An 'ahead' branch must not list its own unpushed edits under a heading promising new
    upstream code - that was a real bug."""
    work, _ = _mkrepo(tmp)
    io.open(os.path.join(work, "scripts", "sector_screen.py"), "w", encoding="utf-8").write("v9\n")
    _git(work, "commit", "-qam", "local only")
    code, out = _run_cfu(work)
    assert code == 0 and "ahead of the remote" in out, out
    assert "THIS RUN WILL USE THE NEW VERSION" not in out
    assert "ALREADY LOADED" not in out


def check_updates_reports_diverged_without_touching_anything(tmp):
    work, other = _mkrepo(tmp)
    io.open(os.path.join(other, "SKILL.md"), "w", encoding="utf-8").write("remote\n")
    _git(other, "commit", "-qam", "r"); _git(other, "push", "-q")
    io.open(os.path.join(work, "scripts", "sector_screen.py"), "w", encoding="utf-8").write("local\n")
    _git(work, "commit", "-qam", "l")
    code, out = _run_cfu(work, "--update")
    assert code == 0 and "DIVERGED" in out, out
    assert io.open(os.path.join(work, "scripts", "sector_screen.py")).read().strip() == "local"


def check_updates_fails_open_when_it_cannot_check(tmp):
    """No git checkout, no upstream, unreachable remote - each must exit 0 so the run continues."""
    plain = os.path.join(tmp, "plain", "scripts")
    os.makedirs(plain)
    shutil.copy(os.path.join(ROOT, "scripts", "check_for_updates.py"), plain)
    code, out = _run_cfu(os.path.dirname(plain))
    assert code == 0 and "not a git checkout" in out, out

    nested = os.path.join(tmp, "b")          # a second repo, clear of the one made above
    os.makedirs(nested, exist_ok=True)
    work, _ = _mkrepo(nested)
    _git(work, "checkout", "-q", "-b", "untracked-branch")
    code, out = _run_cfu(work)
    assert code == 0 and "no upstream" in out, out

    _git(work, "checkout", "-q", "-")
    _git(work, "remote", "set-url", "origin", "https://nonexistent.invalid/x.git")
    code, out = _run_cfu(work, "--timeout", "8")
    assert code == 0 and "unreachable" in out, out


def check_updates_status_and_header_sets_agree():
    src = io.open(os.path.join(ROOT, "scripts", "check_for_updates.py"), encoding="utf-8").read()
    produced = set(re.findall(r'out\["status"\]\s*=\s*"([a-z-]+)"', src))
    block = src[src.index("head = {"):src.index('}.get(v["status"]')]
    assert not (produced - set(re.findall(r'"([a-z-]+)":', block))), "a status has no header"


# ---------------------------------------------------------------- export_portable

def check_export_bundles_every_script(tmp):
    # The portable bundle ships this suite but NOT the exporter - a copy handed to another
    # assistant has nothing left to export. Skip rather than fail there, so the suite a ported
    # copy runs comes back green and a real failure still stands out.
    exporter = os.path.join(ROOT, "scripts", "export_portable.py")
    if not os.path.exists(exporter):
        return "skipped: no exporter in this copy (a portable bundle)"
    out = subprocess.run([sys.executable, exporter, tmp],
                         capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr
    import zipfile
    z = zipfile.ZipFile(os.path.join(tmp, "can-slim-recommend.zip"))
    assert z.testzip() is None
    names = {n.split("/", 1)[1] for n in z.namelist() if "/" in n}
    for f in os.listdir(os.path.join(ROOT, "scripts")):
        if f.endswith(".py") and f != "export_portable.py":
            assert "scripts/" + f in names, "%s missing from the bundle" % f
    md = io.open(os.path.join(tmp, "can-slim-recommend-portable.md"), encoding="utf-8").read()
    assert "check_for_updates.py" in md
    # Every fenced block must close - an unbalanced fence silently swallows the rest of the file.
    # Counted per fence WIDTH: the exporter widens a fence when the file it wraps contains
    # backticks, and a plain "```" count would see the opening of a ````-fence as a match.
    for fence in set(re.findall(r"^(`{3,})", md, re.M)):
        assert md.count("\n" + fence) % 2 == 0, "unbalanced %d-backtick fence" % len(fence)


# ---------------------------------------------------------------- doc/consistency

def _frontmatter_description(path):
    """Resolve SKILL.md's `description: >-` block the way a YAML folded scalar does: every line
    stripped and joined with single spaces. The file's own line breaks are invisible to whatever
    reads the frontmatter, so the source length is NOT the length that counts."""
    src = io.open(path, encoding="utf-8").read()
    assert src.startswith("---\n"), "SKILL.md must open with frontmatter"
    fm = src.split("---", 2)[1]
    m = re.search(r"description: >-\n(.*?)(?=\n[a-z_]+:|\Z)", fm, re.S)
    assert m, "SKILL.md has no folded description block"
    return " ".join(l.strip() for l in m.group(1).strip().splitlines())


DESCRIPTION_LIMIT = 1024


def check_skill_description_fits_the_frontmatter_limit():
    """A description over the limit is the worst kind of failure this skill has: nothing errors,
    the file looks fine, and the skill just stops being offered for the phrases it lists. It had
    grown to 1108 characters unnoticed. Pinned here because no run would ever reveal it.
    """
    d = _frontmatter_description(os.path.join(ROOT, "SKILL.md"))
    assert len(d) <= DESCRIPTION_LIMIT, (
        "SKILL.md description is %d characters, %d over the %d limit - trim it, and keep the "
        "trigger phrases: they are what earns the skill its activations."
        % (len(d), len(d) - DESCRIPTION_LIMIT, DESCRIPTION_LIMIT))
    # the parts worth keeping must survive any future trim
    for must in ("CAN SLIM", "can-slim-grader", "recommend some stocks", "what should I buy",
                 "4.5", "never personalized investment advice"):
        assert must in d, "the description no longer mentions %r" % must


def check_skill_frontmatter_conforms(tmp):
    """The rules an importer enforces before it will load the skill at all. Each of these fails
    SILENTLY somewhere - a BOM hides the opening '---', a tab makes the YAML unparseable, an
    unrecognised key is rejected wholesale - so the skill simply does not appear, with no error
    pointing at the file."""
    raw = io.open(os.path.join(ROOT, "SKILL.md"), "rb").read()
    assert not raw.startswith(b"\xef\xbb\xbf"), "a UTF-8 BOM hides the opening '---'"
    assert b"\r\n" not in raw, "CRLF line endings"
    assert raw.endswith(b"\n"), "no trailing newline"
    src = raw.decode("utf-8")
    assert src.startswith("---\n"), "frontmatter must start on line 1"
    fm, body = src.split("---", 2)[1], src.split("---", 2)[2]
    assert "\t" not in fm, "YAML forbids tabs for indentation"

    keys = re.findall(r"^([A-Za-z_][A-Za-z0-9_-]*):", fm, re.M)
    assert set(keys) <= {"name", "description", "license", "allowed-tools", "metadata", "version"}, \
        "unrecognised frontmatter key in %r" % keys
    assert {"name", "description"} <= set(keys), "name and description are both required"
    name = re.search(r"^name:\s*(.+)$", fm, re.M).group(1).strip()
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), "name %r must be lowercase-and-hyphen" % name
    assert len(name) <= 64, "name is %d chars (limit 64)" % len(name)
    assert re.search(r"^#\s+\S", body, re.M), "the body needs a top-level heading"


def check_no_angle_bracket_placeholders(tmp):
    """`<date>`, `<SYM>` and friends read as HTML tags. A markdown renderer or an importer that
    sanitises HTML drops them, so the reader is told to run
    `build_report.py canslim-recommendations-.html`. Placeholders use {braces} throughout.

    README's `<html>` is exempt: it names the actual element whose data-theme you edit.
    """
    for rel in ["SKILL.md", "README.md"] + ["references/" + f for f in
                                            sorted(os.listdir(os.path.join(ROOT, "references")))
                                            if f.endswith(".md")]:
        text = io.open(os.path.join(ROOT, rel), encoding="utf-8").read()
        found = [t for t in re.findall(r"</?[a-zA-Z][a-zA-Z0-9_ -]*/?>", text)
                 if not (rel == "README.md" and t == "<html>")]
        assert not found, "%s uses angle-bracket placeholders %s - use {braces}" % (rel, sorted(set(found)))


def check_skill_documents_step_zero():
    s = io.open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
    assert "### 0 — Check this copy of the skill is current" in s
    assert "check_for_updates.py" in s
    assert "does NOT take effect this run" in s.replace("**", "")


def check_docs_have_no_dead_scale():
    for f in ("SKILL.md", "README.md", "references/canslim-methodology.md"):
        s = io.open(os.path.join(ROOT, f), encoding="utf-8").read()
        for bad in ("/70", "out of 70"):
            assert bad not in s, "%s mentions %r" % (f, bad)


def check_every_script_compiles():
    import py_compile
    d = os.path.join(ROOT, "scripts")
    for f in sorted(os.listdir(d)):
        if f.endswith(".py"):
            py_compile.compile(os.path.join(d, f), doraise=True)


# ---------------------------------------------------------------- runner

def main():
    want = [a for a in sys.argv[1:] if not a.startswith("-")]
    verbose = "-v" in sys.argv
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("check_") and callable(f)]
    if want:
        tests = [(n, f) for n, f in tests if any(w in n for w in want)]
    passed = failed = skipped = 0
    fails = []
    for name, fn in tests:
        tmp = tempfile.mkdtemp(prefix="canslim-test-")
        try:
            note = fn(tmp) if fn.__code__.co_argcount else fn()
            if isinstance(note, str) and note.startswith("skipped"):
                skipped += 1
                print("  SKIP %s (%s)" % (name, note))
            else:
                passed += 1
                if verbose:
                    print("  ok   %s" % name)
        except Exception as e:
            failed += 1
            fails.append((name, e))
            print("  FAIL %s\n         %s: %s" % (name, type(e).__name__, e))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d passed, %d failed, %d skipped (%d total)" %
          (passed, failed, skipped, len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
`````
