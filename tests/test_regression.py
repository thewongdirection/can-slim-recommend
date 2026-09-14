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
  * check_for_updates must fail OPEN and must never pull over uncommitted work
  * the dashboard's self-audit must actually refuse the contradictions it claims to catch
  * @page margin/size parsing must reject what it cannot hand to another engine verbatim

Tests are plain functions named check_*; each returns None and raises AssertionError on failure.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import sector_screen as ss                                  # noqa: E402
import relative_strength as rs                              # noqa: E402
import html_to_pdf as h2p                                   # noqa: E402
import build_report as br                                   # noqa: E402
import check_for_updates as cfu                             # noqa: E402
import accumulation as acc                                  # noqa: E402
import institutional_cache as ic                            # noqa: E402

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

def _mk13f(path, rows, period="31-MAR-2026"):
    """A zip shaped like SEC's real Form 13F data set: SUBMISSION + COVERPAGE + INFOTABLE.

    Built to the real schema after the first version of these fixtures invented one. The manager's
    CIK lives in SUBMISSION (COVERPAGE has no CIK column at all), one file carries several
    PERIODOFREPORT values, 13F-NT reports no holdings, and amendments restate or add - every one
    of which changes the holder count, and none of which a made-up fixture would have exercised.

    rows: [(accession, cik, submissiontype, period, amendmenttype, [(issuer, cusip, shares,
            sshprnamttype, putcall), ...]), ...]
    """
    import zipfile
    sub = ["ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tCIK\tPERIODOFREPORT"]
    cov = ["ACCESSION_NUMBER\tREPORTCALENDARORQUARTER\tISAMENDMENT\tAMENDMENTNO\tAMENDMENTTYPE\t"
           "FILINGMANAGER_NAME"]
    info = ["ACCESSION_NUMBER\tINFOTABLE_SK\tNAMEOFISSUER\tTITLEOFCLASS\tCUSIP\tFIGI\tVALUE\t"
            "SSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL"]
    k = 0
    for acc, cik, styp, per, amd, holds in rows:
        sub.append("%s\t01-MAY-2026\t%s\t%s\t%s" % (acc, styp, cik, per or period))
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


def check_gzip_is_undone_before_parsing():
    """The bug that made discovery report "the page has no links". urllib returns the RAW encoded
    bytes for the gzip we asked for; curl decompresses transparently, so the same URL behaves
    differently on the command line and is easy to mis-diagnose as an empty page."""
    import gzip as _g
    raw = b'<a href="/x/01mar2026-31may2026_form13f.zip">z</a>'
    assert ic.maybe_gunzip(_g.compress(raw)) == raw
    assert ic.maybe_gunzip(raw) == raw          # not compressed: passed through untouched


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


# ---------------------------------------------------------------- check_for_updates

def _git(cwd, *a, **kw):
    return subprocess.run(("git",) + a, cwd=cwd, capture_output=True, text=True,
                          timeout=60, **kw)


