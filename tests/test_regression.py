#!/usr/bin/env python3
"""
Regression suite for can-slim-recommend. Pure standard library, no pytest needed.

    python tests/test_regression.py            # all suites
    python tests/test_regression.py ceiling    # only suites whose name contains "ceiling"
    python tests/test_regression.py -v         # show every passing assertion

WHAT THIS GUARDS. Every test here exists because the behaviour it pins is one a future edit
could plausibly break without any other signal:

  * the ceiling must never sit BELOW a score a name could actually earn - an unsound ceiling
    silently drops qualifiers, which is invisible in the output
  * triage must skip a check whose data is missing rather than fail it - a null column must
    never masquerade as a disqualification
  * the docs, the exporter and the code must keep agreeing - step numbers, source ladders,
    the bundle's manifest - because prose drift never fails a run, it just misleads one
  * the dashboard's self-audit must actually refuse the contradictions it claims to catch
  * @page margin/size parsing must reject what it cannot hand to another engine verbatim

Tests are plain functions named check_*; each returns None and raises AssertionError on failure.
"""
import datetime as _dt
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tempfile
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import sector_screen as ss                                  # noqa: E402
import relative_strength as rs                              # noqa: E402
import html_to_pdf as h2p                                   # noqa: E402
import build_report as br                                   # noqa: E402
import tv_throttle as thr                                   # noqa: E402
import market_session as mses                               # noqa: E402
import accumulation as acc                                  # noqa: E402
import institutional_cache as ic                            # noqa: E402
import annual_eps as aeps                                   # noqa: E402
import datadir as dd                                        # noqa: E402

W = {"pass": 1.0, "partial": 0.5, "fail": 0.0}
CFG = dict(ss.DEFAULTS)


def row(**kw):
    """A screener row that clears every hard filter unless a test overrides a field."""
    d = {"symbol": "NYSE:TEST", "name": "TEST", "description": "Test Co", "close": 100.0,
         "Perf.6M": 50.0, "market_cap_basic": 5e9, "average_volume_10d_calc": 1e6,
         "relative_volume_10d_calc": 1.5, "sector": "Energy Minerals", "industry": "Oil",
         "price_52_week_high": 101.0, "price_52_week_low": 40.0,
         "EMA50": 90.0, "EMA200": 80.0, "exchange": "NYSE",
         "earnings_release_next_date": "2026-11-01"}
    d.update(kw)
    return d


def sweep(rows_by_sector, bench=10.0):
    return {"asOf": "test", "window": "Perf.6M",
            "benchmark": {"symbol": "AMEX:SPY", "perf": {"Perf.6M": bench}},
            "sectors": rows_by_sector}


# ---------------------------------------------------------------- sector_screen: arithmetic

def check_triage_keeps_a_clean_row():
    r = ss.score_row(row(), "Perf.6M", 10.0, CFG)
    assert r["triage"] == "grade", r["drop_reasons"]
    assert abs(r["off_high_pct"] - (100/101 - 1) * 100) < 1e-9
    assert abs(r["rs_vs_bench_pts"] - 40.0) < 1e-9
    assert r["avg_dollar_volume"] == 100.0 * 1e6


def check_triage_drops_each_hard_filter():
    cases = [
        (dict(close=9.0), "price below"),
        (dict(average_volume_10d_calc=1e4), "average dollar volume under"),
        (dict(market_cap_basic=5e8), "market cap under"),
        (dict(close=60.0, price_52_week_high=101.0), "below the 52-week high"),
        (dict(**{"Perf.6M": 5.0}), "lags the benchmark"),
        (dict(close=79.0, EMA200=80.0, price_52_week_high=80.0), "below the 200-day"),
    ]
    for over, frag in cases:
        r = ss.score_row(row(**over), "Perf.6M", 10.0, CFG)
        assert r["triage"] == "drop", "%s should have dropped" % over
        assert any(frag in x for x in r["drop_reasons"]), (frag, r["drop_reasons"])


def check_missing_data_is_skipped_never_failed():
    """A null column must be recorded as skipped, not silently treated as a disqualification."""
    r = ss.score_row(row(market_cap_basic=None, EMA200=None, relative_volume_10d_calc=None),
                     "Perf.6M", 10.0, CFG)
    assert "market_cap" in r["checks_skipped"], r["checks_skipped"]
    assert "ema200" in r["checks_skipped"], r["checks_skipped"]
    assert r["triage"] == "grade", r["drop_reasons"]


def check_money_formatting():
    assert ss.money(1e9) == "$1B" and ss.money(2.5e7) == "$25M"
    assert ss.money(2e7) == "$20M" and ss.money(400e3) == "$400k"


def check_f_helper_prefers_first_present_numeric():
    assert ss.f({"a": None, "b": "3.5"}, "a", "b") == 3.5
    assert ss.f({"a": "not-a-number"}, "a") is None
    assert ss.f({}, "missing") is None


# ---------------------------------------------------------------- sector_screen: the ceiling

def _ceiling_of(**over):
    out = ss.score_row(row(**over), "Perf.6M", 10.0, CFG)
    out["sector_rank_overall"], out["sector_count"] = 1, 20
    ss.ceiling(out, CFG)
    return out


def check_ceiling_floor_is_exactly_the_cut_when_M_and_I_are_partial():
    """The documented result the two-stage design rests on: with M and I both partial, the
    worst possible ceiling is 4.5, so stage 1 can never eliminate anybody. If a future edit
    changes a cap and this floor moves, the SKILL.md explanation is wrong and must change too."""
    out = _ceiling_of(close=85.0, price_52_week_high=101.0,       # N capped to partial (>10% off)
                      relative_volume_10d_calc=0.9)              # S capped to partial
    out["sector_rank_overall"], out["sector_count"] = 20, 20     # L capped to partial
    ss.ceiling(out, CFG)
    assert out["ceiling"] == 4.5, out["ceiling"]
    assert out["grade_required"] is True


def check_ceiling_caps_N_by_distance_from_the_high():
    assert _ceiling_of(close=100.0, price_52_week_high=101.0)["ceiling_caps"]["N"] == "pass"
    assert _ceiling_of(close=85.0, price_52_week_high=101.0)["ceiling_caps"]["N"] == "partial"
    assert _ceiling_of(close=78.0, price_52_week_high=101.0)["ceiling_caps"]["N"] == "fail"


def check_ceiling_caps_S_by_relative_volume():
    assert _ceiling_of(relative_volume_10d_calc=1.5)["ceiling_caps"]["S"] == "pass"
    assert _ceiling_of(relative_volume_10d_calc=0.9)["ceiling_caps"]["S"] == "partial"
    assert _ceiling_of(relative_volume_10d_calc=0.7)["ceiling_caps"]["S"] == "fail"


def check_ceiling_caps_L_in_a_bottom_half_sector():
    out = _ceiling_of()
    out["sector_rank_overall"], out["sector_count"] = 15, 20
    ss.ceiling(out, CFG)
    assert out["ceiling_caps"]["L"] == "partial"


def check_a_single_sector_sweep_does_not_cap_L():
    """THE invariant: a ceiling below an earnable score silently drops a qualifier. `sr > tot/2`
    is true for rank 1 of 1, so any scoped sweep of one sector ("just tech", "AI stocks") capped
    every name's L at partial - 'leader of a laggard group' in a group of one."""
    for rank, count, expect in ((1, 1, "pass"), (1, 2, "pass"), (2, 2, "partial"), (15, 20, "partial")):
        out = ss.score_row(row(), "Perf.6M", 10.0, CFG)
        out["sector_rank_overall"], out["sector_count"] = rank, count
        ss.ceiling(out, CFG)
        assert out["ceiling_caps"]["L"] == expect, (rank, count, out["ceiling_caps"]["L"])
    # ...and end to end, the figure that matters: a marginal name is still graded in a 1-sector sweep
    marginal = row(close=85.0, price_52_week_high=100.0, relative_volume_10d_calc=0.9)
    res = ss.run(sweep({"Energy Minerals": [marginal]}), CFG, {"NYSE:TEST": {"A": "partial"}})
    m = res["grade_queue"][0]
    assert m["ceiling"] >= 4.5 and m["grade_required"], (m["ceiling"], m.get("ceiling_why"))


def check_known_grades_under_either_key_spelling_are_merged():
    """The A-screen keys by 'NASDAQ:OKTA', institutional_cache by bare 'OKTA'. Only the first
    non-empty entry was used, so a name carrying A under one and I under the other lost one."""
    blob = sweep({"Energy Minerals": [row(symbol="NASDAQ:OKTA", name="OKTA")]})
    both = ss.run(blob, CFG, {"NASDAQ:OKTA": {"A": "partial"}, "OKTA": {"I": "fail"}})
    only_a = ss.run(blob, CFG, {"NASDAQ:OKTA": {"A": "partial"}})
    only_i = ss.run(blob, CFG, {"OKTA": {"I": "fail"}})
    ceil = lambda r: r["grade_queue"][0]["ceiling"]
    assert ceil(both) < ceil(only_a) and ceil(both) < ceil(only_i), \
        "one key's grade was ignored: both=%s A-only=%s I-only=%s" % (ceil(both), ceil(only_a), ceil(only_i))
    # the exchange-qualified key is the more specific, so it wins where both grade a letter
    clash = ss.run(blob, CFG, {"NASDAQ:OKTA": {"A": "pass"}, "OKTA": {"A": "fail"}})
    assert ceil(clash) == ceil(ss.run(blob, CFG, {"NASDAQ:OKTA": {"A": "pass"}}))


def check_a_company_named_after_a_security_word_is_still_common_stock():
    """'Preferred Bank' (PFBC) and 'Unit Corporation' are ordinary common stock; the word opens
    the issuer's own name. The instruments are named issuer-first, security-last."""
    for sym, desc in (("NASDAQ:PFBC", "Preferred Bank"), ("NYSE:UNTC", "Unit Corporation")):
        out = ss.score_row(row(symbol=sym, description=desc), "Perf.6M", 10.0, CFG)
        assert out["triage"] == "grade", (desc, out["drop_reasons"])
    for sym, desc in (("NYSE:APTS", "Preferred Apartment Communities Inc. 6.000% Series A Preferred Stock"),
                      ("NASDAQ:ZZZW", "Warrants"), ("NYSE:UNT", "Unit Corporation Warrant")):
        out = ss.score_row(row(symbol=sym, description=desc), "Perf.6M", 10.0, CFG)
        assert out["triage"] == "drop", (desc, out["triage"])


def check_a_real_grade_overrides_the_screener_cap_in_both_directions():
    """`known` carries grades that were actually awarded, so it REPLACES the screener's guess
    rather than being bounded by it. Downward is the case the two-stage design runs on: an
    A-screen result drops the ceiling and usually saves the C call. Upward is rarer but must also
    hold - a screener column is a proxy, and when a real grade contradicts it the real grade wins.
    """
    out = _ceiling_of()
    base = out["ceiling"]
    ss.ceiling(out, CFG, {"A": "fail"})
    assert out["ceiling"] == base - 1.0, (base, out["ceiling"])
    ss.ceiling(out, CFG, {"A": "partial", "C": "fail"})       # re-graded: caps recompute from scratch
    assert out["ceiling"] == base - 1.5, (base, out["ceiling"])

    thin = _ceiling_of(relative_volume_10d_calc=0.7)          # S capped at fail by the screener
    capped = thin["ceiling"]
    ss.ceiling(thin, CFG, {"S": "pass"})
    assert thin["ceiling_caps"]["S"] == "pass"
    assert thin["ceiling"] == capped + 1.0, (capped, thin["ceiling"])

    # keys are matched case- and whitespace-insensitively; junk is ignored, not crashed on
    loose = _ceiling_of()
    ss.ceiling(loose, CFG, {" a ": "FAIL", "Z": "pass", "C": "nonsense"})
    assert loose["ceiling_caps"]["A"] == "fail" and loose["ceiling_caps"]["C"] == "pass"


def _best_grade_the_rubric_allows(oh, rv, rank, tot, cfg):
    """An INDEPENDENT statement of the same caps, written from the rubric rather than read back
    out of ceiling(). The distinction matters: the first version of this test filtered its grade
    space using ceiling()'s own `ceiling_caps`, which made it circular - it proved the ceiling
    agreed with itself, and a cap set too TIGHT (the failure mode that silently drops qualifiers)
    passed unnoticed. Two implementations that must agree is the point; if you change a band,
    change it here too, deliberately.
    """
    band = cfg["pivot_band"]
    if oh is None or oh >= -band:
        n = "pass"
    elif oh >= -2 * band:
        n = "partial"
    else:
        n = "fail"
    if rv is None or rv >= 1.0:
        sg = "pass"
    elif rv >= cfg["thin_vol"]:
        sg = "partial"
    else:
        sg = "fail"
    l = "partial" if (rank and tot and rank > tot / 2.0) else "pass"
    # C and A are unknown until the fundamentals are pulled, so the rubric allows a full pass.
    return {"C": "pass", "A": "pass", "N": n, "S": sg, "L": l}


def check_ceiling_is_sound_against_every_reachable_grade():
    """THE load-bearing property: no grade a grader could actually award may exceed the ceiling.
    A ceiling that is too HIGH only wastes API calls; one that is too LOW drops a qualifier and
    leaves no trace in the output, so this brute-forces the whole 3^5 grade space against the
    independent rubric above, over every combination of the three screener facts that cap it."""
    import itertools
    for oh, rv, rank in itertools.product([-1.0, -15.0, -22.0], [1.5, 0.9, 0.7], [1, 18]):
        close = 101.0 * (1 + oh / 100.0)
        out = ss.score_row(row(close=close, price_52_week_high=101.0,
                               relative_volume_10d_calc=rv, EMA50=close * 0.9, EMA200=close * 0.8,
                               **{"Perf.6M": 50.0}), "Perf.6M", 10.0, CFG)
        out["sector_rank_overall"], out["sector_count"] = rank, 20
        ss.ceiling(out, CFG)
        best = _best_grade_the_rubric_allows(oh, rv, rank, 20, CFG)
        for combo in itertools.product(["pass", "partial", "fail"], repeat=5):
            g = dict(zip("CANSL", combo))
            if any(W[g[k]] > W[best[k]] for k in "CANSL"):
                continue                       # not a grade this row could earn
            total = sum(W[v] for v in g.values()) + W[CFG["i_grade"]] + W[CFG["m_grade"]]
            assert total <= out["ceiling"] + 1e-9, (g, total, out["ceiling"], out["ceiling_caps"])


# Every name the 2026-09-12 run actually graded, as (symbol, % off the 52-week high, sector rank,
# the six letters awarded as C-A-N-S-L-I where P=pass H=partial F=fail). Real grader output, not
# constructed cases: it is the only evidence here that the caps match what the rubric DOES rather
# than what a second copy of the rubric says it should. Run outputs are gitignored, so the extract
# is pinned in-file; M was graded "partial" market-wide and 20 sectors were swept.
REAL_RUN_2026_09_12 = [
    ("INSW",   2.9,  7, "PPPPPH"),
    ("TNK",   0.1,  6, "PPPPPH"),
    ("CMBT",   2.1,  5, "PPPHPH"),
    ("DELL",   0.1,  2, "PPPHPH"),
    ("ECO",   0.1,  3, "PPPHPH"),
    ("FRO",   0.7,  4, "PPPHPH"),
    ("GEO",   5.0,  1, "HPPPPH"),
    ("OSCR",   4.3,  1, "PHPPPH"),
    ("TRMD",   2.4,  8, "PPPHPH"),
    ("AYA",   8.0,  1, "PPPHHH"),
    ("CON",   2.6,  6, "HPPHPH"),
    ("DINO",   3.9,  2, "PHPHPH"),
    ("DK",   3.0,  4, "PFPPPH"),
    ("GRDN",   7.2, 10, "HPPPHH"),
    ("HPE",   3.4,  4, "PHPHPH"),
    ("LPG",   0.6,  1, "PHPHPH"),
    ("MPC",   3.2,  6, "PHPHPH"),
    ("OII",   5.8,  5, "HHPPPH"),
    ("PARR",   2.7,  8, "PPPFPH"),
    ("PBF",   5.2,  3, "PHPHPH"),
    ("PSX",   2.2, 10, "PHPHPH"),
    ("SBLK",   5.2, 10, "PHPHPH"),
    ("VG",  10.3,  4, "PPHPHH"),
    ("VLO",   2.2,  7, "PHPHPH"),
    ("WT",   7.6,  6, "PPPFPH"),
    ("AAMI",   7.6,  4, "PHPFPH"),
    ("AMD",  11.7,  6, "PHHHPH"),
    ("ARMK",   6.5, 10, "HFPPPH"),
    ("ARW",   3.8,  4, "PFPPHH"),
    ("AVT",   0.4,  3, "PFPPHH"),
    ("CGAU",   7.7,  9, "HPPHHH"),
    ("CNC",   4.2,  5, "PFPHPH"),
    ("CXW",   1.0,  4, "HFPPPH"),
    ("IMAX",   6.3,  3, "HHPPHH"),
    ("MU",  22.3, 10, "PPFHPH"),
    ("NESR",   9.2,  1, "PHPHHH"),
    ("SM",   2.2,  9, "PFPHPH"),
    ("VCTR",  10.7,  5, "PHHHPH"),
    ("BTSG",  20.4,  8, "PHFHPH"),
    ("EAT",  16.7,  8, "HHHHPH"),
    ("MSM",   7.6,  9, "HHPHHH"),
    ("SNX",   9.2,  1, "PFPHHH"),
    ("STT",   1.3,  8, "HFPHPH"),
    ("SUNC",   2.8,  7, "PFPHHH"),
]


def check_ceiling_covers_every_grade_the_last_real_run_awarded():
    """No name in a completed run may have scored above its own ceiling. Relative volume is not
    carried in the report, so S is left unknown here - that only makes the ceiling more generous,
    and the check still binds on N and L, the two caps the real grades can contradict."""
    for sym, off_high, rank, awarded in REAL_RUN_2026_09_12:
        close = 101.0 * (1 - off_high / 100.0)
        out = ss.score_row(row(symbol=sym, close=close, price_52_week_high=101.0,
                               EMA50=close * 0.9, EMA200=close * 0.8, **{"Perf.6M": 50.0}),
                           "Perf.6M", 10.0, CFG)
        out["rel_volume_10d"] = None                      # not reported; the generous branch
        out["sector_rank_overall"], out["sector_count"] = rank, 20
        ss.ceiling(out, CFG)
        g = {"P": "pass", "H": "partial", "F": "fail"}
        total = sum(W[g[c]] for c in awarded) + W[CFG["m_grade"]]
        assert total <= out["ceiling"] + 1e-9, (
            "%s scored %.1f but its ceiling was %.1f - the ceiling would have dropped a name the "
            "grader passed (caps %r)" % (sym, total, out["ceiling"], out["ceiling_caps"]))
        # and the N cap must not contradict the N the grader actually awarded
        assert W[g[awarded[2]]] <= W[out["ceiling_caps"]["N"]], (
            "%s: graded N=%s but the ceiling capped N at %s" % (sym, g[awarded[2]],
                                                                out["ceiling_caps"]["N"]))


# ---------------------------------------------------------------- sector_screen: run()

def check_run_ranks_sectors_and_builds_the_queue():
    blob = sweep({"Energy Minerals": [row(**{"Perf.6M": 90.0}), row(symbol="NYSE:B", name="B", **{"Perf.6M": 80.0})],
                  "Utilities": [row(symbol="NYSE:C", name="C", **{"Perf.6M": 20.0})]})
    res = ss.run(blob, CFG)
    assert res["sector_count"] == 2
    assert res["sectors"][0]["sector"] == "Energy Minerals"     # higher median ranks first
    assert res["sectors"][0]["rank"] == 1
    assert res["graded_candidates"] == 3
    assert res["must_grade"] + res["eliminated_by_ceiling"] == res["graded_candidates"]
    assert res["threshold"] == CFG["threshold"]


def check_run_counts_reconcile_with_known_grades():
    blob = sweep({"Energy Minerals": [row(), row(symbol="NYSE:B", name="B")]})
    res = ss.run(blob, CFG, {"NYSE:B": {"A": "fail", "C": "fail"}})
    assert res["must_grade"] + res["eliminated_by_ceiling"] == res["graded_candidates"]
    q = {m["symbol"]: m for m in res["grade_queue"]}
    assert q["NYSE:B"]["ceiling"] < q["NYSE:TEST"]["ceiling"]


def check_an_unfinished_session_does_not_cap_S():
    """Found by running the skill live on 2026-09-23. `relative_volume_10d_calc` compares today's
    volume SO FAR against the 10-day average, so mid-session it is a partial sum, not a
    measurement: every row of the real sweep came back between 0.06x and 0.44x while SPY's own bar
    showed 2.4M shares against a ~40M norm.

    ceiling() uses that field as a HARD cap on S, so taken intraday it capped S=fail across the
    market and dropped every ceiling a full point. On the real Electronic Technology rows that
    pruned 3 of 6 survivors - MU and SNDK among them - which is the one error the ceiling must
    never make. An unfinished session is MISSING data, and the rule everywhere else in this skill
    is that missing data is skipped, never failed.
    """
    real = [("QMCO", 26.11, 27.80, 0.424), ("DELL", 554.63, 595.51, 0.293),
            ("SNDK", 1836.25, 2354.39, 0.324), ("AMD", 611.91, 624.69, 0.213),
            ("MU", 1078.1, 1255.0, 0.314), ("AMBQ", 69.53, 91.61, 0.067)]
    rows = [row(symbol="NASDAQ:" + t, description=t, close=c, price_52_week_high=h,
                relative_volume_10d_calc=rv, EMA50=c * 0.9, EMA200=c * 0.7, **{"Perf.6M": 200.0})
            for t, c, h, rv in real]
    res = ss.run(sweep({"Electronic Technology": rows}, bench=19.76), CFG)
    assert res["partial_session"] is True, "a whole market at a fifth of normal volume is a "\
        "part-finished session, not thin trading"
    assert "part-finished session" in res["partial_session_note"]
    members = [m for s in res["sectors"] for m in s["members"] if m["triage"] == "grade"]
    assert members, "the fixture should survive triage"
    for m in members:
        assert m["ceiling_caps"]["S"] == "pass", \
            "%s: S capped on a partial sum (%s)" % (m["symbol"], m["ceiling_caps"]["S"])

    # ...and with the detector off, the old behaviour prunes names it should not have
    off = dict(CFG, partial_session_frac=2.0)
    old = ss.run(sweep({"Electronic Technology": rows}, bench=19.76), off)
    assert old["must_grade"] < res["must_grade"], \
        "the detector makes no difference, so it is not doing anything"


