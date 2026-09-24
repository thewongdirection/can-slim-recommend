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

WHAT REAL DATA FORCED, AND WHY FIXTURES COULD NOT HAVE CAUGHT IT. Four things about the bulk
files are invisible until you open one, and each silently corrupts the holder count:

  * COVERPAGE HAS NO CIK. The filing manager's CIK lives in SUBMISSION.tsv. Reading it off
    COVERPAGE yields nothing, and a holder count keyed on the accession number instead counts
    FILINGS, not managers - inflating every name that filed more than once.
  * ONE FILE IS NOT ONE QUARTER. The Mar-May 2026 file holds 10,776 filings for 31-MAR-2026 and
    985 late or amended ones reaching back to 2024. Aggregating the whole file blends quarters,
    so holdings must be filtered on PERIODOFREPORT.
  * 13F-NT IS A NOTICE, NOT A REPORT. 2,001 of 11,761 submissions in that file report no
    holdings at all; counting them as sponsors credits managers who disclosed nothing.
  * AMENDMENTS REPLACE OR ADD. AMENDMENTTYPE=RESTATEMENT supersedes the original filing, so
    counting both double-counts that manager's position; NEW HOLDINGS adds to it. 108 accessions
    in that one file are superseded restatements.

The names are also not what the URL pattern suggests: from 2024 SEC switched from `2023q4_form13f.zip`
to a filing-RECEIPT window, `01mar2026-31may2026_form13f.zip` - and that window is not the holdings
quarter, it is when the filings arrived. Rather than encode either scheme, this script READS SEC's
index page and picks the file whose window contains the period's due date, which keeps working the
next time they rename things.

VALIDATION. Against 01mar2026-31may2026, period 31-MAR-2026: NVDA 5,775 holders / 16.10B shares and
AAPL 6,012 / 9.36B - about 66% and 63% of shares outstanding, matching published institutional
ownership for both. A holder count that is wrong tends to be wrong by a lot, so this is worth
re-checking whenever the parsing changes.

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
import gzip
import io
import json
import os
import re
import sys
import urllib.error
import time
import urllib.request
import zipfile

DEFAULTS = {
    "thin_holders": 20,     # fewer managers than this is a neglected name, not a sponsored one
    "rising_pct": 2.0,      # shares held must move more than this to count as a real change
    "over_owned_pct": 95.0, # institutions holding more than this of the float leaves no new buyer
}

INDEX_URL = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"

# SEC requires a declared User-Agent carrying a real contact address, and returns 403 without one.
# This is their stated access policy, not an obstacle to route around.
#
# THE TRAP THIS CODE EXISTS TO CLOSE. The obvious shape - a constant UA with a placeholder where
# the address goes - looks configured and is not: SEC 403s it, every dataset read fails, and the
# run reports "13F UNAVAILABLE" with an HTTP code. Nothing in that output says the cause was the
# header this script sent, so the failure reads as "SEC is blocked here" and the next step taken
# is usually to go argue with a firewall. Measured against SEC, with the product token held fixed:
#
#     (contact: set --contact)                     403   <- the old default
#     <no address at all>                          403
#     (contact: you@your-domain.com)               200
#     (contact: x@users.noreply.github.com)        403   <- domain blocklist, not parseability
#
# So an address is required, and a throwaway one is not a loophole either: SEC blocklists the
# common no-reply domains, and the fourth line is why this file ships NO built-in default. Any
# address hardcoded here would either be someone else's inbox or a domain SEC already refuses.
# The contact has to come from whoever is running it, so the rule is: refuse to send a request
# we can already tell will be rejected, and say exactly what to set.
UA_TEMPLATE = "can-slim-recommend/1.0 (contact: %s)"

# Deliberately permissive - this is a "did you paste an address or a placeholder" check, not an
# RFC 5322 validator. It exists to catch the bad value locally, before it becomes a 403.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")

