# -*- coding: utf-8 -*-
"""self_test for release-notes-spec — inherits v2 template four defenses:
SystemExit capture / Unicode-safe / Windows newline / SUMMARY last line."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")

import release_notes_spec as mod

TMP = tempfile.mkdtemp(prefix="rns_selftest_")
_n = [0]


def write_md(text):
    _n[0] += 1
    path = os.path.join(TMP, "notes_%d.md" % _n[0])
    with open(path, "w", encoding="utf-8", newline="") as fh:  # defense 3
        fh.write(text)
    return path


def run_cli(argv):
    buf_out, buf_err = io.StringIO(), io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            code = mod.main(argv) or 0
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except Exception as e:
        code = 1
        buf_err.write(repr(e))
    return code, buf_out.getvalue(), buf_err.getvalue()


GOOD = """# Changelog

## [1.0.0] - 2026-01-15

### Added
- Initial release.

### Fixed
- Crash on empty config.
"""

BREAKING_NO_UPGRADE = """## 2.0.0 - 2026-05-01

### Changed
- **BREAKING** config format moved to TOML.
"""

BREAKING_WITH_UPGRADE = """## 2.0.0 - 2026-05-01

### Changed
- **BREAKING** config format moved to TOML.

### Upgrade
- Run `config-migrate` before starting v2.
"""


class TestAFunctional(unittest.TestCase):
    def test_good_notes_exit0(self):
        p = write_md(GOOD)
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)
        self.assertIn("verdict: PASS", out)

    def test_releases_parsed_count(self):
        _, out, _ = run_cli(["validate", write_md(GOOD), "--format", "json"])
        self.assertEqual(json.loads(out)["releases"], 1)

    def test_breaking_without_upgrade_is_error(self):
        p = write_md(BREAKING_NO_UPGRADE)
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, 1)
        self.assertIn("breaking-without-upgrade", out)

    def test_breaking_with_upgrade_passes(self):
        p = write_md(BREAKING_WITH_UPGRADE)
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)

    def test_migration_section_counts_as_upgrade(self):
        p = write_md("## 2.0.0\n\n### Removed\n- **BREAKING** drop v1 API.\n\n### Migration\n- Use v2 client.\n")
        code, _, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)

    def test_lowercase_breaking_prefix_detected(self):
        p = write_md("## 2.0.0\n\n### Changed\n- breaking: new auth flow\n")
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, 1)

    def test_no_release_heading_is_error(self):
        p = write_md("just some prose\n")
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, 1)
        self.assertIn("no-release-heading", out)

    def test_bad_version_flagged(self):
        p = write_md("## 1.2 - 2026-01-01\n\n### Added\n- x\n")
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, 1)
        self.assertIn("bad-version", out)

    def test_bad_date_is_error(self):
        p = write_md("## 1.0.0 - 2026-1-1\n\n### Added\n- x\n")
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, 1)
        self.assertIn("bad-date", out)

    def test_missing_date_warns_not_errors(self):
        p = write_md("## 1.0.0\n\n### Added\n- x\n")
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)
        self.assertIn("missing-date", out)

    def test_duplicate_section_is_error(self):
        p = write_md("## 1.0.0 - 2026-01-01\n\n### Fixed\n- a\n\n### Fixed\n- b\n")
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, 1)
        self.assertIn("duplicate-section", out)

    def test_unknown_section_warns(self):
        p = write_md("## 1.0.0 - 2026-01-01\n\n### Wibbles\n- a\n")
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)
        self.assertIn("unknown-section", out)

    def test_empty_section_warns(self):
        p = write_md("## 1.0.0 - 2026-01-01\n\n### Added\n")
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)
        self.assertIn("empty-section", out)

    def test_non_bullet_item_warns(self):
        p = write_md("## 1.0.0 - 2026-01-01\n\n### Added\njust did stuff\n")
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)
        self.assertIn("non-bullet", out)

    def test_unreleased_no_date_required(self):
        p = write_md("## Unreleased\n\n### Added\n- wip\n")
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)
        self.assertNotIn("missing-date", out)

    def test_upcoming_marker_accepted(self):
        p = write_md("## Upcoming\n\n### Added\n- wip\n")
        code, _, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)

    def test_multiple_releases_parsed(self):
        p = write_md(GOOD + "\n## [0.9.0] - 2025-12-01\n\n### Added\n- beta.\n")
        _, out, _ = run_cli(["validate", p, "--format", "json"])
        self.assertEqual(json.loads(out)["releases"], 2)

    def test_link_refs_ignored(self):
        p = write_md(GOOD + "\n[0.9.0]: https://example.invalid/compare\n")
        code, _, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)

    def test_init_prints_valid_template(self):
        code, out, _ = run_cli(["init"])
        self.assertEqual(code, 0)
        p = write_md(out)
        code2, out2, _ = run_cli(["validate", p])
        self.assertEqual(code2, 0)
        self.assertIn("verdict: PASS", out2)

    def test_json_findings_have_line_numbers(self):
        p = write_md(BREAKING_NO_UPGRADE)
        _, out, _ = run_cli(["validate", p, "--format", "json"])
        f = json.loads(out)["findings"][0]
        self.assertGreater(f["line"], 0)
        self.assertIn("code", f)

    def test_prerelease_version_accepted(self):
        p = write_md("## 1.0.0-rc.1 - 2026-02-02\n\n### Added\n- x\n")
        code, _, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)

    def test_v_prefix_accepted(self):
        p = write_md("## v1.2.3 - 2026-02-02\n\n### Fixed\n- x\n")
        code, _, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)


class TestBErrors(unittest.TestCase):
    def test_missing_file_exit2(self):
        code, _, err = run_cli(["validate", os.path.join(TMP, "nope.md")])
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)

    def test_directory_input_exit2(self):
        self.assertEqual(run_cli(["validate", TMP])[0], 2)

    def test_no_args_exit2(self):
        self.assertEqual(run_cli([])[0], 2)

    def test_unknown_subcommand_exit2(self):
        self.assertEqual(run_cli(["frobnicate"])[0], 2)

    def test_unknown_format_exit2(self):
        p = write_md(GOOD)
        self.assertEqual(run_cli(["validate", p, "--format", "csv"])[0], 2)

    def test_validate_without_file_exit2(self):
        self.assertEqual(run_cli(["validate"])[0], 2)

    def test_binary_garbage_does_not_crash(self):
        _n[0] += 1
        p = os.path.join(TMP, "bin_%d.md" % _n[0])
        with open(p, "wb") as fh:
            fh.write(b"\xff\xfe\x00binary\x01\x02")
        code, _, _ = run_cli(["validate", p])
        self.assertIn(code, (0, 1, 2))  # never crashes

    def test_empty_file_no_release_error(self):
        _n[0] += 1
        p = os.path.join(TMP, "empty_%d.md" % _n[0])
        open(p, "w", encoding="utf-8", newline="").close()
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, 1)
        self.assertIn("no-release-heading", out)

    def test_json_output_counts_consistent(self):
        p = write_md(BREAKING_NO_UPGRADE)
        _, out, _ = run_cli(["validate", p, "--format", "json"])
        rep = json.loads(out)
        self.assertEqual(rep["errors"] + rep["warnings"], len(rep["findings"]))

    def test_json_errors_zero_on_pass(self):
        _, out, _ = run_cli(["validate", write_md(GOOD), "--format", "json"])
        self.assertEqual(json.loads(out)["errors"], 0)

    def test_init_writes_no_file(self):
        before = set(os.listdir(TMP))
        run_cli(["init"])
        self.assertEqual(before, set(os.listdir(TMP)))


class TestCEdge(unittest.TestCase):
    def test_unicode_content(self):
        p = write_md("## 1.0.0 - 2026-03-03\n\n### Added\n- \u652f\u6301\u4e2d\u6587\u6ce8\u91ca\n")
        code, out, _ = run_cli(["validate", p, "--format", "json"])
        self.assertEqual(code, 0)

    def test_crlf_file(self):
        p = write_md(GOOD.replace("\n", "\r\n"))
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)
        self.assertIn("verdict: PASS", out)

    def test_bom_file(self):
        _n[0] += 1
        p = os.path.join(TMP, "bom_%d.md" % _n[0])
        with open(p, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write(GOOD)
        self.assertEqual(run_cli(["validate", p])[0], 0)

    def test_very_long_item_line(self):
        p = write_md("## 1.0.0 - 2026-03-03\n\n### Added\n- %s\n" % ("z" * 20000))
        code, _, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)

    def test_many_releases(self):
        body = "".join("## 1.0.%d - 2026-01-%02d\n\n### Fixed\n- b%d\n"
                       % (i, (i % 28) + 1, i) for i in range(40))
        p = write_md(body)
        _, out, _ = run_cli(["validate", p, "--format", "json"])
        self.assertEqual(json.loads(out)["releases"], 40)

    def test_deep_heading_levels(self):
        p = write_md("# 1.0.0 - 2026-03-03\n\n#### Added\n- x\n")
        code, _, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)

    def test_breaking_in_multiple_sections(self):
        p = write_md("## 3.0.0 - 2026-04-04\n\n### Removed\n- **BREAKING** a\n\n### Changed\n- **BREAKING** b\n")
        code, out, _ = run_cli(["validate", p, "--format", "json"])
        rep = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(sum(1 for f in rep["findings"]
                             if f["code"] == "breaking-without-upgrade"), 1)

    def test_version_without_v_and_with_date(self):
        p = write_md("## 9.9.9 - 2026-09-09\n\n### Security\n- patched\n")
        code, _, _ = run_cli(["validate", p])
        self.assertEqual(code, 0)

    def test_empty_section_names_preserved(self):
        rels = mod.parse_notes("## 1.0.0\n\n### Added\n- a\n\n### Removed\n- b\n")
        self.assertEqual(sorted(rels[0]["sections"].keys()), ["Added", "Removed"])


CASES = [
    ("## 1.2.3 - 2026-01-01\n\n### Added\n- x\n", 0, "PASS"),
    ("## Next\n\n### Added\n- x\n", 0, "PASS"),
    ("## 1.2 - 2026-01-01\n\n### Added\n- x\n", 1, "bad-version"),
    ("## [1.0.0]\n\n### Fixed\n- x\n", 0, "missing-date"),
    ("## 1.0.0 - 2026-1-1\n\n### Added\n- x\n", 1, "bad-date"),
    ("## 1.0.0\n\n### Added\n- x\n\n### Added\n- y\n", 1, "duplicate-section"),
    ("## 1.0.0\n\n### Added\n", 0, "empty-section"),
    ("## 1.0.0\n\n### Notes\n- x\n", 0, "unknown-section"),
    ("## 1.0.0\n\n### Changed\n- **BREAKING** x\n", 1, "breaking-without-upgrade"),
    ("## 1.0.0\n\n### Changed\n- **BREAKING** x\n\n### Upgrade\n- do y\n", 0, "PASS"),
    ("hello world\nno headings here\n", 1, "no-release-heading"),
    ("## 1.0.0\n\n### Security\n- x\n\n### Deprecated\n- y\n", 0, "PASS"),
    ("## Upcoming\n\n### Removed\n- **BREAKING** x\n\n### Migration\n- z\n", 0, "PASS"),
    ("## 0.0.1\n\n### Changed\nplain text\n", 0, "non-bullet"),
    ("## v2.3.4 - 2026-06-06\n\n### Added\n- x\n", 0, "PASS"),
    ("## 1.0.0-beta - 2026-06-06\n\n### Fixed\n- x\n", 0, "PASS"),
    ("## 01.02.03 - 2026-06-06\n\n### Added\n- x\n", 0, "PASS"),
    ("## 1.0.0 - 2026-13-99\n\n### Added\n- x\n", 0, "PASS"),  # shape-checked only
    ("## Unreleased\n\n### Changed\n- breaking stuff ahead\n\n### Upgrade\n- read docs\n", 0, "PASS"),
    ("## 5.0.0 - 2026-06-06\n\n### Removed\n- **BREAKING** x\n", 1, "breaking-without-upgrade"),
    ("# 1.0.0 - 2026-06-06\n\n### Added\n- x\n", 0, "PASS"),
]


def _mk(case):
    text, want_code, needle = case

    def test(self):
        p = write_md(text)
        code, out, _ = run_cli(["validate", p])
        self.assertEqual(code, want_code)
        self.assertIn(needle, out)
    return test


for _i, _c in enumerate(CASES):
    setattr(TestCEdge, "test_table_%02d" % _i, _mk(_c))

if __name__ == "__main__":
    r = unittest.TextTestRunner(verbosity=0).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules["__main__"]))
    total, fails = r.testsRun, len(r.failures) + len(r.errors)
    print("SUMMARY: PASS %d/%d" % (total - fails, total))
    sys.exit(0 if fails == 0 else 1)