def check_real_thin_volume_is_still_caught_after_the_close():
    """The detector must not become a blanket excuse. A normal post-close sweep has a spread of
    readings, and a genuinely thin name in it still has to be capped - that cap is what the S
    letter is for."""
    vols = [1.6, 1.2, 0.9, 0.4, 1.1, 1.8, 0.7, 1.3, 2.0, 0.95]
    rows = [row(symbol="NASDAQ:T%d" % i, description="T%d" % i,
                relative_volume_10d_calc=v, **{"Perf.6M": 80.0}) for i, v in enumerate(vols)]
    res = ss.run(sweep({"Electronic Technology": rows}), CFG)
    assert res["partial_session"] is False, "a normal spread was mistaken for a partial session"
    caps = sorted({m["ceiling_caps"]["S"] for s in res["sectors"] for m in s["members"]
                   if m["triage"] == "grade"})
    assert caps == ["fail", "partial", "pass"], \
        "S stopped discriminating after the close: %s" % caps


def check_dropped_rows_carry_no_ceiling():
    blob = sweep({"Energy Minerals": [row(close=9.0)]})
    res = ss.run(blob, CFG)
    m = res["sectors"][0]["members"][0]
    assert m["triage"] == "drop" and m["ceiling"] is None and m["grade_required"] is False


def check_normalize_accepts_both_sweep_shapes():
    a = ss.normalize_sectors({"sectors": {"X": [row()]}})
    b = ss.normalize_sectors({"sectors": [{"sector": "X", "rows": [row()]}]})
    assert [k for k, _ in a] == [k for k, _ in b] == ["X"]


def check_markdown_renders_without_crashing():
    res = ss.run(sweep({"Energy Minerals": [row()], "Utilities": [row(symbol="NYSE:D", name="D", close=9.0)]}), CFG)
    md = ss.to_markdown(res)
    assert "Grading coverage" in md and "Must grade" in md
    assert "/ 70" not in md and "out of 70" not in md        # the dead scale must never reappear


def check_cli_runs_end_to_end(tmp):
    p = os.path.join(tmp, "sweep.json")
    io.open(p, "w", encoding="utf-8").write(json.dumps(sweep({"Energy Minerals": [row()]})))
    out = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "sector_screen.py"), p,
                          "--m-grade", "partial", "--i-grade", "partial"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    d = json.loads(out.stdout)
    assert d["ceiling_basis"]["M"] == "partial" and d["ceiling_basis"]["I"] == "partial"
    # stdin path
    out2 = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "sector_screen.py"), "--md"],
                          input=json.dumps(sweep({"Energy Minerals": [row()]})),
                          capture_output=True, text=True, timeout=60)
    assert out2.returncode == 0 and "Sector sweep" in out2.stdout


# ---------------------------------------------------------------- relative_strength

def _bars(prices, vols=None):
    vols = vols or [1_000_000] * len(prices)
    return [[i, p, p, p, p, v] for i, (p, v) in enumerate(zip(prices, vols))]


def check_ret_over_and_rs_proxy():
    assert abs(rs.ret_over([100, 110], 1) - 0.1) < 1e-9
    assert rs.ret_over([100], 5) is None                       # not enough history
    assert rs.ret_over([0, 5], 1) is None                      # divide-by-zero guarded
    cand, bench = _bars([100] * 252 + [200]), _bars([100] * 252 + [110])
    rel, blend = rs.rs_proxy(cand, bench)
    assert rel["3m"] > 0 and blend is not None


def check_pct_off_52w_high():
    assert rs.pct_off_52w_high(_bars([100, 50])) == 0.5
    assert rs.pct_off_52w_high(_bars([100])) == 0.0
    assert rs.pct_off_52w_high([]) is None


def check_breakout_volume_excludes_the_latest_bar():
    """The 50-day average must not include the breakout bar itself, or a big day dilutes its
    own signal. 50 bars at 1M then one at 2M is exactly +100%."""
    v = [1_000_000] * 50 + [2_000_000]
    assert rs.breakout_volume(_bars([100] * 51, v), avg_window=50) == 1.0
    assert rs.breakout_volume(_bars([100] * 10), avg_window=50) is None


def check_base_metrics_flags_a_wide_loose_base():
    m = rs.base_metrics(_bars([100] * 10 + [50] + [60] * 5))
    assert m["wide_and_loose_flag"] is True and m["base_depth_pct"] == 0.5
    assert rs.base_metrics(_bars([1, 2])) is None


# ---------------------------------------------------------------- accumulation (I proxy)

def _tape(pattern, vol=None):
    """pattern: 'u'/'d'/'f' per bar (up, down, flat). vol: per-bar multiplier of 1M."""
    bars, price = [], 100.0
    for i, ch in enumerate(pattern):
        price += 1.0 if ch == "u" else (-1.0 if ch == "d" else 0.0)
        v = 1_000_000 * ((vol or [1] * len(pattern))[i])
        bars.append([i, price, price, price, round(price, 2), v])
    return bars


def _dated_bars(kind, n=160, start="2022-10-03"):
    """Weekday bars from `start`, stamped in the given kind; close == index so counts are visible."""
    import datetime as D
    d, out = D.date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            i = len(out)
            midnight = D.datetime(d.year, d.month, d.day, tzinfo=D.timezone.utc)
            ms = int((midnight + D.timedelta(hours=4)).timestamp() * 1000)
            t = {"iso": d.isoformat(), "iso_time": d.isoformat() + "T20:00:00Z", "ms": ms,
                 "s": ms // 1000, "ymd": int(d.strftime("%Y%m%d"))}[kind]
            out.append([t, 100 + i, 100 + i, 100 + i, 100 + i, 1_000_000])
        d += D.timedelta(days=1)
    return out


def check_asof_truncates_every_timestamp_shape():
    """Polygon/Massive bars carry epoch milliseconds - the path SKILL.md recommends for as-of runs
    - and against a "2023-01-31" cutoff they fell into a STRING compare in which "1675..." sorts
    before "2023-...": every bar was kept, so a point-in-time run silently saw the whole future."""
    import datetime as D
    expect = len([b for b in _dated_bars("iso") if b[0] <= "2023-01-31"])
    assert 0 < expect < 160
    for kind in ("iso", "iso_time", "ms", "s", "ymd"):
        for cutoff in ("2023-01-31", 20230131, "2023-01-31T23:59:59Z"):
            kept = rs.truncate_asof(_dated_bars(kind), cutoff)
            assert len(kept) == expect, (kind, cutoff, len(kept), expect)
    # dict-shaped bars (TradingView / Polygon) go through normalize() first
    dicts = [{"t": b[0], "o": b[1], "h": b[2], "l": b[3], "c": b[4], "v": b[5]} for b in _dated_bars("ms")]
    assert len(rs.truncate_asof(rs.normalize(dicts), "2023-01-31")) == expect
    # a cutoff with a time of day is exact; a bare date is inclusive of the whole day
    day = D.datetime(2023, 1, 31, tzinfo=D.timezone.utc)
    noon_ms = int((day + D.timedelta(hours=12)).timestamp() * 1000)
    assert len(rs.truncate_asof(_dated_bars("ms"), noon_ms)) == expect       # the 04:00Z bar is before noon
    assert len(rs.truncate_asof(_dated_bars("ms"), int((day + D.timedelta(hours=3)).timestamp() * 1000))) == expect - 1
    # silence is the bug: a timestamp that cannot be read must raise, never be kept
    for bad in ("garbage", None, True):
        try:
            rs.truncate_asof([[bad, 1, 1, 1, 1, 1]], "2023-01-31")
        except ValueError:
            continue
        raise AssertionError("an unreadable timestamp %r was silently kept" % (bad,))


def check_asof_cli_takes_the_equals_form_and_refuses_a_missing_value(tmp):
    """The hand-rolled loop took only "--asof DATE": "--asof=DATE" and a trailing "--asof" were
    IGNORED, and the run printed a normal-looking answer computed on the whole future."""
    bars = _dated_bars("iso", n=300)
    for i, b in enumerate(bars):                      # rise then fall, so the cutoff changes the answer
        px = 100 + i if i < 150 else 250 - 2 * (i - 150)
        b[1:5] = [px, px, px, px]
    path = os.path.join(tmp, "bars.json")
    io.open(path, "w", encoding="utf-8").write(json.dumps(
        {"benchmark": {"daily": bars}, "candidates": [{"symbol": "X", "daily": bars}]}))
    run = lambda *a: subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "relative_strength.py"), path]
                                    + list(a), capture_output=True, text=True, timeout=60)
    full, spaced, equals = run(), run("--asof", "2023-03-01"), run("--asof=2023-03-01")
    assert full.returncode == spaced.returncode == equals.returncode == 0, equals.stderr
    assert spaced.stdout == equals.stdout, "--asof=DATE and --asof DATE disagree"
    assert spaced.stdout != full.stdout, "--asof changed nothing: the cutoff was ignored"
    assert run("--asof").returncode != 0, "a trailing --asof with no value was accepted"
    assert run("--no-such-flag").returncode != 0, "an unknown flag was silently ignored"


def check_accumulation_honours_asof():
    """accumulation.py says it takes the same JSON as relative_strength.py, which cuts every series
    to `asof`. It did not, so a point-in-time run graded I on bars that had not printed yet."""
    bars = _dated_bars("iso", n=160)
    for i, b in enumerate(bars):                      # a quiet first half, a violent distribution after
        up = i % 3 != 2
        px = 100 + i * 0.1 if i < 80 else 108 - (i - 80) * 0.6
        b[1:5] = [px, px, px, round(px, 2)]
        b[5] = 1_000_000 * (6 if (i >= 80 and not up and i % 2 == 0) else 1)
    cfg = dict(acc.DEFAULTS)
    cut = bars[79][0]
    with_asof = acc.analyze({"asof": cut, "candidates": [{"symbol": "NYSE:X", "daily": bars}]}, cfg)
    truncated = acc.analyze({"candidates": [{"symbol": "NYSE:X", "daily": bars[:80]}]}, cfg)
    whole = acc.analyze({"candidates": [{"symbol": "NYSE:X", "daily": bars}]}, cfg)
    assert with_asof["detail"]["X"]["ud_ratio"] == truncated["detail"]["X"]["ud_ratio"], "asof was ignored"
    assert with_asof["detail"]["X"]["ud_ratio"] != whole["detail"]["X"]["ud_ratio"], "fixture does not discriminate"


def check_up_down_volume_ignores_flat_days():
    """A flat close carries no directional information. Bucketing it with the buyers is how this
    ratio gets quietly inflated on thin names that reprint the same close."""
    assert acc.up_down_volume(_tape("xuudd"), 50) == 1.0        # 2 up, 2 down, equal volume
    # inserting flat days must not move the ratio
    assert acc.up_down_volume(_tape("xuffuddff"), 50) == 1.0
    assert acc.up_down_volume(_tape("xuuu"), 50) == float("inf")   # nothing to divide by
    assert acc.up_down_volume([], 50) is None


def check_up_down_volume_weights_by_volume_not_by_day_count():
    # one heavy up day outweighs three light down days
    r = acc.up_down_volume(_tape("xuddd", [1, 9, 1, 1, 1]), 50)
    assert abs(r - 3.0) < 1e-9, r


def check_big_volume_up_days_counts_only_heavy_advances():
    v = [1] * 20 + [5]                       # last bar heavy
    assert acc.big_volume_up_days(_tape("x" + "ud" * 10, v), 50, 1.4) >= 0
    up_heavy = acc.big_volume_up_days(_tape("x" + "u" * 20, v), 50, 1.4)
    dn_heavy = acc.big_volume_up_days(_tape("x" + "d" * 20, v), 50, 1.4)
    assert up_heavy == 1 and dn_heavy == 0, (up_heavy, dn_heavy)


def check_accumulation_accepts_both_bar_shapes():
    """get_ohlcv returns dicts; relative_strength.py documents positional lists. A grader that
    took only one would need a hand conversion, which is where a column shifts by one."""
    lists = _tape("xuuddu")
    dicts = [{"t": b[0], "o": b[1], "h": b[2], "l": b[3], "c": b[4], "v": b[5]} for b in lists]
    assert acc.up_down_volume(lists, 50) == acc.up_down_volume(dicts, 50)


def _heavy_on(pattern, ch, mult=4, every=6):
    """Volume derived FROM the pattern, so the heavy days land on the intended side, and heavy
    days stay OCCASIONAL.

    Two fixture mistakes are baked into this helper's shape, both found here rather than in the
    code. Building pattern and volume independently put the accumulation volume on the down days.
    And making every up day heavy scores ZERO heavy days - the count is relative to the window
    average, so a uniformly heavy tape has no spikes to find. That is the right behaviour (if
    every day looks the same you cannot pick out the institutions) but it is not what real
    accumulation looks like, which is ordinary volume punctuated by prints.
    """
    out, n = [], 0
    for c in pattern:
        if c == ch:
            n += 1
            out.append(mult if n % every == 0 else 1)
        else:
            out.append(1)
    return out


def check_accumulation_grades_the_three_regimes():
    cfg = dict(acc.DEFAULTS)
    # accumulation: more up days than down, and the heavy prints are on the up days
    p = "uud" * 27
    g, cap, why, m = acc.grade(_tape(p, _heavy_on(p, "u")), cfg)
    assert (g, cap) == ("pass", "pass"), (g, cap, m)
    assert "proxy" in why and m["ud_ratio"] > cfg["accumulate"]
    # distribution: the heavy prints are on the down days
    q = "ddu" * 27
    g2, cap2, _, m2 = acc.grade(_tape(q, _heavy_on(q, "d")), cfg)
    assert g2 == "fail" and m2["ud_ratio"] < cfg["distribute"], (g2, m2)
    # neutral tape sits between the two and must claim nothing
    r = "ud" * 40
    g3, _, _, _ = acc.grade(_tape(r), cfg)
    assert g3 == "partial", g3


def check_a_proxy_fail_never_caps_the_ceiling_at_fail_by_default():
    """THE safety property for the proxy. The ceiling is an upper bound: too high only wastes API
    calls, too low silently drops a qualifier. Volume alone cannot prove no amount of ownership
    data would lift the letter, so a proxy FAIL caps at partial unless --strict is asked for."""
    cfg = dict(acc.DEFAULTS)
    data = {"candidates": [{"symbol": "NYSE:DIST", "daily": _tape("d" * 60 + "dddu" * 8)}]}
    lenient = acc.analyze(data, cfg)
    assert lenient["detail"]["DIST"]["grade"] == "fail"
    assert lenient["known"]["DIST"]["I"] == "partial", "a proxy fail must not cap at fail"
    strict = acc.analyze(data, cfg, strict=True)
    assert strict["known"]["DIST"]["I"] == "fail", "--strict must let it prune"
    # and no proxy output may ever be worse than its own honest grade
    for out in (lenient, strict):
        for t, k in out["known"].items():
            assert acc.ORDER[k["I"]] >= acc.ORDER[out["detail"][t]["grade"]]


def check_too_little_tape_is_partial_never_fail():
    """Same rule as triage: missing data is skipped, never treated as a disqualification."""
    g, cap, why, m = acc.grade(_tape("ud" * 5), dict(acc.DEFAULTS))
    assert g == "partial" and cap == "partial", (g, cap)
    assert "too little tape" in why


# ---------------------------------------------------------------- institutional_cache (I, 13F)

def _mk13f(path, rows, period="31-MAR-2026", filed=None):
    """A zip shaped like SEC's real Form 13F data set: SUBMISSION + COVERPAGE + INFOTABLE.

    Built to the real schema after the first version of these fixtures invented one. The manager's
    CIK lives in SUBMISSION (COVERPAGE has no CIK column at all), one file carries several
    PERIODOFREPORT values, 13F-NT reports no holdings, and amendments restate or add - every one
    of which changes the holder count, and none of which a made-up fixture would have exercised.

    rows: [(accession, cik, submissiontype, period, amendmenttype, [(issuer, cusip, shares,
            sshprnamttype, putcall), ...]), ...]
    filed: {accession: "dd-MON-yyyy"} filing dates; every other accession is filed 01-MAY-2026.
    """
    import zipfile
    sub = ["ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tCIK\tPERIODOFREPORT"]
    cov = ["ACCESSION_NUMBER\tREPORTCALENDARORQUARTER\tISAMENDMENT\tAMENDMENTNO\tAMENDMENTTYPE\t"
           "FILINGMANAGER_NAME"]
    info = ["ACCESSION_NUMBER\tINFOTABLE_SK\tNAMEOFISSUER\tTITLEOFCLASS\tCUSIP\tFIGI\tVALUE\t"
            "SSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL"]
    k = 0
    for acc, cik, styp, per, amd, holds in rows:
        sub.append("%s\t%s\t%s\t%s\t%s" % (acc, (filed or {}).get(acc, "01-MAY-2026"), styp, cik,
                                           per or period))
        cov.append("%s\t%s\t%s\t%s\t%s\tFUND %s" % (acc, per or period, "Y" if amd else "N",
                                                    "1" if amd else "", amd or "", cik))
        for issuer, cusip, sh, typ, pc in holds:
            k += 1
            info.append("%s\t%d\t%s\tCOM\t%s\t\t%d\t%d\t%s\t%s"
                        % (acc, k, issuer, cusip, sh * 10, sh, typ, pc))
    z = zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED)
    z.writestr("SUBMISSION.tsv", "\n".join(sub))
    z.writestr("COVERPAGE.tsv", "\n".join(cov))
    z.writestr("INFOTABLE.tsv", "\n".join(info))
    z.close()
    return io.open(path, "rb").read()


def check_13f_excludes_options_and_principal_rows(tmp):
    """Two filters that are silent if wrong. A PUTCALL row is an option, so counting it credits a
    manager who is SHORT the name via puts as a sponsor. A PRN row is a principal amount of debt,
    and summing it with share counts produces a number that means nothing."""
    b = _mk13f(os.path.join(tmp, "q.zip"), [
        ("A1", "111", "13F-HR", None, None, [("NVIDIA CORPORATION", "67066G104", 1000, "SH", ""),
                                             ("NVIDIA CORPORATION", "67066G104", 500, "SH", "Call"),
                                             ("NVIDIA CORPORATION", "67066G104", 400, "PRN", "")]),
        ("A2", "222", "13F-HR", None, None, [("NVIDIA CORPORATION", "67066G104", 2000, "SH", "")]),
    ])
    agg, note = ic.aggregate(b, "31-MAR-2026")
    e = agg["67066G104"]
    assert e["shares"] == 3000, "options/principal leaked into the share count: %s" % e["shares"]
    assert e["holders"] == 2, e["holders"]


def check_13f_counts_distinct_managers_not_filings(tmp):
    """The manager's CIK comes from SUBMISSION - COVERPAGE has none. Keying on the accession
    instead counts FILINGS, inflating any manager that filed more than once."""
    b = _mk13f(os.path.join(tmp, "q.zip"), [
        ("A1", "555", "13F-HR", None, None, [("ACME CORP", "AAA", 100, "SH", "")]),
        ("A2", "555", "13F-HR", None, None, [("ACME CORP", "AAA", 100, "SH", "")]),
        ("A3", "777", "13F-HR", None, None, [("ACME CORP", "AAA", 100, "SH", "")]),
    ])
    agg, _ = ic.aggregate(b, "31-MAR-2026")
    assert agg["AAA"]["holders"] == 2, agg["AAA"]["holders"]
    assert agg["AAA"]["shares"] == 300


def check_13f_keeps_only_the_requested_period(tmp):
    """One file carries late and amended filings for many quarters - the Mar-May 2026 file holds
    985 of them reaching back to 2024. Aggregating the whole file blends quarters."""
    b = _mk13f(os.path.join(tmp, "q.zip"), [
        ("A1", "111", "13F-HR", "31-MAR-2026", None, [("ACME CORP", "AAA", 100, "SH", "")]),
        ("A2", "222", "13F-HR", "31-DEC-2025", None, [("ACME CORP", "AAA", 900, "SH", "")]),
    ])
    now, _ = ic.aggregate(b, "31-MAR-2026")
    assert now["AAA"]["shares"] == 100 and now["AAA"]["holders"] == 1
    before, _ = ic.aggregate(b, "31-DEC-2025")
    assert before["AAA"]["shares"] == 900


def check_13f_ignores_notices_and_resolves_amendments(tmp):
    """13F-NT reports no holdings, so an NT filer is not a sponsor. And a RESTATEMENT supersedes
    that manager's earlier filing for the period - counting both double-counts the position,
    while NEW HOLDINGS adds to it."""
    b = _mk13f(os.path.join(tmp, "q.zip"), [
        ("N1", "999", "13F-NT", None, None, []),
        ("R0", "111", "13F-HR", None, None, [("ACME CORP", "AAA", 100, "SH", "")]),
        ("R1", "111", "13F-HR/A", None, "RESTATEMENT", [("ACME CORP", "AAA", 250, "SH", "")]),
        ("B0", "222", "13F-HR", None, None, [("ACME CORP", "AAA", 40, "SH", "")]),
        ("B1", "222", "13F-HR/A", None, "NEW HOLDINGS", [("ACME CORP", "AAA", 10, "SH", "")]),
    ])
    agg, note = ic.aggregate(b, "31-MAR-2026")
    e = agg["AAA"]
    # 250 (restated, replacing 100) + 40 + 10 (added) = 300
    assert e["shares"] == 300, (e["shares"], note)
    assert e["holders"] == 2, (e["holders"], note)
    assert "superseded" in note
    # The NT filer never reaches the holder count anyway (a notice files no INFOTABLE rows), so
    # the filter is only visible in the REPORTED manager count - which is what makes that number
    # honest rather than an inflated "managers who filed something".
    assert "2 managers" in note, note


