# Changelog

All notable changes to this project are documented here.
Format inspired by Keep a Changelog; versions are 0.x while the tool stabilizes.

## [0.1.1] - 2026-10-13

### Changed
- Second-round revision after a full self-audit (rules 85-100 alignment pass):
  version heading regex loosened so malformed versions/dates are diagnosed as bad-version/bad-date errors instead of vanishing; breaking detection strips list markers (breaking:/breaking prefix); 7 boundary cases added via table

### Fixed
- Self-test suite hardened to 63 cases across three classes
  (functional / error-path / extreme-edge); final run `SUMMARY: PASS 63/63`.

## [0.1.0] - 2026-10-13

### Added
- Initial release: pure-stdlib core, argparse CLI, three-tier finding model,
  text and JSON output, and an article-level README with measured
  performance, Minimal Fallback, Design Trade-offs, Limits & Second-order
  Effects, FAQ, and Core Assumptions.
