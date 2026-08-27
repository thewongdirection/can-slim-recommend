#!/usr/bin/env python3
"""
export_portable.py - bundle this skill into files you can hand to a NON-Claude model.

The skill normally lives as a directory that Claude Code loads on its own. Other assistants
(Gemini, ChatGPT, a local model, ...) have no such loader, so this writes two artifacts:

  can-slim-recommend-portable.md   ONE self-contained Markdown file - a portability preamble
                                   (what the skill needs from its host, stated in tool-agnostic
                                   terms) followed by every file of the skill inlined verbatim.
                                   Paste or upload this into any assistant with a long context.

  can-slim-recommend.zip           the raw directory, for a host that can take a folder
                                   (Gemini Gems / Custom GPT file uploads, another Claude Code
                                   install, a git checkout).

Both are regenerated from the working tree, so re-run this after changing the skill rather than
hand-editing the bundle - a stale bundle is worse than none.

Usage:  python scripts/export_portable.py [outdir]      (default: ./dist)
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Order matters: this is the reading order for a model meeting the skill for the first time.
FILES = [
    ("SKILL.md",                             "md",   "The skill itself: when it activates and the full workflow, step by step."),
    ("README.md",                            "md",   "Human-facing overview: what it produces and the CAN SLIM ideas behind it."),
    ("references/canslim-methodology.md",    "md",   "The distilled CAN SLIM rule set - the seven criteria, thresholds, base patterns, buy/sell rules."),
    ("references/tradingview-sector-sweep.md","md",  "The primary data guide: verified call shapes, sector taxonomy, triage filters, list construction."),
    ("references/ibkr-data-guide.md",        "md",   "The fallback data path plus the shared fundamental-source ladder."),
    ("scripts/sector_screen.py",             "python", "Sector-sweep arithmetic and CAN SLIM triage over the screener rows."),
    ("scripts/relative_strength.py",         "python", "RS proxy, % off the 52-week high, base depth/length, breakout volume, from OHLCV bars."),
    ("scripts/html_to_pdf.py",               "python", "Renders the filled dashboard to PDF; reads page size and margin from the document's @page rule."),
    ("assets/dashboard_template.html",       "html", "The report template. Fill its CONFIG object and it renders itself, audits itself, and refuses to ship a self-contradicting report."),
]

PREAMBLE = """# CAN SLIM Sector Recommendations - portable skill bundle

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
  scripts/html_to_pdf.py
  assets/dashboard_template.html
```

---
"""


def fence_for(text):
    """A fence longer than any run of backticks inside the file, so its content cannot break out.

    The reference files are Markdown and contain their own ``` blocks, so a plain three-backtick
    fence would end the block early and spill the rest of the file into the document.
    """
    longest = run = 0
    for ch in text:
        run = run + 1 if ch == "`" else 0
        longest = max(longest, run)
    return "`" * max(3, longest + 1)


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist")
    os.makedirs(outdir, exist_ok=True)

    parts = [PREAMBLE]
    missing = []
    for rel, lang, blurb in FILES:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            missing.append(rel)
            continue
        body = open(path, encoding="utf-8").read().rstrip("\n")
        fence = fence_for(body)
        parts.append("\n## `%s`\n\n%s\n\n%s%s\n%s\n%s\n" %
                     (rel, blurb, fence, lang, body, fence))

    md_path = os.path.join(outdir, "can-slim-recommend-portable.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts).rstrip() + "\n")

    zip_path = os.path.join(outdir, "can-slim-recommend.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, _, _ in FILES:
            p = os.path.join(ROOT, rel)
            if os.path.exists(p):
                z.write(p, os.path.join("can-slim-recommend", rel))
        z.writestr("can-slim-recommend/PORTABLE-README.md", PREAMBLE)

    for p in (md_path, zip_path):
        print("%8.1f KB  %s" % (os.path.getsize(p) / 1024.0, p))
    if missing:
        print("WARNING: not found, omitted from the bundle: " + ", ".join(missing),
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