CONTACT_HELP = (
    "SEC requires a contact address in the User-Agent. Pass --contact you@your-domain.com, "
    "or set the SEC_CONTACT environment variable once. Use an address you actually read - "
    "SEC rejects throwaway no-reply domains, and it is how they reach you about your traffic.")


def resolve_contact(cli_contact):
    """The contact to send, or (None, why) if there is not a usable one.

    Checked BEFORE any request goes out. A placeholder that reaches SEC costs a 403 and an error
    message pointing at the wrong layer; caught here it costs one line that names the fix.
    """
    c = (cli_contact or os.environ.get("SEC_CONTACT") or "").strip()
    if not c:
        return None, "no SEC contact address configured. " + CONTACT_HELP
    if not EMAIL_RE.match(c):
        return None, "SEC contact %r is not an email address. %s" % (c, CONTACT_HELP)
    return c, None

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
MONTH_NAME = {v: k for k, v in MONTHS.items()}
QUARTER_END = {1: "31-MAR", 2: "30-JUN", 3: "30-SEP", 4: "31-DEC"}

STOP = re.compile(r"\b(inc|corp|corporation|co|company|ltd|limited|plc|holdings?|group|the|"
                  r"cl|class|a|b|com|common|stock|shs|sa|nv|ag|lp|llc|trust|reit)\b")


def norm_name(s):
    """Normalise an issuer name for matching: case, punctuation and the corporate-suffix noise
    that differs between EDGAR ('NVIDIA CORPORATION') and a screener ('NVIDIA Corp')."""
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = STOP.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def maybe_gunzip(body):
    """Undo the gzip we asked for. urllib hands back the RAW encoded bytes.

    curl decompresses transparently, which is exactly why this is easy to miss: the same URL that
    works on the command line comes back as binary here. Left compressed, SEC's index page yields
    no regex matches and the failure reads as "the page has no links" rather than as an encoding
    bug. Detected by magic number rather than the Content-Encoding header, because a proxy can
    re-encode a response without updating it.
    """
    return gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body


def http(url, contact, timeout, retries=6):
    """GET with backoff on 429. Returns (bytes, None) or (None, why). Never raises.

    The retry is not optional politeness. SEC throttles by source IP, and an agent sandbox reaches
    them through a SHARED egress address, so the first request of a session routinely comes back
    429 "Request Rate Threshold Exceeded" through no fault of this caller. Measured here: two 429s
    then success on the third attempt. Treating the first 429 as failure would make this script
    look broken most of the time it is run.
    """
    ok, why_contact = resolve_contact(contact)
    if not ok:
        return None, why_contact          # never spend a request we know SEC will refuse
    hdrs = {"User-Agent": UA_TEMPLATE % ok,
            "Accept-Encoding": "gzip, deflate"}
    wait, why = 5, ""
    for _ in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdrs),
                                        timeout=timeout) as r:
                body = r.read()
            return maybe_gunzip(body), None
        except urllib.error.HTTPError as e:
            why = "HTTP %s" % e.code
            if e.code == 403:
                # Almost always the User-Agent, not the network. Say so, or this gets debugged
                # as an egress problem.
                why = ("HTTP 403 - SEC rejected the User-Agent. " + CONTACT_HELP +
                       " (sent: %s)" % (UA_TEMPLATE % ok))
            if e.code != 429:
                return None, why
            time.sleep(wait)
            wait *= 2
        except Exception as e:                       # network down, DNS, TLS, egress policy
            return None, str(e)
    return None, why + " after %d attempts (SEC rate limit did not clear)" % retries


