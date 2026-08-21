#!/usr/bin/env python3
"""
html_to_pdf.py - render the filled CAN SLIM recommendations HTML to PDF.

The PDF is this skill's DEFAULT deliverable: the filled canslim-recommendations-<date>.html
is the working file, and this turns it into the report the user gets. The dashboard template
is white/light-themed and print-optimized (A4/Letter, print-color-adjust:exact), so a
headless-Chrome print reproduces the on-screen report faithfully. This script tries several
engines so it works across environments, and prints the engine it used.

Shared with the sister skill `can-slim-grader` (same file, same behaviour) - keep the two in
step if you change it.

Usage:
    python html_to_pdf.py <input.html> [output.pdf]
If output is omitted it is the input path with a .pdf extension.

Engine order: headless Chrome/Chromium/Edge (--print-to-pdf) -> Playwright -> WeasyPrint ->
wkhtmltopdf. Exits non-zero (with guidance) if none is available - in that case hand over the
HTML instead and say why.
"""
import os
import re
import sys
import shutil
import subprocess


def css_page_size(path):
    """Read the document's `@page { size: ... }` rule, if it declares one.

    Chrome's --print-to-pdf honours @page on its own, but Playwright and wkhtmltopdf do not
    unless told, so a landscape report (like the recommend skill's wide screening table) would
    silently clip on those engines. Returns the raw size value lowercased, or None.
    """
    try:
        head = open(path, encoding="utf-8", errors="replace").read(200000)
    except OSError:
        return None
    m = re.search(r"@page[^{]*\{[^}]*?\bsize\s*:\s*([^;}]+)", head, re.I | re.S)
    return m.group(1).strip().lower() if m else None


def _abs(p):
    return os.path.abspath(p)


def find_browser():
    """Return a path to a Chromium-family executable, or None."""
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "chrome", "msedge", "microsoft-edge"):
        p = shutil.which(name)
        if p:
            return p
    cands = []
    # Agent sandboxes often ship a Playwright-managed Chromium that is not on PATH.
    pw = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if pw:
        cands += [os.path.join(pw, "chromium"),
                  os.path.join(pw, "chrome-linux", "chrome")]
    cands += [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def via_chrome(inp, out):
    exe = find_browser()
    if not exe:
        return False
    url = "file:///" + _abs(inp).replace("\\", "/")
    common = [exe, "--disable-gpu", "--no-sandbox",
              "--run-all-compositor-stages-before-draw", "--virtual-time-budget=4000",
              f"--print-to-pdf={_abs(out)}", url]
    # Prefer suppressing Chrome's date/title/URL/page-number header & footer; fall back to
    # plain print if a given Chrome build doesn't accept the flag. Try new then classic headless.
    for head in ("--headless=new", "--headless"):
        for extra in (["--no-pdf-header-footer"], []):
            try:
                if os.path.exists(out):
                    os.remove(out)
            except Exception:
                pass
            try:
                subprocess.run([exe, head] + extra + common[1:], check=True, timeout=120,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(out) and os.path.getsize(out) > 1000:
                    return True
            except Exception:
                continue
    return False


def via_playwright(inp, out):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return False
    try:
        url = "file:///" + _abs(inp).replace("\\", "/")
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            pg.goto(url, wait_until="networkidle")
            kw = dict(path=_abs(out), print_background=True,
                      margin={"top": "12mm", "bottom": "12mm", "left": "12mm", "right": "12mm"})
            if css_page_size(inp):
                kw["prefer_css_page_size"] = True   # the document declares its own page
            else:
                kw["format"] = "A4"
            pg.pdf(**kw)
            b.close()
        return os.path.exists(out) and os.path.getsize(out) > 1000
    except Exception:
        return False


def via_weasyprint(inp, out):
    try:
        from weasyprint import HTML
    except Exception:
        return False
    try:
        HTML(_abs(inp)).write_pdf(_abs(out))
        return os.path.exists(out) and os.path.getsize(out) > 1000
    except Exception:
        return False


def via_wkhtmltopdf(inp, out):
    exe = shutil.which("wkhtmltopdf")
    if not exe:
        return False
    try:
        size = css_page_size(inp) or ""
        orient = ["-O", "Landscape"] if "landscape" in size else []
        subprocess.run([exe, "--enable-local-file-access", "--print-media-type"] + orient +
                       [_abs(inp), _abs(out)], check=True, timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return os.path.exists(out) and os.path.getsize(out) > 1000
    except Exception:
        return False


def main():
    if len(sys.argv) < 2:
        print("usage: html_to_pdf.py <input.html> [output.pdf]", file=sys.stderr)
        sys.exit(2)
    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(inp)[0] + ".pdf"
    for name, fn in (("chrome", via_chrome), ("playwright", via_playwright),
                     ("weasyprint", via_weasyprint), ("wkhtmltopdf", via_wkhtmltopdf)):
        if fn(inp, out):
            print(f"OK {out} (via {name})")
            return
    print("FAILED: no PDF engine available. Install Google Chrome/Chromium/Edge, or "
          "`pip install playwright weasyprint`, or wkhtmltopdf.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