def _mkrepo(tmp):
    """An origin, a working clone with the script inside it, and a second clone to push from."""
    org = os.path.join(tmp, "origin")
    os.makedirs(org)
    _git(org, "init", "-q", "--bare")
    _git(tmp, "clone", "-q", org, "work")
    work = os.path.join(tmp, "work")
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        _git(work, "config", k, v)
    os.makedirs(os.path.join(work, "scripts"))
    os.makedirs(os.path.join(work, "assets"))
    shutil.copy(os.path.join(ROOT, "scripts", "check_for_updates.py"),
                os.path.join(work, "scripts"))
    for f in ("SKILL.md", "scripts/sector_screen.py", "assets/dashboard_template.html"):
        io.open(os.path.join(work, f), "w", encoding="utf-8").write("v1\n")
    _git(work, "add", "-A"); _git(work, "commit", "-qm", "init")
    br_ = _git(work, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    _git(work, "push", "-q", "-u", "origin", br_)
    _git(tmp, "clone", "-q", org, "other")
    other = os.path.join(tmp, "other")
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        _git(other, "config", k, v)
    return work, other


def _run_cfu(cwd, *args):
    r = subprocess.run([sys.executable, os.path.join(cwd, "scripts", "check_for_updates.py")] + list(args),
                       cwd=cwd, capture_output=True, text=True, timeout=90)
    return r.returncode, r.stdout + r.stderr


def check_updates_reports_current(tmp):
    work, _ = _mkrepo(tmp)
    code, out = _run_cfu(work)
    assert code == 0 and "Skill is current" in out, out


def check_updates_separates_code_from_instructions(tmp):
    """The distinction the whole feature rests on: code updates land now, instruction updates
    land next run, and the report must not merge them."""
    work, other = _mkrepo(tmp)
    for f in ("SKILL.md", "scripts/sector_screen.py"):
        io.open(os.path.join(other, f), "w", encoding="utf-8").write("v2\n")
    _git(other, "add", "-A"); _git(other, "commit", "-qm", "bump"); _git(other, "push", "-q")
    code, out = _run_cfu(work)
    assert code == 0 and "OUT OF DATE" in out, out
    live = out.index("THIS RUN WILL USE THE NEW VERSION")
    ctx = out.index("ALREADY LOADED")
    assert out.index("scripts/sector_screen.py") > live
    assert out.index("SKILL.md", ctx) > ctx
    assert io.open(os.path.join(work, "SKILL.md")).read().strip() == "v1"   # report-only: no pull


def check_updates_refuses_to_pull_over_uncommitted_work(tmp):
    work, other = _mkrepo(tmp)
    io.open(os.path.join(other, "SKILL.md"), "w", encoding="utf-8").write("v2\n")
    _git(other, "commit", "-qam", "bump"); _git(other, "push", "-q")
    mine = os.path.join(work, "scripts", "sector_screen.py")
    io.open(mine, "w", encoding="utf-8").write("MY UNCOMMITTED WORK\n")
    code, out = _run_cfu(work, "--update")
    assert code == 1, out
    assert "refused" in out
    assert io.open(mine).read() == "MY UNCOMMITTED WORK\n", "local work was clobbered"
    assert io.open(os.path.join(work, "SKILL.md")).read().strip() == "v1"


def check_updates_fast_forwards_a_clean_tree(tmp):
    work, other = _mkrepo(tmp)
    io.open(os.path.join(other, "scripts", "sector_screen.py"), "w", encoding="utf-8").write("v2\n")
    _git(other, "commit", "-qam", "bump"); _git(other, "push", "-q")
    code, out = _run_cfu(work, "--update")
    assert code == 0 and "fast-forwarded" in out, out
    assert io.open(os.path.join(work, "scripts", "sector_screen.py")).read().strip() == "v2"
    assert out.count("fast-forwarded") == 1, "the update message is duplicated"
    code2, out2 = _run_cfu(work, "--update")                 # idempotent
    assert code2 == 0 and "nothing to update" in out2


def check_updates_ahead_does_not_claim_incoming_code(tmp):
    """An 'ahead' branch must not list its own unpushed edits under a heading promising new
    upstream code - that was a real bug."""
    work, _ = _mkrepo(tmp)
    io.open(os.path.join(work, "scripts", "sector_screen.py"), "w", encoding="utf-8").write("v9\n")
    _git(work, "commit", "-qam", "local only")
    code, out = _run_cfu(work)
    assert code == 0 and "ahead of the remote" in out, out
    assert "THIS RUN WILL USE THE NEW VERSION" not in out
    assert "ALREADY LOADED" not in out


def check_updates_reports_diverged_without_touching_anything(tmp):
    work, other = _mkrepo(tmp)
    io.open(os.path.join(other, "SKILL.md"), "w", encoding="utf-8").write("remote\n")
    _git(other, "commit", "-qam", "r"); _git(other, "push", "-q")
    io.open(os.path.join(work, "scripts", "sector_screen.py"), "w", encoding="utf-8").write("local\n")
    _git(work, "commit", "-qam", "l")
    code, out = _run_cfu(work, "--update")
    assert code == 0 and "DIVERGED" in out, out
    assert io.open(os.path.join(work, "scripts", "sector_screen.py")).read().strip() == "local"


def check_updates_fails_open_when_it_cannot_check(tmp):
    """No git checkout, no upstream, unreachable remote - each must exit 0 so the run continues."""
    plain = os.path.join(tmp, "plain", "scripts")
    os.makedirs(plain)
    shutil.copy(os.path.join(ROOT, "scripts", "check_for_updates.py"), plain)
    code, out = _run_cfu(os.path.dirname(plain))
    assert code == 0 and "not a git checkout" in out, out

    nested = os.path.join(tmp, "b")          # a second repo, clear of the one made above
    os.makedirs(nested, exist_ok=True)
    work, _ = _mkrepo(nested)
    _git(work, "checkout", "-q", "-b", "untracked-branch")
    code, out = _run_cfu(work)
    assert code == 0 and "no upstream" in out, out

    _git(work, "checkout", "-q", "-")
    _git(work, "remote", "set-url", "origin", "https://nonexistent.invalid/x.git")
    code, out = _run_cfu(work, "--timeout", "8")
    assert code == 0 and "unreachable" in out, out


def check_updates_status_and_header_sets_agree():
    src = io.open(os.path.join(ROOT, "scripts", "check_for_updates.py"), encoding="utf-8").read()
    produced = set(re.findall(r'out\["status"\]\s*=\s*"([a-z-]+)"', src))
    block = src[src.index("head = {"):src.index('}.get(v["status"]')]
    assert not (produced - set(re.findall(r'"([a-z-]+)":', block))), "a status has no header"


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
    assert "check_for_updates.py" in md
    # Every fenced block must close - an unbalanced fence silently swallows the rest of the file.
    # Counted per fence WIDTH: the exporter widens a fence when the file it wraps contains
    # backticks, and a plain "```" count would see the opening of a ````-fence as a match.
    for fence in set(re.findall(r"^(`{3,})", md, re.M)):
        assert md.count("\n" + fence) % 2 == 0, "unbalanced %d-backtick fence" % len(fence)


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


def check_skill_documents_step_zero():
    s = io.open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
    assert "### 0 — Check this copy of the skill is current" in s
    assert "check_for_updates.py" in s
    assert "does NOT take effect this run" in s.replace("**", "")


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


def check_every_script_compiles():
    import py_compile
    d = os.path.join(ROOT, "scripts")
    for f in sorted(os.listdir(d)):
        if f.endswith(".py"):
            py_compile.compile(os.path.join(d, f), doraise=True)


# ---------------------------------------------------------------- runner

def main():
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
