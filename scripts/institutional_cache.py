#!/usr/bin/env python3
"""
institutional_cache.py - grade I (institutional sponsorship) from SEC Form 13F, cached quarterly.

THE PROBLEM THIS SOLVES. 13F is filed by MANAGER, not by issuer. EDGAR indexes a filing under the
CIK of the fund that filed it, so "who owns NVDA" is not an endpoint anywhere - it is an
aggregation across every filer in the quarter. That is the entire reason ownership data is sold
rather than looked up, and the reason this skill graded I=partial for every name in every run.

THE SHAPE THAT MAKES IT CHEAP. 13F updates four times a year, so paying the aggregation cost once
per quarter and caching the result turns a per-run impossibility into a file read. Run this after
each 13F deadline (45 days past quarter-end: mid-Feb, mid-May, mid-Aug, mid-Nov); the sweep then
reads the cache and spends no network at all on I.

WHAT IT COMPUTES. For every issuer, in two consecutive quarters: the number of distinct managers
holding it, and the total shares they hold. The quarter-over-quarter change in BOTH is what the
rubric actually asks for - "ownership rising over recent quarters", not merely "institutionally
owned". The level alone is free everywhere; this trend is the part that is hard, and it is the
part that grades the letter.

THE CUSIP PROBLEM, STATED HONESTLY. INFOTABLE identifies holdings by CUSIP and issuer NAME - not
by ticker - and there is no free authoritative CUSIP-to-ticker map. So this script resolves
tickers two ways, in order: an explicit map you supply (--cusip-map), then normalised issuer-name
matching against the candidate list from the sweep (--universe). Names that resolve neither way
are reported in `unresolved` rather than silently dropped, because a name missing from the cache
must fall through to the proxy, not be graded on absent data.

FAILS OPEN, ALWAYS. No network, a moved URL, a corrupt zip - none of these stop a run. The script
says what it could not do and exits 0 with an empty cache, and `--fallback` merges in
accumulation.py's volume proxy for every ticker 13F could not answer. Provenance is recorded per
ticker in `detail[t]["source"]`, so the report can say which evidence graded each letter.

Usage:
  # once per quarter, after the 13F deadline
  python institutional_cache.py --quarter 2026Q2 --prior 2026Q1 -o data/i-cache.json
  # resolve tickers using the sweep's own candidate list, and fill gaps with the volume proxy
  python institutional_cache.py --quarter 2026Q2 --prior 2026Q1 \\
      --universe sweep.json --fallback accum.json -o data/i-cache.json
  # then, per run:
  python sector_screen.py sweep.json --known data/i-cache.json --md

OUTPUT: the same three-part shape accumulation.py emits - meta / known / detail - so either can
feed `sector_screen.py --known`.
Pure standard library.
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
import zipfile

DEFAULTS = {
    "thin_holders": 20,     # fewer managers than this is a neglected name, not a sponsored one
    "rising_pct": 2.0,      # shares held must move more than this to count as a real change
    "over_owned_pct": 95.0, # institutions holding more than this of the float leaves no new buyer
}

# The bulk files have lived under two prefixes over the years. Both are tried, in order, and the
# one that answers is recorded in meta - guessing a single URL and reporting "unreachable" when
# it 404s would blame the network for a moved file.
URL_PATTERNS = [
    "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/{q}_form13f.zip",
    "https://www.sec.gov/files/dera/data/form-13f-data-sets/{q}_form13f.zip",
]

# SEC requires a declared User-Agent with contact details and returns 403 without one. This is
# their stated access policy, not an obstacle to route around.
UA = "can-slim-recommend/1.0 (contact: set --contact)"

STOP = re.compile(r"\b(inc|corp|corporation|co|company|ltd|limited|plc|holdings?|group|the|"
                  r"cl|class|a|b|com|common|stock|shs|sa|nv|ag|lp|llc|trust|reit)\b")


def norm_name(s):
    """Normalise an issuer name for matching: case, punctuation and the corporate-suffix noise
    that differs between EDGAR ('NVIDIA CORPORATION') and a screener ('NVIDIA Corp')."""
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = STOP.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def fetch(quarter, contact, timeout, cache_dir=None):
    """Download one quarter's zip. Returns (bytes, url) or (None, why). Never raises."""
    q = quarter.lower()
    if cache_dir:
        local = os.path.join(cache_dir, "%s_form13f.zip" % q)
        if os.path.exists(local) and os.path.getsize(local) > 1000:
            return open(local, "rb").read(), "file://" + local
    why = []
    for pat in URL_PATTERNS:
        url = pat.format(q=q)
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "can-slim-recommend/1.0 (contact: %s)" % contact if contact else UA,
                "Accept-Encoding": "gzip, deflate"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if len(data) < 1000:
                why.append("%s returned %d bytes" % (url, len(data)))
                continue
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
                open(os.path.join(cache_dir, "%s_form13f.zip" % q), "wb").write(data)
            return data, url
        except urllib.error.HTTPError as e:
            why.append("%s -> HTTP %s" % (url, e.code))
        except Exception as e:                       # network down, DNS, TLS, egress policy
            why.append("%s -> %s" % (url, e))
    return None, "; ".join(why)


