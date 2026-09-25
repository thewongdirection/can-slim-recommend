#!/usr/bin/env python3
"""
annual_eps.py - grade A (annual earnings growth) from SEC XBRL, because nothing else can.

WHY THIS EXISTS. A asks for "EPS up EACH of 3 years at >=25%", and the connector cannot answer
it: TradingView's `get_financial_history` returns 8 quarters no matter what `period` is passed,
which is two fiscal years - one short. Grading A off TTM growth instead is not a shortcut, it is
a DIFFERENT TEST, and the difference changes answers. Avnet's TTM EPS growth reads +46%, which
looks like a comfortable pass; its FY2025 EPS actually FELL 49%, so the three-year rule fails on
a year TTM cannot see. Without a third year every A in a run has to be capped at partial, and a
letter that is always partial is an admission, not a grade.

SEC's XBRL API publishes audited annual figures for every registrant, for free. This reads them.

WHAT IS SAFE TO FEED THE CEILING. Unlike accumulation.py, this is EVIDENCE, not a proxy - the
figures are the ones in the filing - so a `fail` here is sound to hand `sector_screen.py --known`
and let it prune. The cases that are NOT evidence of failure (no filings, a stale series) grade
`partial` instead, so an absence of data can never eliminate a name.

FOUR THINGS THAT LOOK LIKE THEY WORK AND DO NOT - each cost a wrong answer here:

  1. Keying on the `fy` field. In XBRL `fy`/`fp` describe the FILING's fiscal focus, so a 10-K
     tags its comparative prior-year figures with the SAME `fy` as the current one. Keying on it
     collapses three different years into one bucket; "latest filed wins" then picks an
     arbitrary member. Micron came out with FY2025 EPS of -5.34, which is really its FY2023
     loss, and AMD's years arrived shuffled. Both still looked like plausible series. The period
     END date identifies a fiscal year uniquely, so that is the key.
  2. Requiring fp == "FY". Foreign private issuers filing 20-F/40-F frequently leave `fp` unset,
     which silently dropped every one of them. The 330-400 day duration is what actually
     identifies a fiscal year.
  3. Assuming us-gaap. IFRS filers put the figure under `ifrs-full`, so the us-gaap concept 404s
     and the name reads as "no data" when the number is simply in another namespace.
  4. Falling back on payload SIZE. `companyconcept` can return a healthy-looking body holding
     only quarterly durations (Eton: 44 facts, none annual). A size check waves that through and
     the name vanishes from the graded set. The fallback has to trigger on CONTENT.
  5. Stopping at the first EPS tag that has ANY rows. Filers change tag over time, so one tag
     rarely spans the whole history. Eton reports EarningsPerShareDiluted quarterly only,
     EarningsPerShareBasicAndDiluted annually for 2018-2021, and EarningsPerShareBasic annually
     for 2022-2025 - so "first tag wins" returns either nothing or a series that stops in 2021,
     and the years the test actually needs are in the third tag. The tags are merged in
     preference order instead, each filling only the period ends the better ones left empty.

OUTPUT: the same three-part shape institutional_cache.py and accumulation.py emit -
  meta    what was measured, and every name that could not be graded
  known   {symbol: {"A": grade}} - ready for `sector_screen.py --known`
  detail  {symbol: {...}} - the EPS series, the year-on-year steps and the reason string

Usage:
  python scripts/annual_eps.py symbols.json -o data/a-grades.json
  python scripts/annual_eps.py run/screen.json --contact you@your-domain.com
  python scripts/sector_screen.py sweep.json --known data/a-grades.json --md

`symbols.json` may be a plain list of symbols, a sweep payload, or sector_screen.py's own
output - the shape is detected. SEC requires a contact address; see --contact.
Pure standard library.
"""
import argparse
import datetime as dt
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# Reuse the SEC User-Agent policy rather than restating it: one place decides what a usable
# contact is, and this script inherits the 403-names-the-cause behaviour for free.
from institutional_cache import resolve_contact, UA_TEMPLATE, CONTACT_HELP  # noqa: E402

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
CONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK%s/%s/%s.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK%s.json"

# Tried in PREFERENCE order, and merged rather than raced - see trap 5. The us-gaap entries
# cover domestic filers; the ifrs-full ones cover the 20-F/40-F crowd (ArcelorMittal, TORM,
# Teck, Centerra ...). Diluted first because that is the figure the rubric names; the basic
# tags are last-resort fillers for period ends the diluted tags do not cover (for a loss-making
# company the two are usually identical anyway).
CONCEPTS = (("us-gaap", "EarningsPerShareDiluted"),
            ("us-gaap", "EarningsPerShareBasicAndDiluted"),
            ("us-gaap", "EarningsPerShareBasic"),
            ("ifrs-full", "DilutedEarningsLossPerShare"),
            ("ifrs-full", "BasicEarningsLossPerShare"))