def parse_dataset_name(name):
    """Both naming schemes SEC has used, as (start, end) ISO strings, or None.

    Up to 2023q4 the files were named for the holdings quarter; from 2024 they are named for the
    window in which the filings were RECEIVED ('01mar2026-31may2026'), which is a different thing
    and lags the quarter it mostly contains. Parsing both lets a cache be rebuilt for an old
    quarter without a special case.
    """
    m = re.match(r"^(\d{2})([a-z]{3})(\d{4})-(\d{2})([a-z]{3})(\d{4})_form13f\.zip$", name)
    if m:
        d1, m1, y1, d2, m2, y2 = m.groups()
        if m1 in MONTHS and m2 in MONTHS:
            return ("%s-%02d-%s" % (y1, MONTHS[m1], d1), "%s-%02d-%s" % (y2, MONTHS[m2], d2))
    m = re.match(r"^(\d{4})q([1-4])_form13f\.zip$", name)
    if m:
        y, q = m.group(1), int(m.group(2))
        first = {1: "01-01", 2: "04-01", 3: "07-01", 4: "10-01"}[q]
        last = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}[q]
        return ("%s-%s" % (y, first), "%s-%s" % (y, last))
    return None


def list_datasets(contact, timeout):
    """Read SEC's own index page for the available bulk files. Returns (list, why).

    Discovering beats constructing. The URL pattern this script originally guessed
    ('2026q2_form13f.zip') 404s for every quarter after 2023 because SEC renamed the scheme - and
    a guessed URL reports a rename as a dead network. The page is the authority on what exists,
    and parsing it survives the next rename too.
    """
    body, why = http(INDEX_URL, contact, timeout)
    if body is None:
        return [], "could not read %s (%s)" % (INDEX_URL, why)
    out = []
    for href in re.findall(r'href="([^"]*_form13f\.zip)"', body.decode("utf-8", "replace")):
        name = href.rsplit("/", 1)[-1]
        span = parse_dataset_name(name)
        if not span:
            continue
        out.append({"name": name, "start": span[0], "end": span[1],
                    "url": href if href.startswith("http") else "https://www.sec.gov" + href})
    out.sort(key=lambda d: d["end"], reverse=True)
    return out, ("no *_form13f.zip links on the index page" if not out else None)


def period_end(quarter):
    """'2026Q1' or '2026-03-31' -> the EDGAR period string '31-MAR-2026'."""
    q = str(quarter).strip().upper()
    m = re.match(r"^(\d{4})-?Q([1-4])$", q)
    if m:
        return "%s-%s" % (QUARTER_END[int(m.group(2))], m.group(1))
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", q)
    if m:
        y, mo, d = m.groups()
        return "%s-%s-%s" % (d, MONTH_NAME[int(mo)].upper(), y)
    raise ValueError("cannot read %r as a quarter (want 2026Q1 or 2026-03-31)" % quarter)


def prior_quarter(quarter):
    """The quarter before it, in the same '2026Q1' form."""
    m = re.match(r"^(\d{4})-?Q([1-4])$", str(quarter).strip().upper())
    if not m:
        return None
    y, q = int(m.group(1)), int(m.group(2))
    return "%dQ%d" % (y - 1, 4) if q == 1 else "%dQ%d" % (y, q - 1)


def _iso_period(period):
    d, mon, y = period.split("-")
    return "%s-%02d-%s" % (y, MONTHS[mon.lower()], d)


def dataset_for_period(datasets, period):
    """Pick the file whose receipt window contains the period's filing deadline.

    A quarter's 13Fs arrive in the window AFTER it ends, so 31-MAR-2026 holdings live in the
    Mar-May 2026 file. Choosing by name would pick the wrong file under the post-2024 scheme;
    choosing by deadline works under both.
    """
    y, m, d = (int(x) for x in _iso_period(period).split("-"))
    m += 1                                  # ~45 days after quarter end, i.e. the due window
    if m > 12:
        m, y = m - 12, y + 1
    due = "%04d-%02d-%02d" % (y, m, min(d, 28))
    for ds in datasets:
        if ds["start"] <= due <= ds["end"]:
            return ds
    return None


def _member(z, want):
    """Find a table inside the zip regardless of casing or an added directory level."""
    for n in z.namelist():
        base = n.rsplit("/", 1)[-1].lower()
        if base in (want + ".tsv", want + ".txt"):
            return n
    return None


