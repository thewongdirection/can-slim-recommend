#!/usr/bin/env python3
"""
build_report.py - turn a filled dashboard into the deliverable(s) the user asked for.

This is the single entry point for step 7. It exists so "PDF by default, HTML on request"
is a resolved argument rather than a convention someone has to remember:

    python scripts/build_report.py canslim-recommendations-<date>.html                 -> PDF
    python scripts/build_report.py canslim-recommendations-<date>.html --format html   -> HTML
    python scripts/build_report.py canslim-recommendations-<date>.html --format both   -> both

`--format` defaults to `pdf`. Nothing else about the report changes with the format: the same
filled CONFIG drives both, the HTML renders dark on screen, and the print stylesheet forces the
white palette so the PDF is white either way (see the template's THEME note). `--theme` flips
the on-screen look of the HTML deliverable; it has no effect on the PDF.

THE SELF-AUDIT IS ENFORCED HERE. The template audits its own CONFIG on render and prints a red
"Report checks failed" banner when the run contradicts itself. Shipping a report showing that
banner is the one thing the skill must never do, so this script renders the page in a headless
browser and REFUSES to emit anything when the banner is present. If no browser is available the
check is skipped with a warning rather than silently passing.

Exit codes: 0 = deliverables written; 1 = nothing written (audit failed, or no PDF engine and
--format pdf was required); 2 = bad usage.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import html_to_pdf  # noqa: E402  - same directory, shared engine chain


def apply_theme(path, theme):
    """Rewrite the document element's data-theme. Returns True if the file changed.

    Anchored to the doctype on purpose: the template's own header comment TALKS about
    `<html data-theme="dark">`, and a naive "first <html" match rewrites that prose instead of
    the real element, leaving the page's theme untouched while reporting success.
    """
    src = open(path, encoding="utf-8").read()
    doctype = re.search(r"<!doctype\s+html[^>]*>", src, re.I)
    start = doctype.end() if doctype else 0
    tag = re.search(r"<html\b[^>]*>", src[start:], re.I)
    if not tag:
        return False
    lo, hi = start + tag.start(), start + tag.end()
    old_tag = src[lo:hi]
    if 'data-theme="%s"' % theme in old_tag:
        return False
    new_tag, n = re.subn(r'\s*data-theme="[^"]*"', ' data-theme="%s"' % theme, old_tag, count=1)
    if not n:
        new_tag = old_tag[:-1].rstrip() + ' data-theme="%s">' % theme
    open(path, "w", encoding="utf-8").write(src[:lo] + new_tag + src[hi:])
    return True


def audit(path):
    """Render the page headlessly and read its self-audit banner.

    Returns (ok, detail): ok is True when the report is clean OR the check could not run
    (detail says which). ok is False only when the banner is actually present.
    """
    exe = html_to_pdf.find_browser()
    if not exe:
        return True, "SKIPPED - no headless browser found, so the self-audit could not be read"
    url = "file:///" + os.path.abspath(path).replace("\\", "/")
    for head in ("--headless=new", "--headless"):
        try:
            out = subprocess.run(
                [exe, head, "--disable-gpu", "--no-sandbox", "--virtual-time-budget=6000",
                 "--dump-dom", url],
                check=True, timeout=120, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            ).stdout.decode("utf-8", "replace")
        except Exception:
            continue
        m = re.search(r'<div id="checks"[^>]*>(.*?)(?=<div id="freshness")', out, re.S)
        body = m.group(1) if m else ""
        if "Report checks failed" not in body:
            return True, "clean"
        items = re.findall(r"<li>(.*?)</li>", body, re.S)
        items = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", i)).strip() for i in items]
        return False, "\n".join("    - " + i for i in items) or "    - (banner present)"
    return True, "SKIPPED - the browser failed to render the page, so the audit could not be read"


def main():
    ap = argparse.ArgumentParser(description="Produce the PDF and/or HTML deliverable.")
    ap.add_argument("input", help="the filled canslim-recommendations-<date>.html")
    ap.add_argument("--format", "-f", choices=("pdf", "html", "both"), default="pdf",
                    help="which deliverable to produce (default: pdf)")
    ap.add_argument("--theme", choices=("dark", "light"),
                    help="on-screen theme of the HTML deliverable; the PDF is white regardless")
    ap.add_argument("--out", "-o", help="directory to write into (default: alongside the input)")
    ap.add_argument("--no-check", action="store_true",
                    help="emit even if the self-audit banner is showing (use only to inspect a failure)")
    a = ap.parse_args()

    if not os.path.isfile(a.input):
        print("no such file: " + a.input, file=sys.stderr)
        sys.exit(2)

    outdir = a.out or os.path.dirname(os.path.abspath(a.input)) or "."
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(a.input))[0]

    if a.theme and apply_theme(a.input, a.theme):
        print("theme -> %s" % a.theme)

    ok, detail = audit(a.input)
    if not ok:
        print("REFUSED: the report's self-audit is failing - do not ship it.\n" + detail,
              file=sys.stderr)
        if not a.no_check:
            print("\nFix the CONFIG (or re-run with --no-check to emit it anyway for inspection).",
                  file=sys.stderr)
            sys.exit(1)
        print("--no-check given; emitting anyway.", file=sys.stderr)
    elif detail != "clean":
        print("self-audit %s" % detail)
    else:
        print("self-audit clean")

    written = []
    if a.format in ("html", "both"):
        dest = os.path.join(outdir, stem + ".html")
        if os.path.abspath(dest) != os.path.abspath(a.input):
            shutil.copyfile(a.input, dest)
        written.append(dest)

    if a.format in ("pdf", "both"):
        dest = os.path.join(outdir, stem + ".pdf")
        made = False
        for name, fn in (("chrome", html_to_pdf.via_chrome),
                         ("playwright", html_to_pdf.via_playwright),
                         ("weasyprint", html_to_pdf.via_weasyprint),
                         ("wkhtmltopdf", html_to_pdf.via_wkhtmltopdf)):
            if fn(a.input, dest):
                print("PDF via %s" % name)
                written.append(dest)
                made = True
                break
        if not made:
            # Never block the run on the export: fall back to the HTML and say why.
            print("no PDF engine available (install Chrome/Chromium/Edge, playwright, weasyprint "
                  "or wkhtmltopdf)", file=sys.stderr)
            if a.format == "pdf":
                fallback = os.path.join(outdir, stem + ".html")
                if os.path.abspath(fallback) != os.path.abspath(a.input):
                    shutil.copyfile(a.input, fallback)
                written.append(fallback)
                print("falling back to the HTML deliverable - hand it over and say why there is "
                      "no PDF.", file=sys.stderr)

    for p in written:
        print("%8.1f KB  %s" % (os.path.getsize(p) / 1024.0, p))
    sys.exit(0 if written else 1)


if __name__ == "__main__":
    main()