DEFAULTS = {
    "growth": 25.0,      # the rubric's threshold: EPS up at least this much, EACH year
    "roe": 17.0,         # ... AND return on equity at least this. BOTH legs, or it is not a pass
    "years": 3,          # ... across this many year-on-year steps (so 4 annual figures)
    "min_days": 330,     # a fiscal year's duration, wide enough for 52/53-week calendars
    "max_days": 400,
    "stale_days": 700,   # a series ending longer ago than this cannot answer "the last 3 years"
    "pause": 0.15,       # SEC asks for <= 10 requests/second; stay well under
}


def http(url, contact, timeout=60, retries=5):
    """GET with backoff. Returns (bytes, None) or (None, why). Never raises.

    404 is a real answer here - it means "this filer does not report that concept" - so it
    returns immediately rather than burning the retry budget.
    """
    hdrs = {"User-Agent": UA_TEMPLATE % contact}
    wait, why = 2, ""
    for _ in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdrs),
                                        timeout=timeout) as r:
                return r.read(), None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, "HTTP 404"
            why = "HTTP %s" % e.code
            if e.code == 403:
                return None, "HTTP 403 - SEC rejected the User-Agent. " + CONTACT_HELP
        except Exception as e:                      # pragma: no cover - network flake
            why = str(e)
        time.sleep(wait)
        wait *= 2
    return None, why or "unreachable"


def _cached(path, fetch, pause=DEFAULTS["pause"]):
    """Read `path`, or fetch and write it. Returns bytes (possibly b'{}').

    An empty body is cached too, deliberately: "this filer does not report that tag" is a real
    answer and re-asking for it on every run is rude to SEC and slow for us.
    """
    if os.path.exists(path):
        return io.open(path, "rb").read()
    body = fetch() or b"{}"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, "wb").write(body)
    time.sleep(pause)               # SEC asks for <= 10 requests/second; stay well under
    return body


def load_tickers(cache_dir, contact):
    """{TICKER: zero-padded CIK} from SEC's own registrant list."""
    body = _cached(os.path.join(cache_dir, "company_tickers.json"),
                   lambda: http(TICKERS_URL, contact)[0])
    try:
        d = json.loads(body)
    except ValueError:
        return {}
    return {v["ticker"].upper(): "%010d" % int(v["cik_str"]) for v in d.values()}


def parse_annual(body, cfg):
    """{period_end: eps} for every ANNUAL-duration fact in an XBRL payload.

    Keyed by period end, never by `fy` - see trap 1 in the module docstring. Within one end
    date the latest FILED value wins, so a restatement supersedes the original.
    """
    try:
        d = json.loads(body)
    except ValueError:
        return {}
    best = {}
    for unit in (d.get("units") or {}).values():
        for x in unit:
            if not x.get("start"):          # instant facts carry no duration
                continue
            try:
                start = dt.date.fromisoformat(x["start"])
                end = dt.date.fromisoformat(x["end"])
            except (ValueError, TypeError, KeyError):
                continue
            if not (cfg["min_days"] <= (end - start).days <= cfg["max_days"]):
                continue
            key, filed = x["end"], x.get("filed", "")
            if key not in best or filed > best[key][0]:
                best[key] = (filed, x.get("val"))
    return {k: v[1] for k, v in best.items() if v[1] is not None}


def _fill(into, more):
    """Add period ends `into` does not already have. Preference order does the rest."""
    for end, val in more.items():
        into.setdefault(end, val)
    return into


def annual_eps(cik, cache_dir, contact, cfg):
    """{period_end: eps}, from companyconcept and then companyfacts. May be empty.

    Tags are MERGED in preference order rather than raced (trap 5): each one fills only the
    period ends the better-preferred tags left empty, so a filer that changed tag mid-history
    still yields one continuous series.
    """
    got = {}
    for ns, tag in CONCEPTS:
        body = _cached(os.path.join(cache_dir, "concept_%s_%s.json" % (cik, tag)),
                       lambda ns=ns, tag=tag: http(CONCEPT_URL % (cik, ns, tag), contact)[0])
        _fill(got, parse_annual(body, cfg))
        # Enough consecutive years to answer the test, and the newest is recent? Stop paying
        # for calls. Otherwise keep filling from the less-preferred tags.
        keep = consecutive(list(got), cfg)
        if len(keep) >= cfg["years"] + 1 and \
                (dt.date.today() - dt.date.fromisoformat(keep[-1])).days <= cfg["stale_days"]:
            return got
    if got:
        return got
    # Nothing ANNUAL under any tag in the concept feed - trap 4. companyfacts is larger but
    # complete, and is merged across tags for the same reason.
    body = _cached(os.path.join(cache_dir, "facts_%s.json" % cik),
                   lambda: http(FACTS_URL % cik, contact)[0])
    try:
        facts = json.loads(body).get("facts", {})
    except ValueError:
        return {}
    for ns, tag in CONCEPTS:
        hit = (facts.get(ns) or {}).get(tag)
        if hit:
            _fill(got, parse_annual(json.dumps({"units": hit.get("units") or {}}).encode("utf-8"),
                                    cfg))
    return got


