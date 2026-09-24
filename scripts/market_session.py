#!/usr/bin/env python3
"""
market_session.py - is a US trading session in progress right now, and can S be graded?

WHY THE RUN HAS TO ASK THIS FIRST. `relative_volume_10d_calc` - the field the S letter turns on -
compares today's volume SO FAR against the 10-day average. During the session that is a partial
sum, not a measurement: an hour in, every name in the market reads about 0.1x. Measured on the
same twelve Electronic Technology names 26 hours apart:

    during the session   12/12 read under 0.5x   (AMD 0.21x)
    before the open       1/12 read under 0.5x   (AMD 0.64x - its real full-day figure)

Outside the session the screener serves the last COMPLETE session, which is exactly what S wants.
So the condition is simple, and it is the same one either side of the day: the session must not be
in progress. Before the open and after the close are both fine; only "open" is not.

WHY THIS IS NOT A BLANKET WAIT. Waiting until after the close sounds tidy and is a trap: a run
started at 09:31 would block for nearly seven hours, and an agent session that sits mute for seven
hours has failed the person who asked for stock ideas, whatever it eventually prints. So the
policy is graded by how long the wait actually is:

  * a SHORT wait (default: up to 45 minutes) - just wait. Someone running at 16:05 wants the
    report, and a 25-minute pause costs them nothing they would not have spent re-running.
  * a LONG wait - say so, immediately, with the exact local time to come back, and let the person
    choose. The run must not decide on their behalf to disappear for the afternoon.

Either way the answer is announced UP FRONT rather than discovered in the data, which is the part
that was actually broken: a mid-session run used to look completely normal and quietly grade S on
a partial sum.

TIME SOURCE. The ET clock, because it needs no network and cannot be rate-limited. A holiday
cannot fool it in the dangerous direction - a closed market reads as closed either way, and
"closed" is the state S wants. An EARLY CLOSE (13:00 ET) is the one gap: between 13:00 and 16:00
this reports "open" when the session has actually finished, which costs a needless wait but never
a wrong S grade. Pass `--confirm-open false/true` when a connector has told you otherwise.

Usage:
  python scripts/market_session.py                      # report, human-readable
  python scripts/market_session.py --json               # machine-readable
  python scripts/market_session.py --wait               # block ONLY if the wait is short
  python scripts/market_session.py --wait --max-wait 3600
  python scripts/market_session.py --confirm-open false # a connector says it is closed

Exit status:
  0  a session is NOT in progress - S is gradeable, carry on
  2  a session IS in progress and the wait is too long to sit through - ASK the user
  0  (--wait, short wait) after sleeping until the window opens
Pure standard library.
"""
import argparse
import datetime
import json
import sys
import time

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:                      # pragma: no cover - ancient python
    ET = None

OPEN_H, OPEN_M = 9, 30
CLOSE_H, CLOSE_M = 16, 0
# Minutes after the bell before the closing print is trusted. The last bar settles and late prints
# land in the first few minutes; 30 is the skill's default and is deliberately generous.
SETTLE_MIN = 30
# Wait this long or less and just wait. Longer and the run must ask rather than vanish.
MAX_AUTO_WAIT = 45 * 60


def now_et():
    if ET is None:
        return datetime.datetime.now()
    return datetime.datetime.now(datetime.timezone.utc).astimezone(ET)


def classify(now=None, settle_min=SETTLE_MIN):
    """Return a dict describing the session. `s_gradeable` is the only field most callers need."""
    now = now or now_et()
    o = now.replace(hour=OPEN_H, minute=OPEN_M, second=0, microsecond=0)
    c = now.replace(hour=CLOSE_H, minute=CLOSE_M, second=0, microsecond=0)
    settled = c + datetime.timedelta(minutes=settle_min)

    if now.weekday() >= 5:
        return {"state": "weekend", "s_gradeable": True, "wait_seconds": 0,
                "detail": "weekend - the screener serves Friday's completed session.",
                "now_et": now.strftime("%Y-%m-%d %H:%M %Z"), "resume_at_et": None}
    if now < o:
        return {"state": "premarket", "s_gradeable": True, "wait_seconds": 0,
                "detail": ("before the open - the screener still serves the previous completed "
                           "session, which is what S needs."),
                "now_et": now.strftime("%Y-%m-%d %H:%M %Z"), "resume_at_et": None}
    if now >= settled:
        return {"state": "after-close", "s_gradeable": True, "wait_seconds": 0,
                "detail": "after the close - today's session is complete.",
                "now_et": now.strftime("%Y-%m-%d %H:%M %Z"), "resume_at_et": None}

    # Between the bell and the settle window, or mid-session: a session's data is not final.
    wait = max(0, int((settled - now).total_seconds()))
    mid = now < c
    return {
        "state": "open" if mid else "settling",
        "s_gradeable": False,
        "wait_seconds": wait,
        "detail": (("a session is in progress" if mid else
                    "the session has just closed and the final print is still settling") +
                   " - relative volume is a partial sum, so S cannot be graded on it."),
        "now_et": now.strftime("%Y-%m-%d %H:%M %Z"),
        "resume_at_et": settled.strftime("%Y-%m-%d %H:%M %Z"),
    }