def _member(z, want):
    """Find a table inside the zip regardless of casing or an added directory level."""
    for n in z.namelist():
        base = n.rsplit("/", 1)[-1].lower()
        if base in (want + ".tsv", want + ".txt"):
            return n
    return None


def aggregate(zbytes):
    """Aggregate one quarter's holdings by CUSIP. Returns ({cusip: {...}}, note).

    Streamed row by row on purpose: INFOTABLE runs to millions of rows per quarter and reading it
    into memory is the difference between this working on a laptop and not. Only the per-CUSIP
    totals are retained.

    Two filters matter for correctness. SSHPRNAMTTYPE must be 'SH' - a 'PRN' row is a principal
    amount of debt, not a share count, and summing the two together produces nonsense. And a row
    with PUTCALL set is an option position, not ownership of the stock; counting it would credit
    a fund that is short the name via puts as a sponsor.
    """
    try:
        z = zipfile.ZipFile(io.BytesIO(zbytes))
    except Exception as e:
        return None, "not a readable zip (%s)" % e
    cover, info = _member(z, "coverpage"), _member(z, "infotable")
    if not info:
        return None, "no INFOTABLE in the archive (members: %s)" % ", ".join(z.namelist()[:8])

    # accession -> filer CIK, so "holders" counts distinct MANAGERS rather than distinct filings
    acc_cik = {}
    if cover:
        with z.open(cover) as f:
            for row in csv.DictReader(io.TextIOWrapper(f, "utf-8", errors="replace"),
                                      delimiter="\t"):
                a = (row.get("ACCESSION_NUMBER") or "").strip()
                c = (row.get("CIK") or "").strip()
                if a:
                    acc_cik[a] = c or a

    out = {}
    rows = kept = 0
    with z.open(info) as f:
        for row in csv.DictReader(io.TextIOWrapper(f, "utf-8", errors="replace"), delimiter="\t"):
            rows += 1
            if (row.get("PUTCALL") or "").strip():
                continue                                  # an option, not ownership
            if (row.get("SSHPRNAMTTYPE") or "SH").strip().upper() != "SH":
                continue                                  # principal amount, not shares
            cusip = (row.get("CUSIP") or "").strip().upper()
            if not cusip:
                continue
            try:
                sh = float(row.get("SSHPRNAMT") or 0)
            except ValueError:
                continue
            acc = (row.get("ACCESSION_NUMBER") or "").strip()
            e = out.setdefault(cusip, {"name": (row.get("NAMEOFISSUER") or "").strip(),
                                       "shares": 0.0, "value": 0.0, "filers": set()})
            e["shares"] += sh
            try:
                e["value"] += float(row.get("VALUE") or 0)
            except ValueError:
                pass
            e["filers"].add(acc_cik.get(acc, acc))
            kept += 1
    for e in out.values():
        e["holders"] = len(e["filers"])
        del e["filers"]
    return out, "%d rows read, %d share positions kept, %d issuers" % (rows, kept, len(out))


