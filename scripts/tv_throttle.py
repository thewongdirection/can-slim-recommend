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
import re
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
    # Adaptive pacing. The endpoint publishes no limit, so the rate is LEARNED: start well under
    # anything plausible, ease up after a run of clean calls, halve on any rate signal. The cap is
    # a hard ceiling regardless of how well things are going - there is no throughput worth the
    # block, and a sweep needs ~20 screener calls, not hundreds.
    "start_rate": 12,
    "min_rate": 4,
    "max_rate": 90,          # deliberately under 100/min
    "raise_after": 10,       # clean calls before easing up
    "raise_by": 2,
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
    budget = effective_budget(s, cfg)
    if len(recent) >= budget:
        # wait until the oldest call in the window ages out
        win_ready = min(recent) + cfg["window"]
    when = max(gap_ready, win_ready, now)
    if when <= now:
        return now, "clear"
    why = "min gap %.1fs" % cfg["min_gap"] if gap_ready >= win_ready else \
          "budget %d/%.0fs is full" % (effective_budget(s, cfg), cfg["window"])
    return when, why


def effective_budget(s, cfg):
    """Calls allowed this window: the LEARNED rate, floored, capped, and never over --max-rate."""
    r = int(s.get("rate", cfg["start_rate"]))
    r = max(cfg["min_rate"], min(r, cfg["max_rate"]))
    return max(1, int(r * cfg["window"] / 60.0))


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
    print("learned rate           : %d/min (cap %d, floor %d)"
          % (int(s.get("rate", cfg["start_rate"])), cfg["max_rate"], cfg["min_rate"]))
    print("calls in the last %.0fs : %d / %d  (shared across endpoints)"
          % (cfg["window"], len(recent), effective_budget(s, cfg)))
    for k in SCOPES:
        b = s["blocked"][k]
        left = max(0.0, b["until"] - now)
        print("  %-8s blocks: %d%s" % (k, b["n"],
              ("  BLOCKED for another %.0fs" % left) if left else ""))
    when, why = next_free(s, cfg, now, scope)
    print("next %s call in    : %.1fs (%s)" % (scope, max(0.0, when - now), why))
    print("state file             : %s" % STATE)
    return 0


# The only authoritative rate signals for scanner.tradingview.com. It is an undocumented internal
# endpoint - TradingView publishes no limit for it anywhere, and the figures that turn up in a
# search ("2 req/sec Basic, 5 req/sec Pro") belong to tradingviewapi.com, an unrelated commercial
# reseller. So the limit is DISCOVERED from what the endpoint says back, not read from a doc.
RETRY_AFTER = re.compile(r"retry\s+after\s+(\d+(?:\.\d+)?)\s*s", re.I)
RATE_WORDS = re.compile(r"rate[\s_-]?limit|too\s+many\s+requests|\b429\b", re.I)
BLOCK_WORDS = re.compile(r"\b403\b|forbidden|blocked", re.I)