def _table(z, name):
    m = _member(z, name)
    if not m:
        return []
    with z.open(m) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, "utf-8", errors="replace"), delimiter="\t"))


def select_filings(z, period):
    """Which accessions count as THE holdings of each manager for `period`.

    Four real-data rules, each of which silently corrupts the holder count if skipped - see the
    module docstring for the counts that exposed them:

      * the manager's CIK comes from SUBMISSION.tsv (COVERPAGE has no CIK column), so holders
        count MANAGERS rather than filings;
      * only PERIODOFREPORT == period, because one file carries late filings for many quarters;
      * only 13F-HR/13F-HR/A, because 13F-NT is a notice that reports no holdings at all;
      * a RESTATEMENT amendment SUPERSEDES that manager's earlier filing for the period, so only
        the latest one is kept; a NEW HOLDINGS amendment adds and is kept alongside.

    Returns (accession -> manager CIK, stats).
    """
    sub = {r["ACCESSION_NUMBER"]: r for r in _table(z, "submission")}
    cov = {r["ACCESSION_NUMBER"]: r for r in _table(z, "coverpage")}
    if not sub:
        return {}, {"error": "no SUBMISSION table - cannot tell managers apart"}

    cand = [a for a, r in sub.items()
            if (r.get("PERIODOFREPORT") or "").strip().upper() == period
            and (r.get("SUBMISSIONTYPE") or "").upper().startswith("13F-HR")]

    by_cik = {}
    for a in cand:
        by_cik.setdefault((sub[a].get("CIK") or a).strip(), []).append(a)

    keep, superseded = {}, 0
    for cik, accs in by_cik.items():
        restatements = [a for a in accs
                        if (cov.get(a, {}).get("AMENDMENTTYPE") or "").strip().upper()
                        == "RESTATEMENT"]
        if restatements:
            latest = max(restatements, key=lambda a: (sub[a].get("FILING_DATE") or "", a))
            keep[latest] = cik
            superseded += len(accs) - 1
        else:
            for a in accs:
                keep[a] = cik
    return keep, {"submissions": len(sub), "for_period": len(cand), "managers": len(by_cik),
                  "accessions_kept": len(keep), "superseded_by_restatement": superseded}


def aggregate(zbytes, period):
    """Aggregate one period's holdings by CUSIP. Returns ({cusip: {...}}, note).

    INFOTABLE is streamed row by row: it runs to ~4 million rows and ~400MB uncompressed per
    file, so reading it whole is the difference between this working on a laptop and not. Only
    the per-CUSIP totals are retained.

    Two row filters matter for correctness. SSHPRNAMTTYPE must be 'SH' - a 'PRN' row is a
    principal amount of debt, not a share count, and summing the two produces nonsense. And a row
    with PUTCALL set is an option position, not ownership, so counting it would credit a manager
    who is SHORT the name via puts as a sponsor.
    """
    try:
        z = zipfile.ZipFile(io.BytesIO(zbytes))
    except Exception as e:
        return None, "not a readable zip (%s)" % e
    info = _member(z, "infotable")
    if not info:
        return None, "no INFOTABLE in the archive (members: %s)" % ", ".join(z.namelist()[:8])

    keep, stats = select_filings(z, period)
    if stats.get("error"):
        return None, stats["error"]
    if not keep:
        return None, ("no 13F-HR filings for period %s in this file (it holds %d submissions)"
                      % (period, stats.get("submissions", 0)))

    out = {}
    rows = kept = 0
    with z.open(info) as f:
        for row in csv.DictReader(io.TextIOWrapper(f, "utf-8", errors="replace"), delimiter="\t"):
            rows += 1
            cik = keep.get((row.get("ACCESSION_NUMBER") or "").strip())
            if cik is None:
                continue                                  # other period, a notice, or superseded
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
            e = out.setdefault(cusip, {"name": (row.get("NAMEOFISSUER") or "").strip(),
                                       "shares": 0.0, "value": 0.0, "filers": set()})
            e["shares"] += sh
            try:
                e["value"] += float(row.get("VALUE") or 0)
            except ValueError:
                pass
            e["filers"].add(cik)
            kept += 1
    for e in out.values():
        e["holders"] = len(e["filers"])
        del e["filers"]
    note = ("period %s: %d managers over %d filings (%d superseded), %d/%d rows kept, %d issuers"
            % (period, stats["managers"], stats["accessions_kept"],
               stats["superseded_by_restatement"], kept, rows, len(out)))
    return out, note


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


