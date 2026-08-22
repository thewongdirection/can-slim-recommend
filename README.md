# can-slim-recommend

A Claude skill that sweeps **every market sector** for its top performers, grades each one against
the **CAN SLIM** growth-investing methodology using live **TradingView** data, and returns **two
ranked recommendation lists** as a white-themed PDF report.

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

- **Default: a white-themed PDF report** (`scripts/html_to_pdf.py`), A4 landscape so the
  ~10-column pick tables fit. It includes the market verdict, the screening funnel, a leadership
  map (RS vs distance below the 52-week high), both recommendation lists, the sector sweep
  ranking, a **data sources & freshness table**, the portfolio/loss-cutting note, the disclaimer
  and an acronym glossary.
- **On request: the interactive HTML** — same report plus sortable columns and clickable tickers
  that open each name's per-ticker report in an in-page window. A dark rendering is also on
  request (`data-theme="dark"`).
- The dashboard **audits its own CONFIG** on render and prints a red banner for contradictions —
  an ungraded letter, a buy point with N failing, a pivot below new-high ground, a stop that isn't
  7-8%, a verdict that disagrees with the grade, or missing data provenance.

## Fresh data, every run

Every figure comes from a tool call made in that run. Screener rows, bars, financials, grades and
filled reports are never reused from an earlier run, an earlier session, or earlier in the same
conversation — a re-check is a full re-run. Every report names its sources and stamps when each
was pulled, and flags anything gated or stale.

## Contents
- `SKILL.md` — activation + the full workflow.
- `references/canslim-methodology.md` — the distilled CAN SLIM rule set: the seven criteria and
  thresholds, chart-base patterns, buy/sell rules, money management, and the costly mistakes.
  Shared verbatim with `can-slim-grader`.
- `references/tradingview-sector-sweep.md` — the primary data guide: verified TradingView call
  shapes, the sector taxonomy, triage filters, the grader hand-off, and how the two lists are
  built.
- `references/ibkr-data-guide.md` — the fallback path (IBKR / Massive / FMP) plus the shared
  fundamental-source ladder.
- `scripts/sector_screen.py` — sector sweep arithmetic + CAN SLIM triage over the screener rows.
- `scripts/relative_strength.py` — RS proxy, % off 52-week high, base depth/length, breakout
  volume from OHLCV bars. Shared with `can-slim-grader`.
- `scripts/html_to_pdf.py` — renders the filled dashboard to PDF. Shared with `can-slim-grader`.
- `assets/dashboard_template.html` — the self-contained white-themed report template.

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
