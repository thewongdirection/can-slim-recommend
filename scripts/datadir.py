#!/usr/bin/env python3
"""
datadir.py - where this skill keeps the files that must outlive a single run.

THE PROBLEM THIS CLOSES. The caches (the quarterly I-cache, the 13F zips, the SEC XBRL answers, the
TradingView pacing state) used to default to a `data/` folder - but a RELATIVE one for two of the
scripts (wherever you happened to run them from) and one under the skill's own folder for the
third. A marketplace install lives in a folder named for the installed version, so an update starts
that folder empty; a relative path lands in whichever project the run was started in. Neither is a
place you can rely on finding last quarter's cache.

THE RULE, in order:
  1. an explicit flag on the script (`--cache-dir`, `-o`) always wins;
  2. $CANSLIM_DATA_DIR, if set - point it anywhere you like (use an absolute path);
  3. a per-user cache folder that depends on neither the install location nor the working
     directory, so it survives updates and is the same from every project:
         Linux / other   $XDG_CACHE_HOME/can-slim-recommend   (else ~/.cache/can-slim-recommend)
         macOS           ~/Library/Caches/can-slim-recommend
         Windows         %LOCALAPPDATA%\\can-slim-recommend

Everything kept here is REBUILDABLE (the I-cache is ~40 seconds of SEC downloads; the throttle
state is relearned), which is why it is a cache folder and not a data folder. The one thing it must
never be is a place a stale quarter can hide: institutional_cache.py records the quarter inside the
cache and replaces a cache from a different one.

Usage:
  python scripts/datadir.py                  # print the folder
  python scripts/datadir.py i-cache.json     # print the full path of a file inside it
  python scripts/institutional_cache.py --quarter 2026Q1 -o "$(python scripts/datadir.py i-cache.json)"

Pure standard library.
"""
import argparse
import os
import sys
import tempfile

ENV = "CANSLIM_DATA_DIR"
APP = "can-slim-recommend"


def default_dir():
    """The per-user cache folder for this platform (see the module docstring)."""
    home = os.path.expanduser("~")
    if home == "~" or not os.path.isabs(home):      # no resolvable home: expanduser leaves "~" as is
        return os.path.join(tempfile.gettempdir(), APP)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
    elif sys.platform == "darwin":
        base = os.path.join(home, "Library", "Caches")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.join(home, ".cache")
    return os.path.join(base, APP)


def data_dir():
    """The folder the skill keeps its files in. Not created here - the writers create it."""
    chosen = (os.environ.get(ENV) or "").strip()
    return os.path.abspath(os.path.expanduser(chosen)) if chosen else default_dir()


def path(*parts):
    """A file or folder inside the data dir. Refuses a name that would climb out of it."""
    root = data_dir()
    full = os.path.abspath(os.path.join(root, *parts))
    if full != root and not full.startswith(root + os.sep):
        raise ValueError("%r is not inside the data directory %s" % (os.path.join(*parts), root))
    return full


def main(argv=None):
    ap = argparse.ArgumentParser(description="Print the folder this skill keeps its caches in.")
    ap.add_argument("name", nargs="?", help="a file or folder name inside it; prints its full path")
    a = ap.parse_args(argv)
    try:
        print(path(a.name) if a.name else data_dir())
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
