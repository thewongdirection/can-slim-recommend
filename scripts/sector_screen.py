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
}

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
          "average dollar volume under $%.0fM - too thin for institutional sponsorship (S)"
          % (cfg["min_dollar_vol"] / 1e6))
    check(mcap, "market_cap", mcap is not None and mcap < cfg["min_market_cap"],
          "market cap under $%.0fM" % (cfg["min_market_cap"] / 1e6))
    check(off_high, "off_high", off_high is not None and off_high < -cfg["max_off_high"],
          "%.0f%% below the 52-week high - no new-high ground, overhead supply (N)" % (off_high or 0))
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


def normalize_sectors(blob):
    """Accept either {"sectors": {name: [rows]}} or {"sectors": [{"sector","rows"}]}."""
    sec = blob.get("sectors") or {}
    if isinstance(sec, dict):
        return [(k, v or []) for k, v in sec.items()]
    return [(s.get("sector") or s.get("name") or "?", s.get("rows") or s.get("results") or [])
            for s in sec]


def run(blob, cfg):
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

    queue = [m for s in sectors for m in s["members"] if m["triage"] == "grade"]
    queue.sort(key=lambda d: (d["rs_vs_bench_pts"] is None, -(d["rs_vs_bench_pts"] or 0)))

    return {
        "asOf": blob.get("asOf"),
        "window": window,
        "benchmark": {"symbol": bench.get("symbol"), "perf_pct": bench_perf},
        "filters": cfg,
        "sector_count": len(sectors),
        "graded_candidates": len(queue),
        "dropped": sum(len(s["members"]) for s in sectors) - len(queue),
        "sectors": sectors,
        "grade_queue": [{"symbol": m["symbol"], "ticker": m["ticker"], "sector": m["sector"] or "",
                         "sector_rank": m["sector_rank"], "rs_vs_bench_pts": m["rs_vs_bench_pts"],
                         "off_high_pct": m["off_high_pct"], "flags": m["flags"]} for m in queue],
    }


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
    L.append("| # | Sector | Median perf | Survived triage |")
    L.append("|---|---|---:|---:|")
    for s in res["sectors"]:
        L.append("| %d | %s | %s | %d/%d |" % (s["rank"], s["sector"], n(s["median_perf_pct"], 1, "%"),
                                               s["survivors"], len(s["members"])))
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
    ap.add_argument("--md", action="store_true", help="print markdown instead of JSON")
    a = ap.parse_args()

    raw = open(a.input).read() if a.input else sys.stdin.read()
    blob = json.loads(raw)
    cfg = {"top": a.top, "fallback": a.fallback, "min_price": a.min_price,
           "min_dollar_vol": a.min_dollar_vol, "min_market_cap": a.min_market_cap,
           "max_off_high": a.max_off_high, "min_rs": a.min_rs}
    res = run(blob, cfg)
    print(to_markdown(res) if a.md else json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