def check_the_latest_restatement_wins_by_date_not_by_text(tmp):
    """FILING_DATE is dd-MON-yyyy. Compared as TEXT, "30-APR-2026" sorts after "05-MAY-2026" (and
    "15-DEC-2025" after "02-JAN-2026"), so the SUPERSEDED filing's holdings were counted for every
    restating manager."""
    for early, late in (("30-APR-2026", "05-MAY-2026"), ("15-DEC-2026", "02-JAN-2027")):
        b = _mk13f(os.path.join(tmp, "q.zip"), [
            ("R1", "111", "13F-HR/A", None, "RESTATEMENT", [("NVIDIA CORP", "67066G104", 100, "SH", "")]),
            ("R2", "111", "13F-HR/A", None, "RESTATEMENT", [("NVIDIA CORP", "67066G104", 999, "SH", "")])],
            filed={"R1": early, "R2": late})
        agg, _ = ic.aggregate(b, "31-MAR-2026")
        assert agg["67066G104"]["shares"] == 999, (early, late, agg["67066G104"]["shares"])
    assert ic._filed_key("05-MAY-2026") == "2026-05-05" and ic._filed_key("2026-05-05") == "2026-05-05"
    assert ic._filed_key("garbage") == "" and ic._filed_key(None) == ""


def check_new_holdings_filed_after_a_restatement_are_kept(tmp):
    """The docstring said a NEW HOLDINGS amendment "adds and is kept alongside", but only the single
    latest restatement was kept, so holdings filed after it were dropped. Anything filed BEFORE
    the restatement is what it replaced."""
    rows = [("O", "111", "13F-HR", None, None, [("NVIDIA CORP", "67066G104", 100, "SH", "")]),
            ("R", "111", "13F-HR/A", None, "RESTATEMENT", [("NVIDIA CORP", "67066G104", 200, "SH", "")]),
            ("Before", "111", "13F-HR/A", None, "NEW HOLDINGS", [("ORACLE CORP", "68389X105", 7, "SH", "")]),
            ("After", "111", "13F-HR/A", None, "NEW HOLDINGS", [("APPLE INC", "037833100", 50, "SH", "")])]
    b = _mk13f(os.path.join(tmp, "q.zip"), rows,
               filed={"O": "01-APR-2026", "Before": "05-APR-2026", "R": "10-APR-2026", "After": "20-APR-2026"})
    agg, note = ic.aggregate(b, "31-MAR-2026")
    assert {k: v["shares"] for k, v in agg.items()} == {"67066G104": 200, "037833100": 50}, agg
    assert "2 superseded" in note, note                     # the original and the pre-restatement addition