def resolve_tickers(agg, cusip_map, universe):
    """cusip -> ticker, via an explicit map first and normalised issuer names second.

    Ambiguity is dropped rather than guessed: if two issuers normalise to the same name, neither
    is matched. A wrong ticker here attaches one company's sponsorship to another's scorecard,
    which is far worse than leaving the letter to the proxy.
    """
    by_ticker, unresolved = {}, []
    name_to_tick = {}
    dupes = set()
    for tick, comp in (universe or {}).items():
        k = norm_name(comp)
        if not k:
            continue
        if k in name_to_tick and name_to_tick[k] != tick:
            dupes.add(k)
        name_to_tick[k] = tick
    for k in dupes:
        name_to_tick.pop(k, None)

    for cusip, e in agg.items():
        tick = (cusip_map or {}).get(cusip) or name_to_tick.get(norm_name(e["name"]))
        if not tick:
            unresolved.append({"cusip": cusip, "name": e["name"], "holders": e["holders"]})
            continue
        # Two CUSIPs (share classes) can map to one ticker - sum them.
        cur = by_ticker.setdefault(tick, {"name": e["name"], "shares": 0.0, "holders": 0,
                                          "value": 0.0, "cusips": []})
        cur["shares"] += e["shares"]
        cur["value"] += e["value"]
        cur["holders"] = max(cur["holders"], e["holders"])
        cur["cusips"].append(cusip)
    unresolved.sort(key=lambda d: -d["holders"])
    return by_ticker, unresolved


def grade(now, prior, cfg, float_shares=None):
    """Grade I from the two quarters. Returns (grade, reason, metrics).

    Follows the rubric in references/canslim-methodology.md: PASS is ownership RISING with a real
    base of holders and room left for new buyers; PARTIAL is adequate ownership whose trend is
    flat or unverifiable; FAIL is thin, neglected, or declining.
    """
    h, sh = now["holders"], now["shares"]
    m = {"holders": h, "shares": sh, "holders_prior": None, "shares_prior": None,
         "holders_delta": None, "shares_delta_pct": None, "pct_of_float": None}

    if float_shares:
        try:
            m["pct_of_float"] = round(100.0 * sh / float(float_shares), 1)
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    if h < cfg["thin_holders"]:
        return ("fail", "I: only %d institutional holders - thin and neglected, below the "
                        "sponsorship test" % h, m)

    if not prior:
        return ("partial", "I: %d institutional holders (%.1fM shares), but no prior quarter to "
                           "compare - the trend is unverified" % (h, sh / 1e6), m)

    m["holders_prior"], m["shares_prior"] = prior["holders"], prior["shares"]
    m["holders_delta"] = h - prior["holders"]
    if prior["shares"]:
        m["shares_delta_pct"] = round(100.0 * (sh - prior["shares"]) / prior["shares"], 1)

    dh, ds = m["holders_delta"], (m["shares_delta_pct"] or 0.0)
    over = m["pct_of_float"] is not None and m["pct_of_float"] >= cfg["over_owned_pct"]

    if dh > 0 and ds > cfg["rising_pct"]:
        if over:
            return ("partial", "I: sponsorship rising (%+d holders to %d, shares %+.1f%%) but "
                               "institutions already hold %.1f%% of the float - little room for "
                               "new sponsorship" % (dh, h, ds, m["pct_of_float"]), m)
        return ("pass", "I: %d institutional holders, %+d on the quarter, shares held %+.1f%% - "
                        "sponsorship is increasing (SEC 13F)" % (h, dh, ds), m)
    if dh < 0 and ds < -cfg["rising_pct"]:
        return ("fail", "I: sponsorship declining - %d holders (%+d) and shares held %+.1f%% "
                        "(SEC 13F)" % (h, dh, ds), m)
    return ("partial", "I: %d institutional holders (%+d, shares %+.1f%%) - adequate ownership "
                       "but the trend is flat (SEC 13F)" % (h, dh, ds), m)