def consecutive(ends, cfg):
    """Collapse restatements of one year and keep the run of adjacent fiscal years.

    Two entries less than ~200 days apart are the same fiscal year filed twice under slightly
    different end dates, not two years; keeping both would compare a year against itself.
    """
    keep = []
    for e in sorted(ends):
        if keep and (dt.date.fromisoformat(e) - dt.date.fromisoformat(keep[-1])).days < 200:
            keep[-1] = e
        else:
            keep.append(e)
    return keep


def grade(eps_by_end, cfg, today=None, roe=None):
    """(grade, reason, series, steps) for one name. See the module docstring on what is safe.

    `partial` means "the filings cannot answer this", `fail` means "they answer it, and it is a
    no". Only the second is evidence, and only the second should ever prune a name.

    A HAS TWO LEGS. The rubric is "EPS up each of 3 years at >=25% AND ROE >=17%", and grading the
    EPS leg alone is an over-grade: can-slim-grader, working one ticker at a time, checks both, so
    the same name came out A=pass here and A=partial there. `roe` is the percentage; None means it
    could not be verified, which caps the letter at partial rather than awarding a pass on half
    the test. DELL is the live example - EPS up 42/39/36% but negative book equity, so its ROE is
    not a number and the pass is not earned.
    """
    today = today or dt.date.today()
    need = cfg["years"] + 1
    keep = consecutive(list(eps_by_end), cfg)
    if len(keep) < need:
        return ("partial", "only %d fiscal year(s) on file - cannot test %d years of growth"
                % (len(keep), cfg["years"]), [], [])

    last = keep[-need:]
    vals = [eps_by_end[e] for e in last]
    series = [(e[:4], v) for e, v in zip(last, vals)]

    age = (today - dt.date.fromisoformat(last[-1])).days
    if age > cfg["stale_days"]:
        return ("partial",
                "latest annual EPS on file ends %s (%.1f years stale) - cannot test the last %d "
                "years" % (last[-1], age / 365.0, cfg["years"]), series, [])

    steps = []
    for i in range(1, need):
        prev, cur = vals[i - 1], vals[i]
        steps.append(None if prev is None or cur is None or prev <= 0
                     else (cur - prev) / abs(prev) * 100.0)
    if any(s is None for s in steps):
        # A loss year makes "growth" undefined rather than negative. That is a gap in the
        # evidence, not proof of failure, so it must not prune.
        return ("partial", "a year is a loss or missing, so %d-year growth is not defined"
                % cfg["years"], series, steps)

    shown = ", ".join("%.0f%%" % s for s in steps)
    if all(s >= cfg["growth"] for s in steps):
        if roe is None:
            return ("partial", "EPS up %s over %d years, each >=%.0f%% - but ROE could not be "
                    "verified, and A needs both legs" % (shown, cfg["years"], cfg["growth"]),
                    series, steps)
        if roe < cfg["roe"]:
            return ("partial", "EPS up %s over %d years, each >=%.0f%%, but ROE %.1f%% is under "
                    "%.0f%%" % (shown, cfg["years"], cfg["growth"], roe, cfg["roe"]),
                    series, steps)
        return ("pass", "EPS up %s over %d years, each >=%.0f%%, with ROE %.1f%%"
                % (shown, cfg["years"], cfg["growth"], roe), series, steps)
    if all(s > 0 for s in steps):
        return ("partial", "EPS up each year (%s) but not every year >=%.0f%%"
                % (shown, cfg["growth"]), series, steps)
    return ("fail", "EPS not up each of %d years (%s)" % (cfg["years"], shown), series, steps)


def symbols_from(blob):
    """Pull a symbol list out of whichever shape was handed in.

    A plain list, sector_screen.py's output (grade_queue) and a raw sweep payload are all
    things a caller reasonably has lying around; guessing wrong is a silent empty run.
    """
    if isinstance(blob, list):
        return [s for s in blob if isinstance(s, str)]
    if isinstance(blob, dict):
        if isinstance(blob.get("grade_queue"), list):
            return [r["symbol"] for r in blob["grade_queue"] if r.get("symbol")]
        if isinstance(blob.get("sectors"), dict):
            return [r["symbol"] for rows in blob["sectors"].values() for r in rows
                    if r.get("symbol")]
        if isinstance(blob.get("known"), dict):
            return list(blob["known"])
    return []