def check_a_corrupt_archive_member_fails_open(tmp):
    """Only opening the zip was guarded, so a download damaged INSIDE a member (a bad CRC) escaped
    as a traceback and exit 1 - no cache written, --fallback never merged - against the module's
    own promise to fail open."""
    import zipfile
    path = os.path.join(tmp, "c.zip")
    z = zipfile.ZipFile(path, "w", zipfile.ZIP_STORED)
    z.writestr("SUBMISSION.tsv", "ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tCIK\tPERIODOFREPORT\n"
                                 "A\t01-MAY-2026\t13F-HR\t1\t31-MAR-2026")
    z.writestr("COVERPAGE.tsv", "ACCESSION_NUMBER\tAMENDMENTTYPE\nA\t")
    z.writestr("INFOTABLE.tsv", "ACCESSION_NUMBER\tNAMEOFISSUER\tCUSIP\tVALUE\tSSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL\n"
               + "".join("A\tNVIDIA CORP\t67066G104\t1\t5\tSH\t\n" for _ in range(200)))
    z.close()
    good = io.open(path, "rb").read()
    assert ic.aggregate(good, "31-MAR-2026")[0], "the fixture itself is unreadable"
    bad = bytearray(good)
    bad[bad.find(b"A\tNVIDIA CORP", bad.find(b"INFOTABLE.tsv")) + 3] ^= 0x01     # one flipped byte
    agg, why = ic.aggregate(bytes(bad), "31-MAR-2026")
    assert agg is None and "unreadable" in why, (agg, why)
    agg, why = ic.aggregate(good[: len(good) // 2], "31-MAR-2026")                  # cut short
    assert agg is None and why, (agg, why)


def check_a_quote_in_an_issuer_name_does_not_swallow_rows(tmp):
    """SEC's files are tab-separated with no quoting. With the csv default, a name that BEGINS with a
    quote opened a quoted field that ran across tabs and newlines and swallowed every row after it."""
    b = _mk13f(os.path.join(tmp, "q.zip"), [
        ("B", "2", "13F-HR", None, None, [('"BIG 5 SPORTING', "11111111A", 5, "SH", ""),
                                          ("APPLE INC", "037833100", 7, "SH", ""),
                                          ("MICROSOFT CORP", "594918104", 9, "SH", "")])])
    agg, _ = ic.aggregate(b, "31-MAR-2026")
    assert set(agg) == {"11111111A", "037833100", "594918104"}, sorted(agg)


def check_get_dataset_only_caches_a_real_zip(tmp):
    """A proxy or error page returned with a 200 and over 1000 bytes passed the size-only check and
    was saved under the data set's name - then served as "cached" on every run, one HTTP call in
    total, until someone found and deleted it."""
    cache = os.path.join(tmp, "cache")
    ds = {"name": "01mar2026-31may2026_form13f.zip", "url": "https://www.sec.gov/x.zip"}
    calls = []
    real = ic.http
    def serve(body):
        def f(url, c, t, retries=6):
            calls.append(url)
            return body, None
        return f
    try:
        ic.http = serve(b"<html>" + b"x" * 2000 + b"</html>")
        data, where = ic.get_dataset(ds, "me@example.org", 5, cache)
        assert data is None and "not a zip" in where, (data, where)
        assert not os.path.exists(os.path.join(cache, ds["name"])), "an error page was cached"
        ic.get_dataset(ds, "me@example.org", 5, cache)
        assert len(calls) == 2, "the failure was remembered instead of retried"

        os.makedirs(cache, exist_ok=True)                     # an already-poisoned cache heals
        io.open(os.path.join(cache, ds["name"]), "wb").write(b"<html>" + b"y" * 2000)
        ic.http = serve(b"PK" + b"z" * 2000)
        data, where = ic.get_dataset(ds, "me@example.org", 5, cache)
        assert data and data[:2] == b"PK" and not where.startswith("cached"), where
        data, where = ic.get_dataset(ds, "me@example.org", 5, cache)
        assert where.startswith("cached"), "a good zip was not reused"
        assert not [f for f in os.listdir(cache) if f.endswith(".tmp")], "a temp file was left behind"
    finally:
        ic.http = real


def check_prior_quarter_reads_an_iso_date_and_a_bad_month_is_a_value_error():
    """--quarter takes '2026-03-31' (period_end does), and --prior is "derived from --quarter" - but
    prior_quarter returned None for that form, which meant NO PRIOR QUARTER: every grade capped at
    partial for want of a trend, with nothing saying the date form was why. A month of 13 raised a
    KeyError, which build() (it catches ValueError) does not catch."""
    assert ic.prior_quarter("2026-03-31") == "2025Q4" and ic.prior_quarter("2026-06-30") == "2026Q1"
    assert ic.prior_quarter("2026Q3") == "2026Q2" and ic.prior_quarter("nonsense") is None
    assert ic.prior_quarter("2026-13-01") is None
    for bad in ("2026-13-01", "2026-00-10"):
        try:
            ic.period_end(bad)
        except ValueError:
            continue
        raise AssertionError("%s did not raise ValueError" % bad)


def check_a_no_reply_contact_is_refused_with_a_reason():
    """Measured against SEC (see the module comment): x@users.noreply.github.com is a 403 though it
    parses fine. Only that documented case is refused - you@your-domain.com measured 200."""
    c, why = ic.resolve_contact("x@users.noreply.github.com")
    assert c is None and "no-reply" in why, (c, why)
    assert ic.resolve_contact("noreply@mycompany.com")[0] is None
    assert ic.resolve_contact("you@your-domain.com") == ("you@your-domain.com", None)
    assert ic.resolve_contact("me@example.org") == ("me@example.org", None)


def check_a_failed_build_keeps_a_good_cache_of_the_same_quarter_only(tmp):
    """A failed build overwrote the cache with an empty one, so an SEC outage destroyed the right
    answer. It must NOT keep any old cache, though: a cache from last quarter would grade
    sponsorship from last quarter without saying so, which is why it is rebuilt each quarter."""
    out = os.path.join(tmp, "i-cache.json")
    good = lambda quarter: json.dumps({"meta": {"ok": True, "quarter": quarter},
                                       "known": {"NVDA": {"I": "pass"}}, "detail": {}})
    real_http, real_argv = ic.http, sys.argv
    ic.http = lambda *a, **k: (None, "down")
    try:
        def run():
            sys.argv = ["x", "--quarter", "2026Q1", "--contact", "me@mydomain.org", "-o", out,
                        "--cache-dir", os.path.join(tmp, "c")]
            err = io.StringIO()
            real_err, sys.stderr = sys.stderr, err
            try:
                return ic.main(), err.getvalue()
            finally:
                sys.stderr = real_err
        io.open(out, "w", encoding="utf-8").write(good("2026Q1"))
        rc, err = run()
        assert rc == 0 and json.load(io.open(out))["known"] == {"NVDA": {"I": "pass"}}, "a good cache was destroyed"
        assert "KEPT" in err, err

        io.open(out, "w", encoding="utf-8").write(good("2025Q4"))          # last quarter's: replaced
        run()
        assert json.load(io.open(out))["known"] == {} and not json.load(io.open(out))["meta"]["ok"], \
            "last quarter's cache was kept and would be graded as this quarter's"
        assert not [f for f in os.listdir(tmp) if f.endswith(".tmp")], "a temp file was left behind"
    finally:
        ic.http, sys.argv = real_http, real_argv


def check_gzip_is_undone_before_parsing():
    """The bug that made discovery report "the page has no links". urllib returns the RAW encoded
    bytes for the gzip we asked for; curl decompresses transparently, so the same URL behaves
    differently on the command line and is easy to mis-diagnose as an empty page."""
    import gzip as _g
    raw = b'<a href="/x/01mar2026-31may2026_form13f.zip">z</a>'
    assert ic.maybe_gunzip(_g.compress(raw)) == raw
    assert ic.maybe_gunzip(raw) == raw          # not compressed: passed through untouched


def check_sector_screen_derives_its_thresholds_from_the_shared_rubric():
    """scripts/rubric.py is shared VERBATIM with can-slim-grader, so every threshold it owns must
    reach sector_screen.py by import, never by being typed again.

    Restating them is exactly how the pair drifted: the same "10% below the 52-week high" meant
    N<=partial in one skill and N=fail in the other, and nothing failed until a human read both
    files side by side. A second copy inside THIS repo is the same hazard one level down."""
    import rubric
    assert ss.WEIGHT is rubric.WEIGHT, "the scoring weights must BE the shared ones, not a copy"
    for key, shared in (("min_price", rubric.MIN_PRICE),
                        ("min_dollar_vol", rubric.MIN_DOLLAR_VOL),
                        ("max_off_high", rubric.TRIAGE_DROP_PCT),
                        ("min_rs", rubric.MIN_RS),
                        ("threshold", rubric.QUALIFY_THRESHOLD),
                        ("pivot_band", rubric.PIVOT_BAND_PCT),
                        ("thin_vol", rubric.THIN_VOL)):
        assert ss.DEFAULTS[key] == shared, (key, ss.DEFAULTS[key], shared)
    # N's fail line is twice the pivot band in both repos; the sister states it outright.
    assert rubric.N_FAIL_PCT == 2 * rubric.PIVOT_BAND_PCT, (rubric.N_FAIL_PCT, rubric.PIVOT_BAND_PCT)


def check_parity_with_the_sister_skill(tmp):
    """Run scripts/check_parity.py against a can-slim-grader checkout - 100 RANDOM tickers plus
    the exhaustive arithmetic sweep - and fail if the two skills would grade the same evidence
    differently.

    WHY THIS EXISTS AS A TEST AND NOT A CHORE. The pair's whole premise is that a screened idea
    and a graded ticker are comparable, so "4.5/7" has to mean one thing. The sister ships its own
    check_parity.py and its docstring is candid that it cannot do this: it hashes two files in its
    own tree and "cannot see a material change that lives somewhere other than a shared file - a
    threshold reworded in SKILL.md ... a changed pivot definition. Those are the common case."
    Byte tripwires do not notice that one skill started failing N at 10% below the high while the
    other still graded it partial.

    THE SEED IS FRESH ON PURPOSE. The arithmetic layer is exhaustive over all 3^7 scorecards, so
    deterministic coverage is already guaranteed and does not need a fixed seed; the random layer's
    job is to keep exploring messy authored input (capitalised, padded, blank, unknown), and it
    only does that if each run draws a different sample. A failure prints its seed, so
    `--seed N` reproduces it exactly.
    """
    import random as _r
    import subprocess as _sp
    grader = None
    for cand in (os.environ.get("CANSLIM_GRADER") or "",
                 os.path.join(os.path.dirname(ROOT), "can-slim-grader"),
                 "/home/user/thewongdirection/can-slim-grader",
                 "/home/user/can-slim-grader"):
        if cand and os.path.exists(os.path.join(cand, "assets", "evaluation_template.html")):
            grader = cand
            break
    if not grader:
        return ("skipped - no can-slim-grader checkout to compare against. This suite takes no "
                "network, so clone it once and the check runs from then on: "
                "git clone --depth 1 https://github.com/thewongdirection/can-slim-grader "
                "(or set CANSLIM_GRADER). REQUIRED before shipping any change to the rubric, the "
                "scoring arithmetic or a shared file.")
    script = os.path.join(ROOT, "scripts", "check_parity.py")
    if not os.path.exists(script):
        return "skipped: no check_parity.py in this copy (a portable bundle)"
    seed = _r.randrange(1 << 30)
    r = _sp.run([sys.executable, script, "--grader", grader, "--tickers", "100",
                 "--seed", str(seed), "--json"],
                stdout=_sp.PIPE, stderr=_sp.PIPE, timeout=300)
    if r.returncode == 2:
        return "skipped - check_parity.py could not find the sister: " + r.stderr.decode()[:200]
    report = json.loads(r.stdout.decode("utf-8"))
    bad = [l for l in report["layers"] if l["ok"] is False]
    assert not bad, ("the two skills disagree (seed %d - rerun with --seed %d to reproduce):\n%s"
                     % (seed, seed, json.dumps(bad, indent=1)[:1800]))
    # A layer that SKIPPED is not a pass. node drives the two templates' real scoring code, so
    # without it the only thing actually compared is the file hashes.
    skipped = [l["name"] for l in report["layers"] if l["ok"] is None]
    if skipped:
        return "skipped - parity layers could not run: " + ", ".join(skipped)


def check_the_upgrade_path_requires_the_parity_check(tmp):
    """A check nobody is told to run is a check that stops running. The instructions must name
    scripts/check_parity.py as part of shipping a change, or this guard fails."""
    hits = []
    for rel in ("SKILL.md", "README.md", "references/tradingview-sector-sweep.md"):
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            if "check_parity.py" in io.open(p, encoding="utf-8").read():
                hits.append(rel)
    assert hits, ("no instruction file mentions scripts/check_parity.py, so nothing tells a "
                  "future change to verify the sister skill still grades the same way")


def _xbrl(rows, fy=2025, fp="FY"):
    """An XBRL companyconcept payload from (start, end, val, filed) tuples.

    Every row carries the SAME `fy`/`fp`, which is what a real 10-K does to its comparative
    prior-year figures - and is the whole reason keying on `fy` is wrong. Without these fields
    in the fixture a mutant that keys on fy falls back to the end date and the test passes
    while proving nothing; it did exactly that until this was added.
    """
    return json.dumps({"units": {"USD/shares": [
        {"start": s, "end": e, "val": v, "filed": f, "fy": fy, "fp": fp}
        for s, e, v, f in rows]}}).encode("utf-8")


def check_annual_eps_keys_on_period_end_not_the_filing_fiscal_year():
    """XBRL's `fy`/`fp` describe the FILING's fiscal focus, so a 10-K tags its comparative
    prior-year figures with the SAME fy as the current year. Keying on fy collapses three
    distinct years into one bucket and an arbitrary member wins: Micron came out with a FY2025
    EPS of -5.34 that is really its FY2023 loss, and the series still LOOKED plausible.

    Here one filing reports three years, all stamped fy=2025. Keying on the period end must
    keep all three, in order."""
    body = _xbrl([
        ("2022-09-01", "2023-08-31", 1.00, "2025-10-01"),
        ("2023-09-01", "2024-08-31", 2.00, "2025-10-01"),
        ("2024-09-01", "2025-08-31", 3.00, "2025-10-01"),
    ])
    got = aeps.parse_annual(body, aeps.DEFAULTS)
    assert sorted(got.items()) == [("2023-08-31", 1.0), ("2024-08-31", 2.0), ("2025-08-31", 3.0)], got


def check_annual_eps_takes_the_latest_filing_for_a_restated_year():
    """Same period end filed twice - the restatement (later `filed`) supersedes."""
    body = _xbrl([("2024-01-01", "2024-12-31", 5.00, "2025-02-01"),
                  ("2024-01-01", "2024-12-31", 4.10, "2025-11-01")])
    assert aeps.parse_annual(body, aeps.DEFAULTS) == {"2024-12-31": 4.10}


def check_annual_eps_ignores_quarters_and_keeps_odd_length_fiscal_years():
    """A quarter is not a year, and a 52/53-week retailer's year is not exactly 365 days."""
    body = _xbrl([("2025-01-01", "2025-03-31", 0.25, "2025-05-01"),   # a quarter
                  ("2024-01-01", "2024-12-31", 1.00, "2025-02-01"),   # 365 days
                  ("2023-01-29", "2024-02-03", 2.00, "2024-03-01")])  # 53-week year
    got = aeps.parse_annual(body, aeps.DEFAULTS)
    assert sorted(got) == ["2024-02-03", "2024-12-31"], got


def check_annual_eps_does_not_require_the_fp_field():
    """20-F/40-F filers frequently leave `fp` unset. Requiring fp == "FY" silently dropped
    every IFRS filer - ArcelorMittal, TORM, Teck - and they read as "no data"."""
    body = json.dumps({"units": {"USD/shares": [
        {"start": "2024-01-01", "end": "2024-12-31", "val": 2.5, "filed": "2025-03-01"}]}}
    ).encode("utf-8")
    assert aeps.parse_annual(body, aeps.DEFAULTS) == {"2024-12-31": 2.5}


def check_A_grades_follow_the_three_year_rule():
    """pass needs EVERY step at >=25%; all-positive-but-short is partial; any down year fails."""
    def g(vals, today="2026-03-01", roe=31.0):
        # A qualifying ROE by default, so this test isolates the EPS-growth leg; the ROE leg has
        # its own test. Passing no ROE would cap every case at partial and hide the EPS rule.
        ends = ["2022-12-31", "2023-12-31", "2024-12-31", "2025-12-31"]
        return aeps.grade(dict(zip(ends, vals)), aeps.DEFAULTS,
                          today=_dt.date.fromisoformat(today), roe=roe)[0]

    assert g([1.0, 1.30, 1.70, 2.20]) == "pass"       # +30, +31, +29
    assert g([1.0, 1.30, 1.70, 1.90]) == "partial"    # last step +12: up, but under 25
    assert g([1.0, 1.30, 1.20, 2.00]) == "fail"       # a down year
    # AVT: the case that made TTM growth the wrong test - +46% TTM, but FY2025 fell 49%.
    assert g([8.26, 5.43, 2.75, 4.01]) == "fail"


def check_annual_eps_only_hands_the_ceiling_what_the_filings_decided(tmp):
    """The module promises "an absence of data can never eliminate a name", but every partial was
    written to --known, where a known partial is a real cap: a marginal name with N, S and L at
    partial sits exactly on the 4.5 cut, so one stray A=partial (no CIK, a stale series, ROE not
    passed in) put it at 4.0 and it was dropped without being graded."""
    cfg = aeps.DEFAULTS
    d = aeps.decides
    assert d("pass", [30, 30, 30], cfg, 20.0) and d("fail", [30, -5, 30], cfg, 20.0)
    assert d("partial", [30, 12, 30], cfg, 20.0), "EPS up but not every year >=25% is audited evidence"
    assert d("partial", [30, 30, 30], cfg, 9.0), "ROE under the bar is evidence"
    assert not d("partial", [], cfg, 20.0), "too few years / stale: the filings cannot tell"
    assert not d("partial", [30, None, 30], cfg, 20.0), "a loss year makes growth undefined"
    assert not d("partial", [30, 30, 30], cfg, None), "EPS passes but ROE unverified is not a verdict"

    eps_pass = {"2022-12-31": 1.0, "2023-12-31": 1.3, "2024-12-31": 1.7, "2025-12-31": 2.2}
    series = {"AAA": {}, "BBB": eps_pass, "CCC": {"2022-12-31": 1.0, "2023-12-31": 1.3, "2024-12-31": 1.2,
                                                  "2025-12-31": 2.0}}
    real = (aeps.load_tickers, aeps.annual_eps)
    aeps.load_tickers = lambda *a, **k: {"BBB": 1, "CCC": 2}           # AAA has no CIK at all
    aeps.annual_eps = lambda cik, *a, **k: series[{1: "BBB", 2: "CCC"}[cik]]
    try:
        out = aeps.run(["NYSE:AAA", "NYSE:BBB", "NYSE:CCC"], tmp, "me@example.com", cfg, roes={})
    finally:
        aeps.load_tickers, aeps.annual_eps = real
    assert set(out["known"]) == {"NYSE:CCC"} and out["known"]["NYSE:CCC"] == {"A": "fail"}, out["known"]
    withheld = " ".join(out["meta"]["ungraded"])
    assert "AAA" in withheld and "BBB" in withheld, "withheld names must be listed with their reason"
    assert set(out["detail"]) == {"NYSE:AAA", "NYSE:BBB", "NYSE:CCC"}, "a withheld name vanished from detail"


def check_a_missing_fiscal_year_is_not_bridged(tmp):
    """`consecutive` collapses duplicates but never checked the years it kept were ADJACENT, so with
    FY2023 absent, FY2022 -> FY2024 was scored as one annual step: +30%, +31%, +29% PASSED while
    the real growth was 13.8% a year. A missing year is a gap in the evidence, not a result."""
    today = _dt.date(2025, 6, 1)
    gappy = {"2020-12-31": 1.00, "2021-12-31": 1.30, "2022-12-31": 1.70, "2024-12-31": 2.20}
    g, why, series, steps = aeps.grade(gappy, aeps.DEFAULTS, today=today, roe=20.0)
    assert g == "partial" and "missing" in why, (g, why)
    assert not aeps.decides(g, steps, aeps.DEFAULTS, 20.0), "a gap must not reach the ceiling"
    full = {"2021-12-31": 1.00, "2022-12-31": 1.30, "2023-12-31": 1.70, "2024-12-31": 2.20}
    assert aeps.grade(full, aeps.DEFAULTS, today=today, roe=20.0)[0] == "pass"
    # 52/53-week filers drift their year-end by days; that is still adjacent years
    retail = {"2021-12-26": 1.00, "2022-12-31": 1.30, "2024-01-06": 1.70, "2024-12-28": 2.20}
    assert aeps.grade(retail, aeps.DEFAULTS, today=today, roe=20.0)[0] == "pass"


def check_only_what_sec_answered_is_cached(tmp):
    """A 503, 403 or timeout was written to disk as b'{}', so one bad minute left
    company_tickers.json empty for good (every later run: "no CIK" for every name) and a 403 on a
    concept file left that name ungraded permanently. A 404 IS an answer and stays cached."""
    path = os.path.join(tmp, "c", "x.json")
    calls = []
    def fetch(result):
        def f():
            calls.append(1)
            return result
        return f
    assert aeps._cached(path, fetch((None, "HTTP 503")), pause=0) == b"{}"
    assert not os.path.exists(path), "a failure was cached"
    assert aeps._cached(path, fetch((b'{"ok":1}', None)), pause=0) == b'{"ok":1}'
    n = len(calls)
    assert aeps._cached(path, fetch((None, "never")), pause=0) == b'{"ok":1}' and len(calls) == n, \
        "a good cache entry was refetched"

    nf = os.path.join(tmp, "c", "404.json")
    assert aeps._cached(nf, fetch((None, "HTTP 404")), pause=0) == b"{}"
    n = len(calls)
    assert aeps._cached(nf, fetch((b"x", None)), pause=0) == b"{}" and len(calls) == n, \
        "a 404 (the filer does not report this tag) must be remembered"

    # entries expire; and if the refresh fails, the older copy beats an empty answer
    old = time.time() - 31 * 86400
    os.utime(path, (old, old))
    assert aeps._cached(path, fetch((b'{"ok":2}', None)), pause=0) == b'{"ok":2}', "a stale entry was served"
    os.utime(path, (old, old))
    assert aeps._cached(path, fetch((None, "HTTP 503")), pause=0) == b'{"ok":2}', \
        "a failed refresh threw the stale copy away"

    # end to end, the case that bit: the registrant list during an SEC blip, then recovery
    real = aeps.http
    d = os.path.join(tmp, "e2e")
    try:
        aeps.http = lambda *a, **k: (None, "HTTP 503")
        assert aeps.load_tickers(d, "me@example.com") == {}
        aeps.http = lambda *a, **k: (json.dumps({"0": {"ticker": "NVDA", "cik_str": 1045810}}).encode(), None)
        assert aeps.load_tickers(d, "me@example.com") == {"NVDA": "0001045810"}, \
            "the registrant list stayed empty after SEC recovered"
    finally:
        aeps.http = real


def check_A_needs_both_legs_eps_growth_and_roe():
    """The rubric is "EPS up each of 3 years at >=25% AND ROE >=17%". Grading the EPS leg alone
    is an over-grade, and it is one can-slim-grader does not make - working a single ticker it
    checks both - so the same name scored A=pass here and A=partial there.

    DELL is the live case: EPS up 42/39/36% on the filings, but negative book equity, so its ROE
    is not a number and the pass is not earned. An unverifiable ROE caps A at partial; it never
    fails the letter, because "we could not check" is not evidence against."""
    ends = ["2022-12-31", "2023-12-31", "2024-12-31", "2025-12-31"]
    strong = dict(zip(ends, [1.0, 1.30, 1.70, 2.20]))      # +30, +31, +29 - the EPS leg clears
    day = _dt.date.fromisoformat("2026-03-01")

    assert aeps.grade(strong, aeps.DEFAULTS, today=day, roe=31.0)[0] == "pass"
    for roe in (None, 0.0, 16.9):
        g, why, _, _ = aeps.grade(strong, aeps.DEFAULTS, today=day, roe=roe)
        assert g == "partial", (roe, g, why)
        assert "ROE" in why, why


def check_A_never_fails_on_an_absence_of_evidence():
    """A `fail` from this script prunes a name in the ceiling, so it must mean "the filings
    answer the question and the answer is no" - never "the filings could not answer".

    Too few years, a loss year (growth undefined) and a series that stops long ago are all
    gaps in the evidence and must grade partial."""
    import datetime as _d
    today = _d.date.fromisoformat("2026-03-01")
    ends = ["2022-12-31", "2023-12-31", "2024-12-31", "2025-12-31"]

    short = aeps.grade({"2024-12-31": 1.0, "2025-12-31": 2.0}, aeps.DEFAULTS, today=today)
    assert short[0] == "partial" and "fiscal year" in short[1], short

    loss = aeps.grade(dict(zip(ends, [-1.0, 0.5, 1.0, 2.0])), aeps.DEFAULTS, today=today)
    assert loss[0] == "partial" and "loss" in loss[1], loss

    stale = aeps.grade(dict(zip(["2018-12-31", "2019-12-31", "2020-12-31", "2021-12-31"],
                                [1.0, 1.4, 1.9, 2.6])), aeps.DEFAULTS, today=today)
    assert stale[0] == "partial" and "stale" in stale[1], stale


def check_annual_eps_merges_tags_instead_of_racing_them():
    """A filer changes EPS tag over time, so one tag rarely spans the whole history. Eton
    reports EarningsPerShareDiluted quarterly only, BasicAndDiluted annually for 2018-2021 and
    Basic annually for 2022-2025 - so "first tag with any rows wins" returns either nothing or
    a series that stops in 2021, and the years the test needs live in the third tag.

    The preferred tag must still win a period end both report."""
    facts = {"us-gaap": {
        "EarningsPerShareDiluted": {"units": {"USD/shares": [
            {"start": "2025-01-01", "end": "2025-03-31", "val": 0.1, "filed": "2025-05-01"},
            {"start": "2025-01-01", "end": "2025-12-31", "val": 9.99, "filed": "2026-02-01"}]}},
        "EarningsPerShareBasic": {"units": {"USD/shares": [
            {"start": "2023-01-01", "end": "2023-12-31", "val": 1.0, "filed": "2024-02-01"},
            {"start": "2024-01-01", "end": "2024-12-31", "val": 2.0, "filed": "2025-02-01"},
            {"start": "2025-01-01", "end": "2025-12-31", "val": 8.88, "filed": "2026-02-01"}]}},
    }}
    got = {}
    for ns, tag in aeps.CONCEPTS:
        hit = (facts.get(ns) or {}).get(tag)
        if hit:
            aeps._fill(got, aeps.parse_annual(
                json.dumps({"units": hit["units"]}).encode("utf-8"), aeps.DEFAULTS))
    assert sorted(got) == ["2023-12-31", "2024-12-31", "2025-12-31"], got
    # diluted is preferred, so it keeps 2025 even though basic also reports it
    assert got["2025-12-31"] == 9.99, got


def check_symbol_input_shapes_are_all_understood():
    """A plain list, sector_screen.py's output and a raw sweep payload are all things a caller
    has lying around; guessing wrong is a silent empty run, not an error."""
    assert aeps.symbols_from(["NASDAQ:AAPL"]) == ["NASDAQ:AAPL"]
    assert aeps.symbols_from({"grade_queue": [{"symbol": "NYSE:X"}]}) == ["NYSE:X"]
    assert aeps.symbols_from({"sectors": {"Tech": [{"symbol": "NASDAQ:Y"}]}}) == ["NASDAQ:Y"]
    assert aeps.symbols_from({"nothing": 1}) == []


def check_sec_contact_is_required_before_any_request_goes_out():
    """SEC 403s a User-Agent without a real contact address, and the old default shipped a
    PLACEHOLDER ("contact: set --contact") that looked configured and was not. Every read 403d,
    and the run still wrote a well-formed cache with zero tickers - an answer-shaped file that
    graded nothing, whose only clue was an HTTP code that reads like a firewall problem.

    So the contract is: a missing or non-email contact is caught LOCALLY, before a request is
    spent, and the reason names the flag to set."""
    assert ic.resolve_contact("me@example.com") == ("me@example.com", None)

    for bad in ("", None, "   ", "set --contact", "not-an-email", "a@b"):
        got, why = ic.resolve_contact(bad)
        assert got is None, "%r should not be accepted as a contact" % (bad,)
        assert "--contact" in why, why          # the message must name the fix

    # The env var is the configure-once path, and an explicit --contact still wins over it.
    import os as _os
    old = _os.environ.get("SEC_CONTACT")
    try:
        _os.environ["SEC_CONTACT"] = "env@example.com"
        assert ic.resolve_contact("") == ("env@example.com", None)
        assert ic.resolve_contact("cli@example.com") == ("cli@example.com", None)
    finally:
        if old is None:
            _os.environ.pop("SEC_CONTACT", None)
        else:
            _os.environ["SEC_CONTACT"] = old


def check_a_bad_contact_never_reaches_the_network():
    """The check above is only worth anything if http() actually honours it: a placeholder that
    still gets sent costs a 403 and an error pointing at the wrong layer. urlopen is replaced
    with a detonator, so a single escaping request fails the test."""
    import urllib.request as _u
    old = _u.urlopen

    def boom(*a, **k):                      # pragma: no cover - reaching this IS the failure
        raise AssertionError("http() sent a request with no usable contact")

    _u.urlopen = boom
    old_env = __import__("os").environ.pop("SEC_CONTACT", None)
    try:
        body, why = ic.http("https://www.sec.gov/files/company_tickers.json", "", 5)
        assert body is None and "--contact" in why, why
    finally:
        _u.urlopen = old
        if old_env is not None:
            __import__("os").environ["SEC_CONTACT"] = old_env


def check_dataset_names_parse_under_both_sec_schemes():
    """SEC renamed these files in 2024, from the holdings quarter to the window in which filings
    were RECEIVED. The original guessed URL 404s for every quarter after 2023 - which is why the
    list is discovered from SEC's index page rather than constructed."""
    assert ic.parse_dataset_name("2023q4_form13f.zip") == ("2023-10-01", "2023-12-31")
    assert ic.parse_dataset_name("01mar2026-31may2026_form13f.zip") == ("2026-03-01", "2026-05-31")
    assert ic.parse_dataset_name("readme.txt") is None


def check_the_right_dataset_is_picked_for_a_quarter():
    """A quarter's 13Fs arrive in the window AFTER it ends, so 31-MAR-2026 holdings live in the
    Mar-May 2026 file. Picking by name would take the wrong file under the post-2024 scheme."""
    ds = [{"name": "01jun2026-31aug2026_form13f.zip", "start": "2026-06-01", "end": "2026-08-31"},
          {"name": "01mar2026-31may2026_form13f.zip", "start": "2026-03-01", "end": "2026-05-31"},
          {"name": "01dec2025-28feb2026_form13f.zip", "start": "2025-12-01", "end": "2026-02-28"}]
    assert ic.period_end("2026Q1") == "31-MAR-2026"
    assert ic.period_end("2026-03-31") == "31-MAR-2026"
    assert ic.prior_quarter("2026Q1") == "2025Q4"
    assert ic.dataset_for_period(ds, "31-MAR-2026")["name"] == "01mar2026-31may2026_form13f.zip"
    assert ic.dataset_for_period(ds, "31-DEC-2025")["name"] == "01dec2025-28feb2026_form13f.zip"
    assert ic.dataset_for_period(ds, "31-DEC-2030") is None      # nothing published yet


def check_sec_ticker_map_builds_a_market_wide_universe(tmp):
    """CUSIPs resolve against a ticker->name map, and which map you hand it decides how much of
    the market the cache covers. SEC's own company_tickers.json carries every US registrant
    (~10k), which is what makes this a QUARTERLY artifact rather than a per-run one - a cache
    built from a single sweep's candidates only ever answers for that sweep.
    """
    ct = os.path.join(tmp, "ct.json")
    io.open(ct, "w", encoding="utf-8").write(json.dumps({
        "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
        "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}))
    zp = os.path.join(tmp, "q.zip")
    _mk13f(zp, [("A%d" % i, str(100 + i), "13F-HR", None, None,
                 [("NVIDIA CORPORATION", "67066G104", 1000, "SH", ""),
                  ("APPLE INC", "037833100", 500, "SH", "")]) for i in range(25)])

    class A:
        quarter, prior = "2026Q1", None
        universe = cusip_map = None
        sec_tickers = ct
        cache_dir = tmp
        contact, timeout = "", 5

    # point the picker at the local zip by naming it as the dataset the quarter resolves to
    real_list, real_pick = ic.list_datasets, ic.dataset_for_period
    ic.list_datasets = lambda *a: ([{"name": "q.zip", "start": "2026-04-01",
                                     "end": "2026-05-31", "url": "file://" + zp}], None)
    ic.dataset_for_period = lambda ds, period: ds[0]
    try:
        meta, known, detail, un = ic.build(A(), dict(ic.DEFAULTS))
    finally:
        ic.list_datasets, ic.dataset_for_period = real_list, real_pick

    assert any("company_tickers.json" in n for n in meta["notes"]), meta["notes"]
    assert set(known) == {"NVDA", "AAPL"}, known
    assert detail["NVDA"]["holders"] == 25
    # no prior quarter means the TREND is unverified, and an unverified trend is never a pass
    assert all(v["grade"] == "partial" for v in detail.values()), detail
    assert any("NO PRIOR QUARTER" in n for n in meta["notes"]), meta["notes"]


def check_13f_fails_open_when_it_cannot_fetch(tmp):
    """No network, a moved URL, an egress policy - none of these may stop a run."""
    class A:
        quarter, prior = "2099Q4", "2099Q3"
        universe = cusip_map = None
        cache_dir = os.path.join(tmp, "nope")
        contact, timeout = "", 0.2
    meta, known, detail, un = ic.build(A(), dict(ic.DEFAULTS))
    assert meta["ok"] is False and known == {} and detail == {}
    assert meta["notes"], "a failure must say what it could not do"


def check_dataset_links_must_stay_on_the_sec_host():
    """Each request carries the user's contact address in its User-Agent, so a dataset link that
    leaves www.sec.gov hands that address to someone else. String concatenation could not prevent
    it: "https://www.sec.gov" + "@evil.example/x" is a URL whose host is evil.example, and an
    absolute or protocol-relative href passed straight through."""
    page = (b'<a href="@evil.invalid/01jan2026-31mar2026_form13f.zip">at-sign</a>'
            b'<a href="http://evil.invalid/01apr2026-30jun2026_form13f.zip">absolute</a>'
            b'<a href="//evil.invalid/01jul2026-30sep2026_form13f.zip">proto-relative</a>'
            b'<a href="https://evil.invalid/01oct2025-31dec2025_form13f.zip">https</a>'
            b'<a href="/files/dera/data/form-13f/01jan2025-31mar2025_form13f.zip">genuine</a>')
    real = ic.http
    ic.http = lambda *a, **k: (page, None)
    try:
        datasets, _ = ic.list_datasets("me@example.com", 5)
    finally:
        ic.http = real
    assert datasets, "the genuine link was rejected too"
    for d in datasets:
        host = urllib.parse.urlsplit(d["url"])
        assert host.scheme == "https" and host.hostname == "www.sec.gov", d["url"]
    assert any("form-13f" in d["url"] for d in datasets), "lost the genuine link"


def check_a_403_message_never_echoes_the_contact_address():
    """The failure text goes into the cache's notes and stdout, and from there can be pasted into
    a report that gets shared. It said which User-Agent was rejected - address included."""
    import urllib.error
    import urllib.request
    me = "private.person@example.org"

    def boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
    real = urllib.request.urlopen
    urllib.request.urlopen = boom
    try:
        body, why = ic.http("https://www.sec.gov/x", me, 5)
    finally:
        urllib.request.urlopen = real
    assert body is None and "403" in why, why
    assert me not in why and "example.org" not in why, "the contact address leaked: %s" % why


def check_issuer_name_matching_and_its_refusal_to_guess():
    assert ic.norm_name("NVIDIA CORPORATION") == ic.norm_name("NVIDIA Corp")
    assert ic.norm_name("Laggard Industries, Inc.") == ic.norm_name("LAGGARD INDUSTRIES INC")
    agg = {"C1": {"name": "AMBIGUOUS HOLDINGS", "shares": 1.0, "holders": 30, "value": 1.0},
           "C2": {"name": "NVIDIA CORPORATION", "shares": 1.0, "holders": 40, "value": 1.0}}
    # two tickers claiming the same normalised name must resolve to NEITHER - a wrong ticker
    # attaches one company's sponsorship to another's scorecard
    by, un = ic.resolve_tickers(agg, {}, {"AMB": "Ambiguous Holdings", "AMB2": "Ambiguous Holdings",
                                          "NVDA": "NVIDIA Corp"})
    assert "NVDA" in by and "AMB" not in by and "AMB2" not in by
    assert [u["cusip"] for u in un] == ["C1"]


def check_share_classes_collapse_onto_one_ticker():
    agg = {"C1": {"name": "DUAL CO", "shares": 100.0, "holders": 30, "value": 1.0},
           "C2": {"name": "DUAL CO", "shares": 50.0, "holders": 25, "value": 1.0}}
    by, _ = ic.resolve_tickers(agg, {"C1": "DUAL", "C2": "DUAL"}, {})
    assert by["DUAL"]["shares"] == 150.0 and by["DUAL"]["holders"] == 30
    assert sorted(by["DUAL"]["cusips"]) == ["C1", "C2"]


def check_13f_grades_follow_the_rubric():
    cfg = dict(ic.DEFAULTS)
    rise = ic.grade({"holders": 60, "shares": 100.0}, {"holders": 52, "shares": 80.0}, cfg)
    assert rise[0] == "pass", rise
    drop = ic.grade({"holders": 30, "shares": 50.0}, {"holders": 38, "shares": 90.0}, cfg)
    assert drop[0] == "fail", drop
    flat = ic.grade({"holders": 40, "shares": 100.0}, {"holders": 40, "shares": 100.1}, cfg)
    assert flat[0] == "partial", flat
    thin = ic.grade({"holders": 5, "shares": 10.0}, {"holders": 4, "shares": 9.0}, cfg)
    assert thin[0] == "fail" and "thin" in thin[1]
    # no prior quarter = the TREND is unverified, which is partial, never a pass
    solo = ic.grade({"holders": 90, "shares": 100.0}, None, cfg)
    assert solo[0] == "partial" and "unverified" in solo[1]
    # rising but already over-owned: no room left for new sponsorship
    over = ic.grade({"holders": 60, "shares": 99.0}, {"holders": 52, "shares": 80.0}, cfg,
                    float_shares=100.0)
    assert over[0] == "partial" and "float" in over[1], over


def check_fallback_fills_gaps_and_never_overwrites(tmp):
    meta = {"notes": []}
    known = {"NVDA": {"I": "pass"}}
    detail = {"NVDA": {"grade": "pass", "source": "sec-13f"}}
    fb = os.path.join(tmp, "fb.json")
    io.open(fb, "w", encoding="utf-8").write(json.dumps({
        "meta": {"source": "accumulation-proxy"},
        "known": {"NVDA": {"I": "fail"}, "OTHER": {"I": "partial"}},
        "detail": {"NVDA": {"grade": "fail"}, "OTHER": {"grade": "partial"}}}))
    n = ic.merge_fallback(meta, known, detail, fb)
    assert n == 1
    assert known["NVDA"]["I"] == "pass", "a proxy overwrote a real 13F grade"
    assert detail["NVDA"]["source"] == "sec-13f"
    assert detail["OTHER"]["source"] == "accumulation-proxy"


# ---------------------------------------------------------------- known-file plumbing

def check_load_known_unwraps_the_cache_shape(tmp):
    """Without the unwrap, passing an I-cache to --known looks like it worked and grades nothing:
    every lookup misses, silently, and the run reports I=partial for the whole market."""
    a = os.path.join(tmp, "a.json")
    io.open(a, "w", encoding="utf-8").write(json.dumps({
        "meta": {"source": "sec-13f"}, "known": {"NVDA": {"I": "pass"}}, "detail": {}}))
    assert ss.load_known([a]) == {"NVDA": {"I": "pass"}}
    b = os.path.join(tmp, "b.json")          # the bare shape still works
    io.open(b, "w", encoding="utf-8").write(json.dumps({"NVDA": {"A": "fail"}}))
    merged = ss.load_known([a, b])
    assert merged["NVDA"] == {"I": "pass", "A": "fail"}, merged
    c = os.path.join(tmp, "c.json")          # later file wins on a conflict
    io.open(c, "w", encoding="utf-8").write(json.dumps({"NVDA": {"I": "fail"}}))
    assert ss.load_known([a, c])["NVDA"]["I"] == "fail"


def check_a_sourced_letter_is_distinguishable_from_an_unsourced_one():
    """"I = partial (graded)" and "I <= partial: not sourceable" are the same number and entirely
    different evidence. A report that cannot tell them apart cannot say where the grade came from.
    """
    graded = _ceiling_of()
    ss.ceiling(graded, CFG, {"I": "partial"})
    assert any("I = partial (graded)" in r for r in graded["ceiling_reasons"])
    assert not any("not sourceable" in r for r in graded["ceiling_reasons"])
    bare = _ceiling_of()
    ss.ceiling(bare, CFG)
    assert any("not sourceable" in r for r in bare["ceiling_reasons"])
    assert graded["ceiling"] == bare["ceiling"]      # same number, different provenance


# ---------------------------------------------------------------- html_to_pdf

def check_css_page_size_and_margin(tmp):
    p = os.path.join(tmp, "a.html")
    io.open(p, "w", encoding="utf-8").write("<style>@page{size:A4 landscape;margin:15mm}</style>")
    assert h2p.css_page_size(p) == "a4 landscape"
    assert h2p.css_page_margin(p) == "15mm"


def check_css_margin_rejects_what_it_cannot_forward(tmp):
    """A multi-value or unitless margin cannot be handed to wkhtmltopdf verbatim, so the parser
    must fall back rather than pass through something the engine will misread."""
    for css, want in [("@page{margin:10mm 5mm}", h2p.DEFAULT_MARGIN),
                      ("@page{margin:0}", h2p.DEFAULT_MARGIN),
                      ("@page{margin:1.5cm}", "1.5cm"),
                      ("<style></style>", h2p.DEFAULT_MARGIN)]:
        p = os.path.join(tmp, "b.html")
        io.open(p, "w", encoding="utf-8").write("<style>%s</style>" % css)
        assert h2p.css_page_margin(p) == want, (css, h2p.css_page_margin(p))


def check_page_rule_parsing_stays_linear(tmp):
    """The @page regex restarted at every "@page" and ran to the end of the input hunting for a
    "}" that never came: 120KB of "@page{" held PDF export for 35 seconds (twice per engine). A
    document that merely CONTAINS that text (a pasted reason, say) could stall the whole build."""
    hostile = os.path.join(tmp, "hostile.html")
    io.open(hostile, "w", encoding="utf-8").write("@page{" * 20000)
    t0 = time.time()
    assert h2p.css_page_size(hostile) is None
    assert h2p.css_page_margin(hostile) == h2p.DEFAULT_MARGIN
    assert time.time() - t0 < 2.0, "page-rule parsing is quadratic again (%.1fs)" % (time.time() - t0)

    # ...and the real shapes still parse, including a rule that is not the first thing in the file
    real = os.path.join(tmp, "real.html")
    io.open(real, "w", encoding="utf-8").write(
        "<style>body{margin:0}\n@page :first{margin:3mm}\n@page{size:A4 landscape; margin:15mm}</style>")
    assert h2p.css_page_size(real) == "a4 landscape"
    assert h2p.css_page_margin(real) == "3mm"      # the first rule that sets one wins


def check_css_helpers_survive_a_missing_file():
    assert h2p.css_page_size("/nope/nothing.html") is None
    assert h2p.css_page_margin("/nope/nothing.html") == h2p.DEFAULT_MARGIN


def check_render_timeouts_agree():
    """Every engine in the chain shares one ceiling; a mismatch means one engine is the odd one
    out again, which is the bug the constant was introduced to remove."""
    assert h2p.RENDER_TIMEOUT == br.RENDER_TIMEOUT == 240


# ---------------------------------------------------------------- build_report / the template

TPL = os.path.join(ROOT, "assets", "dashboard_template.html")


def check_apply_theme_targets_the_doctype_not_the_prose(tmp):
    """The template's own header comment TALKS ABOUT <html data-theme="dark">; the rewrite must
    anchor on the real doctype or it edits the comment and leaves the document untouched."""
    p = os.path.join(tmp, "r.html")
    shutil.copy(TPL, p)
    assert br.apply_theme(p, "light") is True
    s = io.open(p, encoding="utf-8").read()
    doc = re.search(r"<!doctype html>(?:\s|<!--.*?-->)*<html[^>]*>", s, re.I | re.S)
    assert doc and 'data-theme="light"' in doc.group(0), doc.group(0) if doc else "no doctype"
    assert s.count('<html lang="en" data-theme="light">') == 1


def check_template_scripts_parse():
    src = io.open(TPL, encoding="utf-8").read()
    js = "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", src, re.S))
    node = shutil.which("node")
    if not node:
        return "skipped - node not installed"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        path = f.name
    try:
        r = subprocess.run([node, "--check", path], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
    finally:
        os.unlink(path)


def _strip_comments(src):
    """Drop HTML comments and CSS/JS block comments - the parts that never reach a reader.

    The template deliberately NAMES the dead scales in two comments: the .sc-total rule explains
    why the value and its denominator must live in one span (a split one flattened to "/74.5",
    "i.e. a score out of 70"), and the audit explains which denominators it matches. Grepping raw
    source would fail on the very comments that document the bug, so strip what does not render
    and check the rest - the same distinction the /70 hunt turned on originally.
    """
    src = re.sub(r"<!--.*?-->", " ", src, flags=re.S)
    return re.sub(r"/\*.*?\*/", " ", src, flags=re.S)


def check_template_has_no_dead_scale():
    src = _strip_comments(io.open(TPL, encoding="utf-8").read())
    for bad in ("/70", "out of 70", "/ 70", "/10", "out of 10"):
        assert bad not in src, "template still mentions %r outside a comment" % bad
    assert "out of 7" in src


def check_public_source_status_is_wired_end_to_end():
    """A blocked connector must never cost a letter, and a substituted figure must never ship
    silently. `public` is a FOURTH status, distinct from `reused`: the data is current, it just
    came from somewhere the skill did not specify. Conflating the two would either overstate the
    staleness or hide the substitution, and a reader is weighing different risks in each case."""
    src = io.open(TPL, encoding="utf-8").read()
    assert 'public:"PUBLIC SOURCE"' in src, "the status has no rendered label"
    assert ".fchip.public{" in src, "the status has no chip style, so it renders as UNAVAILABLE"
    assert '["fresh","reused","public","unavailable"]' in src, "the audit rejects the new status"
    # the substituted-sources banner, and the fact that it is separate from the staleness one
    assert 'id="substituted"' in src and "came from a public source" in src


def check_a_public_row_must_declare_which_connector_failed():
    """A public substitute is only legitimate AFTER the specified source was tried and failed, so
    the failure entry is what justifies it. Without that rule a run could quietly prefer whatever
    was easiest to fetch and still print a clean-looking sources table."""
    src = io.open(TPL, encoding="utf-8").read()
    rule = src[src.index('["reused","public","unavailable"].indexOf(st) >= 0'):]
    rule = rule[:rule.index("});")]
    assert "freshness.failures" in rule, rule[:200]
    # and it must name the public source, or a filing and a message board look identical
    assert 'st === "public" && !String(r.source||"").trim()' in src


def check_public_rows_are_not_counted_as_stale():
    """The sources-table subtitle is derived, and it used to call every non-fresh row "did not
    come back fresh". A public row IS fresh, so that wording would be wrong about the one thing
    the reader is trying to judge."""
    src = io.open(TPL, encoding="utf-8").read()
    blk = src[src.index("The subtitle is derived"):]
    blk = blk[:blk.index("})();")]
    assert 'came from a public substitute rather than the specified source' in blk
    assert '["fresh","public"].indexOf(st_(r)) < 0' in blk, "public is still counted as stale"


def check_every_source_ladder_ends_in_a_public_rung():
    """A ladder with no public rung is a letter that gets abandoned when its connector is down."""
    g = io.open(os.path.join(ROOT, "references", "tradingview-sector-sweep.md"),
                encoding="utf-8").read()
    table = g[g.index("| Need | Fallback order |"):]
    table = table[:table.index("\n\n")]
    rows = [l for l in table.splitlines() if l.startswith("|") and "Fallback order" not in l
            and not set(l) <= set("|- ")]
    assert len(rows) >= 5, rows
    for r in rows:
        assert "public" in r.lower(), "ladder has no public rung: %s" % r[:80]


def check_skill_documents_the_public_fallback_policy():
    s = io.open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
    assert "fall back to PUBLIC data" in s, "SKILL.md never tells the run to substitute"
    assert 'status:"public"' in s, "SKILL.md never says how to declare a substitution"
    for must in ["SEC EDGAR", "refuses to emit", "Public is not stale"]:
        assert must in s, "SKILL.md's fallback policy omits %r" % must


def check_the_two_data_banners_do_not_contradict_each_other():
    """A failure answered by a PUBLIC substitute belongs to the substitution banner, not the
    staleness one. Without the split the rendered report said "Used instead: nothing - the report
    works around the gap" (true: no STALE data was reused) directly above a banner naming the two
    public sources it had just used, and headlined a fully-current run "Not all data is fresh".
    """
    src = io.open(TPL, encoding="utf-8").read()
    blk = src[src.index("---- freshness: did this run"):]
    blk = blk[:blk.index("})();")]
    assert "pubItems" in blk and 'status||"fresh"' in blk, "the freshness banner never looks at sourceMap"
    assert "const fails = all.filter(x => !pubItems.has" in blk, \
        "substituted failures are still counted as staleness"
    # ...and the all-substituted case must not claim staleness at all. Matched on a CONTIGUOUS
    # fragment: the sentence is built by concatenation, so the rendered wording does not appear
    # in the source as one string - asserting the rendered phrasing fails against working code.
    assert "is current as of this run" in blk, "the all-substituted case still reports staleness"


def check_every_css_variable_the_template_uses_is_defined():
    """The PUBLIC chip shipped with `var(--accent-bg, #eef2ff)`, and --accent-bg does not exist -
    the template defines --accent-soft. So it silently used a hard-coded LIGHT colour in a
    theme-aware document, which in dark mode is a near-white block. A var() fallback hides this
    perfectly, which is why it needs a rule rather than an eye.
    """
    src = io.open(TPL, encoding="utf-8").read()
    used = set(re.findall(r"var\(\s*(--[a-z0-9-]+)", src))
    declared = set(re.findall(r"^\s*(--[a-z0-9-]+)\s*:", src, re.M))
    declared |= set(re.findall(r"[;{]\s*(--[a-z0-9-]+)\s*:", src))
    missing = sorted(used - declared)
    assert not missing, "template uses CSS variables that are never declared: %s" % missing


def check_template_audit_rules_are_wired():
    """The self-audit is the skill's last line of defence; these are the contradictions it
    promises to catch, each identified by the text it raises."""
    src = io.open(TPL, encoding="utf-8").read()
    for frag in ["CONFIG.sweep.mustGrade says",
                 "verdict AVOID but the scorecard totals",
                 "a buy point is named but N is FAIL",
                 "is more than 10% below the 52-week high",
                 "CONFIG.dataDate is empty",
                 "CONFIG.freshness is missing",
                 "reused data with no `asOf`"]:
        assert frag in src, "audit no longer raises: %s" % frag


def check_funnel_tile_is_addressed_by_identity_not_index():
    """Writing the qualifier count to tiles[4] broke the moment a tile was inserted above it."""
    src = io.open(TPL, encoding="utf-8").read()
    assert 'id:"qualified"' in src and 't.id==="qualified"' in src
    assert "tiles[4]" not in src


# ---------------------------------------------------------------- template, in a real browser
"""Behavioural tests for assets/dashboard_template.html.

The template's bugs were behavioural - a payload that actually executed, a crashed page that the
build gate called clean - and a string-in-the-source check cannot see either. These render the
real template in the same headless browser build_report.audit() uses. With no browser they SKIP,
exactly as the build gate skips its own check; they never fail for want of one.
"""

_NO_BROWSER = "skipped: no headless browser in this environment"
_PAYLOAD = '<img src=x onerror="document.documentElement.setAttribute(\'data-pwn\',\'1\')">'


def _browser():
    return bool(h2p.find_browser())


def _good_cfg():
    """A CONFIG that audits clean: three picks, one of them the documented 'None now' WATCH."""
    scores = lambda **k: dict(dict(C="pass", A="pass", N="pass", S="partial", L="pass", I="partial"), **k)

    def pick(sym, sc, verdict, bp, stop, **kw):
        d = dict(symbol=sym, company=sym + " Corp", sector="Electronic Technology", group="Networking",
                 sectorRank=1, price="100.0", rs="+40", offHigh="3%", high52="104.0", buyPoint=bp,
                 stop=stop, verdict=verdict, scores=sc, reason="C pass, new high out of a sound base.")
        d.update(kw)
        return d
    return {
        "title": "T", "generatedAt": "2026-10-10", "dataDate": "2026-10-09 close", "dataSource": "x",
        "freshness": {"attemptedAt": "2026-10-10 12:00 UTC", "allFresh": True, "failures": []},
        "dataProvenance": "TradingView for everything",
        "sourceMap": [{"item": "Sector sweep", "source": "TradingView", "pulled": "2026-10-10",
                       "asOf": "2026-10-09 close", "status": "fresh"}],
        "sweep": {"windowLabel": "6m", "benchmark": "SPY +5%", "sectorsScanned": 2, "perSector": 10,
                  "screened": 20, "triaged": 3, "graded": 3, "mustGrade": 3, "eliminatedByCeiling": 0},
        "market": {"verdict": "Uptrend", "tone": "up", "mGrade": "partial",
                   "distributionDays": "2", "implication": "ok"},
        "gradeThreshold": 4.5, "topCount": 10,
        "picks": [
            pick("AAA", scores(), "BUY-RANGE", "100.0", "92.5"),
            pick("BBB", scores(N="partial"), "WATCH", "None now - needs a handle above 150.20", "",
                 sector="Health Technology"),
            pick("CCC", scores(C="fail", A="fail", N="fail", S="fail", L="fail", I="fail"), "AVOID",
                 "", "", sector="Health Technology")],
        "sectors": [
            {"rank": 1, "sector": "Electronic Technology", "medianPerf": "+30%", "survivors": 1,
             "considered": 10, "qualified": 1},
            {"rank": 2, "sector": "Health Technology", "medianPerf": "+20%", "survivors": 2,
             "considered": 10, "qualified": 1}],
        "disclaimer": "d", "portfolioNote": "p", "sources": [], "glossary": []}


def _fill(tmp, cfg, name="r.html", raw_json=None):
    """The real template with its CONFIG replaced. `<` is written as <, as SKILL.md instructs."""
    tpl = io.open(os.path.join(ROOT, "assets", "dashboard_template.html"), encoding="utf-8").read()
    js = raw_json if raw_json is not None else json.dumps(cfg).replace("<", "\\u003c")
    out, n = re.subn(r"const CONFIG = \{.*?\n\};\n", lambda m: "const CONFIG = " + js + ";\n",
                     tpl, count=1, flags=re.S)
    assert n == 1, "could not locate the CONFIG block"
    path = os.path.join(tmp, name)
    io.open(path, "w", encoding="utf-8").write(out)
    return path


def _rendered(dom):
    """The dumped DOM without <script>/<style> text. The dump includes the page's own source, so
    a check for "javascript:" or a message string would otherwise match the template's code."""
    return re.sub(r"<(script|style)\b.*?</\1>", "", dom, flags=re.S | re.I)


def _audit_lines(tmp, cfg, **kw):
    ok, detail = br.audit(_fill(tmp, cfg, **kw))
    return ok, [l.strip("- ").strip() for l in detail.splitlines() if l.strip()]


def check_the_template_test_harness_starts_from_a_clean_report(tmp):
    """Every other template test mutates this config, so it has to audit clean to begin with."""
    if not _browser():
        return _NO_BROWSER
    ok, lines = _audit_lines(tmp, _good_cfg())
    assert ok and lines == ["clean"], lines


def _poison(o, key=None):
    """Every string a CONFIG can carry becomes a script-injection attempt, except the grades."""
    keep = {"C", "A", "N", "S", "L", "I", "mGrade", "status"}
    count_fields = {"mustGrade", "graded", "eliminatedByCeiling", "qualified", "sectorRank", "rank",
                    "survivors", "considered", "sectorsScanned", "screened", "triaged", "perSector"}
    if isinstance(o, dict):
        return {k: _poison(v, k) for k, v in o.items()}
    if isinstance(o, list):
        return [_poison(v, key) for v in o]
    if isinstance(o, str) and key not in keep:
        return _PAYLOAD
    if isinstance(o, (int, float)) and not isinstance(o, bool) and key in count_fields:
        return _PAYLOAD
    return o


def check_no_config_field_can_inject_markup(tmp):
    """esc() covers the innerHTML path, but five interpolations skipped it (the sweep counts, a
    sector's qualified count, a fallback row's sectorRank) - an <img onerror> there ran. Poison
    EVERY string and count field and check nothing executed and nothing was created."""
    if not _browser():
        return _NO_BROWSER
    cfg = _poison(_good_cfg())
    cfg["sectors"][0]["top5"] = [{"sectorRank": _PAYLOAD, "ticker": _PAYLOAD, "company": _PAYLOAD,
                                  "perf": _PAYLOAD, "rs": _PAYLOAD, "note": _PAYLOAD}]
    cfg["sectors"][0]["qualified"] = 0                  # so the fallback rows render
    cfg["rationale"] = [{"symbol": _PAYLOAD, "company": _PAYLOAD, "text": _PAYLOAD}]
    cfg["watch"] = [{"symbol": _PAYLOAD, "company": _PAYLOAD, "sector": _PAYLOAD, "note": _PAYLOAD}]
    cfg["glossary"] = [{"term": _PAYLOAD, "def": _PAYLOAD}]
    cfg["sources"] = [{"label": _PAYLOAD, "url": "https://example.com/a"}]
    dom, why = br.dump_dom(_fill(tmp, cfg))
    assert dom, why
    assert not re.search(r"<html[^>]*data-pwn", dom), "injected markup executed"
    assert not re.search(r"<img[^>]+src=\"?x\"?", _rendered(dom)), \
        "injected <img> reached the DOM as an element"
    assert 'data-rendered="1"' in dom, "the page did not finish rendering under hostile input"


def check_script_urls_are_never_rendered_as_links(tmp):
    """esc() protects an attribute, not its scheme: href="javascript:..." and an iframe src of the
    same kind execute in the page's own origin. Only http(s) and relative URLs may become links."""
    if not _browser():
        return _NO_BROWSER
    cfg = _good_cfg()
    cfg["picks"][0]["reviewUrl"] = "javascript:parent.document.documentElement.setAttribute('data-pwn','1')"
    cfg["picks"][1]["reviewUrl"] = "java\tscript:alert(1)"           # browsers ignore the tab
    cfg["picks"][2]["reviewUrl"] = "reviews/CCC-canslim.html"        # a legitimate relative one
    cfg["sources"] = [{"label": "bad", "url": "JaVaScRiPt:alert(1)"},
                      {"label": "data", "url": "data:text/html,<b>x"},
                      {"label": "good", "url": "https://example.com/filing"}]
    dom, why = br.dump_dom(_fill(tmp, cfg))
    assert dom, why
    page = _rendered(dom)
    flat = re.sub(r"[\s\x00-\x20]", "", page.lower())
    assert 'href="javascript:' not in flat and 'data-review="javascript:' not in flat \
        and 'href="data:' not in flat, "a script URL was rendered"
    assert not re.search(r'(?:href|data-review)="[^"]*script:', flat), "a script URL was rendered"
    assert 'data-review="reviews/CCC-canslim.html"' in page, "a legitimate relative reviewUrl was dropped"
    assert 'href="https://example.com/filing"' in page, "a legitimate https source link was dropped"
    assert re.search(r'<iframe[^>]*sandbox="allow-scripts allow-popups"', page), \
        "the review iframe is not sandboxed"
    assert "allow-same-origin" not in page, "the sandbox must not grant same-origin"


def check_a_crashed_page_is_never_reported_clean(tmp):
    """The self-audit is the LAST thing the page runs, so any earlier script error leaves no banner
    - and build_report read 'no banner' as 'clean'. It must now require the page to have finished,
    and the static check must catch the one injection that kills the script before it starts."""
    if not _browser():
        return _NO_BROWSER
    cfg = _good_cfg()
    cfg["sectors"] = [None]                                  # makes the sector table throw
    ok, lines = _audit_lines(tmp, cfg, name="crash.html")
    assert not ok, "a page that threw before its audit ran was reported clean: %s" % lines
    assert any("stopped rendering" in l or "Report checks failed" in l or "never ran" in l
               for l in lines), lines


def check_a_closing_script_tag_in_config_is_refused(tmp):
    """A CONFIG string containing the closing-script-tag text ends the script early; everything
    after it is parsed as HTML (and can run) and the real script dies, so no audit ever executes.
    Reasons are pasted from web pages, so this is reachable. Caught without a browser too."""
    cfg = _good_cfg()
    # silent on purpose: alert() would park a headless browser on a dialog until it times out
    cfg["picks"][0]["reason"] = "ok </script><img src=x onerror=document.title=1> trailing"
    raw = json.dumps(cfg)                                    # deliberately NOT escaped
    path = _fill(tmp, cfg, name="inject.html", raw_json=raw)
    problem = br.script_tag_problem(path)
    assert problem and "closing" in problem, "the static check missed an injected closing script tag"
    clean = _fill(tmp, _good_cfg(), name="clean.html")
    assert br.script_tag_problem(clean) is None, "the static check flagged a clean report"
    if _browser():
        ok, lines = br.audit(path)
        assert not ok, "the browser path reported an injected report clean: %s" % lines


def check_script_tag_pairing_catches_a_balanced_but_nested_injection(tmp):
    """Comparing the NUMBER of opening and closing script tags passed a CONFIG string that holds a
    whole script element: the counts balance, yet the parser ends the real script at the string's
    closing tag and the rest of CONFIG (and the render-complete mark) leaks into the page as text.
    This check is the only guard when no browser is installed, so it has to be positional."""
    one = lambda body: br.script_tag_problem(_write(tmp, "t.html", body))
    assert one('<script>const C={a:"x"};</script><script>1</script>') is None
    for bad in ('<script>const C={a:"saw <script>x</script> here"};</script>',     # balanced, nested
                '<script>const C={a:"</script>"};</script>',                        # stray close
                '<script>const C={a:1};', '</script><script>1</script>'):          # unclosed / leading close
        assert one(bad), "missed: %s" % bad
    cfg = _good_cfg()
    cfg["picks"][0]["reason"] = "saw <script>x</script> on a web page"
    leaked = _fill(tmp, cfg, name="nested.html", raw_json=json.dumps(cfg))          # NOT escaped
    assert br.script_tag_problem(leaked), "the nested injection slipped past the static check"
    assert br.script_tag_problem(_fill(tmp, cfg, name="safe.html")) is None, "the \\u003c form was refused"


def _write(tmp, name, body):
    path = os.path.join(tmp, name)
    io.open(path, "w", encoding="utf-8").write(body)
    return path


def check_file_urls_survive_awkward_paths(tmp):
    """"file:///" + path gave file:////tmp/My Reports #2/r.html: a doubled slash and raw characters,
    where "#" starts a fragment, "?" a query and "%" an escape. A report under a folder named
    "Q3 #2" or "100%" was loaded from the wrong place."""
    import urllib.parse
    import urllib.request
    folder = os.path.join(tmp, "My Reports #2 100% ?x")
    os.makedirs(folder)
    path = _write(folder, "r.html", "<html><body><p id=m>found-it</p></body></html>")
    url = h2p.file_url(path)
    assert url.startswith("file:///") and not url.startswith("file:////"), url
    assert " " not in url and "#2" not in url and "?x" not in url, url
    assert urllib.request.url2pathname(urllib.parse.urlsplit(url).path) == os.path.abspath(path), url
    if _browser():                                  # ...and a real browser actually opens it
        dom, why = br.dump_dom(path)
        assert dom and "found-it" in dom, why


def check_a_pick_without_a_symbol_is_flagged_not_fatal(tmp):
    """d.sym.length threw inside the scatter map for any pick with no symbol (or a 'ticker' key),
    killing the glossary, the sources table and the audit with it."""
    if not _browser():
        return _NO_BROWSER
    cfg = _good_cfg()
    del cfg["picks"][1]["symbol"]
    ok, lines = _audit_lines(tmp, cfg)
    assert not ok and any("no symbol" in l for l in lines), lines


def check_none_now_is_a_legitimate_buy_point(tmp):
    """SKILL.md prescribes 'None now' plus the condition for a strong name with no valid pivot.
    num() read the first number anywhere in the string, so 'None now - needs a handle above
    150.20' was audited as a buy point of 150.20 and refused the report that followed the docs."""
    if not _browser():
        return _NO_BROWSER
    cfg = _good_cfg()
    cfg["picks"][1]["scores"]["N"] = "fail"                  # the WATCH name now has N failing
    cfg["picks"][1]["buyPoint"] = "None now; re-base 30 pct off high"
    ok, lines = _audit_lines(tmp, cfg)
    assert ok, lines
    cfg["picks"][1]["buyPoint"] = "178.40"                   # ...but a real price with N fail is still refused
    ok, lines = _audit_lines(tmp, cfg)
    assert not ok and any("N is FAIL" in l for l in lines), lines


def check_sweep_graded_must_match_the_picks_even_when_zero_or_absent(tmp):
    if not _browser():
        return _NO_BROWSER
    for label, edit in (("zero", lambda c: c["sweep"].update(graded=0)),
                        ("absent", lambda c: c["sweep"].pop("graded"))):
        cfg = _good_cfg()
        edit(cfg)
        ok, lines = _audit_lines(tmp, cfg)
        assert not ok and any("sweep.graded" in l for l in lines), (label, lines)


def check_exact_boundaries_are_not_flagged_by_float_noise(tmp):
    """104 * 0.9 is 93.60000000000001 in floating point, so a buy point exactly 10% below the
    high was called 'more than 10% below'. The same drift hit a stop at exactly 9%."""
    if not _browser():
        return _NO_BROWSER
    cfg = _good_cfg()
    cfg["picks"][0].update(high52="104", buyPoint="93.6", stop="85.2")      # 10.0% and 8.97% / 9.0%
    ok, lines = _audit_lines(tmp, cfg)
    assert ok, lines
    cfg["picks"][0].update(buyPoint="93.5")                                # genuinely past 10%
    ok, lines = _audit_lines(tmp, cfg)
    assert not ok and any("more than 10% below" in l for l in lines), lines


def check_sector_qualified_counts_must_agree_with_the_picks(tmp):
    if not _browser():
        return _NO_BROWSER
    cfg = _good_cfg()
    cfg["sectors"][1]["qualified"] = 0                       # but BBB (Health) scores 5/7
    ok, lines = _audit_lines(tmp, cfg)
    assert not ok and any("qualified" in l and "Health Technology" in l for l in lines), lines


def check_an_invalid_market_grade_is_reported_once(tmp):
    if not _browser():
        return _NO_BROWSER
    cfg = _good_cfg()
    cfg["market"]["mGrade"] = "maybe"
    ok, lines = _audit_lines(tmp, cfg)
    assert not ok and sum("mGrade" in l for l in lines) == 1, lines


def check_the_empty_state_does_not_call_ceiling_eliminated_names_unreached(tmp):
    """The empty list said '5 further names ... were never graded ... not reached' while the note
    above it said those same 5 were eliminated by the ceiling: it fired on every normal run."""
    if not _browser():
        return _NO_BROWSER
    cfg = _good_cfg()
    for p in cfg["picks"]:
        p["scores"] = {k: "fail" for k in "CANSLI"}
        p["verdict"], p["buyPoint"], p["stop"] = "AVOID", "", ""
    cfg["sweep"].update(triaged=8, graded=3, mustGrade=3, eliminatedByCeiling=5)
    for sec in cfg["sectors"]:
        sec["qualified"] = 0
    dom, why = br.dump_dom(_fill(tmp, cfg))
    assert dom, why
    text = re.sub(r"<[^>]+>", " ", _rendered(dom))
    assert "never graded in this run" not in text, "ceiling-eliminated names were called unreached"
    cfg["sweep"].update(eliminatedByCeiling=2)               # 3 genuinely ungraded survivors
    dom, _ = br.dump_dom(_fill(tmp, cfg, name="r2.html"))
    assert "3 further names cleared triage but were never graded" in re.sub(r"<[^>]+>", " ", _rendered(dom))


def check_skill_tells_the_run_how_to_write_config_strings():
    """The template and build_report defend against a closing-script-tag in a CONFIG string, but
    the author is the first line of defence and has to be told what to do."""
    flat = " ".join(io.open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read().split())
    assert "write every `<` in a CONFIG string as `\\u003c`" in flat, \
        "SKILL.md no longer says how to write < inside CONFIG strings"
    assert "`reviewUrl` and `sources[].url` must be `http(s)` or relative" in flat


def check_the_sort_hint_is_hidden_in_print():
    """`.hint` was meant to vanish on paper, but `.legend span{display:inline-flex}` out-ranks it,
    so 'Click a column header to sort' printed into the PDF."""
    src = io.open(os.path.join(ROOT, "assets", "dashboard_template.html"), encoding="utf-8").read()
    printed = src[src.index("@media print"):]
    assert ".legend span.hint" in printed.split("}", 5)[0] + printed[:3000], \
        "the print stylesheet no longer hides the on-screen hint at a specificity that wins"


# ---------------------------------------------------------------- export_portable

def check_export_bundles_every_script(tmp):
    # The portable bundle ships this suite but NOT the exporter - a copy handed to another
    # assistant has nothing left to export. Skip rather than fail there, so the suite a ported
    # copy runs comes back green and a real failure still stands out.
    exporter = os.path.join(ROOT, "scripts", "export_portable.py")
    if not os.path.exists(exporter):
        return "skipped: no exporter in this copy (a portable bundle)"
    out = subprocess.run([sys.executable, exporter, tmp],
                         capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr
    import zipfile
    z = zipfile.ZipFile(os.path.join(tmp, "can-slim-recommend.zip"))
    assert z.testzip() is None
    names = {n.split("/", 1)[1] for n in z.namelist() if "/" in n}
    for f in os.listdir(os.path.join(ROOT, "scripts")):
        if f.endswith(".py") and f != "export_portable.py":
            assert "scripts/" + f in names, "%s missing from the bundle" % f
    md = io.open(os.path.join(tmp, "can-slim-recommend-portable.md"), encoding="utf-8").read()
    # The manifest tells a reader which files to recreate. It was typed by hand and listed 10 of
    # the bundle's files - rubric.py among the missing, which sector_screen.py imports - so a skill
    # rebuilt from it alone could not start. It is generated from FILES now; hold it to that.
    m = re.search(r"^```\ncan-slim-recommend/\n(.*?)^```", md, re.M | re.S)
    assert m, "the bundle has no file manifest"
    listed = {l.strip() for l in m.group(1).splitlines() if l.strip()}
    shipped = names - {"PORTABLE-README.md"}
    assert listed == shipped, ("manifest and bundle disagree: only in manifest %s, only in bundle %s"
                               % (sorted(listed - shipped), sorted(shipped - listed)))
    # Every fenced block must close - an unbalanced fence silently swallows the rest of the file.
    # Counted per fence WIDTH: the exporter widens a fence when the file it wraps contains
    # backticks, and a plain "```" count would see the opening of a ````-fence as a match.
    for fence in set(re.findall(r"^(`{3,})", md, re.M)):
        assert md.count("\n" + fence) % 2 == 0, "unbalanced %d-backtick fence" % len(fence)


def check_the_committed_bundle_matches_the_sources(tmp):
    """dist/can-slim-recommend-portable.md is committed so there is a stable link to hand someone,
    and it inlines every other file in the repo - this suite included. It is generated, never
    edited, so any change to a source file leaves it stale until the exporter is re-run, and a
    stale bundle keeps teaching whatever the sources no longer say (it would go on shipping a
    removed script and the instructions to run it). Nothing else would notice.

    Fix a failure here with `python scripts/export_portable.py`, then commit dist/.
    """
    exporter = os.path.join(ROOT, "scripts", "export_portable.py")
    committed = os.path.join(ROOT, "dist", "can-slim-recommend-portable.md")
    if not (os.path.exists(exporter) and os.path.exists(committed)):
        return "skipped: no exporter or committed bundle in this copy"
    out = subprocess.run([sys.executable, exporter, tmp], capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr
    fresh = io.open(os.path.join(tmp, "can-slim-recommend-portable.md"), encoding="utf-8").read()
    assert fresh == io.open(committed, encoding="utf-8").read(), (
        "dist/can-slim-recommend-portable.md is stale - run `python scripts/export_portable.py` "
        "and commit the result")


# ---------------------------------------------------------------- tv_throttle

def _thr(tmp, *args):
    """Run the throttle with its state redirected into tmp, and time how long it blocked."""
    env = dict(os.environ, CANSLIM_THROTTLE_STATE=os.path.join(tmp, "t.json"))
    t0 = time.time()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "tv_throttle.py")]
                       + list(args), capture_output=True, text=True, timeout=120, env=env)
    return time.time() - t0, r.returncode, (r.stdout + r.stderr)


def check_throttle_enforces_a_gap_between_calls(tmp):
    """The point of the script rather than a written rule: --wait BLOCKS. A rule in a markdown
    file is a suggestion that gets skipped once a sweep is twenty sectors deep and going well."""
    _thr(tmp, "--reset")
    d1, rc1, _ = _thr(tmp, "--wait", "--min-gap", "2", "--quiet")
    d2, rc2, _ = _thr(tmp, "--wait", "--min-gap", "2", "--quiet")
    assert rc1 == 0 and rc2 == 0
    assert d1 < 1.0, "the first call should not wait (%.1fs)" % d1
    assert d2 >= 1.8, "the second call must be held for the gap (%.1fs)" % d2


def check_throttle_state_survives_separate_invocations(tmp):
    """An agent calls this one shell command at a time, so pacing has to live in a file. A
    throttle that only remembered the current process would reset on every call and enforce
    nothing at all."""
    _thr(tmp, "--reset")
    _thr(tmp, "--wait", "--quiet")
    _, _, out = _thr(tmp, "--status")
    assert "1 / 12" in out.replace("  ", " "), out


def check_throttle_holds_a_full_rolling_budget(tmp):
    """The gap alone is not enough: a hundred calls each just inside the spacing still creeps up
    on the limit. The rolling window is what stops a long sweep doing that."""
    _thr(tmp, "--reset")
    state = os.path.join(tmp, "t.json")
    now = time.time()
    io.open(state, "w", encoding="utf-8").write(json.dumps(
        {"calls": [now - i * 0.1 for i in range(12)], "blocks": 0, "blocked_until": 0.0}))
    _, _, out = _thr(tmp, "--status")
    assert "budget" in out and "full" in out, out
    _, rc, out = _thr(tmp, "--wait", "--max-wait", "5")
    assert rc == 1 and "REFUSED" in out, out


def check_a_block_escalates_and_success_decays_it(tmp):
    """A 403 is a door closing for many minutes, not a slow-down, so the cooldown doubles. It
    decays on success so a connector that has recovered is not taxed for the whole session."""
    _thr(tmp, "--reset")
    _, _, o1 = _thr(tmp, "--blocked")
    _, _, o2 = _thr(tmp, "--blocked")
    assert "300s" in o1 and "600s" in o2, (o1, o2)
    _, _, st = _thr(tmp, "--status")
    assert "scanner  blocks: 2" in st, st
    _thr(tmp, "--ok")
    _thr(tmp, "--ok")
    _, _, st = _thr(tmp, "--status")
    assert "scanner  blocks: 0" in st and "BLOCKED" not in st, st


def check_throttle_refuses_rather_than_stalling_forever(tmp):
    """A blocked connector is not a slow one. --wait returns non-zero rather than sleeping out
    the cooldown, so the caller can stop and say so instead of hanging for half an hour."""
    _thr(tmp, "--reset")
    _thr(tmp, "--blocked")
    d, rc, out = _thr(tmp, "--wait", "--max-wait", "3")
    assert rc == 1 and d < 3.0, (rc, d)
    # the block message must carry the rule, since this is the moment it is tempting to break
    assert "not narrow the sweep" in _thr(tmp, "--blocked")[2].lower()


def check_a_scanner_block_does_not_halt_bar_calls(tmp):
    """Measured on the live connector: with scanner.tradingview.com returning 403, get_ohlcv kept
    answering normally. Blocks are imposed per endpoint family, so halting every TradingView call
    for a scanner 403 stops work that would have succeeded. The call BUDGET stays shared, because
    both draw on one upstream quota."""
    _thr(tmp, "--reset")
    _thr(tmp, "--blocked", "--scope", "scanner")
    _, rc_scan, _ = _thr(tmp, "--wait", "--scope", "scanner", "--max-wait", "3")
    assert rc_scan == 1, "a scanner block must hold scanner calls"
    d, rc_bars, _ = _thr(tmp, "--wait", "--scope", "ohlcv", "--max-wait", "3")
    assert rc_bars == 0 and d < 3.0, "a scanner block must NOT hold bar calls (%s)" % rc_bars
    # ... but the bar call still spends from the shared budget
    _, _, st = _thr(tmp, "--status")
    assert "1 / 12" in st.replace("  ", " "), st


def check_a_named_retry_after_is_obeyed_exactly(tmp):
    """When TradingView names its own cooldown ("Retry after 32s") that number beats any we
    guessed, so it is used verbatim rather than fed into the block ladder."""
    _thr(tmp, "--reset")
    _, rc, out = _thr(tmp, "--observe", "Rate limit exceeded. Retry after 32s")
    assert rc == 2 and "32s" in out and "obeying it exactly" in out, out
    _, _, st = _thr(tmp, "--status")
    assert "learned rate           : 6/min" in st, st        # halved from the 12 default
    _, rc, out = _thr(tmp, "--wait", "--max-wait", "5")
    assert rc == 1, "the named cooldown must actually hold calls"


def check_rate_signals_halve_and_clean_calls_ease_up(tmp):
    """AIMD, which is the standard answer to an UNDOCUMENTED limit: approach it slowly, retreat
    fast. scanner.tradingview.com publishes no rate limit anywhere - the numbers that turn up in
    a search belong to tradingviewapi.com, an unrelated commercial reseller - so the only honest
    source is what the endpoint says back."""
    _thr(tmp, "--reset")
    _, _, out = _thr(tmp, "--observe", '{"error":"Too Many Requests"}')
    assert "halved to 6/min" in out, out
    _thr(tmp, "--reset")
    for _ in range(10):
        _thr(tmp, "--observe", '{"success":true}')
    _, _, st = _thr(tmp, "--status")
    assert "learned rate           : 14/min" in st, st       # 12 + raise_by after raise_after


def check_the_rate_cap_holds_however_well_it_is_going(tmp):
    """A hard ceiling regardless of the learned rate. There is no throughput worth the block, and
    a sweep needs about twenty screener calls, not hundreds."""
    _thr(tmp, "--reset")
    for _ in range(60):
        _thr(tmp, "--observe", '{"success":true}', "--max-rate", "16")
    _, _, st = _thr(tmp, "--status", "--max-rate", "16")
    assert "learned rate           : 16/min (cap 16" in st, st


def check_a_403_observation_escalates_the_block_ladder(tmp):
    """A 403 is a block, not a slow-down: it must reach the cooldown ladder, not just trim the
    rate, or the next call walks straight back into it."""
    _thr(tmp, "--reset")
    _, rc, out = _thr(tmp, "--observe",
                      "HTTPStatusError: Client error '403 Forbidden' for url "
                      "https://scanner.tradingview.com/america/scan")
    assert rc == 2 and "block #1" in out, out
    _, rc, _ = _thr(tmp, "--wait", "--max-wait", "5")
    assert rc == 1


def check_status_survives_a_closed_pipe(tmp):
    """`--status | head -2` is an ordinary thing to type; a traceback is a poor reward for it."""
    r = subprocess.run("%s %s --status 2>&1 | head -2"
                       % (sys.executable, os.path.join(ROOT, "scripts", "tv_throttle.py")),
                       shell=True, capture_output=True, text=True, timeout=60)
    assert "BrokenPipeError" not in r.stdout, r.stdout


def check_the_gap_follows_the_learned_rate(tmp):
    """A fixed gap and a learned rate are two throttles fighting each other: at 4s apart nothing
    above 15/min is reachable, so every rate above that was decorative and the 90/min cap meant
    nothing. Gap and budget now both read effective_rate(), so they cannot disagree."""
    cfg = dict(thr.DEFAULTS)
    for rate in (4, 12, 24, 48):
        gap = thr.effective_gap({"rate": rate}, cfg)
        assert abs(60.0 / gap - rate) < 0.01, (rate, gap)
        assert thr.effective_budget({"rate": rate}, cfg) == rate
    # the floor still applies at the top end, and the cap still binds
    assert thr.effective_gap({"rate": 10000}, cfg) == cfg["min_gap"]
    assert thr.effective_budget({"rate": 10000}, cfg) == cfg["max_rate"]


def check_a_clean_observation_decays_the_block_count(tmp):
    """The docstring promises "success decays", and only --ok was honouring it while SKILL.md
    routes every call through --observe. Left unfixed, escalation ratchets up permanently: the
    second block of a session starts at 10 minutes even after everything recovered."""
    _thr(tmp, "--reset")
    _thr(tmp, "--observe", "HTTPStatusError: 403 Forbidden")
    _, _, st = _thr(tmp, "--status")
    assert "scanner  blocks: 1" in st, st
    for _ in range(3):
        _thr(tmp, "--observe", '{"success":true}')
    _, _, st = _thr(tmp, "--status")
    assert "scanner  blocks: 0" in st and "BLOCKED" not in st, st


def check_a_block_resets_the_clean_call_streak(tmp):
    """Multiplicative decrease only works if the backoff STICKS. With the streak carried across a
    block, nine clean calls then a rate-limit then one more clean call re-raised the rate that was
    just halved - undoing the decrease with a single success."""
    _thr(tmp, "--reset")
    for _ in range(9):
        _thr(tmp, "--observe", '{"success":true}')
    _, _, out = _thr(tmp, "--observe", '{"error":"Too Many Requests"}')
    assert "halved to 6/min" in out, out
    _thr(tmp, "--observe", '{"success":true}')
    _, _, st = _thr(tmp, "--status")
    assert "learned rate           : 6/min" in st, "one clean call re-raised a halved rate: %s" % st


def check_data_that_looks_like_a_status_code_is_not_a_block(tmp):
    """The response given to --observe is usually DATA. A bare \\b403\\b matched the 403 in
    {"close": 403.25}, so any price crossing $403 or $429 cooled the scanner for five minutes,
    halved the rate and made --wait REFUSE the sweep - which SKILL.md says to stop on."""
    for payload in ('{"rows":[{"s":"AAPL","close":403.25}]}', '{"c":429.17}', '{"Perf.6M":403.0}',
                    '{"close":403,"volume":429}', 'status: 403.25'):
        _, rc, out = _thr(tmp, "--observe", payload)
        assert rc == 0 and out.strip().splitlines()[-1].startswith("ok"), (payload, rc, out)
        assert "blocked" not in out and "rate-limited" not in out, (payload, out)
    _, _, st = _thr(tmp, "--status")
    assert "BLOCKED" not in st.upper().replace("NOT BLOCKED", ""), st
    # ...while the genuine articles are still recognised
    for payload, verdict in (("HTTPStatusError: 403 Forbidden", "blocked"), ("HTTP 429 Too Many Requests", "rate-limited"),
                             ("Error 403", "blocked"), ("status code 429", "rate-limited")):
        _, rc, out = _thr(tmp, "--observe", payload)
        assert rc == 2 and out.strip().splitlines()[-1].startswith(verdict), (payload, rc, out)


def check_a_damaged_state_file_is_discarded_not_fatal(tmp):
    """An uncaught exception exits 1 - the code for "REFUSED, the connector is blocked", which
    SKILL.md tells the run to stop on. A state file that is a list, or holds a string where a
    number belongs, raised AttributeError/TypeError/ValueError and ended sweeps that nothing was
    wrong with."""
    state = os.path.join(tmp, "t.json")
    for junk in ("[]", '{"calls":["x"]}', '{"rate":"fast"}', '{"blocked":{"scanner":"x"}}',
                 '{"blocked":{"scanner":{"until":"soon","n":null}}}', "not json at all", '{"calls":[1e999]}'):
        io.open(state, "w", encoding="utf-8").write(junk)
        _, rc, out = _thr(tmp, "--observe", '{"success":true}')
        assert rc == 0, (junk, rc, out)
        _, rc, out = _thr(tmp, "--status")
        assert rc == 0, (junk, rc, out)


def check_the_throttle_survives_where_it_cannot_write(tmp):
    """A bare filename made os.makedirs('') raise; an unwritable directory raised too. Not being
    able to remember the pace degrades the throttle - it must not end the run (exit 1)."""
    script = os.path.join(ROOT, "scripts", "tv_throttle.py")
    env = dict(os.environ, CANSLIM_THROTTLE_STATE="bare-name.json")
    r = subprocess.run([sys.executable, script, "--observe", '{"success":true}'], cwd=tmp,
                       capture_output=True, text=True, timeout=60, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert os.path.exists(os.path.join(tmp, "bare-name.json")), "a bare filename was not written"

    env = dict(os.environ, CANSLIM_THROTTLE_STATE=os.path.join(tmp, "no", "such", "dir", "x.json"))
    blocker = os.path.join(tmp, "no")
    io.open(blocker, "w").close()                 # a FILE where the directory should be: makedirs fails
    r = subprocess.run([sys.executable, script, "--observe", '{"success":true}'], cwd=tmp,
                       capture_output=True, text=True, timeout=60, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "not saved" in r.stderr, "a failed save must say so, not stay silent: %r" % r.stderr


def check_preferred_and_warrant_rows_are_not_graded():
    """A live sweep returned NYSE:HPE/PC - HPE's 7.625% Series C Mandatory Convertible Preferred -
    ranked SEVENTH on 6-month performance, next to HPE itself. Graded as a candidate it would put
    a preferred stock on a recommendation list with a buy point and a stop: no EPS of its own, no
    base, and a price that tracks conversion terms rather than the business."""
    pfd = ss.score_row(row(symbol="NYSE:HPE/PC", description="Hewlett Packard Enterprise Company "
                           "7.625% Series C Mandatory Convertible Preferred Stock"),
                       "Perf.6M", 10.0, CFG)
    assert pfd["triage"] == "drop" and any("not common stock" in d for d in pfd["drop_reasons"])
    for sym, desc in [("NASDAQ:ABCDW", "Acme Corp Warrant"), ("NASDAQ:XYZU", "Something Units"),
                      ("NYSE:FOO/PB", "Foo Inc Series B Preferred")]:
        out = ss.score_row(row(symbol=sym, description=desc), "Perf.6M", 10.0, CFG)
        assert out["triage"] == "drop", (sym, out["drop_reasons"])
    # ...and ordinary common stock still passes, including a DOTTED class like BRK.B
    for sym, desc in [("NYSE:HPE", "Hewlett Packard Enterprise Company"),
                      ("NYSE:BRK.B", "Berkshire Hathaway Inc. Class B"),
                      ("NASDAQ:NVDA", "NVIDIA Corp")]:
        out = ss.score_row(row(symbol=sym, description=desc), "Perf.6M", 10.0, CFG)
        assert out["triage"] == "grade", (sym, out["drop_reasons"])


def check_the_throttle_has_no_flag_that_does_nothing(tmp):
    """`--max-in-window` was accepted, threaded into cfg, and then never read - so
    `--max-in-window 2` ran at 12 and told the user nothing. A flag that is silently ignored is
    worse than one that does not exist: it reads as a working safety limit.

    Guards the general case, not just that one flag: every knob in DEFAULTS must be read
    somewhere, and every CLI option must reach cfg or be used by name in main().
    """
    src = io.open(os.path.join(ROOT, "scripts", "tv_throttle.py"), encoding="utf-8").read()
    body = src.split("DEFAULTS = {", 1)[1]
    keys = re.findall(r'^\s*"([a-z_]+)":', body.split("}", 1)[0], re.M)
    assert keys, "could not read the DEFAULTS block"
    for k in keys:
        uses = len(re.findall(r'cfg\["%s"\]' % k, src))
        assert uses > 0, "DEFAULTS['%s'] is never read - dead config" % k


def check_skill_documents_the_throttle():
    """A throttle nobody is told to call is not a throttle."""
    s = io.open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
    assert "tv_throttle.py" in s, "SKILL.md never tells the run to pace its TradingView calls"
    assert "--wait" in s
    assert "--observe" in s, "SKILL.md never tells the run to CHECK the limit it is pacing against"
    # --scope defaults to "scanner", so a bar-endpoint 403 observed without it records the block
    # against the SCANNER and pauses the sweep for a failure that happened somewhere else. The
    # documented flow has to carry it, or the default quietly misattributes.
    assert "--scope" in s, "SKILL.md's throttle flow omits --scope, so blocks misattribute"
    flow = s[s.index("tv_throttle.py --wait"):]
    flow = flow[:flow.index("```")]
    assert "--scope" in flow, "the --wait/--observe flow itself must pass --scope: %r" % flow
    # The response is remote text. Pasted into a quoted shell argument, "Macy's" breaks the command
    # and a hostile response is injection - so the documented flow reads it from stdin.
    assert "--observe -" in flow, "the documented flow must hand the response over on stdin: %r" % flow
    for doc in ("SKILL.md", os.path.join("scripts", "tv_throttle.py")):
        text = io.open(os.path.join(ROOT, doc), encoding="utf-8").read()
        assert not re.search(r"--observe\s+['\"]", text), \
            "%s shows a response pasted into the command line" % doc

# ---------------------------------------------------------------- the data directory

class _Env(object):
    """Set and restore environment variables, sys.platform and the cwd around a block."""
    def __init__(self, **env):
        self.env, self.saved = env, {}

    def __enter__(self):
        self.cwd, self.plat = os.getcwd(), sys.platform
        for k, v in self.env.items():
            self.saved[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return self

    def __exit__(self, *a):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        sys.platform = self.plat
        os.chdir(self.cwd)


def check_the_data_dir_is_stable_and_overridable(tmp):
    """The caches defaulted to a RELATIVE data/ (wherever you ran the script) or to a folder inside
    the install - and a marketplace install lives in a folder named for the version, so an update
    starts it empty. The default must depend on neither the install nor the working directory."""
    home = os.path.join(tmp, "home")
    os.makedirs(home)
    with _Env(**{dd.ENV: os.path.join(tmp, "mine"), "HOME": home, "USERPROFILE": home,
                 "XDG_CACHE_HOME": None, "LOCALAPPDATA": None}):
        assert dd.data_dir() == os.path.join(tmp, "mine"), "CANSLIM_DATA_DIR was not honoured"
        os.environ[dd.ENV] = "~/elsewhere"
        assert dd.data_dir() == os.path.join(home, "elsewhere"), "~ was not expanded"
        os.environ[dd.ENV] = "   "
        assert dd.data_dir() == dd.default_dir(), "a blank override must count as unset"

        del os.environ[dd.ENV]
        here = dd.data_dir()
        os.chdir(tmp)
        assert dd.data_dir() == here and os.path.isabs(here), "the default moved with the cwd"
        assert not here.startswith(ROOT + os.sep), "the default lives inside the install: %s" % here

        # the per-platform shapes
        sys.platform = "linux"
        os.environ["XDG_CACHE_HOME"] = os.path.join(tmp, "xdg")
        assert dd.default_dir() == os.path.join(tmp, "xdg", "can-slim-recommend")
        del os.environ["XDG_CACHE_HOME"]
        assert dd.default_dir() == os.path.join(home, ".cache", "can-slim-recommend")
        sys.platform = "darwin"
        assert dd.default_dir() == os.path.join(home, "Library", "Caches", "can-slim-recommend")
        sys.platform = "win32"
        assert dd.default_dir() == os.path.join(home, "AppData", "Local", "can-slim-recommend")
        os.environ["LOCALAPPDATA"] = os.path.join(tmp, "lad")
        assert dd.default_dir() == os.path.join(tmp, "lad", "can-slim-recommend")

        # no resolvable home: expanduser hands "~" back, and that must not become a literal folder
        sys.platform = "linux"
        real = os.path.expanduser
        os.path.expanduser = lambda p: p
        try:
            fallback = dd.default_dir()
        finally:
            os.path.expanduser = real
        assert os.path.isabs(fallback) and "~" not in fallback, fallback


def check_datadir_path_cannot_climb_out_and_the_cli_prints_it(tmp):
    root = os.path.join(tmp, "d")
    with _Env(**{dd.ENV: root}):
        assert dd.path("13f", "x.zip") == os.path.join(root, "13f", "x.zip")
        for bad in ("../x", os.path.join("a", "..", "..", "x"), os.path.join(tmp, "elsewhere")):
            try:
                dd.path(bad)
            except ValueError:
                continue
            raise AssertionError("%r escaped the data directory" % bad)
    script = os.path.join(ROOT, "scripts", "datadir.py")
    env = dict(os.environ, **{dd.ENV: root})
    run = lambda *a: subprocess.run([sys.executable, script] + list(a), capture_output=True,
                                    text=True, timeout=30, env=env)
    assert run().stdout.strip() == root
    assert run("i-cache.json").stdout.strip() == os.path.join(root, "i-cache.json")
    bad = run("../x")
    assert bad.returncode == 2 and "not inside" in bad.stderr, (bad.returncode, bad.stderr)


def check_every_cache_defaults_into_the_data_dir(tmp):
    """Three scripts used to pick their own default. Each must now land in the data directory when
    given no flag, and an explicit flag or CANSLIM_THROTTLE_STATE must still win."""
    root = os.path.join(tmp, "data")
    clean = {k: v for k, v in os.environ.items() if k != "CANSLIM_THROTTLE_STATE"}
    clean[dd.ENV] = root
    status = lambda env: subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "tv_throttle.py"),
                                         "--status"], capture_output=True, text=True, timeout=30, env=env).stdout
    assert os.path.join(root, ".tv-throttle.json") in status(clean), "the pacing state ignored the data dir"
    pinned = dict(clean, CANSLIM_THROTTLE_STATE=os.path.join(tmp, "pinned.json"))
    assert os.path.join(tmp, "pinned.json") in status(pinned), "CANSLIM_THROTTLE_STATE no longer wins"

    def quiet_main(fn, argv):
        real_argv, real_out = sys.argv, sys.stdout
        sys.argv, sys.stdout = ["x"] + argv, io.StringIO()
        try:
            return fn()
        finally:
            sys.argv, sys.stdout = real_argv, real_out

    with _Env(**{dd.ENV: root}):
        real = (ic.list_datasets, ic.http)
        ic.list_datasets = lambda *a, **k: ([{"name": "01mar2026-31may2026_form13f.zip",
                                              "start": "2026-03-01", "end": "2026-05-31",
                                              "url": "https://www.sec.gov/x.zip"}], None)
        ic.http = lambda *a, **k: (b"PK" + b"z" * 2000, None)
        try:
            quiet_main(ic.main, ["--quarter", "2026Q1", "--contact", "me@mydomain.org"])
        finally:
            ic.list_datasets, ic.http = real
        assert os.path.exists(os.path.join(root, "13f", "01mar2026-31may2026_form13f.zip")), \
            "institutional_cache ignored the data dir for its zips: %s" % os.listdir(root)

        syms = os.path.join(tmp, "syms.json")
        io.open(syms, "w", encoding="utf-8").write('["NYSE:AAA"]')
        real_http, calls = aeps.http, []
        def offline(*a, **k):                                     # never reach the network from a test
            calls.append(a)
            return b"{}", None
        aeps.http = offline
        try:
            quiet_main(aeps.main, [syms, "--contact", "me@mydomain.org"])
            assert os.path.exists(os.path.join(root, "sec-eps", "company_tickers.json")), \
                "annual_eps ignored the data dir for its cache"
            explicit = os.path.join(tmp, "explicit")              # an explicit flag still wins
            quiet_main(aeps.main, [syms, "--contact", "me@mydomain.org", "--cache-dir", explicit])
            assert os.path.exists(os.path.join(explicit, "company_tickers.json")), \
                "--cache-dir no longer wins over the data dir"
        finally:
            aeps.http = real_http
        assert calls, "the offline stand-in was never used, so the test proved nothing"


def check_an_unwritable_cache_dir_does_not_stop_a_run(tmp):
    """Moving the default into a home folder makes "cannot write there" a live possibility. Every
    cache here is an optimisation, so failing to write one must cost a slower run, not a crashed
    one. (A regular file stands in for the folder, so this holds when the tests run as root.)"""
    blocker = os.path.join(tmp, "blocker")
    io.open(blocker, "w").close()
    bad = os.path.join(blocker, "sub")
    real = ic.http
    ic.http = lambda *a, **k: (b"PK" + b"z" * 2000, None)
    err, real_err = io.StringIO(), sys.stderr
    sys.stderr = err
    try:
        data, where = ic.get_dataset({"name": "d.zip", "url": "https://www.sec.gov/d.zip"},
                                     "me@mydomain.org", 5, bad)
    finally:
        ic.http, sys.stderr = real, real_err
    assert data and data[:2] == b"PK", (data, where)
    assert "could not cache" in err.getvalue(), "a failed cache write must say so"
    assert aeps._cached(os.path.join(bad, "x.json"), lambda: (b'{"ok":1}', None), pause=0) == b'{"ok":1}'


def check_docs_point_at_the_data_dir_and_not_a_relative_data_folder():
    """The docs showed `-o data/i-cache.json`, which lands in whatever directory the command ran
    from. They must teach the stable location instead, and name the override."""
    skill = io.open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
    readme = io.open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    assert "CANSLIM_DATA_DIR" in readme and "datadir.py" in readme and "datadir.py" in skill
    relative = re.compile(r"(?:-o|--out|--known|--cache-dir)\s+['\"]?data/")
    for rel in ["SKILL.md", "README.md"] + sorted("scripts/" + f for f in os.listdir(
            os.path.join(ROOT, "scripts")) if f.endswith(".py")):
        text = io.open(os.path.join(ROOT, rel), encoding="utf-8").read()
        hit = relative.search(text)
        assert not hit, "%s still shows a relative data/ path: %r" % (rel, hit.group(0))


# ---------------------------------------------------------------- doc/consistency

def _frontmatter_description(path):
    """Resolve SKILL.md's `description: >-` block the way a YAML folded scalar does: every line
    stripped and joined with single spaces. The file's own line breaks are invisible to whatever
    reads the frontmatter, so the source length is NOT the length that counts."""
    src = io.open(path, encoding="utf-8").read()
    assert src.startswith("---\n"), "SKILL.md must open with frontmatter"
    fm = src.split("---", 2)[1]
    m = re.search(r"description: >-\n(.*?)(?=\n[a-z_]+:|\Z)", fm, re.S)
    assert m, "SKILL.md has no folded description block"
    return " ".join(l.strip() for l in m.group(1).strip().splitlines())


DESCRIPTION_LIMIT = 1024


def check_skill_description_fits_the_frontmatter_limit():
    """A description over the limit is the worst kind of failure this skill has: nothing errors,
    the file looks fine, and the skill just stops being offered for the phrases it lists. It had
    grown to 1108 characters unnoticed. Pinned here because no run would ever reveal it.
    """
    d = _frontmatter_description(os.path.join(ROOT, "SKILL.md"))
    assert len(d) <= DESCRIPTION_LIMIT, (
        "SKILL.md description is %d characters, %d over the %d limit - trim it, and keep the "
        "trigger phrases: they are what earns the skill its activations."
        % (len(d), len(d) - DESCRIPTION_LIMIT, DESCRIPTION_LIMIT))
    # the parts worth keeping must survive any future trim
    for must in ("CAN SLIM", "can-slim-grader", "recommend some stocks", "what should I buy",
                 "4.5", "never personalized investment advice"):
        assert must in d, "the description no longer mentions %r" % must


def check_skill_frontmatter_conforms(tmp):
    """The rules an importer enforces before it will load the skill at all. Each of these fails
    SILENTLY somewhere - a BOM hides the opening '---', a tab makes the YAML unparseable, an
    unrecognised key is rejected wholesale - so the skill simply does not appear, with no error
    pointing at the file."""
    raw = io.open(os.path.join(ROOT, "SKILL.md"), "rb").read()
    assert not raw.startswith(b"\xef\xbb\xbf"), "a UTF-8 BOM hides the opening '---'"
    assert b"\r\n" not in raw, "CRLF line endings"
    assert raw.endswith(b"\n"), "no trailing newline"
    src = raw.decode("utf-8")
    assert src.startswith("---\n"), "frontmatter must start on line 1"
    fm, body = src.split("---", 2)[1], src.split("---", 2)[2]
    assert "\t" not in fm, "YAML forbids tabs for indentation"

    keys = re.findall(r"^([A-Za-z_][A-Za-z0-9_-]*):", fm, re.M)
    assert set(keys) <= {"name", "description", "license", "allowed-tools", "metadata", "version"}, \
        "unrecognised frontmatter key in %r" % keys
    assert {"name", "description"} <= set(keys), "name and description are both required"
    name = re.search(r"^name:\s*(.+)$", fm, re.M).group(1).strip()
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), "name %r must be lowercase-and-hyphen" % name
    assert len(name) <= 64, "name is %d chars (limit 64)" % len(name)
    assert re.search(r"^#\s+\S", body, re.M), "the body needs a top-level heading"


def check_no_angle_bracket_placeholders(tmp):
    """`<date>`, `<SYM>` and friends read as HTML tags. A markdown renderer or an importer that
    sanitises HTML drops them, so the reader is told to run
    `build_report.py canslim-recommendations-.html`. Placeholders use {braces} throughout.

    README's `<html>` is exempt: it names the actual element whose data-theme you edit.
    """
    for rel in ["SKILL.md", "README.md"] + ["references/" + f for f in
                                            sorted(os.listdir(os.path.join(ROOT, "references")))
                                            if f.endswith(".md")]:
        text = io.open(os.path.join(ROOT, rel), encoding="utf-8").read()
        found = [t for t in re.findall(r"</?[a-zA-Z][a-zA-Z0-9_ -]*/?>", text)
                 if not (rel == "README.md" and t == "<html>")]
        assert not found, "%s uses angle-bracket placeholders %s - use {braces}" % (rel, sorted(set(found)))


def check_no_reference_points_at_a_workflow_step_that_moved():
    """Inserting a step renumbers every later one, and the cross-references elsewhere do not
    follow. Inserting the market-session check as step 1 left SKILL.md pointing at "step 4a" (now
    5a), "Step 7" (now 8), and build_report.py calling itself "the entry point for step 7" - each
    silently sending a reader to the wrong instruction. "step-7 entry point" survived that, in
    SKILL.md and the exporter, because the pattern only matched "step 7" with a space.

    A reference qualified by a file - "`tradingview-sector-sweep.md` Step 4" - points into THAT
    file's numbering, which is its own ("## Step 4"), not SKILL.md's. The first version checked
    every reference against SKILL.md and so passed those only by coincidence (SKILL.md also had a
    step 4); it broke the day SKILL.md lost its step 0 while the sweep guide kept its own.
    """
    skill = io.open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
    # the headings that actually exist, e.g. {"1","2","5a",...}
    steps = set(re.findall(r"^###\s+([0-9]+[a-z]?)\s+—", skill, re.M))
    assert len(steps) >= 8, "could not read the workflow headings: %s" % sorted(steps)
    targets = [os.path.join(ROOT, "SKILL.md"), os.path.join(ROOT, "scripts", "build_report.py")]
    exporter = os.path.join(ROOT, "scripts", "export_portable.py")
    if os.path.exists(exporter):             # a portable copy ships this suite, not the exporter
        targets.append(exporter)
    qualified = re.compile(r"([\w/-]+\.md)`?\s+[Ss]tep[\s-]+([0-9]+[a-z]?)\b")
    bad = []
    for path in targets:
        name = os.path.basename(path)
        text = io.open(path, encoding="utf-8").read()
        for m in qualified.finditer(text):
            if os.path.basename(m.group(1)) == "SKILL.md":
                theirs = steps
            else:
                doc = os.path.join(ROOT, "references", os.path.basename(m.group(1)))
                if not os.path.exists(doc):
                    bad.append("%s: %s is not a file under references/" % (name, m.group(1)))
                    continue
                theirs = set(re.findall(r"^##\s+Step\s+([0-9]+[a-z]?)\s+—",
                                        io.open(doc, encoding="utf-8").read(), re.M))
            if m.group(2) not in theirs:
                bad.append("%s: '%s step %s' (that file's steps are %s)"
                           % (name, m.group(1), m.group(2), sorted(theirs)))
        # whatever is left refers to SKILL.md's own workflow
        for m in re.finditer(r"\b[Ss]tep[\s-]+([0-9]+[a-z]?)\b", qualified.sub("", text)):
            if m.group(1) not in steps:
                bad.append("%s: 'step %s' (headings are %s)" % (name, m.group(1), sorted(steps)))
    assert not bad, "cross-reference to a workflow step that does not exist: %s" % bad[:4]


def check_market_session_classifies_the_whole_day():
    """Before the open and after the close BOTH serve the last complete session, which is what S
    needs - so the condition is "a session is not in progress", not "it is after the close"."""
    import datetime
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        return "skipped: no zoneinfo"
    et = ZoneInfo("America/New_York")
    cases = [((2026, 9, 24, 8, 0), "premarket", True), ((2026, 9, 24, 9, 31), "open", False),
             ((2026, 9, 24, 13, 0), "open", False), ((2026, 9, 24, 16, 10), "settling", False),
             ((2026, 9, 24, 16, 35), "after-close", True), ((2026, 9, 26, 11, 0), "weekend", True)]
    for parts, state, gradeable in cases:
        v = mses.classify(datetime.datetime(*parts, tzinfo=et))
        assert v["state"] == state and v["s_gradeable"] is gradeable, (parts, v)


def check_a_long_wait_is_never_sat_through_silently():
    """THE policy question. Waiting until after the close sounds tidy and is a trap: a run started
    at 09:31 would block for nearly seven hours, and an agent that disappears for the afternoon has
    failed the person who asked for stock ideas whatever it eventually prints. Short waits are
    waited; long ones are announced with a resume time so the user can choose."""
    import datetime
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        return "skipped: no zoneinfo"
    et = ZoneInfo("America/New_York")
    just_opened = mses.classify(datetime.datetime(2026, 9, 24, 9, 31, tzinfo=et))
    assert just_opened["wait_seconds"] > mses.MAX_AUTO_WAIT, "a 7-hour wait must not be automatic"
    out = mses.render(just_opened)
    assert "too long to sit through" in out and "16:30" in out, out
    assert "Do NOT silently block" in out

    near_bell = mses.classify(datetime.datetime(2026, 9, 24, 15, 55, tzinfo=et))
    assert 0 < near_bell["wait_seconds"] <= mses.MAX_AUTO_WAIT, near_bell
    assert "short wait" in mses.render(near_bell)


def check_eastern_time_is_exact_without_a_tz_database():
    """Without tzdata (stock Windows Python, slim containers) ZoneInfo raises, and the module fell
    back to the MACHINE clock labelled ET: a container on UTC at 16:30 (12:30 ET, session open)
    read as "after-close, S gradeable", and S was graded on a partial session with no warning.
    The fallback now computes ET from UTC with the US DST rule, and must agree with the database."""
    import datetime as D
    utc = D.timezone.utc
    for parts, want_hour in (((2026, 7, 1, 16, 0), 12), ((2026, 1, 15, 16, 0), 11),
                             ((2026, 3, 8, 6, 59), 1), ((2026, 3, 8, 7, 0), 3),       # spring forward
                             ((2026, 11, 1, 5, 59), 1), ((2026, 11, 1, 6, 0), 1)):    # fall back
        got = mses.et_from_utc(D.datetime(*parts, tzinfo=utc))
        assert got.hour == want_hour, (parts, got)
    try:
        from zoneinfo import ZoneInfo
        real = ZoneInfo("America/New_York")
    except Exception:
        real = None
    if real is not None:                       # agree with the database, boundaries included
        t = D.datetime(2024, 1, 1, tzinfo=utc)
        while t.year < 2032:
            assert mses.et_from_utc(t).replace(tzinfo=None) == t.astimezone(real).replace(tzinfo=None), t
            t += D.timedelta(minutes=97)
        for y in range(2024, 2032):
            for m, d in ((3, 8), (3, 14), (11, 1), (11, 7)):
                for h in range(0, 24):
                    t = D.datetime(y, m, d, h, 30, tzinfo=utc)
                    assert mses.et_from_utc(t).replace(tzinfo=None) == t.astimezone(real).replace(tzinfo=None), t
    # ...and the failure that mattered: no database, container clock on UTC, session open
    v = mses.classify(mses.et_from_utc(D.datetime(2026, 9, 22, 16, 30, tzinfo=utc)))     # Tue 12:30 ET
    assert v["state"] == "open" and v["s_gradeable"] is False, v
    saved = mses.ET
    mses.ET = None
    try:
        assert mses.now_et().utcoffset() in (D.timedelta(hours=-4), D.timedelta(hours=-5))
    finally:
        mses.ET = saved


def check_confirming_the_market_open_actually_holds_the_run(tmp):
    """--confirm-open exists to override the clock, which cannot see an early close. The first
    version overrode the STATE but kept the premarket dict's wait_seconds=0, so `--wait` slept for
    nothing, reclassified from the clock and exited 0 - the override could not hold the run, which
    is the only thing it is for."""
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "market_session.py"),
                        "--confirm-open", "true", "--json"],
                       capture_output=True, text=True, timeout=60)
    v = json.loads(r.stdout)
    assert r.returncode == 2 and v["s_gradeable"] is False, (r.returncode, v)
    assert v["wait_seconds"] > 0 and v["resume_at_et"], \
        "the override reports no wait, so --wait would sleep zero and pass: %s" % v


