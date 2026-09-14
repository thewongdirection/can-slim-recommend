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
