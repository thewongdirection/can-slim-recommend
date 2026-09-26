#!/usr/bin/env python3
"""
check_parity.py - prove this skill and `can-slim-grader` still grade the same way.

WHY THE SISTER'S OWN CHECKER IS NOT ENOUGH. can-slim-grader ships a check_parity.py too, and its
docstring is honest about the limit: "it compares bytes in THIS repo against the last recorded
sync. It does not read the sister repo, and it cannot see a material change that lives somewhere
other than a shared file - a threshold reworded in SKILL.md, a new freshness rule, a changed pivot
definition. Those are the common case and they are yours to notice."

A byte tripwire on two files cannot notice that one skill started failing N at 10% below the high
while the other still graded it partial. That is the failure that matters: the same evidence
scoring differently in the two skills makes "4.5/7" mean two things, and the whole point of the
pair is that a screened idea and a graded ticker are comparable. So this checker reads BOTH repos
and tests BEHAVIOUR, in four layers:

  1. SHARED BYTES - the files the manifest calls verbatim, compared across the two checkouts and
     against the manifest hash, so drift is attributed rather than merely detected.
  2. ARITHMETIC - the two dashboards' REAL scoring code, lifted out of the templates and run in
     node over every one of the 3^7 = 2187 possible scorecards. Exhaustive, so this is a proof and
     not a sample: if any grade tuple totals differently, it is named.
  3. RUNGS - the "easy to grade too kindly" thresholds in the shared methodology, parsed out of
     the prose and checked against what sector_screen.py's ceiling actually implements. This is
     the layer that catches a reworded threshold.
  4. TICKERS - N random synthetic tickers (default 100) pushed through both scorers with messy
     score spellings, to catch input handling that diverges where the arithmetic does not.

Usage:
  python scripts/check_parity.py                        # find the sister automatically
  python scripts/check_parity.py --grader ../can-slim-grader
  python scripts/check_parity.py --tickers 100 --seed 7 # reproduce a reported failure
  python scripts/check_parity.py --json

Exit: 0 all layers agree; 1 a divergence (the report names it); 2 the sister repo was not found.
Needs node for layers 2 and 4; without it they are reported as skipped rather than passed.
Pure standard library.
"""
import argparse
import hashlib
import io
import itertools
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Two CLASSES of shared file, and conflating them is a trap this checker fell into itself.
#
# VERBATIM: no local extensions, so byte-identity is the contract and a diff is drift.
# SUBSTANCE: the sister's SKILL.md says outright that these are "no longer byte-identical, and
#   that is expected - port the CHANGE, not the file", because each side carries its own
#   additions (this repo: a "Modern refinements" methodology section, and `--asof` point-in-time
#   truncation in relative_strength.py). Demanding byte-identity here does not detect drift, it
#   MANUFACTURES it: the only way to satisfy the check is to copy one side over the other and
#   delete the extension. That is exactly what happened - commit 6e281fb wholesale-copied both
#   files and destroyed both extensions to make this layer go green. So substance files are
#   checked for shared SUBSTANCE (the rungs, and the maths), never for equal bytes.
VERBATIM = ["scripts/rubric.py"]
SUBSTANCE = ["references/canslim-methodology.md", "scripts/relative_strength.py"]
SHARED = VERBATIM + SUBSTANCE
GRADES = ("pass", "partial", "fail")
LETTERS = "CANSLIM"

# Where the sister checkout is likely to be, in order. The add_repo lane puts a read-only clone
# under /home/user/<owner>/<repo>; a developer is more likely to have it beside this one.
CANDIDATES = (
    os.environ.get("CANSLIM_GRADER") or "",
    os.path.join(os.path.dirname(ROOT), "can-slim-grader"),
    "/home/user/thewongdirection/can-slim-grader",
    "/home/user/can-slim-grader",
)


def find_grader(explicit=None):
    for p in ((explicit,) if explicit else ()) + CANDIDATES:
        if p and os.path.exists(os.path.join(p, "assets", "evaluation_template.html")):
            return os.path.abspath(p)
    return None