def check_skill_documents_the_market_session_check():
    s = io.open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
    assert "market_session.py" in s, "SKILL.md never tells the run to check the session"
    assert "partial sum" in s, "SKILL.md never says WHY a live session breaks S"
    assert "Never block silently for hours" in s, "SKILL.md omits the wait policy"


def check_skill_documents_the_fresh_data_policy():
    """These standing rules once sat under a '### 0' heading about checking for skill updates, so
    removing that step could have taken them along - and nothing else pins the prose. They govern
    every step, so they live in their own section ahead of the numbered workflow."""
    s = io.open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
    for must in ("## Fresh data, every run", "ALWAYS ATTEMPT FRESH DATA",
                 "### When a fresh pull fails", "### Always date the data"):
        assert must in s, "SKILL.md lost %r" % must
    assert s.index("## Fresh data, every run") < s.index("## Workflow"), \
        "the fresh-data rules must be read before the first numbered step, not buried inside one"


def check_the_self_update_machinery_stays_removed():
    """Updating is the installer's job now (a marketplace), not the skill's. What fails badly is
    half of the feature coming back: a doc telling the run to execute a script that no longer
    exists, or to log a 'skill version' failure nothing can produce. Neither errors anywhere - the
    run just chases an instruction that cannot be followed."""
    gone = os.path.join(ROOT, "scripts", "check_for_updates.py")
    assert not os.path.exists(gone), "scripts/check_for_updates.py is back"
    needles = ("check_for_" + "updates", "skill " + "version", "--" + "update",
               "fast" + "-forward", "git " + "fetch")
    for top in ("SKILL.md", "README.md", "references", "scripts", "assets", ".gitignore"):
        path = os.path.join(ROOT, top)
        files = [path] if os.path.isfile(path) else [
            os.path.join(d, f) for d, _, fs in os.walk(path) for f in fs
            if f.endswith((".md", ".py", ".html"))]
        for f in files:
            text = io.open(f, encoding="utf-8").read().lower()
            for n in needles:
                assert n not in text, "%s still mentions %r" % (os.path.relpath(f, ROOT), n)
    assert not re.search(r"^###\s+0\s+—", io.open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read(), re.M), \
        "SKILL.md has a step 0 again - the workflow starts at step 1"


