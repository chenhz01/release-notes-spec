# -*- coding: utf-8 -*-
"""release-notes-spec — validate Markdown release notes structure.

Pure standard library. Schema: version headings (semver or Unreleased/Next/
Upcoming, optional - YYYY-MM-DD date), sections from the Keep-a-Changelog set
(Added/Changed/Deprecated/Removed/Fixed/Security), bullet items, and a rule
that any **BREAKING** item must be paired with an Upgrade/Migration section.
Exit codes: 0 = no errors (warnings allowed), 1 = errors found, 2 = input error.
"""
import argparse
import json
import re
import sys

SECTIONS = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")
UPCOMING = ("Unreleased", "Next", "Upcoming")

_RELEASE = re.compile(
    r"^#{1,3}\s+\[?(v?\d[^\]\s]*|Unreleased|Next|Upcoming)\]?"
    r"(?:\s*[-–]\s*(\S+))?\s*$")
_SECTION = re.compile(r"^#{2,4}\s+([A-Za-z][A-Za-z ]*)\s*$")
_SEMVER_CORE = re.compile(r"^v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LINK_REF = re.compile(r"^\[.+\]:\s*\S+")


def parse_notes(text):
    """Split text into releases: [{version, date, line, sections: {name: [(line, text)]}}]"""
    releases = []
    cur = None
    cur_section = None
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        m = _RELEASE.match(stripped)
        if m:
            cur = {"version": m.group(1), "date": m.group(2), "line": lineno,
                   "sections": {}, "section_order": []}
            releases.append(cur)
            cur_section = None
            continue
        if cur is None or _LINK_REF.match(stripped) or not stripped:
            continue
        m = _SECTION.match(stripped)
        if m:
            cur_section = m.group(1).strip()
            cur["sections"].setdefault(cur_section, [])
            cur["section_order"].append((cur_section, lineno))
            continue
        if cur_section is not None:
            cur["sections"][cur_section].append((lineno, stripped))
    return releases


def _is_breaking(item_text):
    bare = item_text.lstrip("-* ").strip()
    return ("**BREAKING**" in item_text or bare.lower().startswith("breaking:")
            or bare.lower().startswith("breaking "))


def _has_upgrade_section(release):
    return any("upgrade" in name.lower() or "migration" in name.lower()
               for name, _ in release["section_order"])


def validate_notes(text):
    findings = []
    releases = parse_notes(text)
    if not releases:
        findings.append({"severity": "error", "line": 1, "code": "no-release-heading",
                         "message": "no version heading found (e.g. '## 1.2.0 - 2026-10-13')"})
        return findings, releases

    for rel in releases:
        ver = rel["version"]
        if ver not in UPCOMING and not _SEMVER_CORE.match(ver):
            findings.append({"severity": "error", "line": rel["line"],
                             "code": "bad-version",
                             "message": "%r is not valid semver or an upcoming marker" % ver})
        if ver not in UPCOMING and not rel["date"]:
            findings.append({"severity": "warning", "line": rel["line"],
                             "code": "missing-date",
                             "message": "release %s has no date (YYYY-MM-DD)" % ver})
        if rel["date"] and not _DATE.match(rel["date"]):
            findings.append({"severity": "error", "line": rel["line"],
                             "code": "bad-date",
                             "message": "date %r is not YYYY-MM-DD" % rel["date"]})

        seen = set()
        breaking_items = []
        for name, line in rel["section_order"]:
            if name not in SECTIONS:
                findings.append({"severity": "warning", "line": line,
                                 "code": "unknown-section",
                                 "message": "section %r is outside the standard set %s"
                                            % (name, "/".join(SECTIONS))})
            if name in seen:
                findings.append({"severity": "error", "line": line,
                                 "code": "duplicate-section",
                                 "message": "duplicate section %r in release %s" % (name, ver)})
            seen.add(name)
            items = rel["sections"][name]
            if not items:
                findings.append({"severity": "warning", "line": line,
                                 "code": "empty-section",
                                 "message": "section %r in release %s has no items" % (name, ver)})
            for iline, itext in items:
                if not itext.startswith(("-", "*")):
                    findings.append({"severity": "warning", "line": iline,
                                     "code": "non-bullet",
                                     "message": "item under %r should start with '- '" % name})
                if _is_breaking(itext):
                    breaking_items.append((iline, itext))

        if breaking_items and not _has_upgrade_section(rel):
            findings.append({"severity": "error", "line": breaking_items[0][0],
                             "code": "breaking-without-upgrade",
                             "message": "release %s marks BREAKING changes but has no "
                                        "Upgrade/Migration section" % ver})
    return findings, releases


def render_text(findings, n_releases):
    lines = ["release-notes-spec report", "=" * 28,
             "releases parsed: %d" % n_releases]
    errors = 0
    for f in findings:
        marker = "ERROR" if f["severity"] == "error" else "warn "
        if f["severity"] == "error":
            errors += 1
        lines.append("%s line %3d  %-26s %s" % (marker, f["line"], f["code"], f["message"]))
    lines.append("verdict: %s (%d error(s), %d warning(s))"
                 % ("FAIL" if errors else "PASS", errors, len(findings) - errors))
    return "\n".join(lines)


TEMPLATE = """# Changelog

## [Unreleased]

## [1.0.0] - 2026-01-01

### Added
- First stable release.

### Upgrade
- No action required for new installs.
"""


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="release-notes-spec",
        description="Validate Markdown release notes: sections, dates, breaking/upgrade coupling.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_val = sub.add_parser("validate", help="validate a release-notes Markdown file")
    p_val.add_argument("file")
    p_val.add_argument("--format", choices=("text", "json"), default="text")
    sub.add_parser("init", help="print a compliant template to stdout")
    args = parser.parse_args(argv)

    if args.cmd == "init":
        print(TEMPLATE, end="")
        return 0

    try:
        with open(args.file, "r", encoding="utf-8-sig", newline="") as fh:
            text = fh.read()
    except OSError as exc:
        print("error: cannot read %s: %s" % (args.file, exc), file=sys.stderr)
        return 2
    try:
        findings, releases = validate_notes(text)
    except Exception as exc:  # defensive: never crash on odd input
        print("error: %s" % exc, file=sys.stderr)
        return 2

    if args.format == "json":
        errors = sum(1 for f in findings if f["severity"] == "error")
        print(json.dumps({"tool": "release-notes-spec",
                          "releases": len(releases),
                          "errors": errors,
                          "warnings": len(findings) - errors,
                          "findings": findings}, ensure_ascii=False, indent=2))
    else:
        print(render_text(findings, len(releases)))
    return 1 if any(f["severity"] == "error" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
