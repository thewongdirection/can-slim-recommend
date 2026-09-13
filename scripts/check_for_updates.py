#!/usr/bin/env python3
"""
check_for_updates.py - step 0: is this copy of the skill current?

The skill is iterated on constantly, and a stale checkout fails SILENTLY - it produces a
plausible-looking report built by last month's rules. So every run starts here.

WHAT AN UPDATE CAN AND CANNOT FIX MID-RUN. This is the whole reason the script reports two
groups rather than one number:

  scripts/ and assets/   READ FROM DISK when they run. Updating them takes effect THIS RUN -
                         the new sector_screen.py and the new dashboard template are what
                         actually execute.
  SKILL.md, references/  READ INTO CONTEXT when the skill is invoked, before this script runs.
                         Updating the files on disk does NOT replace the instructions already
                         guiding this run; those land on the NEXT invocation.

So "always use the newest version" is achievable for the code and only partly for the
instructions. When the instructions are the part that moved, the honest move is to say so and
let the user decide whether to re-invoke - never to imply the run picked them up.

FAILS OPEN, ALWAYS. No git, no network, no remote, a fetch that times out - none of these stop
a run. The script says what it could not check and exits 0. A skill that refuses to work
offline is worse than one that works on a possibly-stale copy and says so.

NEVER AUTO-PULLS OVER YOUR WORK. `--update` refuses to touch a dirty tree or a diverged branch;
it reports and leaves the decision to you. Uncommitted local changes are someone's work in
progress, not garbage to be overwritten.

Usage:
  python scripts/check_for_updates.py              # report only (what step 0 runs)
  python scripts/check_for_updates.py --update     # also fast-forward when it is safe to
  python scripts/check_for_updates.py --json       # machine-readable verdict
  python scripts/check_for_updates.py --timeout 20 # network patience, seconds (default 15)

Exit status is 0 for "current", "behind", and every can't-check case - the run continues either
way. It is 1 only when --update was asked for and the update itself failed.
Pure standard library.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Which half of the skill a changed path belongs to - see the module docstring.
LIVE_PREFIXES = ("scripts/", "assets/")


def git(*args, **kw):
    """Run a git command in the skill root. Returns (ok, output). Never raises.

    On failure the output is git's STDERR - git writes "could not resolve host", "repository not
    found" and every other diagnosis there, and a failure message that cannot say why is useless
    to whoever has to fix it.
    """
    try:
        p = subprocess.run(("git", "-C", ROOT) + args, capture_output=True, text=True,
                           timeout=kw.get("timeout", 15))
        if p.returncode == 0:
            return True, (p.stdout or "").strip()
        return False, ((p.stderr or "") + (p.stdout or "")).strip()
    except FileNotFoundError:
        return False, "git is not installed on this host"
    except subprocess.TimeoutExpired:
        return False, "git timed out after %ss" % kw.get("timeout", 15)
    except Exception as e:                      # anything else - still never raise
        return False, str(e)


def classify(paths):
    """Split changed paths into what this run will actually pick up and what it will not."""
    live = sorted(p for p in paths if p.startswith(LIVE_PREFIXES))
    ctx = sorted(p for p in paths if not p.startswith(LIVE_PREFIXES))
    return live, ctx


def check(timeout):
    """Return a verdict dict. `status` is one of:
       current | behind | ahead | diverged | no-upstream | not-a-repo | unreachable | no-git
    """
    out = {"status": "unknown", "branch": None, "behind": 0, "ahead": 0,
           "changed_live": [], "changed_context": [], "detail": "", "can_fast_forward": False,
           "dirty": False}

    ok, why = git("rev-parse", "--git-dir")
    if not ok:
        # Two very different situations that must not share a message: git absent (the copy may
        # be perfectly current, we simply cannot look) vs. a real non-checkout (a zip export).
        if "not installed" in why or "not found" in why or "No such file" in why:
            out["status"] = "no-git"
            out["detail"] = ("git is not available on this host, so the version cannot be checked "
                             "- this copy may or may not be current. Continue, and say in the "
                             "report that the version could not be verified.")
        else:
            out["status"] = "not-a-repo"
            out["detail"] = ("this copy of the skill is not a git checkout (a zip export, a "
                             "vendored copy, or another assistant's upload), so there is nothing "
                             "to compare against. Continue, and say in the report that the "
                             "version could not be verified.")
        return out

    ok, branch = git("rev-parse", "--abbrev-ref", "HEAD")
    out["branch"] = branch if ok else None

    ok, st = git("status", "--porcelain")
    out["dirty"] = bool(ok and st)

    ok, upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if not ok or not upstream:
        out["status"] = "no-upstream"
        out["detail"] = ("the current branch tracks no remote, so there is no newer version to "
                         "compare against. Continue.")
        return out

    remote = upstream.split("/", 1)[0]
    ok, err = git("fetch", "--quiet", remote, timeout=timeout)
    if not ok:
        out["status"] = "unreachable"
        out["detail"] = ("could not reach '%s' (%s). The network may be down or the remote may be "
                         "private to another host. Continue on this copy and say in the report "
                         "that the version could not be verified." % (remote, err.splitlines()[0] if err else "no detail"))
        return out

    ok, counts = git("rev-list", "--left-right", "--count", "HEAD...@{u}")
    if not ok:
        out["status"] = "unreachable"
        out["detail"] = "fetched, but could not compare against %s. Continue." % upstream
        return out
    try:
        ahead, behind = (int(x) for x in counts.split())
    except ValueError:
        ahead = behind = 0
    out["ahead"], out["behind"] = ahead, behind

    # Only list files when there is something INCOMING. `git diff HEAD @{u}` is symmetric, so on
    # an "ahead" branch it would list the run's own unpushed edits under a heading promising new
    # upstream code - the opposite of what is true.
    if behind:
        ok, names = git("diff", "--name-only", "HEAD", "@{u}")
        paths = [p for p in names.splitlines() if p.strip()] if ok else []
        out["changed_live"], out["changed_context"] = classify(paths)

    if behind and ahead:
        out["status"] = "diverged"
        out["detail"] = ("local and %s have both moved on (%d local commit(s), %d remote). A "
                         "fast-forward is not possible; this needs a human to merge or rebase. "
                         "Continue on this copy and say so in the report." % (upstream, ahead, behind))
    elif behind:
        out["status"] = "behind"
        out["can_fast_forward"] = not out["dirty"]
        out["detail"] = "%d commit(s) behind %s." % (behind, upstream)
        if out["dirty"]:
            out["detail"] += (" The working tree has uncommitted changes, so this will NOT be "
                              "updated automatically - that would overwrite someone's work. "
                              "Commit or stash first.")
    elif ahead:
        out["status"] = "ahead"
        out["detail"] = ("%d local commit(s) not yet pushed. This copy is newer than the remote; "
                         "nothing to pull." % ahead)
    else:
        out["status"] = "current"
        out["detail"] = "up to date with %s." % upstream
    return out


def do_update(v, timeout):
    """Fast-forward only, and only when check() already said it is safe. Returns (ok, message)."""
    if v["status"] != "behind":
        return True, "nothing to update (%s)" % v["status"]
    if v["dirty"]:
        return False, ("refused: the working tree has uncommitted changes. Commit or stash them, "
                       "then re-run. Pulling over local work is never the right default.")
    ok, out = git("merge", "--ff-only", "@{u}", timeout=timeout)
    if not ok:
        return False, "fast-forward failed: %s" % (out.splitlines()[0] if out else "no detail")
    return True, "fast-forwarded %d commit(s)." % v["behind"]


def render(v, updated=None):
    L = []
    head = {"current": "Skill is current",
            "behind": "Skill is OUT OF DATE",
            "ahead": "Skill is ahead of the remote",
            "diverged": "Skill has DIVERGED from the remote",
            "no-upstream": "Version not verified - no upstream",
            "not-a-repo": "Version not verified - not a git checkout",
            "unreachable": "Version not verified - remote unreachable",
            "no-git": "Version not verified - git unavailable",
            }.get(v["status"], "Version check inconclusive")
    L.append("%s%s" % (head, (" (%s)" % v["branch"]) if v["branch"] else ""))
    L.append("  " + v["detail"])

    if v["changed_live"]:
        L.append("  Code that changed - THIS RUN WILL USE THE NEW VERSION once updated:")
        for p in v["changed_live"]:
            L.append("      %s" % p)
    if v["changed_context"]:
        L.append("  Instructions that changed - ALREADY LOADED, so this run keeps the OLD ones:")
        for p in v["changed_context"]:
            L.append("      %s" % p)
        L.append("      -> re-invoke the skill after updating to pick these up, or tell the user "
                 "the run used the previous instructions.")
    if updated is not None:
        L.append("  Update: %s" % updated)
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update", action="store_true",
                    help="fast-forward to the remote when it is safe (clean tree, not diverged)")
    ap.add_argument("--json", action="store_true", help="machine-readable verdict")
    ap.add_argument("--timeout", type=float, default=15.0,
                    help="seconds to wait on the network (default %(default)s)")
    a = ap.parse_args()

    v = check(a.timeout)
    msg = None
    if a.update:
        ok, msg = do_update(v, a.timeout)
        if ok and v["status"] == "behind" and not v["dirty"]:
            # Re-read so the verdict reflects the update. Keep the fresh detail ("up to date
            # with ...") - the fast-forward itself is reported once, on the Update line.
            v = check(a.timeout)
    if a.json:
        v["update_message"] = msg
        print(json.dumps(v, indent=2))
    else:
        print(render(v, msg))
    # Fail open: only an update that was asked for and did not work is an error.
    return 1 if (a.update and msg and msg.startswith(("refused", "fast-forward failed"))) else 0


if __name__ == "__main__":
    sys.exit(main())