def check_fmp_is_last_on_every_source_ladder():
    """FMP ranks below web search on every ladder, which is evidence rather than taste: on this
    account `form13F` needs Ultimate/Enterprise and `insiderTrades` needs Starter or above, and
    both returned ACCESS DENIED. A source that refuses more often than it answers belongs under
    one that always returns something.

    Pinned because a ladder is prose: reordering one back is a two-word edit that changes which
    source a run actually reaches for, and nothing else in the suite would notice.
    """
    for rel in ["SKILL.md", "README.md"] + ["references/" + f for f in
                                            sorted(os.listdir(os.path.join(ROOT, "references")))
                                            if f.endswith(".md")]:
        for i, line in enumerate(io.open(os.path.join(ROOT, rel), encoding="utf-8"), 1):
            if "FMP" not in line or "\u2192" not in line:
                continue
            # Only real source ladders: a fallback-table row, or prose that calls itself a ladder.
            # An arrow also joins ENDPOINTS of one source ("`search` -> `search-company-screener`"),
            # which is a call chain, not a ranking - the first version of this test flagged one.
            if not (line.lstrip().startswith("|") or "ladder" in line.lower()):
                continue
            hops = line.split("\u2192")
            bad = [h.strip() for h in hops[:-1] if "FMP" in h]
            assert not bad, ("%s:%d puts FMP ahead of %r on a source ladder - it is the last rung "
                             "everywhere, below web search" % (rel, i, hops[-1].strip()[:40]))


