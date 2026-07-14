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