def render(v, auto_max=MAX_AUTO_WAIT):
    L = []
    if v["s_gradeable"]:
        L.append("Market session: %s - S CAN be graded." % v["state"].upper())
        L.append("  " + v["detail"])
        return "\n".join(L)
    mins = v["wait_seconds"] / 60.0
    L.append("Market session: %s - S CANNOT be graded on live data." % v["state"].upper())
    L.append("  " + v["detail"])
    L.append("  Now %s. A complete session is available from %s (%.0f min)."
             % (v["now_et"], v["resume_at_et"], mins))
    if v["wait_seconds"] <= auto_max:
        L.append("  That is a short wait - waiting is the right call; --wait will sit it out.")
    else:
        L.append("  That is too long to sit through. TELL THE USER NOW, with the resume time, and")
        L.append("  let them choose: wait and re-run then, run now with S ungraded (the ceiling")
        L.append("  stays generous and the report says S was not measured), or scope the request.")
        L.append("  Do NOT silently block, and do NOT grade S on a partial session.")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="machine-readable verdict")
    ap.add_argument("--wait", action="store_true",
                    help="sleep until a complete session is available, but ONLY if the wait is "
                         "under --max-wait; otherwise exit 2 so the run can ask the user")
    ap.add_argument("--max-wait", type=float, default=MAX_AUTO_WAIT,
                    help="longest wait to sit through without asking, seconds (default %(default)s)")
    ap.add_argument("--settle-min", type=int, default=SETTLE_MIN,
                    help="minutes after the bell before the close is trusted (default %(default)s)")
    ap.add_argument("--confirm-open", choices=("true", "false"),
                    help="override the clock when a connector has reported the market state - "
                         "the clock cannot see an early close on its own")
    a = ap.parse_args()

    v = classify(settle_min=a.settle_min)
    if a.confirm_open == "false" and not v["s_gradeable"]:
        v = {"state": "after-close", "s_gradeable": True, "wait_seconds": 0,
             "now_et": v["now_et"], "resume_at_et": None,
             "detail": ("a connector reports the market closed (an early close the clock cannot "
                        "see) - today's session is complete.")}
    elif a.confirm_open == "true" and v["s_gradeable"]:
        # Overriding the state is not enough: the wait has to be recomputed too. Carrying the
        # premarket dict's wait_seconds=0 through made `--wait` sleep for nothing, reclassify
        # from the clock, and exit 0 - so the override could not actually hold the run, which is
        # the only thing it exists to do.
        now = now_et()
        settled = now.replace(hour=CLOSE_H, minute=CLOSE_M, second=0, microsecond=0) \
            + datetime.timedelta(minutes=a.settle_min)
        if settled <= now:                      # already past today's close: the next one is tomorrow
            settled += datetime.timedelta(days=1)
        v = dict(v, state="open", s_gradeable=False,
                 wait_seconds=max(0, int((settled - now).total_seconds())),
                 resume_at_et=settled.strftime("%Y-%m-%d %H:%M %Z"),
                 detail="a connector reports the market OPEN - relative volume is a partial sum.")

    if a.wait and not v["s_gradeable"]:
        if v["wait_seconds"] > a.max_wait:
            print(render(v, a.max_wait), file=sys.stderr)
            return 2
        print("waiting %.0f min for the session to complete (until %s)"
              % (v["wait_seconds"] / 60.0, v["resume_at_et"]))
        time.sleep(v["wait_seconds"] + 1)
        after = classify(settle_min=a.settle_min)
        # Keep the override's verdict if the clock still disagrees - a connector that said "open"
        # knows something the clock does not, and silently reverting to the clock here would undo
        # the wait we just sat through.
        v = after if (after["s_gradeable"] or a.confirm_open != "true") else v

    if a.json:
        print(json.dumps(v, indent=2))
    else:
        print(render(v, a.max_wait))
    return 0 if v["s_gradeable"] else 2


if __name__ == "__main__":
    sys.exit(main())