def check_docs_have_no_dead_scale():
    for f in ("SKILL.md", "README.md", "references/canslim-methodology.md"):
        s = io.open(os.path.join(ROOT, f), encoding="utf-8").read()
        for bad in ("/70", "out of 70"):
            assert bad not in s, "%s mentions %r" % (f, bad)


def check_the_prose_grades_the_same_way_the_code_does():
    """Two rungs once said one thing in prose and another in code, and prose is what a human
    grader reads. Both were resolved in favour of the code, and both directions are pinned here
    so restoring either wording fails a test instead of quietly moving a grade.

      L. The prose demanded the #1 or #2 name in a strong group; `cap_l` caps at PARTIAL only
         once the rank passes HALF the group. Grading to the prose costs half a point on nearly
         every name this skill reports - #3 of 20 is a comfortable pass in code and a partial in
         the old words.
      N. The prose called extension >25% above the 50-day a FAIL; the code raises a flag and
         leaves the letter to the 52-week-high distance. Grading to the prose fails N outright
         on a name that is merely running ahead of a sound base, which is a PARTIAL with no
         entry price, not a broken chart.

    This runs without a can-slim-grader checkout, so it guards the rungs even when the
    cross-repo parity layer is skipped. The methodology file is shared, so a green result here
    is also a statement about the sister's copy.
    """
    md = io.open(os.path.join(ROOT, "references", "canslim-methodology.md"),
                 encoding="utf-8").read()

    def rung(letter):
        m = re.search(r"\*\*%s\.\*\*(.+?)(?=\n- \*\*|\n\n)" % letter, md, re.S)
        assert m, "no %s rung in the shared methodology - the extractor is stale" % letter
        return " ".join(m.group(1).split())

    n_text, l_text = rung("N"), rung("L")
    assert re.search(r"PASS needs.{0,60}top half", l_text), \
        "L's rung no longer states the top-half pass bar the code implements"
    assert not re.search(r"PASS needs[^.]{0,80}#1 or #2", l_text), \
        "L's rung is back to demanding the #1 or #2 name, which cap_l does not"
    assert re.search(r"50-day.{0,160}flag, not a FAIL", n_text), \
        "N's rung no longer says the 50-day extension is a flag rather than a FAIL"
    assert not re.search(r"50-day[^.]{0,120}is a \*\*FAIL\*\*", n_text), \
        "N's rung is back to calling the 50-day extension a FAIL, which cap_n never returns"

    # ...and the code still behaves the way the prose now describes.
    for rank, want in ((1, "pass"), (10, "pass"), (11, "partial"), (20, "partial")):
        out = {"symbol": "X:Y", "off_high_pct": -1.0, "rel_volume_10d": 1.2,
               "sector_rank_overall": rank, "sector_count": 20}
        ss.ceiling(out, CFG, {})
        assert out["ceiling_caps"]["L"] == want, (rank, out["ceiling_caps"]["L"])

    ext = ss.score_row(row(close=100.0, price_52_week_high=100.0, EMA50=60.0, EMA200=50.0),
                       "Perf.6M", 10.0, CFG)
    ss.ceiling(ext, CFG, {})
    assert ext["vs_ema50_pct"] > 25.0
    assert ext["ceiling_caps"]["N"] == "pass", "extension must not move N's cap"
    assert any("50-day" in f for f in ext["flags"]), "the run-up must still be reported"
    assert not any("50-day" in d for d in ext["drop_reasons"]), \
        "extension is context, never a disqualification"