def build(args, cfg):
    meta = {"source": "sec-13f", "is_proxy": False, "quarter": args.quarter, "prior": args.prior,
            "thresholds": dict(cfg), "urls": {}, "notes": [], "ok": False}
    known, detail = {}, {}

    universe, cusip_map, floats = {}, {}, {}
    if args.universe:
        blob = json.load(open(args.universe, encoding="utf-8"))
        for _, rows in (blob.get("sectors") or {}).items() if isinstance(
                blob.get("sectors"), dict) else []:
            for r in rows or []:
                t = (r.get("symbol") or "").split(":")[-1]
                if t:
                    universe[t] = r.get("description") or r.get("name") or ""
                    if r.get("float_shares_outstanding_current"):
                        floats[t] = r["float_shares_outstanding_current"]
        meta["notes"].append("universe: %d tickers from %s" % (len(universe), args.universe))
    if args.cusip_map:
        cusip_map = {k.strip().upper(): v for k, v in
                     json.load(open(args.cusip_map, encoding="utf-8")).items()}
        meta["notes"].append("cusip map: %d entries" % len(cusip_map))

    aggs = {}
    for label, q in (("quarter", args.quarter), ("prior", args.prior)):
        if not q:
            continue
        data, where = fetch(q, args.contact, args.timeout, args.cache_dir)
        meta["urls"][q] = where
        if data is None:
            meta["notes"].append("%s %s could not be fetched: %s" % (label, q, where))
            continue
        agg, note = aggregate(data)
        meta["notes"].append("%s %s: %s" % (label, q, note))
        if agg:
            aggs[label] = agg

    if "quarter" not in aggs:
        meta["notes"].append("no 13F data for the current quarter - every ticker falls through "
                             "to the fallback, if one was given")
        return meta, known, detail, []

    now_t, unresolved = resolve_tickers(aggs["quarter"], cusip_map, universe)
    prior_t = resolve_tickers(aggs["prior"], cusip_map, universe)[0] if "prior" in aggs else {}
    meta["ok"] = True
    meta["notes"].append("resolved %d tickers; %d issuers unresolved" % (len(now_t), len(unresolved)))

    for tick, e in now_t.items():
        g, why, m = grade(e, prior_t.get(tick), cfg, floats.get(tick))
        known[tick] = {"I": g}
        detail[tick] = dict(m, grade=g, ceiling_cap=g, reason=why, source="sec-13f",
                            issuer=e["name"], cusips=e["cusips"])
    return meta, known, detail, unresolved


def merge_fallback(meta, known, detail, path):
    """Fill every ticker 13F could not answer from accumulation.py's volume proxy.

    Only gaps are filled - a real 13F grade is never overwritten by a proxy. Each entry keeps its
    own `source`, so the report can say which evidence graded which name instead of implying the
    whole column came from one place.
    """
    try:
        fb = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        meta["notes"].append("fallback %s could not be read: %s" % (path, e))
        return 0
    n = 0
    for tick, v in (fb.get("known") or {}).items():
        if tick in known:
            continue
        known[tick] = v
        d = (fb.get("detail") or {}).get(tick) or {}
        detail[tick] = dict(d, source=(fb.get("meta") or {}).get("source", "accumulation-proxy"))
        n += 1
    meta["notes"].append("fallback filled %d ticker(s) 13F did not cover" % n)
    meta["fallback"] = {"path": path, "source": (fb.get("meta") or {}).get("source"), "filled": n}
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quarter", required=True, help="e.g. 2026Q2 (the latest 13F deadline past)")
    ap.add_argument("--prior", help="the quarter before it, e.g. 2026Q1 - needed for the TREND")
    ap.add_argument("--universe", metavar="FILE",
                    help="the sweep JSON, used to resolve CUSIPs by issuer name")
    ap.add_argument("--cusip-map", metavar="FILE", help='{"67066G104": "NVDA", ...}')
    ap.add_argument("--fallback", metavar="FILE",
                    help="accumulation.py output, used for tickers 13F could not answer")
    ap.add_argument("--cache-dir", default="data/13f", help="keep the zips (default %(default)s)")
    ap.add_argument("--contact", default="", help="contact address for SEC's User-Agent policy")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--thin-holders", type=int, default=DEFAULTS["thin_holders"])
    ap.add_argument("-o", "--out", metavar="FILE", help="write here (default: stdout)")
    ap.add_argument("--known-only", action="store_true", help="print just the --known map")
    a = ap.parse_args()

    cfg = dict(DEFAULTS, thin_holders=a.thin_holders)
    meta, known, detail, unresolved = build(a, cfg)
    if a.fallback:
        merge_fallback(meta, known, detail, a.fallback)
    meta["graded"] = len(known)

    res = {"meta": meta, "known": known, "detail": detail,
           "unresolved": unresolved[:200]}
    text = json.dumps(known if a.known_only else res, indent=2)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        open(a.out, "w", encoding="utf-8").write(text + "\n")
        print("%s: %d ticker(s) graded%s" % (a.out, len(known),
              "" if meta["ok"] else " - 13F UNAVAILABLE, see meta.notes"), file=sys.stderr)
        for nte in meta["notes"]:
            print("  " + nte, file=sys.stderr)
    else:
        print(text)
    return 0        # fails open: a run continues on the proxy, or on I=partial


if __name__ == "__main__":
    sys.exit(main())