def observe(text, cfg, scope="scanner"):
    """Read one TradingView response and adapt the pace to it. Returns (verdict, note).

    This is the "check the limit" half of the throttle, and it is the only honest way to do it:
    ask the endpoint, every call, rather than hard-coding a number nobody publishes. Three
    signals, in descending order of authority:

      * "Retry after 32s"  - TradingView naming its own cooldown. Obeyed exactly; a number from
                             the server always beats a number we guessed.
      * a rate-limit phrase - back off multiplicatively (halve the rate) and cool down.
      * 403 / forbidden     - a block, not a slow-down: escalate per the block ladder.

    Success moves the other way, additively: after a run of clean calls the allowed rate creeps
    up by one. That is AIMD, and it is the standard answer to an undocumented limit - it finds
    the ceiling by approaching it slowly and retreats from it fast, so the cost of being wrong is
    a pause rather than a block.
    """
    s = load()
    t = text or ""
    m = RETRY_AFTER.search(t)
    if m:
        secs = float(m.group(1))
        s["blocked"][scope] = {"n": s["blocked"][scope]["n"] + 1, "until": time.time() + secs}
        s["rate"] = max(cfg["min_rate"], int(s.get("rate", cfg["start_rate"]) / 2))
        save(s)
        return "retry-after", ("TradingView asked for %.0fs - obeying it exactly, and halving the "
                               "rate to %d/min" % (secs, s["rate"]))
    if BLOCK_WORDS.search(t) and not RATE_WORDS.search(t):
        s["rate"] = max(cfg["min_rate"], int(s.get("rate", cfg["start_rate"]) / 2))
        save(s)
        cmd_blocked(cfg, scope)
        return "blocked", "rate halved to %d/min" % s["rate"]
    if RATE_WORDS.search(t):
        s["rate"] = max(cfg["min_rate"], int(s.get("rate", cfg["start_rate"]) / 2))
        s["blocked"][scope]["until"] = max(s["blocked"][scope]["until"], time.time() + 60)
        save(s)
        return "rate-limited", "rate halved to %d/min, holding 60s" % s["rate"]

    # clean response: additive increase, but only after a run of them, and never past the cap
    s["streak"] = s.get("streak", 0) + 1
    old = s.get("rate", cfg["start_rate"])
    if s["streak"] >= cfg["raise_after"] and old < cfg["max_rate"]:
        s["rate"] = min(cfg["max_rate"], old + cfg["raise_by"])
        s["streak"] = 0
        save(s)
        return "ok", "%d clean calls - easing the rate up to %d/min" % (cfg["raise_after"], s["rate"])
    save(s)
    return "ok", ""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--wait", action="store_true", help="block until a call is safe, then record it")
    g.add_argument("--ok", action="store_true", help="the call worked; decay any block penalty")
    g.add_argument("--blocked", action="store_true", help="403/rate-limited; escalate the cooldown")
    g.add_argument("--status", action="store_true", help="budget, penalty and next safe time")
    g.add_argument("--reset", action="store_true", help="clear state")
    g.add_argument("--observe", metavar="TEXT",
                   help="feed one TradingView response (or '-' for stdin) and adapt the pace to "
                        "it. This is the 'check the limit' step: scanner.tradingview.com "
                        "publishes no rate limit, so it is learned from what the endpoint says "
                        "back - 'Retry after Ns' is obeyed exactly, a rate-limit phrase halves "
                        "the rate, a 403 escalates the block ladder, and a run of clean calls "
                        "eases the rate up.")
    ap.add_argument("--min-gap", type=float, default=DEFAULTS["min_gap"],
                    help="seconds between calls (default %(default)s)")
    ap.add_argument("--window", type=float, default=DEFAULTS["window"])
    ap.add_argument("--max-in-window", type=int, default=DEFAULTS["max_in_window"],
                    help="calls allowed per window (default %(default)s)")
    ap.add_argument("--max-rate", type=int, default=DEFAULTS["max_rate"],
                    help="hard ceiling on calls per minute, whatever the learned rate says "
                         "(default %(default)s)")
    ap.add_argument("--max-wait", type=float, default=90.0,
                    help="refuse rather than sleep longer than this (default %(default)s)")
    ap.add_argument("--scope", choices=SCOPES, default="scanner",
                    help="which endpoint family: 'scanner' is run_screener/get_symbol_data/"
                         "get_quote, 'ohlcv' is bars. Blocks are tracked per scope because they "
                         "are imposed per endpoint - a scanner 403 leaves bars working (default "
                         "%(default)s)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    cfg = dict(DEFAULTS, min_gap=a.min_gap, window=a.window, max_in_window=a.max_in_window,
               max_rate=a.max_rate)
    if a.reset:
        try:
            os.remove(STATE)
        except OSError:
            pass
        print("throttle state cleared")
        return 0
    if a.observe is not None:
        text = sys.stdin.read() if a.observe == "-" else a.observe
        verdict, note = observe(text, cfg, a.scope)
        print("%s%s" % (verdict, (": " + note) if note else ""))
        return 0 if verdict == "ok" else 2
    if a.wait:
        return cmd_wait(cfg, a.max_wait, a.quiet, a.scope)
    if a.blocked:
        return cmd_blocked(cfg, a.scope)
    if a.ok:
        return cmd_ok(cfg, a.scope)
    return cmd_status(cfg, a.scope)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # `tv_throttle.py --status | head -2` is an ordinary thing to type, and a traceback is a
        # poor reward for it. Close stderr too, or the interpreter prints the same complaint again
        # while shutting down.
        try:
            os.close(sys.stderr.fileno())
        except OSError:
            pass
        sys.exit(0)
