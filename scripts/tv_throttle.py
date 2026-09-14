#!/usr/bin/env python3
"""
tv_throttle.py - pace TradingView calls so a sweep never earns a block.

WHY A SCRIPT AND NOT A RULE. The TradingView calls are MCP tool invocations, so nothing in this
repo can wrap them. The only throttle that actually works is one the caller has to WAIT on, and a
rule in a markdown file is not a wait - it is a suggestion that gets skipped the moment a sweep is
twenty sectors deep and going well. `--wait` blocks. That is the whole design: pacing you cannot
forget to apply, because the shell does not return until it is safe to call.

WHAT EARNED THIS. Observed on this connector, in order of severity:
  * 10 parallel calls           -> "Rate limit exceeded. Retry after 32s"
  * 4-6 calls per message       -> fine, with a pause between batches
  * a sustained burst           -> HTTP 403 on scanner.tradingview.com for >20 minutes, whose
                                   stated remedy is to re-run client-side from a browser. There is
                                   no server-side way out of that one, so it must not be reached.
The asymmetry is what matters: a few seconds of waiting costs a sweep a minute or two, while one
block costs the entire run and cannot be retried around. Pace for the block you cannot recover
from, not for the throughput you would like.

THE STATE IS SHARED AND PERSISTENT. Call timestamps live in a JSON file, so pacing holds ACROSS
separate shell invocations - which is how an agent calls this, one command at a time. A throttle
that only remembered the current process would reset on every call and enforce nothing.

BLOCKS ESCALATE, SUCCESS DECAYS. Report a 403 with `--blocked` and the cooldown doubles from 5
minutes, capped at 30. Report success with `--ok` and the penalty halves. So a connector having a
bad afternoon is backed off hard, and one that has recovered is not punished for it all session.

BLOCKS ARE PER-ENDPOINT; THE RATE BUDGET IS SHARED. Measured: with scanner.tradingview.com
returning 403, `get_ohlcv` kept answering normally - the block covers the SCANNER family
(run_screener, get_symbol_data, get_quote) and not the bars endpoint. So a scanner block must not
halt bar work that would succeed; `--scope` keeps the two cooldowns apart. The call budget stays
global, because both endpoints draw on the same upstream quota and pacing one while flooding the
other is how the next block gets earned.

Usage, around every TradingView call:
  python scripts/tv_throttle.py --wait          # blocks until safe, then records the call
  <make the TradingView call>
  python scripts/tv_throttle.py --ok            # it worked; relax the penalty
  python scripts/tv_throttle.py --blocked       # 403/rate-limited; escalate the cooldown

  python scripts/tv_throttle.py --status        # budget, penalty, next safe time
  python scripts/tv_throttle.py --reset         # clear state (new session, or after a long idle)

Exit status is 0 for --wait even when it had to sleep - waiting is success. It is 1 only when
--wait would have to sleep past --max-wait, so a caller can decide to stop rather than stall.
Pure standard library.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# Overridable so a test can pace its own state file instead of fighting the real one - and so a
# parallel sweep in a worktree does not share a budget with the session that spawned it.
STATE = os.environ.get("CANSLIM_THROTTLE_STATE") or os.path.join(ROOT, "data", ".tv-throttle.json")

DEFAULTS = {
    # One call every few seconds, never in parallel. The connector tolerates far more in short
    # bursts, which is exactly the trap: the burst succeeds and the block arrives later.
    "min_gap": 4.0,
    # A rolling budget on top of the gap, so a long sweep cannot creep up on the limit by
    # staying just inside the per-call spacing for a hundred calls.
    "window": 60.0,
    "max_in_window": 12,
    # A 403 is not a slow-down, it is a door closing for many minutes. Treat it as such.
    "block_base": 300.0,
    "block_cap": 1800.0,
}


SCOPES = ("scanner", "ohlcv", "other")


def load():
    try:
        with open(STATE, encoding="utf-8") as f:
            s = json.load(f)
    except (OSError, ValueError):
        s = {}
    s.setdefault("calls", [])                 # shared: one upstream quota
    s.setdefault("blocked", {})               # per-scope: {scope: {"n": int, "until": float}}
    for k in SCOPES:
        s["blocked"].setdefault(k, {"n": 0, "until": 0.0})
    return s


def save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, STATE)          # atomic, so a killed run cannot leave half a state file


def prune(s, cfg, now):
    s["calls"] = [t for t in s["calls"] if now - t < cfg["window"] * 2]
    return s


def next_free(s, cfg, now, scope="scanner"):
    """Earliest time a call may be made. Returns (when, why)."""
    b = s["blocked"].get(scope) or {"n": 0, "until": 0.0}
    if b["until"] > now:
        return b["until"], "%s cooling down after %d block(s)" % (scope, b["n"])
    if s["calls"]:
        gap_ready = max(s["calls"]) + cfg["min_gap"]
    else:
        gap_ready = now
    recent = [t for t in s["calls"] if now - t < cfg["window"]]
    win_ready = now
    if len(recent) >= cfg["max_in_window"]:
        # wait until the oldest call in the window ages out
        win_ready = min(recent) + cfg["window"]
    when = max(gap_ready, win_ready, now)
    if when <= now:
        return now, "clear"
    why = "min gap %.1fs" % cfg["min_gap"] if gap_ready >= win_ready else \
          "budget %d/%.0fs is full" % (cfg["max_in_window"], cfg["window"])
    return when, why


def cmd_wait(cfg, max_wait, quiet, scope):
    s = prune(load(), cfg, time.time())
    now = time.time()
    when, why = next_free(s, cfg, now, scope)
    delay = max(0.0, when - now)
    if delay > max_wait:
        print("REFUSED: would need to wait %.0fs (%s), over --max-wait %.0fs. The connector is "
              "blocked, not slow - stop the sweep and say so rather than stalling."
              % (delay, why, max_wait), file=sys.stderr)
        return 1
    if delay > 0:
        if not quiet:
            print("waiting %.1fs (%s)" % (delay, why))
        time.sleep(delay)
    s = load()
    s["calls"].append(time.time())
    save(prune(s, cfg, time.time()))
    if not quiet:
        recent = len([t for t in s["calls"] if time.time() - t < cfg["window"]])
        print("go (%d call(s) in the last %.0fs)" % (recent, cfg["window"]))
    return 0


def cmd_blocked(cfg, scope):
    s = load()
    b = s["blocked"][scope]
    b["n"] += 1
    cool = min(cfg["block_base"] * (2 ** (b["n"] - 1)), cfg["block_cap"])
    b["until"] = time.time() + cool
    save(s)
    print("%s block #%d recorded - holding %s calls for %.0fs (until %s). Other endpoints are "
          "unaffected, so keep working where you can; otherwise stop and tell the user. Do NOT "
          "narrow the sweep to get around a 403 - the call itself is fine."
          % (scope, b["n"], scope, cool, time.strftime("%H:%M:%S", time.localtime(b["until"]))))
    return 0


def cmd_ok(cfg, scope):
    s = load()
    b = s["blocked"][scope]
    if b["n"]:
        b["n"] = max(0, b["n"] - 1)        # decay, so one bad patch is not a session-long tax
        if not b["n"]:
            b["until"] = 0.0
        save(s)
    return 0


def cmd_status(cfg, scope):
    s = prune(load(), cfg, time.time())
    now = time.time()
    recent = [t for t in s["calls"] if now - t < cfg["window"]]
    print("calls in the last %.0fs : %d / %d  (shared across endpoints)"
          % (cfg["window"], len(recent), cfg["max_in_window"]))
    for k in SCOPES:
        b = s["blocked"][k]
        left = max(0.0, b["until"] - now)
        print("  %-8s blocks: %d%s" % (k, b["n"],
              ("  BLOCKED for another %.0fs" % left) if left else ""))
    when, why = next_free(s, cfg, now, scope)
    print("next %s call in    : %.1fs (%s)" % (scope, max(0.0, when - now), why))
    print("state file             : %s" % STATE)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--wait", action="store_true", help="block until a call is safe, then record it")
    g.add_argument("--ok", action="store_true", help="the call worked; decay any block penalty")
    g.add_argument("--blocked", action="store_true", help="403/rate-limited; escalate the cooldown")
    g.add_argument("--status", action="store_true", help="budget, penalty and next safe time")
    g.add_argument("--reset", action="store_true", help="clear state")
    ap.add_argument("--min-gap", type=float, default=DEFAULTS["min_gap"],
                    help="seconds between calls (default %(default)s)")
    ap.add_argument("--window", type=float, default=DEFAULTS["window"])
    ap.add_argument("--max-in-window", type=int, default=DEFAULTS["max_in_window"],
                    help="calls allowed per window (default %(default)s)")
    ap.add_argument("--max-wait", type=float, default=90.0,
                    help="refuse rather than sleep longer than this (default %(default)s)")
    ap.add_argument("--scope", choices=SCOPES, default="scanner",
                    help="which endpoint family: 'scanner' is run_screener/get_symbol_data/"
                         "get_quote, 'ohlcv' is bars. Blocks are tracked per scope because they "
                         "are imposed per endpoint - a scanner 403 leaves bars working (default "
                         "%(default)s)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    cfg = dict(DEFAULTS, min_gap=a.min_gap, window=a.window, max_in_window=a.max_in_window)
    if a.reset:
        try:
            os.remove(STATE)
        except OSError:
            pass
        print("throttle state cleared")
        return 0
    if a.wait:
        return cmd_wait(cfg, a.max_wait, a.quiet, a.scope)
    if a.blocked:
        return cmd_blocked(cfg, a.scope)
    if a.ok:
        return cmd_ok(cfg, a.scope)
    return cmd_status(cfg, a.scope)


if __name__ == "__main__":
    sys.exit(main())