def get_dataset(ds, contact, timeout, cache_dir):
    """Bytes for one dataset, from the local cache if present. Returns (bytes, where)."""
    if cache_dir:
        local = os.path.join(cache_dir, ds["name"])
        if os.path.exists(local) and os.path.getsize(local) > 1000:
            return open(local, "rb").read(), "cached " + local
    data, why = http(ds["url"], contact, timeout)
    if data is None:
        return None, "%s -> %s" % (ds["url"], why)
    if len(data) < 1000:
        return None, "%s returned %d bytes" % (ds["url"], len(data))
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        open(os.path.join(cache_dir, ds["name"]), "wb").write(data)
    return data, ds["url"]


def build(args, cfg):
    meta = {"source": "sec-13f", "is_proxy": False, "quarter": args.quarter, "prior": args.prior,
            "thresholds": dict(cfg), "datasets": {}, "notes": [], "ok": False}
    known, detail = {}, {}

    universe, cusip_map, floats = {}, {}, {}
    # SEC's own ticker->registrant-name map covers every US registrant (~10k), so the cache can be
    # built ONCE for the whole market instead of only for the names one sweep happened to surface.
    # That is what makes it a quarterly artifact rather than a per-run one.
    if getattr(args, "sec_tickers", None):
        src = args.sec_tickers
        if src == "auto":
            body, why = http("https://www.sec.gov/files/company_tickers.json",
                             args.contact, args.timeout)
            if body is None:
                meta["notes"].append("company_tickers.json: %s" % why)
                body = b"{}"
        else:
            body = io.open(src, "rb").read()
        try:
            for e in json.loads(body.decode("utf-8", "replace")).values():
                t = (e.get("ticker") or "").strip().upper()
                if t:
                    universe.setdefault(t, e.get("title") or "")
            meta["notes"].append("universe: %d tickers from SEC company_tickers.json" % len(universe))
        except Exception as e:
            meta["notes"].append("could not read company_tickers.json (%s)" % e)
    if getattr(args, "universe", None):
        blob = json.load(open(args.universe, encoding="utf-8"))
        sec = blob.get("sectors") or {}
        groups = sec.items() if isinstance(sec, dict) else [
            (g.get("sector"), g.get("rows") or g.get("members") or []) for g in sec]
        for _, rows in groups:
            for r in rows or []:
                t = (r.get("symbol") or r.get("ticker") or "").split(":")[-1]
                if not t:
                    continue
                universe[t] = r.get("description") or r.get("company") or r.get("name") or ""
                if r.get("float_shares_outstanding_current"):
                    floats[t] = r["float_shares_outstanding_current"]
        meta["notes"].append("universe: %d tickers from %s" % (len(universe), args.universe))
    if getattr(args, "cusip_map", None):
        cusip_map = {k.strip().upper(): v for k, v in
                     json.load(open(args.cusip_map, encoding="utf-8")).items()}
        meta["notes"].append("cusip map: %d entries" % len(cusip_map))

    datasets, why = list_datasets(args.contact, args.timeout)
    if why:
        meta["notes"].append(why)
    meta["available"] = [d["name"] for d in datasets[:6]]

    aggs = {}
    for label, q in (("quarter", args.quarter), ("prior", args.prior)):
        if not q:
            continue
        try:
            period = period_end(q)
        except ValueError as e:
            meta["notes"].append(str(e))
            continue
        ds = dataset_for_period(datasets, period)
        if not ds:
            meta["notes"].append(
                "%s %s (period %s): no published data set covers it yet%s" %
                (label, q, period,
                 " - newest is %s" % datasets[0]["name"] if datasets else ""))
            continue
        meta["datasets"][q] = ds["name"]
        data, where = get_dataset(ds, args.contact, args.timeout, args.cache_dir)
        if data is None:
            meta["notes"].append("%s %s: %s" % (label, q, where))
            continue
        agg, note = aggregate(data, period)
        meta["notes"].append("%s %s [%s]: %s" % (label, q, ds["name"], note))
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
    if "prior" not in aggs:
        meta["notes"].append("NO PRIOR QUARTER: every grade is capped at partial, because the "
                             "TREND is what the letter turns on and it cannot be computed")

    for tick, e in now_t.items():
        g, why_, m = grade(e, prior_t.get(tick), cfg, floats.get(tick))
        known[tick] = {"I": g}
        detail[tick] = dict(m, grade=g, ceiling_cap=g, reason=why_, source="sec-13f",
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
    ap.add_argument("--quarter", help="the HOLDINGS quarter, e.g. 2026Q1 or 2026-03-31. Note this "
                                      "is not the data-set file name: a quarter's 13Fs arrive in "
                                      "the window after it ends. Omit with --list.")
    ap.add_argument("--prior", help="the quarter before it - needed for the TREND, which is what "
                                    "the letter turns on. Derived from --quarter if omitted.")
    ap.add_argument("--list", action="store_true",
                    help="print the data sets SEC currently publishes, newest first, and exit")
    ap.add_argument("--universe", metavar="FILE",
                    help="the sweep JSON, used to resolve CUSIPs by issuer name. Layered OVER "
                         "--sec-tickers, so a sweep name wins where the two disagree.")
    ap.add_argument("--sec-tickers", metavar="FILE|auto",
                    help="SEC's company_tickers.json as the ticker->name map, covering every US "
                         "registrant - 'auto' downloads it. Use this to build a MARKET-WIDE cache "
                         "once a quarter rather than one limited to a single sweep's candidates.")
    ap.add_argument("--cusip-map", metavar="FILE", help='{"67066G104": "NVDA", ...}')
    ap.add_argument("--fallback", metavar="FILE",
                    help="accumulation.py output, used for tickers 13F could not answer")
    ap.add_argument("--cache-dir", default="data/13f", help="keep the zips (default %(default)s)")
    ap.add_argument("--contact", default="",
                    help="contact email for SEC's User-Agent policy - REQUIRED. Defaults to the "
                         "SEC_CONTACT environment variable. SEC returns 403 without a real "
                         "address and blocklists throwaway no-reply domains, so there is no "
                         "usable built-in default")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--thin-holders", type=int, default=DEFAULTS["thin_holders"])
    ap.add_argument("-o", "--out", metavar="FILE", help="write here (default: stdout)")
    ap.add_argument("--known-only", action="store_true", help="print just the --known map")
    a = ap.parse_args()

    # Fail here rather than 400MB and six retries later. Without a contact every SEC read 403s,
    # and the run still produces a well-formed cache with zero tickers in it - a file that looks
    # like an answer and silently grades nothing. One upfront check, naming the flag, is the
    # difference between a fixable error and a quiet wrong result.
    _, why_contact = resolve_contact(a.contact)
    if why_contact:
        print("cannot reach SEC: " + why_contact, file=sys.stderr)
        return 2

    if a.list:
        datasets, why = list_datasets(a.contact, a.timeout)
        if why:
            print(why, file=sys.stderr)
        for d in datasets:
            print("%-34s filings received %s .. %s" % (d["name"], d["start"], d["end"]))
        return 0
    if not a.quarter:
        ap.error("--quarter is required (or use --list)")
    if not a.prior:
        a.prior = prior_quarter(a.quarter)

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
