# stock-recommend

A Claude skill that generates a **ranked, sector-diversified watchlist of stock
recommendations** using William J. O'Neil's **CAN SLIM** methodology (from *How to Make
Money in Stocks*, 4th ed.), screened against live **Interactive Brokers (IBKR)** market
data plus web research.

It activates when you ask for stock ideas — *"recommend some stocks"*, *"what should I
buy"*, *"give me a list of growth stocks"*, *"screen for CAN SLIM names"*, *"recommend AI
stocks"*. It asks how many names you want (**default 20**) and spreads them across
non-overlapping industry groups.

## How it works

1. **M first** — assesses general-market direction (S&P/Nasdaq trend + distribution days).
   It still delivers a list in a correction, but flags the risk and tightens the stops.
2. **Generate candidates** — leading themes/groups via IBKR's investment-topic tools + web
   research on current leaders.
3. **Screen with CAN SLIM** — IBKR supplies the technical letters (N new highs/bases, S
   volume, L relative strength/leadership, M market); web research supplies the fundamental
   letters (C quarterly earnings & sales, A annual earnings/ROE, I institutional ownership).
4. **Diversify & rank** — caps names per sector, ranks by CAN SLIM score, and returns a
   shortlist with a per-name rationale, buy point, and 7–8% loss-cutting stop.

If fewer names qualify than you asked for, it returns fewer and explains why — it never
pads the list with weak stocks.

## Contents
- `SKILL.md` — activation + workflow.
- `references/canslim-methodology.md` — the full distilled CAN SLIM rule set: the seven
  criteria and thresholds, chart-base patterns, buy/sell rules, money management, and the
  21 costly mistakes.
- `references/ibkr-data-guide.md` — candidate generation and the exact IBKR call sequence /
  formulas to compute each CAN SLIM letter.
- `scripts/relative_strength.py` — computes the relative-strength proxy, % off 52-week high,
  base depth/length, and breakout volume from IBKR OHLCV bars. Standard library only.

## Requirements
- IBKR MCP connector connected and authorized (read-only market data; never trades).
- Web search available in the session.

## Disclaimer
This skill is **informational decision support, not investment advice.** It never places
orders and never gives personalized buy/sell directives. CAN SLIM is a probability edge,
not a guarantee; every recommendation is paired with its loss-cutting exit rule. Markets
carry risk of loss.

Methodology credit: William J. O'Neil, *How to Make Money in Stocks: A Winning System in
Good Times or Bad* (4th edition, McGraw-Hill). This is an independent implementation of the
publicly described method for personal use; it reproduces no copyrighted text.