def check_readme_install_uses_the_real_marketplace_commands():
    """The install instructions name the-wong-marketplace and this plugin's exact id. They were
    checked against the real thing - the marketplace was added, the plugin installed from it, and
    the session reported the skill as can-slim-recommend:can-slim-recommend - so a trim that
    drops them, or a typo in the id, would leave a reader with a command that does nothing."""
    readme = io.open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    install = readme.split("## Install", 1)[1].split("\n## ", 1)[0]
    for must in ("/plugin marketplace add thewongdirection/the-wong-marketplace",
                 "/plugin install can-slim-recommend@the-wong-marketplace",
                 "claude plugin update can-slim-recommend@the-wong-marketplace",
                 "claude plugin marketplace update the-wong-marketplace"):
        assert must in install, "README's Install section lost %r" % must
    for companion in ("securities-filings-lookup", "can-slim-grader", "ibkr-review-ticker"):
        assert "/plugin install %s@the-wong-marketplace" % companion in install, \
            "the marketplace install line for %s is missing" % companion


def check_the_companion_data_skills_are_documented_as_installs():
    """`securities-filings-lookup` is not a nice-to-have; it is the PRIMARY source for C and A.

    A reader who installs this skill alone gets a working run whose C and A quietly come off a
    fallback rung, and nothing on the page says a better source existed. So the install
    instructions have to name it as something to download, with its repo URL, in the place where
    someone is actually cloning things - a mention buried in a reference file reaches the model
    and not the person. Pinned because doc trims delete exactly this kind of paragraph: it reads
    like an aside, and the only symptom of losing it is a quieter, worse-sourced report.
    """
    readme = io.open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    skill = io.open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()

    install = readme.split("## Install", 1)
    assert len(install) == 2, "README has no ## Install section"
    install = install[1].split("\n## ", 1)[0]
    for repo in ("securities-filings-lookup", "can-slim-grader", "ibkr-review-ticker"):
        url = "https://github.com/thewongdirection/%s" % repo
        assert url in install, \
            "README's Install section never tells the reader to get %s from %s" % (repo, url)
    assert re.search(r"git clone\s+\S*securities-filings-lookup", install), \
        "the filings lookup is named in Install but not as something to clone"

    # ...and both documents have to say WHY, or the reader treats it as an optional extra.
    for name, text in (("README", readme), ("SKILL.md", skill)):
        assert re.search(r"(?:part of|one of).{0,60}data.{0,20}sourc", text, re.I), \
            "%s does not say the companion skills are part of this skill's data sourcing" % name

    # A missing companion must be reported, never silently swapped for a weaker rung.
    assert "not installed" in skill and "install it" in skill.lower(), \
        "SKILL.md no longer tells the run to prompt for a missing companion skill"


def check_every_script_is_listed_in_the_docs():
    """README's Contents and SKILL.md's 'Files in this skill' are the only map of what ships.
    Seven scripts were missing from SKILL.md's and three from README's, and nothing noticed -
    an unlisted script is one a reader (or a model loading SKILL.md cold) never learns exists.
    The exporter is exempt from SKILL.md: it is packaging, not part of a run."""
    docs = {name: io.open(os.path.join(ROOT, name), encoding="utf-8").read()
            for name in ("README.md", "SKILL.md")}
    for f in sorted(os.listdir(os.path.join(ROOT, "scripts"))):
        if not f.endswith(".py"):
            continue
        for name, text in docs.items():
            if name == "SKILL.md" and f == "export_portable.py":
                continue
            assert "scripts/" + f in text, "%s does not list scripts/%s" % (name, f)


def check_every_script_compiles():
    import py_compile
    d = os.path.join(ROOT, "scripts")
    for f in sorted(os.listdir(d)):
        if f.endswith(".py"):
            py_compile.compile(os.path.join(d, f), doraise=True)


# ------------------------------------------------- securities-filings-lookup sourcing

"""Where C/A come from, and the one place that skill must never be used.

Ported from can-slim-grader, where the same two contradictions were found and fixed. Both
repos now state this policy identically, and both pin it.

The sharp half is the second one. `securities-filings-lookup` resolves ticker -> that
company's OWN CIK, so an operating company which is itself a 13F filer returns what it OWNS
rather than who owns it - NVDA's CIK carries eleven 13F-HRs listing Coherent, CoreWeave,
Intel, Nebius, Nokia and Synopsys. Graded as I that is a portfolio dressed as a shareholder
base: a plausible wrong answer, which is worse than an empty one. Sponsorship is an
aggregation across every filer, which is what institutional_cache.py is for. The IBKR guide
said to use the filings skill for I until this port, contradicting the sweep guide two files
over.
"""

FILINGS = "securities-filings-lookup"
_I_SOURCING = re.compile(r"13F|Form 4|sponsorship|institutional ownership", re.I)
# A negation has to sit NEXT to the mention, not merely somewhere in the same sentence: in the
# grader a sentence-wide check passed the old wording, because an unrelated "cannot" earlier in
# the same sentence satisfied it. 48 characters either side is what makes this able to fail.
_NEGATION = re.compile(r"\bnot\b|\bcannot\b|\bcan't\b|\bnever\b|\binstead\b|\bwrong\b", re.I)
_NEAR = 48
# The name-based check above is blind to a pronoun: "Also use IT for I" reintroduced the bug and
# passed, because the claim never repeats the skill's name. Inside the rung that IS the filings
# skill, an imperative "use ... for I" is wrong however it refers to the skill, so that block gets
# its own rule. Descriptive prose ("Graded as I that is...") is not imperative and is left alone.
_USE_FOR_I = re.compile(
    r"\b(?:use|used|using|take|taken|takes|source|sourced|reach|pull|get|fetch)\b"
    r"[^.]{0,60}?\b(?:for|at|from)\s+\*?\*?I\*?\*?(?=[\s.,:;)]|$)", re.I)
_BEFORE = 34   # characters before the match that must carry the negation

_DOCS = ("SKILL.md",
         os.path.join("references", "ibkr-data-guide.md"),
         os.path.join("references", "tradingview-sector-sweep.md"))


def _doc(rel):
    return io.open(os.path.join(ROOT, rel), encoding="utf-8").read()


def _ladder(ibkr):
    """Just the fundamental-source ladder. Slicing to end-of-file swallowed the numbered list
    that follows it, whose own "1." silently overwrote rung 1 and made this pass on a broken
    cross-reference."""
    start = ibkr.index("**Fundamental source priority")
    return ibkr[start:ibkr.index("**Handling gated / throttled", start)]


def _claims(text):
    """Claim-sized chunks. A Markdown table ROW is its own claim - table rows carry no full
    stops, so flattening a table into one chunk would let a legitimate C/A mention sit beside
    the I row and mask exactly the pairing these checks look for."""
    out = []
    for blk in re.split(r"\n\s*\n", text):
        lines = blk.split("\n")
        out.extend(" ".join(r.split()) for r in lines if r.lstrip().startswith("|"))
        rest = " ".join(" ".join(l.split()) for l in lines if not l.lstrip().startswith("|"))
        out.extend(s for s in re.split(r"(?<=[.!?])\s+", rest) if s)
    return out


def check_filings_lookup_is_documented_as_part_of_the_data_sourcing():
    """A reader who never installs it grades C/A off vendor-derived fields, unwarned."""
    s, ibkr = _doc("SKILL.md"), _doc(os.path.join("references", "ibkr-data-guide.md"))
    for doc, rel in ((s, "SKILL.md"), (ibkr, "references/ibkr-data-guide.md")):
        flat = " ".join(doc.split())
        assert re.search(r"part of this skill's data sourcing, not (?:an )?optional extras?", flat), \
            "%s does not call %s part of the data sourcing" % (rel, FILINGS)
        assert re.search(r"primary source for C and A", flat), \
            "%s does not name it primary for C/A" % rel
    assert "https://github.com/thewongdirection/" + FILINGS in ibkr, \
        "the IBKR guide gives no repo to install it from"
    assert "should install it too" in " ".join(s.split()), \
        "SKILL.md never tells the user to install it alongside this skill"


def check_a_missing_filings_skill_is_reported_not_silently_absorbed():
    ibkr = " ".join(_doc(os.path.join("references", "ibkr-data-guide.md")).split())
    assert "If it is not installed, say so" in ibkr, "the IBKR guide allows a silent fallback"
    assert "vendor-derived" in ibkr, "it never says what the substituted figures are"


def check_filings_lookup_is_never_offered_as_a_source_for_I():
    """The whole point of the port: it answers what a company OWNS, not who owns it."""
    for rel in _DOCS:
        for claim in _claims(_doc(rel)):
            if FILINGS not in claim or not _I_SOURCING.search(claim):
                continue
            for m in re.finditer(re.escape(FILINGS), claim):
                win = claim[max(0, m.start() - _NEAR):m.end() + _NEAR]
                assert _NEGATION.search(win), \
                    "%s names %s as an I source: %s" % (rel, FILINGS, claim[:200])


def check_the_filings_rung_never_tells_anyone_to_source_I_from_it():
    """Pronoun-proof version of the check above, scoped to the rung about the filings skill."""
    rung = _ladder(_doc(os.path.join("references", "ibkr-data-guide.md")))
    rung = " ".join(rung[:rung.index("\n2. **")].split())
    for m in _USE_FOR_I.finditer(rung):
        lead = rung[max(0, m.start() - _BEFORE):m.start()]
        assert _NEGATION.search(lead) or _NEGATION.search(m.group(0)), \
            "the filings rung tells the run to source I from it: %r" % m.group(0)


def check_the_cik_trap_is_explained_with_its_evidence():
    """Without the worked example this reads as a rule to be argued with rather than a finding."""
    for rel in ("SKILL.md", os.path.join("references", "ibkr-data-guide.md"),
                os.path.join("references", "tradingview-sector-sweep.md")):
        flat = " ".join(_doc(rel).split())
        assert re.search(r"(?:keyed on the ticker's|resolves ticker).{0,40}CIK", flat), \
            "%s omits the ticker -> own-CIK mechanism" % rel
        assert "eleven 13F-HRs" in flat, "%s omits the NVDA evidence" % rel
        assert re.search(r"not who owns NVIDIA", flat), "%s omits the direction" % rel


def check_I_is_sourced_by_aggregating_across_filers():
    for rel in _DOCS:
        flat = " ".join(_doc(rel).split())
        assert "institutional_cache.py" in flat, \
            "%s never points I at the 13F aggregation" % rel
        assert re.search(r"aggregation across (?:every )?filer", flat), \
            "%s never says I is an aggregation rather than a lookup" % rel


def check_the_two_fundamental_ladders_agree_on_what_comes_first():
    """They ranked the same four sources oppositely: the Tier-2 table put filings first for C/A
    while the IBKR ladder had them 4th, below Daloopa/bigdata/LSEG. Same question, two answers."""
    ibkr = _doc(os.path.join("references", "ibkr-data-guide.md"))
    body = _ladder(ibkr)
    rungs = re.findall(r"^(\d+)\. \*\*(.+?)\*\*", body, re.M)
    assert rungs, "the fundamental ladder has moved"
    first_n, first_name = rungs[0]
    assert first_n == "1" and FILINGS in first_name, \
        "the IBKR ladder no longer opens with the filings rung: %r" % (rungs[0],)
    for n, name in rungs[1:]:
        assert FILINGS not in name, "%s is also ranked as fallback %s" % (FILINGS, n)

    sweep = _doc(os.path.join("references", "tradingview-sector-sweep.md"))
    row = re.search(r"^\| C / A fundamentals \|.*$", sweep, re.M)
    assert row, "the Tier-2 C/A row has moved"
    order = row.group(0)
    assert order.index(FILINGS) < order.index("Daloopa"), \
        "the Tier-2 table no longer puts the filings skill first for C/A"


def check_no_dangling_rung_number_references():
    """Renumbering a ladder silently breaks every cross-reference into it."""
    ibkr = _doc(os.path.join("references", "ibkr-data-guide.md"))
    rungs = dict((n, name) for n, name
                 in re.findall(r"^(\d+)\. \*\*(.+?)\*\*", _ladder(ibkr), re.M))
    for n in re.findall(r"rung (\d+)", ibkr):
        assert n in rungs, "text refers to rung %s, which the ladder does not have" % n
    m = re.search(r"official filings \(rung (\d+)\)", ibkr)
    assert m and FILINGS in rungs[m.group(1)], \
        "the 'official filings (rung N)' cross-reference points at the wrong rung"


# ---------------------------------------------------------------- runner

def main():
    # The suite must never read or write a real user's caches. Every script resolves its default
    # folder from $CANSLIM_DATA_DIR (datadir.py), and the subprocesses the tests start inherit it.
    sandbox = tempfile.mkdtemp(prefix="canslim-data-")
    os.environ["CANSLIM_DATA_DIR"] = sandbox
    try:
        return _run_suites()
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def _run_suites():
    want = [a for a in sys.argv[1:] if not a.startswith("-")]
    verbose = "-v" in sys.argv
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("check_") and callable(f)]
    if want:
        tests = [(n, f) for n, f in tests if any(w in n for w in want)]
    passed = failed = skipped = 0
    fails = []
    for name, fn in tests:
        tmp = tempfile.mkdtemp(prefix="canslim-test-")
        try:
            note = fn(tmp) if fn.__code__.co_argcount else fn()
            if isinstance(note, str) and note.startswith("skipped"):
                skipped += 1
                print("  SKIP %s (%s)" % (name, note))
            else:
                passed += 1
                if verbose:
                    print("  ok   %s" % name)
        except Exception as e:
            failed += 1
            fails.append((name, e))
            print("  FAIL %s\n         %s: %s" % (name, type(e).__name__, e))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d passed, %d failed, %d skipped (%d total)" %
          (passed, failed, skipped, len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