def sha256(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- layer 1: bytes
def check_shared_bytes(grader):
    """VERBATIM files must match byte for byte; SUBSTANCE files must match in substance.

    For a substance file a byte diff is reported as INFORMATIONAL, with what each side adds, so
    drift is visible without the check pressuring anyone into deleting an extension to silence it.
    """
    man = {}
    mp = os.path.join(grader, "parity-manifest.json")
    if os.path.exists(mp):
        man = (json.load(io.open(mp, encoding="utf-8")) or {}).get("files") or {}
    rows, bad = [], 0
    for rel in SHARED:
        a, b = os.path.join(ROOT, rel), os.path.join(grader, rel)
        ha = sha256(a) if os.path.exists(a) else None
        hb = sha256(b) if os.path.exists(b) else None
        same = ha is not None and ha == hb
        if rel in VERBATIM:
            verdict = "identical" if same else (
                "DRIFT - this file carries no extensions, so the bytes must match")
            if not same:
                bad += 1
        else:
            verdict = ("identical" if same else
                       "differs (EXPECTED - substance file; each side keeps its own extensions). "
                       "Substance is checked by the rungs and maths layers, not here.")
        rows.append({"file": rel, "class": "verbatim" if rel in VERBATIM else "substance",
                     "ours": ha, "theirs": hb, "manifest": man.get(rel), "verdict": verdict})
    return {"name": "shared files (verbatim byte-equal; substance may extend)",
            "ok": bad == 0, "detail": rows}


def check_shared_substance(grader):
    """The two SUBSTANCE files must agree where it counts, extensions notwithstanding.

    methodology: every canonical rung paragraph must appear verbatim in our copy. Ours may add
      sections; it may not reword a threshold, which is the drift that changes a grade.
    relative_strength: both modules are imported and run over the same bars, and every computed
      number must match. This is the layer that would have caught the ret_over divergence the
      manifest described - the same series giving a 12-month RS on one side and None on the other.
    """
    probs = []

    ours_md = io.open(os.path.join(ROOT, "references", "canslim-methodology.md"),
                      encoding="utf-8").read()
    theirs_md = io.open(os.path.join(grader, "references", "canslim-methodology.md"),
                        encoding="utf-8").read()
    rungs = re.findall(r"^- \*\*[CANSLIM]\.\*\*.+?(?=\n- \*\*|\n\n)", theirs_md, re.S | re.M)
    missing = []
    for r in rungs:
        norm = " ".join(r.split())
        if norm not in " ".join(ours_md.split()):
            missing.append(norm[:110])
    if not rungs:
        probs.append("could not find any rung paragraphs in the canonical methodology - the "
                     "extractor is stale, so this layer is not actually checking anything")
    if missing:
        probs.append({"reworded_or_missing_rungs": missing})

    # relative_strength: run both implementations over the same synthetic series.
    #
    # Compiled from the SOURCE TEXT, never through the import system, because __pycache__ can and
    # does lie here. Restoring a file with `cp` rewrites the bytes but can leave a .pyc that
    # Python still considers valid, so exec_module runs the PREVIOUS edit: this checker spent a
    # while reporting a maths divergence between two byte-identical functions because our copy was
    # running a stale tol=0.5 while the file on disk said 0.9. A parity checker that can be fooled
    # by bytecode would also MISS real drift whenever the stale .pyc happened to agree.
    import types as _types

    def load(path, name):
        src = io.open(path, encoding="utf-8").read()
        mod = _types.ModuleType(name)
        mod.__file__ = path
        exec(compile(src, path, "exec"), mod.__dict__)
        return mod

    try:
        ours = load(os.path.join(ROOT, "scripts", "relative_strength.py"), "rs_ours")
        theirs = load(os.path.join(grader, "scripts", "relative_strength.py"), "rs_theirs")
    except Exception as e:
        probs.append("could not import both relative_strength copies: %s" % e)
        return {"name": "shared substance (rungs verbatim, maths identical)",
                "ok": False, "detail": probs}

    rng = random.Random(20260926)
    mism = []
    for case in range(60):
        n = rng.choice((40, 130, 251, 252, 300))
        px = [100.0]
        for _ in range(n - 1):
            px.append(max(1.0, px[-1] * (1 + rng.uniform(-0.05, 0.05))))
        bars = [[i, p, p * 1.01, p * 0.99, p, 1000 + i] for i, p in enumerate(px)]
        bench = [[i, 100, 101, 99, 100 + i * 0.05, 1000] for i in range(n)]
        d = {"benchmark": {"daily": bench}, "candidates": [{"symbol": "X:Y", "daily": bars}]}
        ra = ours.analyze(json.loads(json.dumps(d)))["candidates"][0]
        rb = theirs.analyze(json.loads(json.dumps(d)))["candidates"][0]
        for k in ("rs_blended", "pct_off_52w_high", "breakout_vol_vs_avg"):
            va, vb = ra.get(k), rb.get(k)
            if (va is None) != (vb is None) or (va is not None and abs(va - vb) > 1e-9):
                mism.append({"case": case, "bars": n, "field": k, "ours": va, "theirs": vb})
        if ra.get("rs_relative_return") != rb.get("rs_relative_return"):
            mism.append({"case": case, "bars": n, "field": "rs_relative_return",
                         "ours": ra.get("rs_relative_return"), "theirs": rb.get("rs_relative_return")})
    if mism:
        probs.append({"relative_strength_disagreements": mism[:10],
                      "total": len(mism)})
    return {"name": "shared substance (rungs verbatim, maths identical)",
            "ok": not probs, "checked": 60, "detail": probs}


# ------------------------------------------------------------------- layers 2 & 4: arithmetic
GRADER_SCORE = re.compile(r"const SCORE = \(function\(\)\{.*?\}\)\(\);", re.S)
# LINE-anchored on purpose. A non-greedy ".*?;" looks right and truncates every one of these at
# the first semicolon INSIDE its own arrow body - gradeOf became
# "const gradeOf = (v)=>{ const g=String(v==null?"":v).trim().toLowerCase();" - which is an
# unbalanced brace that node reports as "Unexpected end of input" from a generated temp file,
# about as far from the cause as an error can land. These are one-liners in the template; match
# the line.
OURS_PARTS = (
    r"^const WEIGHT = \{[^}]*\};$",
    r"^const LETTERS6 = \[[^\]]*\];$",
    # "[^\n]*" not ".*": the grader's SCORE block needs re.S to span lines, and under DOTALL a
    # ".*$" line pattern greedily swallows the rest of the file - which it did, dragging in a
    # second "const m" and making node complain about a redeclared identifier.
    r"^const isGrade = [^\n]*$",
    r"^const gradeOf = [^\n]*$",
    r"^const mGrade = [^\n]*$",
    r"^const scoreTotal = [^\n]*$",
)


def _extract(text, pattern, what):
    m = re.search(pattern, text, re.S | re.M)
    if not m:
        raise LookupError("could not find %s - the scoring block moved, so parity is unverified "
                          "until this extractor is updated" % what)
    return m.group(0)


def build_harness(grader):
    """A node program exposing both skills' REAL scoring functions over stdin scorecards."""
    g = io.open(os.path.join(grader, "assets", "evaluation_template.html"), encoding="utf-8").read()
    r = io.open(os.path.join(ROOT, "assets", "dashboard_template.html"), encoding="utf-8").read()
    grader_src = _extract(g, GRADER_SCORE.pattern, "the grader's SCORE block")
    ours_src = "\n".join(_extract(r, p, "our " + p.split()[1].lstrip("^")) for p in OURS_PARTS)
    return """
'use strict';
// The two skills' own scoring code, lifted verbatim from their templates. Nothing is
// reimplemented here: a divergence reported below is a divergence in the shipped skills.
function graderTotal(letters){
  const CONFIG = {letters: letters};
  %s
  return SCORE.tally;
}
function oursTotal(scores, m){
  const CONFIG = {market: {mGrade: m}};
  %s
  return scoreTotal({scores: scores});
}
let input = '';
process.stdin.on('data', d => input += d);
process.stdin.on('end', () => {
  const cases = JSON.parse(input);
  const out = cases.map(c => {
    const letters = "CANSLIM".split("").map(k => ({key: k, score: c.scores[k]}));
    let a = null, b = null, ea = null, eb = null;
    try { a = graderTotal(letters); } catch (e) { ea = String(e); }
    try { b = oursTotal(c.scores, c.scores.M); } catch (e) { eb = String(e); }
    return {id: c.id, grader: a, ours: b, graderErr: ea, oursErr: eb};
  });
  process.stdout.write(JSON.stringify(out));
});
""" % (grader_src, ours_src)


def run_harness(harness, cases):
    node = shutil.which("node") or shutil.which("nodejs")
    if not node:
        return None
    d = tempfile.mkdtemp(prefix="canslim-parity-")
    try:
        p = os.path.join(d, "harness.js")
        io.open(p, "w", encoding="utf-8").write(harness)
        chk = subprocess.run([node, "--check", p], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=60)
        if chk.returncode != 0:
            raise RuntimeError(
                "the harness assembled from the two templates is not valid JS, so one of the "
                "scoring blocks was extracted wrong (the extractor is anchored to the templates' "
                "current shape - if either moved, fix the pattern). node said:\n" +
                chk.stderr.decode("utf-8", "replace")[:400])
        out = subprocess.run([node, p], input=json.dumps(cases).encode("utf-8"),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        if out.returncode != 0:
            raise RuntimeError("node harness failed: " + out.stderr.decode("utf-8", "replace")[:400])
        return json.loads(out.stdout.decode("utf-8"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def compare(rows, label):
    bad = [r for r in rows
           if r["graderErr"] or r["oursErr"] or r["grader"] is None or r["ours"] is None
           or abs(r["grader"] - r["ours"]) > 1e-9]
    return {"name": label, "ok": not bad, "checked": len(rows),
            "detail": bad[:15] + ([{"note": "... %d more" % (len(bad) - 15)}] if len(bad) > 15 else [])}


def check_arithmetic(harness):
    """EXHAUSTIVE over every possible scorecard - 3^7 = 2187 - so this is a proof, not a sample."""
    cases = [{"id": "".join(t), "scores": dict(zip(LETTERS, t))}
             for t in itertools.product(GRADES, repeat=7)]
    rows = run_harness(harness, cases)
    if rows is None:
        return {"name": "arithmetic (all 2187 scorecards)", "ok": None, "detail": "node not installed"}
    return compare(rows, "arithmetic (all 2187 scorecards)")


# A real scorecard is authored by hand, so a letter can arrive capitalised, padded or blank. The
# two skills must agree on what those mean, not merely on the clean case.
MESSY = ("pass", "PASS", "Pass", " pass ", "partial", "Partial", "fail", "FAIL", "", None, "n/a")


def check_tickers(harness, n, seed):
    rng = random.Random(seed)
    cases = []
    for i in range(n):
        # Most letters clean, a minority deliberately messy - the mix a hand-authored run has.
        scores = {k: (rng.choice(GRADES) if rng.random() < 0.75 else rng.choice(MESSY))
                  for k in LETTERS}
        cases.append({"id": "T%03d-%s" % (i, "".join(str(scores[k])[:1] for k in LETTERS)),
                      "scores": scores})
    rows = run_harness(harness, cases)
    if rows is None:
        return {"name": "%d random tickers (seed %s)" % (n, seed), "ok": None,
                "detail": "node not installed"}
    res = compare(rows, "%d random tickers (seed %s)" % (n, seed))
    res["cases"] = {c["id"]: c["scores"] for c in cases}
    return res


# ------------------------------------------------------------------------- layer 3: the rungs
def check_rungs(grader):
    """Parse the shared methodology's N rung and check our ceiling implements it.

    N is the rung most easily reworded into a different grade, and it is the one that actually
    drifted: the canonical text says more than ~10% below the high means N CANNOT PASS and more
    than ~20% below means N FAILS, which is a partial band in between. A copy that lists ">10%
    below" under FAIL grades a name 15% off its high half a point lower than the sister does.
    """
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import sector_screen as ss

    src = io.open(os.path.join(grader, "references", "canslim-methodology.md"),
                  encoding="utf-8").read()
    rung = re.search(r"\*\*N\.\*\*(.+?)(?=\n- \*\*|\n\n)", src, re.S)
    text = " ".join((rung.group(1) if rung else "").split())
    says_partial_band = bool(re.search(r"10%.{0,80}cannot pass", text)) and \
        bool(re.search(r"20%.{0,40}fails?", text))

    cfg = dict(ss.DEFAULTS)
    band = cfg["pivot_band"]

    def n_for(off_high):
        row = {"symbol": "X:Y", "ticker": "Y", "off_high_pct": off_high, "rel_volume_10d": 1.2,
               "sector_rank_overall": 1, "sector_count": 20}
        ss.ceiling(row, cfg, {})
        return row["ceiling_caps"]["N"] if "ceiling_caps" in row else None

    probes = [(-(band / 2.0), "pass"), (-(band + 5), "partial"), (-(2 * band + 5), "fail")]
    got = [(off, want, n_for(off)) for off, want in probes]
    mism = [g for g in got if g[1] != g[2]]

    # A has TWO legs - "EPS up each of 3 years at >=25% AND ROE >=17%" - and grading the EPS leg
    # alone is an over-grade the sister would not make, because it checks both on the one ticker
    # it is looking at. annual_eps.py must refuse to pass a name whose ROE it cannot verify.
    import annual_eps as ae
    import datetime as _dt
    ends = ["2022-12-31", "2023-12-31", "2024-12-31", "2025-12-31"]
    strong = dict(zip(ends, [1.0, 1.3, 1.7, 2.2]))          # +30, +31, +29: EPS leg clears
    day = _dt.date.fromisoformat("2026-03-01")
    roe_probes = [(None, "partial"), (ae.DEFAULTS["roe"] - 5, "partial"),
                  (ae.DEFAULTS["roe"] + 5, "pass")]
    roe_got = [(r, want, ae.grade(strong, ae.DEFAULTS, today=day, roe=r)[0])
               for r, want in roe_probes]
    roe_mism = [g for g in roe_got if g[1] != g[2]]

    ok = (not mism) and says_partial_band and (not roe_mism)
    return {"name": "rungs: methodology prose vs our code (N band, A's two legs)", "ok": ok,
            "detail": {"canonical_has_partial_band": says_partial_band,
                       "canonical_text": text[:240],
                       "N_probes": [{"off_high": o, "expected": w, "ceiling": c} for o, w, c in got],
                       "A_roe_probes": [{"roe": r, "expected": w, "got": c} for r, w, c in roe_got]}}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--grader", help="path to a can-slim-grader checkout")
    ap.add_argument("--tickers", type=int, default=100,
                    help="random synthetic tickers to compare (default %(default)s)")
    ap.add_argument("--seed", type=int, default=None,
                    help="RNG seed; omitted means a fresh one, printed so a failure reproduces")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    grader = find_grader(a.grader)
    if not grader:
        print("can-slim-grader not found. Clone it beside this repo, or pass --grader PATH, or "
              "set CANSLIM_GRADER.\n  git clone --depth 1 "
              "https://github.com/thewongdirection/can-slim-grader", file=sys.stderr)
        return 2

    seed = a.seed if a.seed is not None else random.randrange(1 << 30)
    layers = [check_shared_bytes(grader), check_shared_substance(grader)]
    try:
        harness = build_harness(grader)
        layers.append(check_arithmetic(harness))
        layers.append(check_tickers(harness, a.tickers, seed))
    except LookupError as e:
        layers.append({"name": "arithmetic", "ok": False, "detail": str(e)})
    layers.append(check_rungs(grader))

    failed = [l for l in layers if l["ok"] is False]
    if a.json:
        print(json.dumps({"grader": grader, "seed": seed, "layers": layers}, indent=2))
    else:
        print("parity vs %s  (seed %d)" % (grader, seed))
        for l in layers:
            mark = {True: "ok  ", False: "FAIL", None: "SKIP"}[l["ok"]]
            print("  %s %s%s" % (mark, l["name"],
                                 "" if l.get("checked") is None else "  [%d cases]" % l["checked"]))
            if l["ok"] is not True:
                print("       " + json.dumps(l["detail"], indent=2).replace("\n", "\n       ")[:1600])
        print("\n%d layer(s) failing" % len(failed) if failed else "\nall layers agree")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