def run(symbols, cache_dir, contact, cfg, roes=None):
    roes = roes or {}
    tmap = load_tickers(cache_dir, contact)
    known, detail, ungraded = {}, {}, []
    for sym in symbols:
        tick = sym.split(":")[-1].upper()
        cik = tmap.get(tick)
        eps = annual_eps(cik, cache_dir, contact, cfg) if cik else {}
        if not eps:
            # Record it rather than dropping it. A name missing from the output looks like a
            # name that was never a candidate; "partial, nothing on file" is an honest
            # ungraded letter the ceiling can still reason about.
            why = ("no CIK for this ticker in SEC's registrant list" if not cik
                   else "no annual EPS on file at SEC")
            ungraded.append("%s (%s)" % (sym, why))
            known[sym] = {"A": "partial"}
            detail[sym] = {"grade": "partial", "cik": cik, "series": [], "steps": [],
                           "reason": "A: not graded - " + why, "source": "sec-xbrl"}
            continue
        roe = roes.get(sym, roes.get(tick))
        g, why, series, steps = grade(eps, cfg, roe=roe)
        known[sym] = {"A": g}
        detail[sym] = {"grade": g, "cik": cik, "series": series,
                       "steps": [None if s is None else round(s, 1) for s in steps],
                       "roe": roe, "reason": "A: " + why, "source": "sec-xbrl"}
    return {
        "meta": {
            "source": "sec-xbrl",
            "measures": "audited annual diluted EPS, %d year-on-year steps at >=%.0f%%"
                        % (cfg["years"], cfg["growth"]),
            "is_proxy": False,
            "ceiling_policy": "a fail here is EVIDENCE and may prune; partial means the filings "
                              "could not answer, and never prunes",
            "thresholds": {k: v for k, v in cfg.items()},
            "graded": len(known),
            "ungraded": ungraded,
        },
        "known": known,
        "detail": detail,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", help="symbols JSON (default: stdin)")
    ap.add_argument("--contact", default="",
                    help="contact email for SEC's User-Agent policy - REQUIRED. Defaults to the "
                         "SEC_CONTACT environment variable")
    ap.add_argument("--cache-dir", default="data/sec-eps",
                    help="keep SEC responses here (default %(default)s)")
    ap.add_argument("--growth", type=float, default=DEFAULTS["growth"],
                    help="each year must beat this %% (default %(default)s)")
    ap.add_argument("--years", type=int, default=DEFAULTS["years"],
                    help="year-on-year steps to require (default %(default)s)")
    ap.add_argument("--roe", metavar="FILE",
                    help='{"NASDAQ:AAPL": 147.2} return-on-equity percentages. A needs BOTH legs, '
                         'so without this every A caps at partial rather than passing on the EPS '
                         'leg alone. TradingView get_financials returns_on_equity is the source.')
    ap.add_argument("--stale-days", type=int, default=DEFAULTS["stale_days"],
                    help="a series older than this cannot answer the test (default %(default)s)")
    ap.add_argument("-o", "--out", metavar="FILE", help="write here (default: stdout)")
    ap.add_argument("--known-only", action="store_true",
                    help="print just the --known map, ready for sector_screen.py")
    a = ap.parse_args()

    contact, why = resolve_contact(a.contact)
    if why:
        print("cannot reach SEC: " + why, file=sys.stderr)
        return 2

    raw = io.open(a.input, encoding="utf-8").read() if a.input else sys.stdin.read()
    symbols = symbols_from(json.loads(raw))
    if not symbols:
        print("no symbols found in the input - expected a list, a sweep payload, or "
              "sector_screen.py output", file=sys.stderr)
        return 2

    cfg = dict(DEFAULTS, growth=a.growth, years=a.years, stale_days=a.stale_days)
    roes = json.load(io.open(a.roe, encoding="utf-8")) if a.roe else {}
    res = run(symbols, a.cache_dir, contact, cfg, roes)
    text = json.dumps(res["known"] if a.known_only else res, indent=2)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        io.open(a.out, "w", encoding="utf-8").write(text + "\n")
        from collections import Counter
        tally = Counter(v["A"] for v in res["known"].values())
        print("%s: %d graded (%s)" % (a.out, len(res["known"]),
                                      ", ".join("%s %d" % (k, tally[k])
                                                for k in ("pass", "partial", "fail") if tally[k])),
              file=sys.stderr)
        for u in res["meta"]["ungraded"]:
            print("  ungraded: " + u, file=sys.stderr)
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
