# can-slim-recommend

A Claude skill that generates a **ranked, sector-diversified watchlist of stock
recommendations** using the **CAN SLIM** growth-investing methodology, screened against
live **Interactive Brokers (IBKR)** market data plus web research.

It activates when you ask for stock ideas — *"recommend some stocks"*, *"what should I
buy"*, *"give me a list of growth stocks"*, *"screen for CAN SLIM names"*, *"recommend AI
stocks"*. It asks how many names you want (**default 20**) and spreads them across
non-overlapping industry groups.

## Core concepts & critical ideas

CAN SLIM is a rules-based framework for finding **growth stocks poised for a big advance**.
It is built on how the market actually behaves — supply, demand, and crowd psychology —
rather than on valuation "cheapness," forecasts, dividends, or opinion. The whole approach
rests on a handful of critical ideas:

- **The seven factors (CAN SLIM).** Each letter is a trait the biggest historical winners
  shared *just before* their major moves:
  - **C — Current quarterly earnings & sales** up sharply (≥25%, ideally far more) versus
    the same quarter a year ago, and *accelerating*.
  - **A — Annual earnings** growing (≥25%/yr over 3 years) with a high return on equity
    (≥17%).
  - **N — Something new** (product, management, or industry condition) **and** the stock
    breaking out to **new highs from a sound price base** — the key entry trigger.
  - **S — Supply & demand** — a big volume surge on the breakout, a manageable share
    float, buybacks, low debt.
  - **L — Leader, not laggard** — high relative price strength; the #1 or #2 name in a
    strong industry group, not the cheap also-ran.
  - **I — Institutional sponsorship** — increasing ownership by high-quality funds.
  - **M — Market direction** — the general market must be in a confirmed uptrend.
- **"M" gates everything.** Roughly three of four stocks follow the general market, so the
  market's direction is assessed *first*. A market top is spotted through **distribution
  days** (heavy-volume down days); a new uptrend is confirmed by a **follow-through day**
  (a decisive high-volume rally day). You don't buy breakouts in a downtrend.
- **Buy high to sell higher (the "Great Paradox").** What looks too high to the crowd
  tends to go higher; what looks cheap tends to go lower. You buy **strength emerging from
  a base near new highs**, never a falling "bargain." Real leaders begin their big moves at
  new highs, not new lows.
- **Bases and pivots.** Winners consolidate into recognizable patterns (cup-with-handle,
  double-bottom, flat base, etc.) before advancing. You buy at the **pivot** as the stock
  breaks out on volume ≥40–50% above average — and never chase it more than ~5% past that
  point.
- **Defense first — cut losses at 7–8%, no exceptions.** Every large loss began as a small
  one; a 50% loss needs a 100% gain to recover. You take losses quickly and profits slowly,
  **average up, never down**, and take many 20–25% gains while letting the strongest leaders
  run.
- **Leadership & groups.** About half of a stock's move comes from its industry group and
  sector, so you buy leaders in **top-ranked groups** and confirm strength with a second
  strong name in the same group.
- **Concentration over diversification.** The method favors owning just a handful of the
  very best names (4–6) rather than spreading thin — so the 20-name list this skill produces
  is best treated as a **research shortlist to narrow down**, not 20 positions to hold at
  once.

`references/canslim-methodology.md` in this repo contains the full rule set, thresholds,
base patterns, sell rules, and the classic mistakes to avoid.

## How it works

1. **M first** — assesses general-market direction (S&P/Nasdaq trend + distribution days).
   It still delivers a list in a correction, but flags the risk and tightens the stops.
2. **Generate candidates** — leading themes/groups via IBKR's investment-topic tools + web
   research on current leaders.
3. **Screen with CAN SLIM** — IBKR supplies the technical letters (N new highs/bases, S
   volume, L relative strength/leadership, M market); web research supplies the fundamental
   letters (C quarterly earnings & sales, A annual earnings/ROE, I institutional ownership).
4. **Diversify & rank** — caps names per sector, grades every letter 0–10 (total /70 including
   the market's M score), sorts each survivor into **BUY-RANGE / WATCH / AVOID**, and returns a
   shortlist with a per-name rationale, buy point, and 7–8% loss-cutting stop.

If fewer names qualify than you asked for, it returns fewer and explains why — it never
pads the list with weak stocks.

## Sister skill — [`can-slim-grader`](https://github.com/thewongdirection/can-slim-grader)

The two are a matched pair on one CAN SLIM methodology, pointed in opposite directions:
this skill is the **market-wide screener** (a whole market in → a ranked LIST out), while
`can-slim-grader` is the **single-ticker grading lens** (one ticker in → one verdict out).
Ask for ideas and you get this; ask "is NVDA any good?" and you get the grader.

They are deliberately kept in step: `references/canslim-methodology.md` and
`scripts/relative_strength.py` are shared verbatim, `scripts/html_to_pdf.py` is the same
helper, and both use one **verdict vocabulary** — **BUY-RANGE / WATCH / AVOID** — over one
grading scale at two resolutions (this skill's per-letter **0-10** maps to the grader's
pass/partial/fail as 8-10 = pass, 4-7 = partial, 0-3 = fail). The same stock should never
read as a buy in one and a fail in the other.

## Contents
- `SKILL.md` — activation + workflow.
- `references/canslim-methodology.md` — the full distilled CAN SLIM rule set: the seven
  criteria and thresholds, chart-base patterns, buy/sell rules, money management, the 0-10
  grading rubric (and its bridge to the grader's pass/partial/fail), and the classic costly
  mistakes.
- `references/ibkr-data-guide.md` — candidate generation, the exact IBKR call sequence /
  formulas to compute each CAN SLIM letter, the fundamental source ladder, and the verdict tiers.
- `scripts/relative_strength.py` — computes the relative-strength proxy, % off 52-week high,
  base depth/length, and breakout volume from IBKR OHLCV bars, with an optional `--asof`
  point-in-time cutoff. Standard library only.
- `scripts/html_to_pdf.py` — optional PDF export of the finished dashboard (headless
  Chrome/Chromium/Edge → Playwright → WeasyPrint → wkhtmltopdf). Standard library only.
- `assets/dashboard_template.html` — the default deliverable: a self-contained, dark-themed
  interactive dashboard driven by one `CONFIG` object.

## Requirements
- IBKR MCP connector connected and authorized (read-only market data; never trades).
- Web search available in the session.

## Disclaimer
This skill is **informational decision support, not investment advice.** It never places
orders and never gives personalized buy/sell directives. CAN SLIM is a probability edge,
not a guarantee; every recommendation is paired with its loss-cutting exit rule. Markets
carry risk of loss. It is an independent implementation of a publicly known investing
framework and reproduces no third-party copyrighted text.
