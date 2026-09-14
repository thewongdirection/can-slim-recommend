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
